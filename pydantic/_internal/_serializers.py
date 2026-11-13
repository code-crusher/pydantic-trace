from __future__ import annotations

import collections
import collections.abc
import re
import typing
from typing import Any

from pydantic_core import PydanticOmit, core_schema

from ._typing_extra import is_namedtuple

# Inline flag letters accepted by `re.compile()` in a `(?...)` group, in the order used by the `re` parser.
# `re.LOCALE` is left out: it is only valid for bytes patterns, and JSON serialization always produces
# a string (so `(?L)` would make the serialized pattern invalid). `re.TEMPLATE` and `re.DEBUG` are left
# out as well: they are deprecated/undocumented and don't affect matching.
_PATTERN_FLAG_LETTERS: tuple[tuple[re.RegexFlag, str], ...] = (
    (re.IGNORECASE, 'i'),
    (re.MULTILINE, 'm'),
    (re.DOTALL, 's'),
    (re.VERBOSE, 'x'),
    (re.ASCII, 'a'),
    (re.UNICODE, 'u'),
)

SEQUENCE_ORIGIN_MAP: dict[Any, Any] = {
    typing.Deque: collections.deque,  # noqa: UP006
    collections.deque: collections.deque,
    list: list,
    typing.List: list,  # noqa: UP006
    tuple: tuple,
    typing.Tuple: tuple,  # noqa: UP006
    set: set,
    typing.AbstractSet: set,
    typing.Set: set,  # noqa: UP006
    frozenset: frozenset,
    typing.FrozenSet: frozenset,  # noqa: UP006
    typing.Sequence: list,
    typing.MutableSequence: list,
    typing.MutableSet: set,
    # this doesn't handle subclasses of these
    # parametrized typing.Set creates one of these
    collections.abc.MutableSet: set,
    collections.abc.Set: frozenset,
}


def serialize_sequence_via_list(
    v: Any, handler: core_schema.SerializerFunctionWrapHandler, info: core_schema.SerializationInfo
) -> Any:
    items: list[Any] = []

    value_type = type(v)
    mapped_origin = SEQUENCE_ORIGIN_MAP.get(value_type)
    if mapped_origin is None and not is_namedtuple(value_type):
        # we shouldn't hit this branch, should probably add a serialization error or something
        return v

    for index, item in enumerate(v):
        try:
            item_v = handler(item, index)
        except PydanticOmit:  # noqa: PERF203
            pass
        else:
            items.append(item_v)

    if info.mode_is_json():
        return items
    elif mapped_origin is not None:
        return mapped_origin(items)
    else:
        # named tuple: if some items were excluded, it can't be re-created
        return value_type(*items) if len(items) == len(v) else tuple(items)


def serialize_pattern(pattern: re.Pattern[Any]) -> str | bytes:
    """Serialize a compiled regex pattern to its pattern string, preserving flags.

    Flags are prepended as an inline `(?...)` group, which `re.compile()` understands, so that
    the pattern round-trips through JSON serialization (see https://github.com/pydantic/pydantic/issues/13761).
    """
    text = pattern.pattern
    is_bytes = isinstance(text, bytes)
    default_flags = 0 if is_bytes else int(re.UNICODE)
    if int(pattern.flags) == default_flags:
        return text
    try:
        # Flags implied by the pattern text itself (e.g. from an inline `(?i)` group) don't need to be repeated.
        implicit_flags = int(re.compile(text).flags)
    except re.error:
        # The text is only valid when the flags are applied (e.g. it contains comments and `re.VERBOSE`
        # was used), so only the flags implied by the pattern type can be omitted.
        implicit_flags = default_flags
    flags = int(pattern.flags) & ~implicit_flags
    flag_letters = ''.join(letter for flag, letter in _PATTERN_FLAG_LETTERS if flags & flag)
    if not flag_letters:
        return text
    group = f'(?{flag_letters})'
    return group.encode() + text if is_bytes else group + text
