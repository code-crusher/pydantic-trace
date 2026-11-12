"""Tests for the agent skills shipped with the package.

See https://github.com/pydantic/pydantic/issues/13791.
"""

import re
from pathlib import Path

import pytest

import pydantic

PACKAGE_ROOT = Path(pydantic.__file__).parent
SKILLS_ROOT = PACKAGE_ROOT / '.agents' / 'skills'
REPO_ROOT = PACKAGE_ROOT.parent

# `library-skills` only accepts skill names made of lowercase letters, numbers and
# hyphens, without consecutive hyphens:
SKILL_NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def skill_dirs() -> list[Path]:
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(path for path in SKILLS_ROOT.iterdir() if path.is_dir())


def test_skill_is_shipped_in_the_package() -> None:
    """The skill must live inside the package so installed distributions ship it.

    Tools such as `library-skills` discover skills from the installed distribution's
    `RECORD`, looking for `<package>/.agents/skills/<skill>/SKILL.md`.

    https://github.com/pydantic/pydantic/issues/13791
    """
    assert (SKILLS_ROOT / 'pydantic' / 'SKILL.md').is_file()


@pytest.mark.parametrize('skill_dir', skill_dirs(), ids=lambda path: path.name)
def test_skill_frontmatter(skill_dir: Path) -> None:
    """Skills must declare a `name` matching their directory and a `description`."""
    content = (skill_dir / 'SKILL.md').read_text(encoding='utf-8')

    match = re.match(r'^---\n(?P<frontmatter>.*?)\n---\n', content, flags=re.DOTALL)
    assert match is not None, 'SKILL.md must start with a YAML frontmatter block'

    frontmatter = match.group('frontmatter')
    name = re.search(r'^name: (?P<name>.+)$', frontmatter, flags=re.MULTILINE)
    description = re.search(r'^description: (?P<description>.+)$', frontmatter, flags=re.MULTILINE)

    assert name is not None, 'SKILL.md frontmatter must declare a name'
    name = name.group('name').strip()
    assert SKILL_NAME_RE.match(name), f'invalid skill name {name!r}'
    assert name == skill_dir.name

    assert description is not None, 'SKILL.md frontmatter must declare a description'
    assert description.group('description').strip()


def test_skill_is_exposed_at_the_repository_root() -> None:
    """The root `.agents/skills` path is kept for agents working in the repository."""
    if not (REPO_ROOT / 'pyproject.toml').is_file():
        pytest.skip('not running from a source checkout')

    root_skill = REPO_ROOT / '.agents' / 'skills' / 'pydantic' / 'SKILL.md'
    assert root_skill.is_file()
    assert root_skill.resolve() == (SKILLS_ROOT / 'pydantic' / 'SKILL.md').resolve()
