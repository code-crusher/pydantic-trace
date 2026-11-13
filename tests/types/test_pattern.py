import json
import re
from re import Pattern
from typing import Annotated

import pytest

from pydantic import BaseModel, Field, PydanticSchemaGenerationError, StringConstraints, TypeAdapter, ValidationError


@pytest.mark.parametrize(
    ('pattern_type', 'pattern_value', 'matching_value', 'non_matching_value'),
    [
        pytest.param(re.Pattern, r'^whatev.r\d$', 'whatever1', ' whatever1', id='re.Pattern'),
        pytest.param(Pattern, r'^whatev.r\d$', 'whatever1', ' whatever1', id='Pattern'),
        pytest.param(Pattern[str], r'^whatev.r\d$', 'whatever1', ' whatever1', id='Pattern[str]'),
        pytest.param(Pattern[bytes], rb'^whatev.r\d$', b'whatever1', b' whatever1', id='Pattern[bytes]'),
    ],
)
def test_pattern(pattern_type, pattern_value, matching_value, non_matching_value):
    ta = TypeAdapter(pattern_type)

    pattern = ta.validate_python(pattern_value)
    assert pattern.__class__.__name__ == 'Pattern'
    # check it's really a proper pattern
    assert pattern.match(matching_value)
    assert not pattern.match(non_matching_value)

    # Check that pre-compiled patterns are accepted unchanged
    p = re.compile(pattern_value)
    assert ta.validate_python(p) is p

    assert ta.json_schema() == {'type': 'string', 'format': 'regex'}


@pytest.mark.parametrize(
    'use_field',
    [pytest.param(True, id='Field'), pytest.param(False, id='StringConstraints')],
)
def test_compiled_pattern_in_field(use_field):
    """
    https://github.com/pydantic/pydantic/issues/9052
    https://github.com/pydantic/pydantic/pull/9053
    """
    pattern_value = r'^whatev.r\d$'
    field_pattern = re.compile(pattern_value)

    if use_field:

        class Foobar(BaseModel):
            str_regex: str = Field(pattern=field_pattern)
    else:

        class Foobar(BaseModel):
            str_regex: Annotated[str, StringConstraints(pattern=field_pattern)] = ...

    field_general_metadata = Foobar.model_fields['str_regex'].metadata
    assert len(field_general_metadata) == 1
    field_metadata_pattern = field_general_metadata[0].pattern

    assert field_metadata_pattern == field_pattern
    assert isinstance(field_metadata_pattern, re.Pattern)

    matching_value = 'whatever1'
    f = Foobar(str_regex=matching_value)
    assert f.str_regex == matching_value

    with pytest.raises(
        ValidationError,
        match=re.escape("String should match pattern '" + pattern_value + "'"),
    ):
        Foobar(str_regex=' whatever1')

    assert Foobar.model_json_schema() == {
        'type': 'object',
        'title': 'Foobar',
        'properties': {'str_regex': {'pattern': pattern_value, 'title': 'Str Regex', 'type': 'string'}},
        'required': ['str_regex'],
    }


def test_pattern_with_invalid_param():
    with pytest.raises(
        PydanticSchemaGenerationError,
        match=re.escape('Unable to generate pydantic-core schema for re.Pattern[int].'),
    ):
        TypeAdapter(Pattern[int])


@pytest.mark.parametrize(
    ('pattern_type', 'pattern_value', 'error_type', 'error_msg'),
    [
        pytest.param(
            re.Pattern,
            '[xx',
            'pattern_regex',
            'Input should be a valid regular expression',
            id='re.Pattern-pattern_regex',
        ),
        pytest.param(re.Pattern, (), 'pattern_type', 'Input should be a valid pattern', id='re.Pattern-pattern_type'),
        pytest.param(
            re.Pattern[str],
            re.compile(b''),
            'pattern_str_type',
            'Input should be a string pattern',
            id='re.Pattern[str]-pattern_str_type-non_str',
        ),
        pytest.param(
            re.Pattern[str],
            b'',
            'pattern_str_type',
            'Input should be a string pattern',
            id='re.Pattern[str]-pattern_str_type-bytes',
        ),
        pytest.param(
            re.Pattern[str], (), 'pattern_type', 'Input should be a valid pattern', id='re.Pattern[str]-pattern_type'
        ),
        pytest.param(
            re.Pattern[bytes],
            re.compile(''),
            'pattern_bytes_type',
            'Input should be a bytes pattern',
            id='re.Pattern[bytes]-pattern_bytes_type-non_bytes',
        ),
        pytest.param(
            re.Pattern[bytes],
            '',
            'pattern_bytes_type',
            'Input should be a bytes pattern',
            id='re.Pattern[bytes]-pattern_bytes_type-str',
        ),
        pytest.param(
            re.Pattern[bytes],
            (),
            'pattern_type',
            'Input should be a valid pattern',
            id='re.Pattern[bytes]-pattern_type',
        ),
    ],
)
def test_pattern_error(pattern_type, pattern_value, error_type, error_msg):
    ta = TypeAdapter(pattern_type)

    with pytest.raises(ValidationError) as exc_info:
        ta.validate_python(pattern_value)
    # insert_assert(exc_info.value.errors(include_url=False))
    assert exc_info.value.errors(include_url=False) == [
        {'type': error_type, 'loc': (), 'msg': error_msg, 'input': pattern_value}
    ]


@pytest.mark.parametrize(
    ('pattern_type', 'pattern', 'expected'),
    [
        pytest.param(Pattern[str], re.compile('^regex$'), '^regex$', id='str-no-flags'),
        pytest.param(Pattern[str], re.compile('^regex$', re.IGNORECASE), '(?i)^regex$', id='str-ignorecase'),
        pytest.param(
            Pattern[str], re.compile('^regex$', re.IGNORECASE | re.MULTILINE), '(?im)^regex$', id='str-multiple-flags'
        ),
        pytest.param(Pattern[str], re.compile('(?i)^regex$'), '(?i)^regex$', id='str-inline-flag'),
        pytest.param(
            Pattern[str], re.compile('(?i)^regex$', re.MULTILINE), '(?m)(?i)^regex$', id='str-inline-and-flags'
        ),
        pytest.param(Pattern[str], re.compile('^regex$', re.ASCII), '(?a)^regex$', id='str-ascii'),
        pytest.param(Pattern[bytes], re.compile(b'^regex$'), '^regex$', id='bytes-no-flags'),
        pytest.param(Pattern[bytes], re.compile(b'^regex$', re.IGNORECASE), '(?i)^regex$', id='bytes-ignorecase'),
    ],
)
def test_pattern_serialization_preserves_flags(pattern_type, pattern, expected):
    """https://github.com/pydantic/pydantic/issues/13761"""
    ta = TypeAdapter(pattern_type)
    assert ta.dump_python(pattern, mode='json') == expected
    assert ta.dump_json(pattern) == json.dumps(expected).encode()


@pytest.mark.parametrize(
    'pattern',
    [
        pytest.param(re.compile('^regex$'), id='no-flags'),
        pytest.param(re.compile('^regex$', re.IGNORECASE), id='ignorecase'),
        pytest.param(re.compile('^regex$', re.IGNORECASE | re.MULTILINE), id='multiple-flags'),
        pytest.param(re.compile('(?i)^regex$'), id='inline-flag'),
        pytest.param(re.compile('(?i)^regex$', re.MULTILINE), id='inline-and-flags'),
        pytest.param(re.compile('^regex$', re.ASCII), id='ascii'),
        pytest.param(re.compile('^regex$', re.DOTALL | re.VERBOSE), id='dotall-verbose'),
        pytest.param(re.compile('^reg # comment\nex$', re.VERBOSE), id='verbose-comment'),
    ],
)
def test_pattern_json_round_trip_preserves_flags(pattern):
    """https://github.com/pydantic/pydantic/issues/13761"""

    class Model(BaseModel):
        pattern: Pattern[str]

    loaded = Model.model_validate_json(Model(pattern=pattern).model_dump_json())
    assert loaded.pattern.flags == pattern.flags
    # The flags are effective, i.e. the deserialized pattern matches the same strings.
    for value in ['regex', 'REGEX', 'regex\nREGEX', 'not-a-match']:
        assert bool(loaded.pattern.search(value)) == bool(pattern.search(value))


def test_pattern_json_serialization_keeps_flags_that_affect_matching():
    """https://github.com/pydantic/pydantic/issues/13761"""

    class Model(BaseModel):
        pattern: Pattern[str]

    dumped = Model(pattern=re.compile('^regex$', re.IGNORECASE)).model_dump_json()
    loaded = Model.model_validate_json(dumped)
    assert loaded.pattern.match('REGEX')
    assert loaded.pattern.flags == re.IGNORECASE | re.UNICODE


def test_pattern_json_round_trip_text_only_valid_with_flags():
    """https://github.com/pydantic/pydantic/issues/13761"""

    class Model(BaseModel):
        pattern: Pattern[str]

    # The text alone is invalid: the unterminated group is inside a comment, so `re.VERBOSE` is required.
    pattern = re.compile('a # (unclosed', re.VERBOSE)
    loaded = Model.model_validate_json(Model(pattern=pattern).model_dump_json())
    assert loaded.pattern.flags == pattern.flags
    assert loaded.pattern.match('a')
