from typing import Any

from typing_extensions import Self

from pydantic import BaseModel, create_model


class Model(BaseModel):
    a: int


SubModel = create_model('SubModel', __base__=Model)


class Main(BaseModel):
    sub: SubModel


FieldsModel = create_model(
    'FieldsModel',
    __base__=Model,
    __module__=Model.__module__,
    parameter_1=(int, ...),
    parameter_2=(str, None),
)
fields_model = FieldsModel(a=1, parameter_1=1)
fields_parameter_1: int = fields_model.parameter_1
fields_parameter_2: str | None = fields_model.parameter_2
fields_a: int = fields_model.a

LiteralFieldsModel = create_model('LiteralFieldsModel', **{'literal_parameter': (int, ...)})
literal_fields_model = LiteralFieldsModel(literal_parameter=1)
literal_parameter: int = literal_fields_model.literal_parameter

field_definitions = {'dict_parameter': (str, ...)}
DictFieldsModel = create_model('DictFieldsModel', **field_definitions)
dict_fields_model = DictFieldsModel(dict_parameter='value')
dict_parameter: str = dict_fields_model.dict_parameter

SpecialFieldsModel = create_model('SpecialFieldsModel', **{'__base__': Model, 'special_parameter': (int, ...)})
special_fields_model = SpecialFieldsModel(a=1, special_parameter=2)
special_parameter: int = special_fields_model.special_parameter
special_a: int = special_fields_model.a


# This only crashes in parallel mode (see https://github.com/python/mypy/issues/21472):
def dyn_model() -> type[BaseModel]:
    local_field_definitions = {'local_parameter': (int, ...)}
    LocalFieldsModel = create_model('LocalFieldsModel', **local_field_definitions)
    local_fields_model = LocalFieldsModel(local_parameter=1)
    local_parameter: int = local_fields_model.local_parameter

    Inner = create_model("Inner", __base__=BaseModel, value=(int, ...))

    class Outer(Inner):
        pass

    return Outer


class ClassmethodModel(BaseModel):
    @classmethod
    def composite(cls) -> type[Self]:
        # Ensures the mypy plugin defers to the `create_model()` overload:
        model = create_model(cls.__name__, __base__=cls)
        return model
