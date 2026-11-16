from typing import Any

from pydantic import Field, create_model


def get_field_definitions() -> Any:
    return {'runtime_parameter': (int, ...)}


field_definitions = {'x': (int, ...)}
Model = create_model('Model', **field_definitions)

Model()
# MYPY: error: Missing named argument "x" for "Model"  [call-arg]
Model(x='bad')
# MYPY: error: Argument "x" to "Model" has incompatible type "str"; expected "int"  [arg-type]
Model(y=1)
# MYPY: error: Unexpected keyword argument "y" for "Model"  [call-arg]

model = Model(x=1)
reveal_type(model.x)
# MYPY: note: Revealed type is "int"

# Only the latest assignment of the field definitions is taken into account:
latest_field_definitions: Any = {'x': (int, ...)}
latest_field_definitions = {'y': (str, ...)}
LatestModel = create_model('LatestModel', **latest_field_definitions)
latest_model = LatestModel(y='ok')
reveal_type(latest_model.y)
# MYPY: note: Revealed type is "str"

# The field definitions cannot be determined statically, so nothing is known about the fields:
dynamic_field_definitions: Any = get_field_definitions()
DynamicModel = create_model('DynamicModel', **dynamic_field_definitions)
dynamic_model = DynamicModel(runtime_parameter=1)
# MYPY: error: Unexpected keyword argument "runtime_parameter" for "DynamicModel"  [call-arg]
reveal_type(dynamic_model.runtime_parameter)
# MYPY: error: "DynamicModel" has no attribute "runtime_parameter"  [attr-defined]
# MYPY: note: Revealed type is "Any"

# Same for conditionally assigned field definitions, as they depend on runtime behavior:
conditional_field_definitions: dict[str, Any] = {'conditional_parameter': (int, ...)}
if bool(conditional_field_definitions):
    conditional_field_definitions = {'other_conditional_parameter': (int, ...)}
ConditionalModel = create_model('ConditionalModel', **conditional_field_definitions)
conditional_model = ConditionalModel(conditional_parameter=1)
# MYPY: error: Unexpected keyword argument "conditional_parameter" for "ConditionalModel"  [call-arg]
reveal_type(conditional_model)
# MYPY: note: Revealed type is "tests.mypy.modules.create_model_var_strict.ConditionalModel"

# Aliases and defaults supplied through `Field()` are respected:
AliasModel = create_model('AliasModel', x=(int, Field(alias='X')), y=(int, Field(default=0)))
AliasModel(X=1)
AliasModel(x=1)
# MYPY: error: Unexpected keyword argument "x" for "AliasModel"  [call-arg]
alias_model = AliasModel(X=1)
reveal_type(alias_model.y)
# MYPY: note: Revealed type is "int"
