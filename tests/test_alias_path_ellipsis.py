"""Tests for `...` (array unpacking) support in `AliasPath`.

https://github.com/pydantic/pydantic/issues/13784
"""

import json
from collections.abc import Sequence
from typing import Annotated, Any

import pytest
from typing_extensions import TypedDict

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class Blog(BaseModel):
    name: str
    authors: list[str] = Field(validation_alias=AliasPath('authors', ..., 'name'))


def test_alias_path_wildcard() -> None:
    """https://github.com/pydantic/pydantic/issues/13784"""
    data = {'name': 'Blog entry', 'authors': [{'name': 'Alice'}, {'name': 'Bob'}]}
    assert Blog.model_validate(data).authors == ['Alice', 'Bob']
    assert Blog.model_validate_json(json.dumps(data)).authors == ['Alice', 'Bob']


def test_alias_path_wildcard_model_construct() -> None:
    """`model_construct()` resolves aliases in Python, not through the compiled validator."""
    data = {'name': 'Blog entry', 'authors': [{'name': 'Alice'}, {'name': 'Bob'}]}
    assert Blog.model_construct(**data).authors == ['Alice', 'Bob']


def test_alias_path_wildcard_empty_list() -> None:
    assert Blog.model_validate({'name': 'x', 'authors': []}).authors == []
    assert Blog.model_validate_json('{"name": "x", "authors": []}').authors == []


@pytest.mark.parametrize('validate_json', [False, True])
def test_alias_path_wildcard_omits_unresolved_items(validate_json: bool) -> None:
    data = {'name': 'x', 'authors': [{'name': 'Alice'}, {}]}

    def validate():
        if validate_json:
            return Blog.model_validate_json(json.dumps(data))
        else:
            return Blog.model_validate(data)

    assert validate().authors == ['Alice']
    assert Blog.model_construct(**data).authors == ['Alice']


@pytest.mark.parametrize('validate_json', [False, True])
def test_alias_path_wildcard_nested(validate_json: bool) -> None:
    class Model(BaseModel):
        names: list[list[str]] = Field(validation_alias=AliasPath('groups', ..., ..., 'name'))

    data = {'groups': [[{'name': 'A'}, {'name': 'B'}], [{'name': 'C'}]]}

    def validate(value: Any):
        if validate_json:
            return Model.model_validate_json(json.dumps(value))
        else:
            return Model.model_validate(value)

    assert validate(data).names == [['A', 'B'], ['C']]
    assert Model.model_construct(**data).names == [['A', 'B'], ['C']]
    # only the items failing to resolve past the wildcard are omitted:
    assert validate({'groups': [[{'name': 'A'}, {}], [{'name': 'C'}]]}).names == [['A'], ['C']]


def test_alias_path_wildcard_terminal() -> None:
    class Model(BaseModel):
        authors: list[dict[str, str]] = Field(validation_alias=AliasPath('authors', ...))

    data = {'authors': [{'name': 'Alice'}]}
    assert Model.model_validate(data).authors == [{'name': 'Alice'}]
    assert Model.model_validate_json(json.dumps(data)).authors == [{'name': 'Alice'}]


def test_alias_path_wildcard_tuple_and_generic_sequence() -> None:
    class Model(BaseModel):
        authors: list[str] = Field(validation_alias=AliasPath('authors', ..., 'name'))

    assert Model.model_validate({'authors': ({'name': 'Alice'},)}).authors == ['Alice']

    class Seq(Sequence[dict[str, str]]):
        def __init__(self, items: list[dict[str, str]]) -> None:
            self._items = items

        def __getitem__(self, index: int) -> dict[str, str]:
            return self._items[index]

        def __len__(self) -> int:
            return len(self._items)

    assert Model.model_validate({'authors': Seq([{'name': 'Alice'}])}).authors == ['Alice']


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('not-a-list', id='str'),
        pytest.param({'name': 'Alice'}, id='dict'),
    ],
)
@pytest.mark.parametrize('validate_json', [False, True])
def test_alias_path_wildcard_non_sequence_is_not_found(value: Any, validate_json: bool) -> None:
    class Model(BaseModel):
        authors: list[str] | None = Field(None, validation_alias=AliasPath('authors', ..., 'name'))

    if validate_json:
        assert Model.model_validate_json(json.dumps({'authors': value})).authors is None
    else:
        assert Model.model_validate({'authors': value}).authors is None


@pytest.mark.parametrize(
    'value',
    [
        pytest.param(b'not-a-list', id='bytes'),
        pytest.param(bytearray(b'not-a-list'), id='bytearray'),
    ],
)
def test_alias_path_wildcard_bytes_is_not_a_sequence(value: Any) -> None:
    class Model(BaseModel):
        authors: list[str] | None = Field(None, validation_alias=AliasPath('authors', ..., 'name'))

    assert Model.model_validate({'authors': value}).authors is None


def test_alias_path_wildcard_sequence_exception_propagates() -> None:
    class BadSequence(Sequence[Any]):
        def __len__(self) -> int:
            raise ValueError('len boom')

        def __getitem__(self, index: int) -> Any:
            raise IndexError

    class Model(BaseModel):
        authors: list[str] | None = Field(None, validation_alias=AliasPath('authors', ..., 'name'))

    with pytest.raises(ValueError, match='len boom'):
        Model.model_validate({'authors': BadSequence()})


@pytest.mark.parametrize('validate_json', [False, True])
def test_alias_path_wildcard_error_loc(validate_json: bool) -> None:
    data = {'name': 'x', 'authors': [{'name': 'Alice'}, {'name': 123}]}
    with pytest.raises(
        ValidationError,
        check=lambda e: (
            e.errors(include_url=False)
            == [
                {
                    'type': 'string_type',
                    'loc': ('authors', '*', 'name', 1),
                    'msg': 'Input should be a valid string',
                    'input': 123,
                }
            ]
        ),
    ):
        if validate_json:
            Blog.model_validate_json(json.dumps(data))
        else:
            Blog.model_validate(data)


def test_alias_path_wildcard_nested_error_loc() -> None:
    class Model(BaseModel):
        names: list[list[str]] = Field(validation_alias=AliasPath('groups', ..., ..., 'name'))

    with pytest.raises(
        ValidationError,
        check=lambda e: (
            e.errors(include_url=False)
            == [
                {
                    'type': 'string_type',
                    'loc': ('groups', '*', '*', 'name', 0, 1),
                    'msg': 'Input should be a valid string',
                    'input': 123,
                }
            ]
        ),
    ):
        Model.model_validate({'groups': [[{'name': 'A'}, {'name': 123}]]})


def test_alias_choices_wildcard() -> None:
    class Model(BaseModel):
        names: list[str] = Field(
            validation_alias=AliasChoices(AliasPath('authors', ..., 'name'), 'writers'),
        )

    assert Model.model_validate({'authors': [{'name': 'A'}]}).names == ['A']
    assert Model.model_validate({'writers': ['W']}).names == ['W']


def test_alias_path_wildcard_extra_forbid() -> None:
    class Model(BaseModel):
        model_config = ConfigDict(extra='forbid')
        authors: list[str] = Field(validation_alias=AliasPath('authors', ..., 'name'))

    data = {'authors': [{'name': 'Alice'}]}
    assert Model.model_validate(data).authors == ['Alice']
    assert Model.model_validate_json(json.dumps(data)).authors == ['Alice']


def test_alias_path_wildcard_extra_allow() -> None:
    class Model(BaseModel):
        model_config = ConfigDict(extra='allow')
        authors: list[str] = Field(validation_alias=AliasPath('authors', ..., 'name'))

    data = {'authors': [{'name': 'Alice'}]}
    model = Model.model_validate(data)
    assert model.authors == ['Alice']
    assert model.model_extra == {}


@pytest.mark.parametrize('validate_json', [False, True])
def test_alias_choices_wildcard_extra_allow_surfaces_unused_root(validate_json: bool) -> None:
    class Model(BaseModel):
        model_config = ConfigDict(extra='allow')
        names: list[str] = Field(validation_alias=AliasChoices('writers', AliasPath('authors', ..., 'name')))

    data = {'writers': ['X'], 'authors': [{'name': 'A'}]}
    if validate_json:
        model = Model.model_validate_json(json.dumps(data))
    else:
        model = Model.model_validate(data)
    assert model.names == ['X']
    assert model.model_extra == {'authors': [{'name': 'A'}]}


def test_alias_path_wildcard_from_attributes() -> None:
    class Author:
        def __init__(self, name: str) -> None:
            self.name = name

    class Input:
        authors = [Author('Alice'), Author('Bob')]

    class Model(BaseModel):
        model_config = ConfigDict(from_attributes=True)
        authors: list[str] = Field(validation_alias=AliasPath('authors', ..., 'name'))

    assert Model.model_validate(Input()).authors == ['Alice', 'Bob']


def test_alias_path_wildcard_typed_dict() -> None:
    class Model(TypedDict):
        authors: Annotated[list[str], Field(validation_alias=AliasPath('authors', ..., 'name'))]

    data = {'authors': [{'name': 'Alice'}]}
    adapter = TypeAdapter(Model)
    assert adapter.validate_python(data) == {'authors': ['Alice']}
    assert adapter.validate_json(json.dumps(data)) == {'authors': ['Alice']}


def test_alias_path_wildcard_named_tuple() -> None:
    from typing import NamedTuple

    class Model(NamedTuple):
        authors: Annotated[list[str], Field(validation_alias=AliasPath('authors', ..., 'name'))]

    assert TypeAdapter(Model).validate_python({'authors': [{'name': 'Alice'}]}).authors == ['Alice']
