"""Tests for the `pydantic_core_build` PEP 517 backend.

https://github.com/pydantic/pydantic/issues/13293
"""

import importlib.util
import sys
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

# The backend lives next to `Cargo.toml`, in the parent directory, and isn't installed. It is
# loaded by path, as it isn't necessarily importable when the tests are run from the `pydantic`
# root (`pydantic-core/tests` is symlinked under `tests/pydantic_core/` there):
BACKEND_PATH = Path(__file__).resolve().parent.parent / 'pydantic_core_build.py'
_spec = importlib.util.spec_from_file_location('pydantic_core_build', BACKEND_PATH)
assert _spec is not None and _spec.loader is not None
pydantic_core_build = importlib.util.module_from_spec(_spec)
sys.modules['pydantic_core_build'] = pydantic_core_build
_spec.loader.exec_module(pydantic_core_build)

MAX_MINOR_VERSION = pydantic_core_build._max_supported_minor_version('cpython')

if MAX_MINOR_VERSION is None:  # pragma: no cover
    pytest.fail('The `pyo3-ffi` style metadata must be declared in `Cargo.toml`')

_FakeVersionInfo = namedtuple('_FakeVersionInfo', 'major minor micro releaselevel serial')


def _as_interpreter(monkeypatch: pytest.MonkeyPatch, minor_version: int, implementation: str = 'cpython') -> None:
    """Pretend the build is running on the given interpreter."""
    # A named tuple is used, as the backend relies on both indexing and attribute access:
    monkeypatch.setattr(sys, 'version_info', _FakeVersionInfo(3, minor_version, 0, 'final', 0))
    if implementation != sys.implementation.name:
        # `importlib` relies on `sys.implementation` attributes when importing modules, so a
        # minimal stand-in is used, only exposing the attributes read by the backend:
        monkeypatch.setattr(sys, 'implementation', SimpleNamespace(name=implementation, cache_tag=implementation))


def test_metadata_matches_cargo_manifest() -> None:
    """The maximum supported versions must be readable from the `Cargo.toml` manifest."""
    import tomllib

    manifest = tomllib.loads((BACKEND_PATH.with_name('Cargo.toml')).read_text(encoding='utf-8'))
    declared = manifest['package']['metadata']
    assert declared['cpython'] == {'max-version': f'3.{MAX_MINOR_VERSION}'}
    # As for `pyo3-ffi`, the supported versions are declared per implementation. A minimum
    # version isn't needed, as `requires-python` in `pyproject.toml` covers it:
    assert set(declared) == {'cpython', 'pypy', 'graalpy'}
    for implementation in ('pypy', 'graalpy'):
        assert pydantic_core_build._max_supported_minor_version(implementation) is not None


def test_missing_metadata_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed manifest must not prevent the build from being delegated to `maturin`."""
    monkeypatch.setattr(pydantic_core_build, '_MANIFEST_PATH', BACKEND_PATH.with_name('Cargo.lock'))
    assert pydantic_core_build._max_supported_minor_version('cpython') is None

    with mock.patch.object(pydantic_core_build, 'import_module') as import_module:
        pydantic_core_build._maturin()
    import_module.assert_called_once_with('maturin')


@pytest.mark.parametrize('minor_version', [MAX_MINOR_VERSION + 2, MAX_MINOR_VERSION + 10])  # type: ignore[list-item]
def test_unsupported_python_version_aborts_build(monkeypatch: pytest.MonkeyPatch, minor_version: int) -> None:
    """Interpreters newer than the maximum supported version plus one must abort the build."""
    _as_interpreter(monkeypatch, minor_version)
    with pytest.raises(SystemExit) as exc_info:
        pydantic_core_build._maturin()

    message = str(exc_info.value)
    assert f'pydantic-core only supports cpython 3.11 up to 3.{MAX_MINOR_VERSION}' in message
    assert f'(the current interpreter is cpython 3.{minor_version})' in message
    assert 'no pre-built wheel is available' in message
    assert 'upgrade to a newer version of `pydantic`' in message
    assert 'PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1' in message


def test_experimental_python_version_warns_but_builds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Python version following the last supported one is granted experimental support."""
    _as_interpreter(monkeypatch, MAX_MINOR_VERSION + 1)
    with mock.patch.object(pydantic_core_build, 'import_module') as import_module:
        pydantic_core_build._maturin()

    import_module.assert_called_once_with('maturin')
    stderr = capsys.readouterr().err
    assert f'pydantic-core only supports cpython 3.11 up to 3.{MAX_MINOR_VERSION}' in stderr
    assert 'experimental support' in stderr


def test_experimental_python_version_aborts_free_threaded_builds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Contrary to GIL-enabled builds, PyO3 refuses to build for free-threaded interpreters."""
    _as_interpreter(monkeypatch, MAX_MINOR_VERSION + 1)
    with (
        mock.patch.object(pydantic_core_build, '_is_free_threaded', return_value=True),
        pytest.raises(SystemExit) as exc_info,
    ):
        pydantic_core_build._maturin()

    assert 'PYO3_USE_STABLE_ABI_FORWARD_COMPATIBILITY=1' in str(exc_info.value)
    assert capsys.readouterr().err == ''


@pytest.mark.parametrize(
    'env_var',
    ['PYO3_USE_ABI3_FORWARD_COMPATIBILITY', 'PYO3_USE_STABLE_ABI_FORWARD_COMPATIBILITY'],
)
def test_forward_compatibility_env_vars_skip_check(
    monkeypatch: pytest.MonkeyPatch, env_var: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Opting into PyO3 forward compatibility must also skip this check, whatever the version."""
    monkeypatch.setenv(env_var, '1')
    _as_interpreter(monkeypatch, MAX_MINOR_VERSION + 5)
    with mock.patch.object(pydantic_core_build, 'import_module') as import_module:
        pydantic_core_build._maturin()

    import_module.assert_called_once_with('maturin')
    assert capsys.readouterr().err == ''


def test_pyo3_skip_version_check_env_var_is_honored(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The escape hatch honored by PyO3 itself must be honored here too."""
    monkeypatch.setenv('UNSAFE_PYO3_SKIP_VERSION_CHECK', '1')
    _as_interpreter(monkeypatch, MAX_MINOR_VERSION + 5)
    with mock.patch.object(pydantic_core_build, 'import_module') as import_module:
        pydantic_core_build._maturin()

    import_module.assert_called_once_with('maturin')
    assert capsys.readouterr().err == ''


def test_other_implementations_are_not_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    """PyO3 doesn't perform any version check for implementations it doesn't know about."""
    _as_interpreter(monkeypatch, MAX_MINOR_VERSION + 5, 'rustpython')
    with mock.patch.object(pydantic_core_build, 'import_module') as import_module:
        pydantic_core_build._maturin()

    import_module.assert_called_once_with('maturin')


def test_pypy_version_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """PyPy supports a smaller range of Python versions than CPython."""
    pypy_max_minor_version = pydantic_core_build._max_supported_minor_version('pypy')
    assert pypy_max_minor_version is not None

    _as_interpreter(monkeypatch, pypy_max_minor_version + 2, 'pypy')
    with pytest.raises(SystemExit) as exc_info:
        pydantic_core_build._maturin()

    assert f'pydantic-core only supports pypy 3.11 up to 3.{pypy_max_minor_version}' in str(exc_info.value)


def test_supported_python_version_builds_silently(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Supported interpreters must not see any additional output."""
    _as_interpreter(monkeypatch, MAX_MINOR_VERSION)
    with mock.patch.object(pydantic_core_build, 'import_module') as import_module:
        pydantic_core_build._maturin()

    import_module.assert_called_once_with('maturin')
    assert capsys.readouterr().err == ''
