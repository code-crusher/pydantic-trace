"""PEP 517 build backend for `pydantic-core`.

This module is a thin wrapper around the `maturin` build backend. Its only purpose is to emit a
comprehensible message when the Python interpreter used for the build is newer than the versions
supported by the version of PyO3 pinned in `Cargo.toml` (see
https://github.com/pydantic/pydantic/issues/13293).

Without it, such a build fails deep inside the Rust build script of `pyo3-ffi`, with a message
that doesn't mention `pydantic-core` at all, leaving users without any pointer towards a
resolution. The supported versions are declared in the `[package.metadata]` section of
`Cargo.toml`, using the same format as the metadata published by `pyo3-ffi` (which is what
`maturin` itself relies on to discover the versions supported by the bindings), and are kept in
sync with the pinned PyO3 version.

Two behaviors are implemented, mirroring the version check performed by PyO3:

* On the Python version following the last supported one, PyO3 allows an experimental build
  (except on free-threaded builds, where it refuses to build). A warning is printed, as the
  one emitted by PyO3 is swallowed by the build tools.
* On any later version, the build is interrupted with an explanation of the failure and of the
  possible resolutions, instead of the cryptic error emitted by the Rust build script.
"""

from __future__ import annotations

import os
import sys
import tomllib
from collections.abc import Mapping
from importlib import import_module
from pathlib import Path
from typing import Any

_MANIFEST_PATH = Path(__file__).with_name('Cargo.toml')

# Environment variables defined by PyO3 to opt into building for a newer, not yet supported,
# Python version using the stable ABI. When one of them is set, the check is skipped entirely,
# so that it never becomes stricter than the one performed by PyO3 itself.
_FORWARD_COMPATIBILITY_ENV_VARS = (
    'PYO3_USE_ABI3_FORWARD_COMPATIBILITY',
    'PYO3_USE_STABLE_ABI_FORWARD_COMPATIBILITY',
)

# Implementations for which `pyo3-ffi` publishes a supported version range. For other
# implementations (e.g. RustPython), PyO3 doesn't perform any version check:
_IMPLEMENTATIONS = ('cpython', 'pypy', 'graalpy')


def _max_supported_minor_version(implementation: str) -> int | None:
    """Return the maximum Python minor version supported for `implementation`.

    The value is read from the `[package.metadata.<implementation>.max-version]` key of
    `Cargo.toml`. `None` is returned if the metadata is missing or malformed, in which case
    no check can be performed.
    """
    try:
        manifest = tomllib.loads(_MANIFEST_PATH.read_text(encoding='utf-8'))
        max_version = manifest['package']['metadata'][implementation]['max-version']
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
        return None

    # The value uses the same format as the one published by `pyo3-ffi`, e.g. `'3.15'`:
    try:
        return int(max_version.rsplit('.', maxsplit=1)[-1])
    except (AttributeError, ValueError):
        return None


def _is_free_threaded() -> bool:
    """Return whether the running interpreter is a free-threaded (PEP 703) build."""
    import sysconfig

    return bool(sysconfig.get_config_var('Py_GIL_DISABLED'))


def _check_python_version() -> None:
    """Warn or abort the build if the interpreter is not supported by the pinned PyO3 version."""
    if os.environ.get('UNSAFE_PYO3_SKIP_VERSION_CHECK') == '1':
        # Escape hatch honored by PyO3 itself (mostly used for CI purposes):
        return
    if any(os.environ.get(var) == '1' for var in _FORWARD_COMPATIBILITY_ENV_VARS):
        # The user explicitly opted into forward compatibility, let PyO3 handle the rest:
        return

    implementation = sys.implementation.name
    if implementation not in _IMPLEMENTATIONS:
        # PyO3 doesn't perform any version check for other implementations:
        return

    max_minor_version = _max_supported_minor_version(implementation)
    if max_minor_version is None or sys.version_info[:2] <= (3, max_minor_version):
        return

    python_version = f'{sys.version_info.major}.{sys.version_info.minor}'
    max_version = f'3.{max_minor_version}'
    message_head = (
        f'pydantic-core only supports {implementation} 3.11 up to {max_version} '
        f'(the current interpreter is {implementation} {python_version}).\n'
    )
    message_tail = (
        '\n'
        'This error usually means that no pre-built wheel is available for your Python version, '
        'and that `pydantic-core` is being built from its source distribution. Such a build '
        'requires a Python version supported by the version of PyO3 pinned by this release of '
        '`pydantic-core`.\n'
        '\n'
        f'To fix this, either use Python {max_version} or older, or upgrade to a newer version '
        'of `pydantic` (and `pydantic-core`) supporting your Python version.'
    )

    if sys.version_info.minor == max_minor_version + 1 and not _is_free_threaded():
        # The following Python version is granted experimental support by PyO3. The build is
        # allowed to proceed, but the warning emitted by PyO3 isn't visible when building
        # through `pip`/`uv`, so print it here:
        print(
            f'Warning: {message_head}'
            'PyO3 only provides experimental support for this Python version: the build might '
            'fail or produce a broken extension module, and the resulting wheel must not be '
            'distributed. To build anyway without this warning, set the '
            '`PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` environment variable.',
            file=sys.stderr,
        )
        return

    sys.exit(
        f'{message_head}'
        'As a last resort, the build can be forced by setting the '
        '`PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1` environment variable '
        '(`PYO3_USE_STABLE_ABI_FORWARD_COMPATIBILITY=1` on a free-threaded build), which uses '
        f'the stable ABI without any support guarantee.{message_tail}'
    )


def _maturin() -> Any:
    """Import the `maturin` backend, after performing the Python version check."""
    _check_python_version()
    return import_module('maturin')


def get_requires_for_build_wheel(config_settings: Mapping[str, Any] | None = None) -> list[str]:
    """Return the requirements to build a wheel, as defined by `maturin`."""
    return _maturin().get_requires_for_build_wheel(config_settings)  # type: ignore[no-any-return]


def get_requires_for_build_editable(config_settings: Mapping[str, Any] | None = None) -> list[str]:
    """Return the requirements to build an editable wheel, as defined by `maturin`."""
    return _maturin().get_requires_for_build_editable(config_settings)  # type: ignore[no-any-return]


def get_requires_for_build_sdist(config_settings: Mapping[str, Any] | None = None) -> list[str]:
    """Return the requirements to build an sdist, as defined by `maturin`."""
    return _maturin().get_requires_for_build_sdist(config_settings)  # type: ignore[no-any-return]


def build_wheel(
    wheel_directory: str,
    config_settings: Mapping[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    """Build a wheel, as defined by `maturin`."""
    return _maturin().build_wheel(wheel_directory, config_settings, metadata_directory)  # type: ignore[no-any-return]


def build_editable(
    wheel_directory: str,
    config_settings: Mapping[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    """Build an editable wheel, as defined by `maturin`."""
    return _maturin().build_editable(wheel_directory, config_settings, metadata_directory)  # type: ignore[no-any-return]


def build_sdist(sdist_directory: str, config_settings: Mapping[str, Any] | None = None) -> str:
    """Build an sdist, as defined by `maturin`."""
    return _maturin().build_sdist(sdist_directory, config_settings)  # type: ignore[no-any-return]


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings: Mapping[str, Any] | None = None) -> str:
    """Prepare the wheel metadata, as defined by `maturin`."""
    return _maturin().prepare_metadata_for_build_wheel(metadata_directory, config_settings)  # type: ignore[no-any-return]


def prepare_metadata_for_build_editable(
    metadata_directory: str, config_settings: Mapping[str, Any] | None = None
) -> str:
    """Prepare the editable wheel metadata, as defined by `maturin`."""
    return _maturin().prepare_metadata_for_build_editable(metadata_directory, config_settings)  # type: ignore[no-any-return]
