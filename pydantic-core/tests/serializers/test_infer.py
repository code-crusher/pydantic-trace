from enum import Enum

import pytest

from pydantic_core import PydanticSerializationError, SchemaSerializer, core_schema, to_json, to_jsonable_python


# serializing enum calls methods in serializers::infer
def test_infer_to_python():
    class MyEnum(Enum):
        complex_ = complex(1, 2)

    v = SchemaSerializer(core_schema.enum_schema(MyEnum, list(MyEnum.__members__.values())))
    assert v.to_python(MyEnum.complex_, mode='json') == '1+2j'


def test_infer_serialize():
    class MyEnum(Enum):
        complex_ = complex(1, 2)

    v = SchemaSerializer(core_schema.enum_schema(MyEnum, list(MyEnum.__members__.values())))
    assert v.to_json(MyEnum.complex_) == b'"1+2j"'


def test_infer_json_key():
    class MyEnum(Enum):
        complex_ = {complex(1, 2): 1}  # noqa: RUF012

    v = SchemaSerializer(core_schema.enum_schema(MyEnum, list(MyEnum.__members__.values())))
    assert v.to_json(MyEnum.complex_) == b'{"1+2j":1}'


def test_infer_invalid_pydantic_serializer_fallback():
    """https://github.com/pydantic/pydantic/issues/13734"""
    # `unittest.mock.call` fakes arbitrary attributes (including `__pydantic_serializer__`)
    # via `__getattr__`, so type inference thinks it's pydantic-serializable; the value of the
    # attribute is invalid, which used to raise a `TypeError` instead of using the fallback
    from unittest.mock import call

    assert to_jsonable_python(call(1, 2, 3), fallback=lambda c: c.args) == [1, 2, 3]
    assert to_jsonable_python([call(1), call(2)], fallback=lambda c: c.args) == [[1], [2]]
    assert to_json(call(1, 2, 3), fallback=lambda c: list(c.args)) == b'[1,2,3]'


def test_infer_invalid_pydantic_serializer_no_fallback():
    class Fake:
        __pydantic_serializer__ = 42

    # no fallback: behaves like an unknown type
    with pytest.raises(PydanticSerializationError, match="Unable to serialize unknown type: <class '.+Fake'>"):
        to_jsonable_python(Fake())

    with pytest.raises(PydanticSerializationError, match="Unable to serialize unknown type: <class '.+Fake'>"):
        SchemaSerializer(core_schema.any_schema()).to_python(Fake(), mode='json')


def test_infer_invalid_pydantic_serializer_python_mode():
    class Fake:
        __pydantic_serializer__ = 42

    v = Fake()
    # in python mode, unknown types are returned as-is (after a warning)
    with pytest.warns(
        UserWarning,
        match=r'Expected `pydantic-serializable` - serialized value may not be as expected '
        r'\[input_value=<.+ at 0x[0-9a-f]+>, input_type=Fake\]',
    ):
        assert SchemaSerializer(core_schema.any_schema()).to_python(v) is v
