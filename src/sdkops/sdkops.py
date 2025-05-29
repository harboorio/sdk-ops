import re
import os
import ast
import black
from typing import Any, List, Union
from dataclasses import dataclass, asdict


class APISpecServer:
    def __init__(self, url: str, description: str = ""):
        self.url = ""
        self.description = ""


class APISpecComponentSchema:
    def __init__(self):
        self.name: str = ""
        self.schema: dict[str, Any] = {}


class APISpecPathOperationContent:
    def __init__(self):
        self.media_type: str = ""
        self.examples: dict[str, Any] | None = None
        self.schema: dict[str, Any] | None = None
        self.extensions: dict[str, Any] = {"x-id": ""}

    def set_id(self, value: str):
        self.extensions["x-id"] = value
        return self

    def get_id(self):
        return self.extensions["x-id"]


class APISpecPathOperationRequestBody:
    def __init__(self):
        self.description: str = ""
        self.required: bool = False
        self.contents: List[APISpecPathOperationContent] = []


class APISpecPathOperationResponse:
    def __init__(self):
        self.status_code: int = 200
        self.description: str = ""
        self.contents: List[APISpecPathOperationContent] = []


class APISpecPathOperationParameter:
    def __init__(self):
        self.name: str = ""
        self.kind: str = ""  # path, query, header, cookie
        self.required: bool = False
        self.schema: dict[str, Any] = {}


class APISpecPathOperation:
    def __init__(self):
        self.method: str = ""
        self.operation_id: str = ""
        self.parameters: List[APISpecPathOperationParameter] = []
        self.request_body: APISpecPathOperationRequestBody | None = None
        self.responses: List[APISpecPathOperationResponse] = []


class APISpecPathItem:
    def __init__(self):
        self.pattern: str = ""
        self.operations: List[APISpecPathOperation] = []


@dataclass
class APISpecApplicationInfo:
    def __init__(self):
        self.title: str = ""
        self.version: str = ""


class APISpec:
    def __init__(self):
        self.version_openapi: str = ""
        self.version: str = ""
        self.info: APISpecApplicationInfo = APISpecApplicationInfo()
        self.paths: List[APISpecPathItem] = []
        self.components: List[APISpecComponentSchema] = []
        self.servers: List[APISpecServer] = []

    def update_info(self, data: Union[APISpecApplicationInfo, dict[str, Any]]):
        data_dict = asdict(data) if isinstance(data, APISpecApplicationInfo) else data
        for k, v in data_dict.items():
            if hasattr(APISpecApplicationInfo, k):
                setattr(self.info, k, v)

        return True

    def find_component_schema(self, ref: str):
        if len(self.components) == 0:
            return None
        kind, schema_name = ref.rsplit("/")[-2:]
        for component in self.components:
            if kind == "schemas":  # this is the only one we support currently
                if component.name == schema_name:
                    return component.schema
        return None


def parse(schema_dict: dict[str, Any]):
    spec = APISpec()

    def parse_content(
        contents_dict: dict[str, Any], op_id: str
    ) -> List[APISpecPathOperationContent]:
        result = []
        for media_type, content_dict in contents_dict.items():
            content = APISpecPathOperationContent()
            content.media_type = media_type

            if "examples" in content_dict:
                content.examples = content_dict["examples"]

            if "schema" in content_dict:
                schema_resolved = content_dict["schema"]
                if "$ref" in schema_resolved:
                    content_id = schema_resolved["$ref"].split("/")[-1]
                    content.set_id(op_id)  # could be content_id too
                    schema_resolved = spec.find_component_schema(
                        schema_resolved["$ref"]
                    )
                else:
                    content.set_id(op_id)
                content.schema = schema_resolved

            result.append(content)
        return result

    if "openapi" in schema_dict:
        spec.version_openapi = schema_dict["openapi"]

    if "info" in schema_dict:
        spec.update_info(schema_dict["info"])

    if "servers" in schema_dict:
        for server in schema_dict["servers"]:
            spec.servers.append(APISpecServer(server["url"], server["description"]))

    if "components" in schema_dict:
        if "schemas" in schema_dict["components"]:
            for name, component_dict in schema_dict["components"]["schemas"].items():
                component = APISpecComponentSchema()
                component.name = name
                component.schema = component_dict
                spec.components.append(component)

    if "paths" in schema_dict:
        for pattern, operations_dict in schema_dict["paths"].items():
            path_item = APISpecPathItem()
            path_item.pattern = pattern
            for method, operation_dict in operations_dict.items():
                path_op = APISpecPathOperation()
                path_op.method = method

                if "operationId" in operation_dict:
                    path_op.operation_id = text_path_pattern_to_snake_case(
                        operation_dict["operationId"]
                    )
                else:
                    path_op.operation_id = f"{text_path_pattern_to_snake_case(path_item.pattern)}_{path_op.method}"

                if "parameters" in operation_dict:
                    for parameter in operation_dict["parameters"]:
                        parameter_ins = APISpecPathOperationParameter()
                        parameter_ins.name = parameter["name"]
                        parameter_ins.kind = parameter["in"]
                        parameter_ins.required = (
                            parameter["required"]
                            if "required" in parameter or parameter["in"] == "path"
                            else False
                        )
                        parameter_ins.schema = parameter["schema"]
                        path_op.parameters.append(parameter_ins)

                if "requestBody" in operation_dict:
                    path_op.request_body = APISpecPathOperationRequestBody()

                    if "required" in operation_dict["requestBody"]:
                        path_op.request_body.required = operation_dict["requestBody"][
                            "required"
                        ]

                    if "description" in operation_dict["requestBody"]:
                        path_op.request_body.description = operation_dict[
                            "requestBody"
                        ]["description"]

                    if "content" in operation_dict["requestBody"]:
                        contents = parse_content(
                            operation_dict["requestBody"]["content"],
                            f"{path_op.operation_id}_request_body",
                        )
                        path_op.request_body.contents.extend(contents)

                if "responses" in operation_dict:
                    responses_dict = operation_dict["responses"]
                    for status_code, response_dict in responses_dict.items():
                        status_code_num = int(status_code)
                        op_id_snake_case = (
                            f"{path_op.operation_id}_response_{status_code}"
                        )
                        response = APISpecPathOperationResponse()
                        response.status_code = status_code
                        response.description = response_dict["description"]

                        if "content" in response_dict:
                            contents = parse_content(
                                response_dict["content"], op_id_snake_case
                            )
                            response.contents.extend(contents)

                        if status_code_num in range(301, 309):
                            empty = {"text/plain": {"schema": {"type": "string"}}}
                            response.contents.extend(
                                parse_content(empty, op_id_snake_case)
                            )

                        path_op.responses.append(response)
                path_item.operations.append(path_op)
            spec.paths.append(path_item)

    return True, spec


def find_base_url(base_url: str | None, spec: APISpec):
    if base_url is not None:
        return True, "", base_url

    if len(spec.servers) == 1:
        return True, "", spec.servers[0].url

    if (len(spec.servers)) > 1:
        localhost_url = next(
            (x.url for x in spec.servers if "localhost" in x.url or "192" in x.url),
            None,
        )
        is_local = bool(os.environ.get("DEBUG")) or (
            "dev" in os.environ.get("PYTHON_ENV")
        )
        if localhost_url and is_local:
            return True, "", localhost_url

    return False, "couldn't find base url. specify the -u, --url option, please.", None


def generate_ast(spec: APISpec, sdk_name: str, dest: str, base_url: str | None):
    def json_schema_to_python_type(key: str):
        type_mapping: dict[str, str] = {
            "string": "str",
            "integer": "int",
            "number": "float",
            "boolean": "bool",
            "array": "list",
            "object": "dict",
        }
        return type_mapping[key]

    def get_default_value_from_type(key: str):
        default_value_mapping: dict[str, Any] = {
            "str": "",
            "int": 0,
            "float": 0,
            "list": [],
            "dict": {},
        }
        return default_value_mapping[key]

    def ast_generate_class_from_json_schema(
        json: dict[str, Any], class_name: str, class_defs: List[ast.ClassDef] = None
    ):
        if class_defs is None:
            class_defs = []

        _type = json["type"]
        required_props = json["required"] if "required" in json else []

        if _type == "object":
            properties = []
            for name, prop in json["properties"].items():
                is_required = True if name in required_props else False
                default_value = (
                    ast.Constant(
                        value=get_default_value_from_type(
                            json_schema_to_python_type(prop["type"])
                        )
                    )
                    if not is_required
                    else None
                )
                child_class_name = json_schema_to_python_type(prop["type"])
                if prop["type"] == "object":
                    child_class_name = text_snake_to_pascal_case(f"{class_name}_{name}")
                    ast_generate_class_from_json_schema(
                        prop, f"{class_name}_{name}", class_defs
                    )
                assign_ast = ast.AnnAssign(
                    target=ast.Name(id=name, ctx=ast.Store()),
                    annotation=ast.Name(id=child_class_name, ctx=ast.Load()),
                    simple=1,
                    value=default_value,
                )
                properties.append(assign_ast)
            class_def = ast.ClassDef(
                name=text_snake_to_pascal_case(class_name),
                bases=[],
                keywords=[],
                body=properties,
                decorator_list=[],
                type_params=[],
            )
            class_defs.append(class_def)

        return class_defs

    def ast_generate_sdk_class():
        return ast.parse(
            source=f"""
class {text_snake_to_pascal_case(sdk_name)}:
    client = httpx.Client(
        base_url="{base_url}",
        headers={{'user-agent': '{sdk_name}', 'accept': 'application/json'}},
        timeout=10,
    )


    def _cleanup(self):
        if not self.client.is_closed:
            self.client.close()


    def _send_request(self, request: httpx.Request) -> httpx.Response:
        try:
            response = self.client.send(request)
            return response
        except httpx.HTTPError as e:
            message = f"An unexpected error occurred while handling request to {{e.request.url}}. {{e}}"
            return httpx.Response(status_code=500, json={{'error': {{'code': 'unexpected', 'message': message}}}})
"""
        )

    def ast_generate_class_method(pattern: str, operation: APISpecPathOperation):
        args = [ast.arg(arg="self", annotation=None)]
        args_defaults = []
        request_call_keywords = []

        if operation.request_body:
            for content in operation.request_body.contents:
                if "json" in content.media_type:
                    py_type = text_snake_to_pascal_case(content.get_id())
                    args.append(
                        ast.arg(
                            arg="json", annotation=ast.Name(id=py_type, ctx=ast.Load())
                        )
                    )
                    request_call_keywords.append(
                        ast.keyword(
                            arg="json", value=ast.Name(id="json", ctx=ast.Load())
                        )
                    )

        for parameter in operation.parameters:
            if parameter.kind == "path" or parameter.kind == "query":
                py_type = json_schema_to_python_type(parameter.schema["type"])
                if "default" in parameter.schema:
                    args_defaults.append(
                        ast.Constant(value=parameter.schema["default"])
                    )
                elif parameter.required:
                    args_defaults.append(
                        ast.Constant(value=get_default_value_from_type(py_type))
                    )
                # default_value = get_default_value_from_type(py_type) if parameter.required else None
                # default_value = parameter.schema['default'] if 'default' in parameter.schema else default_value
                # if default_value:
                #    args_defaults.append(default_value)
                args.append(
                    ast.arg(
                        arg=parameter.name,
                        annotation=ast.Name(id=py_type, ctx=ast.Load()),
                    )
                )

        query_params = [x.name for x in operation.parameters if x.kind == "query"]
        if query_params:
            request_call_keywords.append(
                ast.keyword(
                    arg="params",
                    value=ast.Dict(
                        keys=[ast.Constant(value=_param) for _param in query_params],
                        values=[
                            ast.Name(id=_param, ctx=ast.Load())
                            for _param in query_params
                        ],
                    ),
                )
            )

        request_call_func_def = ast.Attribute(
            value=ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()), attr="client", ctx=ast.Load()
            ),
            attr="build_request",
            ctx=ast.Load(),
        )
        path_params = re.findall(r"\{([^}]+)\}", pattern)
        url_arg = (
            ast.parse('f"' + pattern + '"')
            if len(path_params) > 0
            else ast.Constant(value=pattern)
        )

        request_call = ast.Assign(
            targets=[ast.Name(id="request", ctx=ast.Store())],
            value=ast.Call(
                func=request_call_func_def,
                args=[ast.Constant(value=operation.method), url_arg],
                keywords=request_call_keywords,
            ),
            lineno=1,
        )
        response_call = ast.Assign(
            targets=[ast.Name(id="response", ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr="_send_request",
                    ctx=ast.Load(),
                ),
                args=[ast.Name(id="request", ctx=ast.Load())],
                keywords=[],
            ),
            lineno=1,
        )
        response_type = []
        has_plain_text_response = False
        for response in operation.responses:
            for content in response.contents:
                if "json" in content.media_type:
                    response_type.append(text_snake_to_pascal_case(content.get_id()))
                elif "text/plain" in content.media_type:
                    has_plain_text_response = True
                    response_type.append("str")
        response_attr = ast.Attribute(
            value=ast.Name(id="response", ctx=ast.Load()),
            attr="json" if has_plain_text_response is False else "text",
            ctx=ast.Load(),
        )
        if has_plain_text_response:
            return_call = ast.Return(value=response_attr)
        else:
            return_call = ast.Return(
                value=ast.Call(func=response_attr, args=[], keywords=[])
            )

        return ast.FunctionDef(
            name=operation.operation_id,
            args=ast.arguments(
                args=args, defaults=args_defaults, posonlyargs=[], kwonlyargs=[]
            ),
            body=[request_call, response_call, return_call],
            decorator_list=[],
            returns=(
                ast.Name(id=" | ".join(response_type), ctx=ast.Load())
                if len(response_type) > 0
                else None
            ),
            lineno=1,
        )

    # import statements
    import_stmt = ast.Import(names=[ast.alias("httpx")])

    # json schemas to python classes
    schema_class_defs_ids = []
    schema_class_defs: List[ast.ClassDef] = []
    for path_item in spec.paths:
        for operation in path_item.operations:
            if operation.request_body is not None:
                for content in operation.request_body.contents:
                    if content.schema:
                        _class_defs = ast_generate_class_from_json_schema(
                            content.schema, content.get_id()
                        )
                        __class_defs = [
                            _class_def
                            for _class_def in _class_defs
                            if _class_def.name not in schema_class_defs_ids
                        ]
                        schema_class_defs.extend(__class_defs)
                        schema_class_defs_ids.extend([x.name for x in __class_defs])

            for response in operation.responses:
                for content in response.contents:
                    if content.schema:
                        _class_defs = ast_generate_class_from_json_schema(
                            content.schema, content.get_id()
                        )
                        __class_defs = [
                            _class_def
                            for _class_def in _class_defs
                            if _class_def.name not in schema_class_defs_ids
                        ]
                        schema_class_defs.extend(__class_defs)
                        schema_class_defs_ids.extend([x.name for x in __class_defs])

    # path operations as sdk class methods
    sdk_class_def = ast_generate_sdk_class()
    for path_item in spec.paths:
        for operation in path_item.operations:
            method_def = ast_generate_class_method(path_item.pattern, operation)
            sdk_class_def.body[0].body.append(method_def)

    # sdk assignment
    sdk_assign = ast.parse(f"{sdk_name} = {text_snake_to_pascal_case(sdk_name)}()")

    body = [import_stmt]
    body.extend(schema_class_defs)
    body.append(sdk_class_def)
    body.append(sdk_assign)
    root = ast.Module(body=body, type_ignores=[])
    code = ast.unparse(root)
    code_formatted = black.format_str(code, mode=black.FileMode())

    with open(os.path.join(dest, f"{sdk_name}.py"), "w") as f:
        f.write(code_formatted)

    return True, "sdk generated successfully."


def text_path_pattern_to_snake_case(text: str) -> str:
    if text.startswith("/"):
        text = text[1:]
    # return home if it's "/"
    if len(text) == 0:
        return "home"

    text = text.replace("/", "_")

    # Handle path parameters in curly braces {paramName}
    text = re.sub(r"\{([^}]+)\}", r"\1", text)

    # Handle path parameters with colon :paramName
    text = re.sub(r":([^/_]+)", r"\1", text)

    # Convert camelCase to snake_case
    # Insert underscore before uppercase letters that follow lowercase letters
    text = re.sub(r"([a-z])([A-Z])", r"\1_\2", text)

    text = text.lower()
    text = re.sub(r"_+", "_", text)
    text = text.rstrip("_")

    return text


def text_snake_to_pascal_case(text: str) -> str:
    if not text:
        return text
    components = [comp for comp in text.split("_") if comp]
    if not components:
        return text
    return "".join(word.capitalize() for word in components)
