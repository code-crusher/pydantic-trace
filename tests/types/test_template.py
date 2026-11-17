"""
https://github.com/pydantic/pydantic/issues/13160
"""

import json
import sys

import pytest

if sys.version_info < (3, 14):
    pytest.skip(
        reason='The `string.templatelib.Template` type is only available in Python 3.14+', allow_module_level=True
    )
else:
    from string.templatelib import Interpolation, Template

from pydantic import BaseModel, TypeAdapter, ValidationError


def test_template_field() -> None:
    class Model(BaseModel):
        field: Template

    t = Template('hello ', Interpolation('world', 'name', None, ''), '')
    m = Model(field=t)
    assert m.field is t


def test_template_invalid_type() -> None:
    class Model(BaseModel):
        field: Template

    with pytest.raises(ValidationError) as exc_info:
        Model(field='not a template')  # type: ignore[arg-type]
    assert exc_info.value.errors()[0]['type'] == 'is_instance_of'


def test_template_type_adapter() -> None:
    ta = TypeAdapter(Template)
    t = Template('hello ', Interpolation('world', 'name', None, ''), '')

    assert ta.validate_python(t) is t

    with pytest.raises(ValidationError) as exc_info:
        ta.validate_python('not a template')
    assert exc_info.value.errors()[0]['type'] == 'is_instance_of'


def test_template_generic_alias() -> None:
    ta = TypeAdapter(Template[str])
    t = Template('hello ', Interpolation('world', 'name', None, ''), '')

    assert ta.validate_python(t) is t


def test_template_strict() -> None:
    ta = TypeAdapter(Template, config={'strict': True})
    t = Template('hello ', Interpolation('world', 'name', None, ''), '')

    assert ta.validate_python(t) is t


def test_template_serialization() -> None:
    ta = TypeAdapter(Template)
    t = Template('hello ', Interpolation('world', 'name', None, ''), '')

    assert ta.dump_python(t) is t
    assert ta.dump_python(t, mode='json') == str(t)
    assert ta.dump_json(t) == f'"{t}"'.encode()


def test_template_model_dump() -> None:
    class Model(BaseModel):
        field: Template

    t = Template('hello ', Interpolation('world', 'name', None, ''), '')
    m = Model(field=t)

    assert m.model_dump() == {'field': t}
    assert m.model_dump(mode='json') == {'field': str(t)}
    assert json.loads(m.model_dump_json()) == {'field': str(t)}


def test_template_json_schema() -> None:
    ta = TypeAdapter(Template)
    assert ta.json_schema() == {'type': 'string'}

    class Model(BaseModel):
        field: Template

    assert Model.model_json_schema()['properties']['field'] == {'type': 'string', 'title': 'Field'}


def test_template_union_with_str() -> None:
    ta = TypeAdapter(Template | str)
    t = Template('hello ', Interpolation('world', 'name', None, ''), '')

    assert ta.validate_python(t) is t
    assert ta.validate_python('hello') == 'hello'


def test_template_interpolation_strings_preserved() -> None:
    class Model(BaseModel):
        field: Template

    t = Template('hello ', Interpolation('world', 'name', None, ''), '')
    m = Model(field=t)
    assert m.field.strings == ('hello ', '')
    assert m.field.interpolations[0].value == 'world'
