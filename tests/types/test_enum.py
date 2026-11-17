from enum import Enum, IntEnum, StrEnum
from typing import Annotated, Any, NamedTuple

import pytest
from dirty_equals import IsStr
from pydantic_core import CoreSchema, core_schema

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    Strict,
    TypeAdapter,
    ValidationError,
)


def test_enum_successful():
    class ToolEnum(IntEnum):
        spanner = 1
        wrench = 2

    ta = TypeAdapter(ToolEnum)

    v = ta.validate_python(2)
    assert v == ToolEnum.wrench
    assert repr(v) == '<ToolEnum.wrench: 2>'


def test_enum_fails():
    class ToolEnum(IntEnum):
        spanner = 1
        wrench = 2

    ta = TypeAdapter(ToolEnum)

    with pytest.raises(ValueError) as exc_info:
        ta.validate_python(3)
    # insert_assert(exc_info.value.errors(include_url=False))
    assert exc_info.value.errors(include_url=False) == [
        {
            'ctx': {'expected': '1 or 2'},
            'input': 3,
            'loc': (),
            'msg': 'Input should be 1 or 2',
            'type': 'enum',
        }
    ]


def test_enum_fails_error_msg():
    class Number(IntEnum):
        one = 1
        two = 2
        three = 3

    ta = TypeAdapter(Number)

    with pytest.raises(ValueError) as exc_info:
        ta.validate_python(4)
    # insert_assert(exc_info.value.errors(include_url=False))
    assert exc_info.value.errors(include_url=False) == [
        {
            'type': 'enum',
            'loc': (),
            'msg': 'Input should be 1, 2 or 3',
            'input': 4,
            'ctx': {'expected': '1, 2 or 3'},
        }
    ]


def test_int_enum_successful_for_str_int():
    class ToolEnum(IntEnum):
        spanner = 1
        wrench = 2

    ta = TypeAdapter(ToolEnum)

    v = ta.validate_python('2')
    assert v == ToolEnum.wrench
    assert repr(v) == '<ToolEnum.wrench: 2>'


def test_plain_enum_validate():
    class MyEnum(Enum):
        a = 1

    class Model(BaseModel):
        x: MyEnum

    m = Model(x=MyEnum.a)
    assert m.x is MyEnum.a

    assert TypeAdapter(MyEnum).validate_python(1) is MyEnum.a
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(MyEnum).validate_python(1, strict=True)
    assert exc_info.value.errors(include_url=False) == [
        {
            'ctx': {'class': 'test_plain_enum_validate.<locals>.MyEnum'},
            'input': 1,
            'loc': (),
            'msg': IsStr(regex='Input should be an instance of test_plain_enum_validate.<locals>.MyEnum'),
            'type': 'is_instance_of',
        }
    ]

    assert TypeAdapter(MyEnum).validate_json('1') is MyEnum.a
    TypeAdapter(MyEnum).validate_json('1', strict=True)
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(MyEnum).validate_json('"1"', strict=True)
    assert exc_info.value.errors(include_url=False) == [
        {'ctx': {'expected': '1'}, 'input': '1', 'loc': (), 'msg': 'Input should be 1', 'type': 'enum'}
    ]


def test_plain_enum_validate_json():
    class MyEnum(Enum):
        a = 1

    class Model(BaseModel):
        x: MyEnum

    m = Model.model_validate_json('{"x":1}')
    assert m.x is MyEnum.a


def test_enum_type():
    class Model(BaseModel):
        my_enum: Enum

    class MyEnum(Enum):
        a = 1

    m = Model(my_enum=MyEnum.a)
    assert m.my_enum == MyEnum.a
    assert m.model_dump() == {'my_enum': MyEnum.a}
    assert m.model_dump_json() == '{"my_enum":1}'

    with pytest.raises(ValidationError) as exc_info:
        Model(my_enum=1)
    assert exc_info.value.errors(include_url=False) == [
        {
            'ctx': {'class': 'Enum'},
            'input': 1,
            'loc': ('my_enum',),
            'msg': 'Input should be an instance of Enum',
            'type': 'is_instance_of',
        }
    ]


def test_enum_missing_default():
    class MyEnum(Enum):
        a = 1

    ta = TypeAdapter(MyEnum)

    assert ta.validate_python(1) is MyEnum.a
    with pytest.raises(ValidationError):
        ta.validate_python(2)
    with pytest.raises(ValidationError):
        ta.validate_json('2')


def test_enum_missing_custom():
    class MyEnum(Enum):
        a = 1

        @classmethod
        def _missing_(cls, value):
            return MyEnum.a

    ta = TypeAdapter(MyEnum)

    assert ta.validate_python(1) is MyEnum.a
    assert ta.validate_python(2) is MyEnum.a
    assert ta.validate_json('2') is MyEnum.a


def test_enum_missing_receives_input_value() -> None:
    """https://github.com/pydantic/pydantic/issues/12960"""
    seen = []

    class MyEnum(Enum):
        a = 1
        b = 2

        @classmethod
        def _missing_(cls, value):
            seen.append(value)
            return cls.b

    ta = TypeAdapter(MyEnum)

    assert ta.validate_python(3) is MyEnum.b
    assert ta.validate_json('3') is MyEnum.b
    assert ta.validate_json('3', strict=True) is MyEnum.b
    assert ta.validate_python('3') is MyEnum.b
    assert ta.validate_json('"3"') is MyEnum.b
    assert seen == [3, 3, 3, '3', '3']


def test_enum_missing_raises() -> None:
    class MyEnum(Enum):
        a = 1
        b = 2

        @classmethod
        def _missing_(cls, value):
            if value == 3:
                raise ValueError('nope')
            raise KeyError(value)

    ta = TypeAdapter(MyEnum)

    # `ValueError` is converted to a validation error, as in `Enum.__new__()`:
    with pytest.raises(ValidationError, match=r'Input should be 1 or 2 \[type=enum, input_value=3, input_type=int\]'):
        ta.validate_python(3)
    with pytest.raises(ValidationError, match=r'Input should be 1 or 2 \[type=enum, input_value=3, input_type=int\]'):
        ta.validate_json('3')

    # other exceptions are propagated:
    with pytest.raises(KeyError):
        ta.validate_python(4)
    with pytest.raises(KeyError):
        ta.validate_json('4')


def test_int_enum_type():
    class Model(BaseModel):
        my_enum: IntEnum

    class MyEnum(Enum):
        a = 1

    class MyIntEnum(IntEnum):
        b = 2

    m = Model(my_enum=MyIntEnum.b)
    assert m.my_enum == MyIntEnum.b
    assert m.model_dump() == {'my_enum': MyIntEnum.b}
    assert m.model_dump_json() == '{"my_enum":2}'

    with pytest.raises(ValidationError) as exc_info:
        Model(my_enum=MyEnum.a)
    assert exc_info.value.errors(include_url=False) == [
        {
            'ctx': {'class': 'IntEnum'},
            'input': MyEnum.a,
            'loc': ('my_enum',),
            'msg': 'Input should be an instance of IntEnum',
            'type': 'is_instance_of',
        }
    ]


@pytest.mark.parametrize('enum_base,strict', [(Enum, False), (IntEnum, False), (IntEnum, True)])
def test_enum_from_json(enum_base, strict):
    class MyEnum(enum_base):
        a = 1
        b = 3

    class Model(BaseModel):
        my_enum: MyEnum

    m = Model.model_validate_json('{"my_enum":1}', strict=strict)
    assert m.my_enum is MyEnum.a

    with pytest.raises(ValidationError) as exc_info:
        Model.model_validate_json('{"my_enum":2}', strict=strict)

    if strict:
        assert exc_info.value.errors(include_url=False) == [
            {
                'ctx': {'expected': '1 or 3'},
                'input': 2,
                'loc': ('my_enum',),
                'msg': 'Input should be 1 or 3',
                'type': 'enum',
            }
        ]
    else:
        assert exc_info.value.errors(include_url=False) == [
            {
                'ctx': {'expected': '1 or 3'},
                'input': 2,
                'loc': ('my_enum',),
                'msg': 'Input should be 1 or 3',
                'type': 'enum',
            }
        ]


def test_strict_enum() -> None:
    class Demo(Enum):
        A = 0
        B = 1

    class User(BaseModel):
        model_config = ConfigDict(strict=True)

        demo_strict: Demo
        demo_not_strict: Demo = Field(strict=False)

    user = User(demo_strict=Demo.A, demo_not_strict=1)

    assert isinstance(user.demo_strict, Demo)
    assert isinstance(user.demo_not_strict, Demo)
    assert user.demo_strict.value == 0
    assert user.demo_not_strict.value == 1

    with pytest.raises(ValidationError, match='Input should be an instance of test_strict_enum.<locals>.Demo'):
        User(demo_strict=0, demo_not_strict=1)


def test_enum_with_no_cases() -> None:
    class MyEnum(Enum):
        pass

    class MyModel(BaseModel):
        e: MyEnum

    json_schema = MyModel.model_json_schema()
    assert json_schema['properties']['e']['enum'] == []


def test_enum_custom_schema() -> None:
    class MyEnum(StrEnum):
        foo = 'FOO'
        bar = 'BAR'
        baz = 'BAZ'

        @classmethod
        def __get_pydantic_core_schema__(
            cls,
            source_type: Any,
            handler: GetCoreSchemaHandler,
        ) -> CoreSchema:
            # check that we can still call handler
            handler(source_type)

            # return a custom unrelated schema so we can test that
            # it gets used
            schema = core_schema.union_schema(
                [
                    core_schema.str_schema(),
                    core_schema.is_instance_schema(cls),
                ]
            )
            return core_schema.no_info_after_validator_function(
                function=lambda x: MyEnum(x.upper()) if isinstance(x, str) else x,
                schema=schema,
                serialization=core_schema.plain_serializer_function_ser_schema(
                    lambda x: x.value, return_schema=core_schema.int_schema()
                ),
            )

    ta = TypeAdapter(MyEnum)

    assert ta.validate_python('foo') == MyEnum.foo


def test_diff_enums_diff_configs() -> None:
    class MyEnum(StrEnum):
        A = 'a'

    class MyModel(BaseModel, use_enum_values=True):
        my_enum: MyEnum

    class OtherModel(BaseModel):
        my_enum: MyEnum

    class Model(BaseModel):
        my_model: MyModel
        other_model: OtherModel

    obj = Model.model_validate({'my_model': {'my_enum': 'a'}, 'other_model': {'my_enum': 'a'}})
    assert not isinstance(obj.my_model.my_enum, MyEnum)
    assert isinstance(obj.other_model.my_enum, MyEnum)


def test_strict_enum_with_use_enum_values() -> None:
    class SomeEnum(int, Enum):
        SOME_KEY = 1

    class Foo(BaseModel):
        model_config = ConfigDict(strict=False, use_enum_values=True)
        foo: Annotated[SomeEnum, Strict(strict=True)]

    f = Foo(foo=SomeEnum.SOME_KEY)
    assert f.foo == 1

    # validation error raised bc foo field uses strict mode
    with pytest.raises(ValidationError):
        Foo(foo='1')


def test_enum_with_namedtuple_values() -> None:
    """https://github.com/pydantic/pydantic/issues/12503"""

    class NT(NamedTuple):
        f: str

    class SomeEnum(NT, Enum):
        FOO = 'foo'

    class Model1(BaseModel):
        value: SomeEnum

    assert Model1(value=SomeEnum.FOO).value is SomeEnum.FOO

    class Model2(BaseModel, use_enum_values=True):
        value: SomeEnum

    assert Model2(value=NT('foo')).value == NT('foo')

    with pytest.raises(ValidationError):
        Model2(value=NT('bar'))


def test_use_enum_names() -> None:
    """https://github.com/pydantic/pydantic/issues/13195"""

    class StateAbbrev(Enum):
        NY = 'New York'
        MA = 'Massachusetts'

    class Address(BaseModel):
        model_config = ConfigDict(use_enum_names=True)

        state: StateAbbrev

    addr = Address(state='NY')
    assert addr.state is StateAbbrev.NY
    assert addr.model_dump() == {'state': 'NY'}
    assert addr.model_dump_json() == '{"state":"NY"}'

    # values are rejected
    with pytest.raises(ValidationError):
        Address(state='New York')

    # JSON input validates by name
    assert Address.model_validate_json('{"state": "MA"}').state is StateAbbrev.MA
    with pytest.raises(ValidationError):
        Address.model_validate_json('{"state": "Massachusetts"}')

    # enum member instances are accepted as-is
    assert Address(state=StateAbbrev.NY).state is StateAbbrev.NY

    # json schema advertises the member names
    schema = Address.model_json_schema()
    assert schema['$defs']['StateAbbrev']['enum'] == ['NY', 'MA']


def test_use_enum_names_int_enum() -> None:
    """https://github.com/pydantic/pydantic/issues/13195"""

    class Priority(IntEnum):
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    class Task(BaseModel):
        model_config = ConfigDict(use_enum_names=True)

        priority: Priority

    task = Task(priority='HIGH')
    assert task.priority is Priority.HIGH
    assert task.model_dump() == {'priority': 'HIGH'}
    assert task.model_dump_json() == '{"priority":"HIGH"}'

    with pytest.raises(ValidationError):
        Task(priority=3)
    with pytest.raises(ValidationError):
        Task(priority='3')

    schema = Task.model_json_schema()
    assert schema['$defs']['Priority']['enum'] == ['LOW', 'MEDIUM', 'HIGH']
    assert schema['$defs']['Priority']['type'] == 'string'


def test_use_enum_names_str_enum() -> None:
    """https://github.com/pydantic/pydantic/issues/13195"""

    class Color(StrEnum):
        RED = 'red_value'
        GREEN = 'green_value'

    class Model(BaseModel):
        model_config = ConfigDict(use_enum_names=True)

        color: Color

    m = Model(color='RED')
    assert m.color is Color.RED
    assert m.model_dump() == {'color': 'RED'}
    assert m.model_dump_json() == '{"color":"RED"}'

    with pytest.raises(ValidationError):
        Model(color='red_value')


def test_use_enum_names_plain_enum_tuple_values() -> None:
    """https://github.com/pydantic/pydantic/issues/13195"""

    class Multi(Enum):
        A = ('a', 1)
        B = ('b', 2)

    class Model(BaseModel):
        model_config = ConfigDict(use_enum_names=True)

        x: Multi

    assert Model(x='A').x is Multi.A
    assert Model(x='A').model_dump() == {'x': 'A'}
    with pytest.raises(ValidationError):
        Model(x=('a', 1))


def test_use_enum_names_with_use_enum_values() -> None:
    """https://github.com/pydantic/pydantic/issues/13195"""

    class StateAbbrev(Enum):
        NY = 'New York'
        MA = 'Massachusetts'

    class Address(BaseModel):
        model_config = ConfigDict(use_enum_names=True, use_enum_values=True)

        state: StateAbbrev

    addr = Address(state='NY')
    # validation happens by name; the value is extracted as per use_enum_values
    assert addr.state == 'New York'
    assert addr.model_dump() == {'state': 'New York'}


def test_use_enum_names_dict_keys() -> None:
    """https://github.com/pydantic/pydantic/issues/13195"""

    class Priority(IntEnum):
        LOW = 1
        HIGH = 2

    class Model(BaseModel):
        model_config = ConfigDict(use_enum_names=True)

        mapping: dict[Priority, str]

    m = Model(mapping={Priority.LOW: 'low'})
    assert m.model_dump() == {'mapping': {'LOW': 'low'}}
    assert m.model_dump_json() == '{"mapping":{"LOW":"low"}}'


def test_use_enum_names_default() -> None:
    """https://github.com/pydantic/pydantic/issues/13195"""

    class StateAbbrev(Enum):
        NY = 'New York'
        MA = 'Massachusetts'

    class Address(BaseModel):
        state: StateAbbrev

    # default behavior unchanged: values are used
    addr = Address(state='New York')
    assert addr.state is StateAbbrev.NY
    assert addr.model_dump() == {'state': StateAbbrev.NY}
    assert addr.model_dump_json() == '{"state":"New York"}'

    with pytest.raises(ValidationError):
        Address(state='NY')
