from typing import Any

from pydantic import Field, create_model


def get_field_definitions() -> Any:
    return {'runtime_parameter': (int, ...)}


field_definitions = {'x': (int, ...)}
Model = create_model('Model', **field_definitions)

Model()
Model(x='bad')
Model(y=1)

model = Model(x=1)
reveal_type(model.x)

# Only the latest assignment of the field definitions is taken into account:
latest_field_definitions: Any = {'x': (int, ...)}
latest_field_definitions = {'y': (str, ...)}
LatestModel = create_model('LatestModel', **latest_field_definitions)
latest_model = LatestModel(y='ok')
reveal_type(latest_model.y)

# The field definitions cannot be determined statically, so nothing is known about the fields:
dynamic_field_definitions: Any = get_field_definitions()
DynamicModel = create_model('DynamicModel', **dynamic_field_definitions)
dynamic_model = DynamicModel(runtime_parameter=1)
reveal_type(dynamic_model.runtime_parameter)

# Same for conditionally assigned field definitions, as they depend on runtime behavior:
conditional_field_definitions: dict[str, Any] = {'conditional_parameter': (int, ...)}
if bool(conditional_field_definitions):
    conditional_field_definitions = {'other_conditional_parameter': (int, ...)}
ConditionalModel = create_model('ConditionalModel', **conditional_field_definitions)
conditional_model = ConditionalModel(conditional_parameter=1)
reveal_type(conditional_model)

# Aliases and defaults supplied through `Field()` are respected:
AliasModel = create_model('AliasModel', x=(int, Field(alias='X')), y=(int, Field(default=0)))
AliasModel(X=1)
AliasModel(x=1)
alias_model = AliasModel(X=1)
reveal_type(alias_model.y)
