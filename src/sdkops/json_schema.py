import ast
from typing import Any


ref_cache: dict[str, dict] = {}
ref_name_cache: dict[str, str] = {}


def to_ast(root_name: str, root_schema: dict[str, Any]):
    ref_cache = []
    ref_name_cache = {}
    class_defs: list[ast.ClassDef] = []

    def process_ref(input_schema: dict[str, Any]):
        is_ref = False
        ref_name = None
        is_ref_on_path = False
        if "$ref" in input_schema:
            is_ref = True
            is_ref_on_path = input_schema["$ref"].startswith("#/properties")
            ref_name = schema_generate_name_by_ref(root_schema, input_schema["$ref"])
            input_schema, _trace = schema_resolve_ref(root_schema, input_schema["$ref"])
            if input_schema is None:
                raise ValueError(f"failed to resolve ref. {_trace}")
        return input_schema, is_ref, ref_name, is_ref_on_path

    def to_ast_recursive(
        name_chain: tuple[str],
        schema: dict[str, Any],
        ast_class: ast.ClassDef = None,
        is_required=False,
    ):
        prop_name = name_chain[-1]

        schema, is_ref, ref_name, is_ref_on_path = process_ref(schema)

        if "anyOf" in schema:
            all_types = []
            object_count = 0
            for child_schema in schema["anyOf"]:
                child_schema, is_ref, ref_name, is_ref_on_path = process_ref(
                    child_schema
                )
                if "type" in child_schema and child_schema["type"] == "object":
                    class_name = case_snake_to_pascal("_".join(name_chain)) + (
                        str(object_count + 1) if object_count > 0 else ""
                    )
                    new_class = ast_create_class(class_name)
                    required_props = (
                        child_schema["required"] if "required" in child_schema else []
                    )
                    for child_prop_name, any_child_schema in child_schema[
                        "properties"
                    ].items():
                        _is_required = (
                            True if child_prop_name in required_props else False
                        )
                        to_ast_recursive(
                            name_chain + (child_prop_name,),
                            any_child_schema,
                            new_class,
                            _is_required,
                        )
                    class_defs.append(new_class)
                    all_types.append(class_name)
                    object_count += 1
                elif "type" in child_schema:
                    all_types.append(schema_type_to_py_type(child_schema["type"]))
            ann = ast_create_annotation(all_types)
            if ast_class is None:
                return ast_create_assignment(prop_name, ann)
            else:
                has_default_value = False if is_required is True else True
                default_value = find_default_value_from_types(types=all_types)
                return ast_class_add_init_argument(
                    ast_class, prop_name, ann, has_default_value, default_value
                )

        elif (
            schema["type"] == "string"
            or schema["type"] == "integer"
            or schema["type"] == "boolean"
        ):
            item_type = schema_type_to_py_type(schema["type"])
            if ast_class is None:
                return ast_create_assignment(prop_name, item_type)
            else:
                has_default_value = False if is_required is True else True
                default_value = find_default_value_from_types(types=[item_type])
                return ast_class_add_init_argument(
                    ast_class, prop_name, item_type, has_default_value, default_value
                )

        elif schema["type"] == "array":
            if "items" in schema:
                if "$ref" in schema["items"]:
                    schema["items"], _trace = schema_resolve_ref(
                        root_schema, schema["items"]["$ref"]
                    )
                    if schema["items"] is None:
                        raise ValueError(f"failed to resolve ref. {_trace}")
                if "type" not in schema["items"]:
                    raise Exception(
                        f"there is not type in the schema items. it's either broken or contains functionality this module doesn't support yet."
                    )
                if schema["items"]["type"] == "object":
                    class_name = case_snake_to_pascal("_".join(name_chain))
                    new_class = ast_create_class(class_name)
                    required_props = (
                        schema["items"]["required"]
                        if "required" in schema["items"]
                        else []
                    )
                    for child_prop_name, child_schema in schema["items"][
                        "properties"
                    ].items():
                        _is_required = (
                            True if child_prop_name in required_props else False
                        )
                        to_ast_recursive(
                            name_chain + (child_prop_name,),
                            child_schema,
                            new_class,
                            _is_required,
                        )
                    class_defs.append(new_class)
                    item_type = class_name
                else:
                    item_type = schema_type_to_py_type(schema["items"]["type"])
                items_type = f"list[{item_type}]"
            else:
                raise Exception(
                    "there is no 'items' in the array schema. it's either broken or contains functionality this module doesn't support yet."
                )
            if ast_class is None:
                return ast_create_assignment(prop_name, items_type)
            else:
                has_default_value = False if is_required is True else True
                default_value = find_default_value_from_types(types=[items_type])
                return ast_class_add_init_argument(
                    ast_class, prop_name, items_type, has_default_value, default_value
                )

        elif schema["type"] == "object":
            if is_ref is False or (
                is_ref is True and (ast_class is None or is_ref_on_path is False)
            ):
                class_name = case_snake_to_pascal(
                    "_".join(name_chain)
                    if is_ref is False or (is_ref is True and ast_class is None)
                    else f"{root_name}_{ref_name}"
                )
                new_class = ast_create_class(class_name)
                required_props = schema["required"] if "required" in schema else []
                for child_prop_name, child_schema in schema["properties"].items():
                    _is_required = True if child_prop_name in required_props else False
                    to_ast_recursive(
                        name_chain + (child_prop_name,),
                        child_schema,
                        new_class,
                        is_required=_is_required,
                    )
                if is_ref is False and ast_class is not None:
                    has_default_value = False if is_required is True else True
                    ast_class_add_init_argument(
                        ast_class, prop_name, class_name, has_default_value, None
                    )
                class_defs.append(new_class)

            if is_ref is True and ast_class is not None:
                has_default_value = False if is_required is True else True
                ast_class_add_init_argument(
                    ast_class,
                    prop_name,
                    case_snake_to_pascal(f"{root_name}_{ref_name}"),
                    has_default_value,
                    None,
                )

            return class_defs

        else:
            raise Exception("invalid schema.")

    return to_ast_recursive((root_name,), root_schema, None)


def schema_generate_name_by_ref(schema: dict[str, Any], ref: str):
    if not ref.startswith("#/"):
        raise ValueError("ref must start with '#/'")

    if ref in ref_name_cache:
        return ref_name_cache[ref]

    # remove the '#/' prefix and split by '/'
    path_parts = ref[2:].split("/") if len(ref) > 2 else []

    name_chain = []

    # handle empty path (just "#/" or "#")
    if not path_parts or (len(path_parts) == 1 and path_parts[0] == ""):
        return "_".join(name_chain)

    current = schema
    for i, part in enumerate(path_parts):
        if not isinstance(current, dict):
            raise ValueError(f"invalid ref path: {part}")

        part = part.replace("~1", "/").replace("~0", "~")

        if part not in current:
            raise ValueError(f"invalid ref path: {part} (key not found)")

        next_part = path_parts[i + 1] if i + 1 < len(path_parts) else None
        prev_part = path_parts[i - 1] if i - 1 >= 0 else None
        schema_type = current["type"] if "type" in current else None

        if "anyOf" in current:
            pass

        elif (
            schema_type == "string"
            or schema_type == "integer"
            or schema_type == "boolean"
        ):
            ref_name_cache[ref] = "_".join(name_chain)
            return "_".join(name_chain)

        elif schema_type == "array":
            pass

        elif schema_type == "object" and part == "properties" and next_part is not None:
            for child_prop_name, child_schema in current["properties"].items():
                if child_prop_name == next_part:
                    name_chain.append(child_prop_name)

        else:
            pass

        current = current[part]

        if (
            next_part is None
            and prev_part != "properties"
            and part != "properties"
            and "type" in current
            and current["type"] == "object"
        ):
            # NOTE: we only handle object types here
            name_chain.append(part)

    ref_name_cache[ref] = "_".join(name_chain)

    return "_".join(name_chain)


def schema_resolve_ref(
    schema: dict[str, Any], ref: str
) -> tuple[dict | None, list[str]]:
    if not ref.startswith("#/"):
        raise ValueError("ref must start with '#/'")

    if ref in ref_cache:
        return ref_cache[ref], []

    # remove the '#/' prefix and split by '/'
    path_parts = ref[2:].split("/") if len(ref) > 2 else []

    # handle empty path (just "#/" or "#")
    if not path_parts or (len(path_parts) == 1 and path_parts[0] == ""):
        return schema, ["root"]

    current = schema
    trace = ["root"]

    for part in path_parts:
        if not isinstance(current, dict):
            return None, trace + [f"invalid ref path: {part}"]

        # handle url-decoded characters (json pointer spec)
        part = part.replace("~1", "/").replace("~0", "~")

        if part not in current:
            return None, trace + [f"invalid ref path: {part} (key not found)"]

        current = current[part]
        trace.append(part)

    ref_cache[ref] = current

    return current, trace


def schema_type_to_py_type(key: str):
    mapping: dict[str, str] = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
        "null": "None",
    }
    if key not in mapping:
        raise Exception(f"unknown type '{key}'")
    return mapping[key]


def ast_create_class(id: str):
    return ast.ClassDef(
        name=id,
        bases=[ast.Name(id="dict", ctx=ast.Load())],
        keywords=[],
        decorator_list=[],
        type_params=[],
        body=[
            ast.FunctionDef(
                name="__init__",
                args=ast.arguments(
                    args=[ast.arg(arg="self", annotation=None)],
                    defaults=[],
                    posonlyargs=[],
                    kwonlyargs=[],
                ),
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Call(
                                    func=ast.Name(id="super", ctx=ast.Load()),
                                    args=[],
                                    keywords=[],
                                ),
                                attr="__init__",
                                ctx=ast.Load(),
                            ),
                            args=[],
                            keywords=[],
                        )
                    )
                ],
                decorator_list=[],
                returns=None,
                lineno=1,
            )
        ],
    )


def ast_class_add_init_argument(
    current_class: ast.ClassDef,
    name: str,
    py_type: ast.expr | str | None,
    has_default_value: bool = False,
    default_value: Any = None,
):
    if isinstance(py_type, str):
        py_type = ast_create_annotation([py_type])

    # adding argument to the def __init__(self, name: type):
    arg = ast.arg(arg=name, annotation=py_type)
    if has_default_value is True:
        current_class.body[0].args.args.append(arg)
        # NOTE: it only handles constant nodes, maybe support ast names too
        current_class.body[0].args.defaults.append(ast.Constant(value=default_value))
    else:
        current_class.body[0].args.args.insert(1, arg)
    # adding argument to the super().__init__(name=name)
    current_class.body[0].body[0].value.keywords.append(
        ast.keyword(arg=name, value=ast.Name(id=name, ctx=ast.Load()))
    )
    # adding self.name: type = name
    assignment = ast_create_assignment(f"self.{name}", py_type, name, False)
    current_class.body[0].body.append(assignment)


def ast_create_assignment(
    id: str,
    py_type: ast.expr | str | None,
    value: Any = None,
    is_constant: bool = False,
) -> ast.AnnAssign:
    def is_primitive(value: Any) -> bool:
        primitive_types = (int, float, str, bytes, bool, type(None))
        return isinstance(value, primitive_types)

    if isinstance(py_type, str):
        py_type = ast_create_annotation([py_type])

    if isinstance(value, str) and is_constant is False:
        value = ast.Name(id=value, ctx=ast.Load())
    elif is_primitive(value) and is_constant is True:
        value = ast.Constant(value=value)
    else:
        value = None

    # it also handles "self.obj.nested.prop" like identifiers
    id_parts = id.split(".")
    if len(id_parts) == 1:
        target = ast.Name(id=id_parts[0], ctx=ast.Store())
    else:
        target = ast.Name(id=id_parts[0], ctx=ast.Load())
        for i, attr in enumerate(id_parts[1:], 1):
            ctx = ast.Store() if i == len(id_parts) - 1 else ast.Load()
            target = ast.Attribute(value=target, attr=attr, ctx=ctx)

    return ast.AnnAssign(
        target=target,
        annotation=py_type,
        value=value,
        simple=1 if len(id_parts) == 1 else 0,
    )


def ast_create_annotation(types: list[str]) -> ast.expr | None:
    if not types:
        return None

    if len(types) == 1:
        type_name = types[0]
        if type_name == "None":
            return ast.Constant(value=None)
        else:
            return ast.Name(id=type_name, ctx=ast.Load())

    def create_type_node(type_name) -> ast.expr:
        if type_name == "None":
            return ast.Constant(value=None)
        else:
            return ast.Name(id=type_name, ctx=ast.Load())

    result = create_type_node(types[0])

    for type_name in types[1:]:
        result = ast.BinOp(
            left=result, op=ast.BitOr(), right=create_type_node(type_name)
        )

    return result


def find_default_value_from_types(types: list[str]):
    if not types or len(types) == 0:
        return None

    if "None" in types:
        return None

    if "str" in types:
        return ""

    if "int" in types or "float" in types:
        return 0

    if "bool" in types:
        return False

    if "dict" in types:
        return {}

    if len([x for x in types if x.startswith("list")]) > 0:
        return []

    return None


def case_snake_to_pascal(text: str) -> str:
    components = [comp for comp in text.split("_") if comp]
    if not components:
        return text
    return "".join(word[0].upper() + word[1:] if word else word for word in components)
