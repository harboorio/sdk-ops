import ast
import re
from typing import Any
from sdkops.openapi import APISpec, APISpecPathOperation
from sdkops.json_schema import (
    case_snake_to_pascal,
    to_ast as schema_to_ast,
    schema_type_to_py_type,
    ast_create_annotation,
    schema_resolve_ref,
    find_default_value_from_types,
)


def to_ast(spec: APISpec, sdk_name: str, base_url: str | None):
    # import statements
    import_stmt = ast.Import(names=[ast.alias("httpx")])

    # json schemas to python classes
    schema_class_defs: list[ast.ClassDef] = []
    for path_item in spec.paths:
        for operation in path_item.operations:
            if operation.request_body is not None:
                for content in operation.request_body.contents:
                    if content.schema:
                        combined_schema = {
                            **content.schema,
                            **{"components": spec.schema_dict["components"]},
                        }
                        class_defs = schema_to_ast(
                            f"{sdk_name}_{content.get_id()}", combined_schema
                        )
                        if isinstance(class_defs, list):
                            schema_class_defs.extend(class_defs)
                        if isinstance(class_defs, ast.AnnAssign):
                            schema_class_defs.append(class_defs)

            for response in operation.responses:
                for content in response.contents:
                    if content.schema:
                        combined_schema = {
                            **content.schema,
                            **{"components": spec.schema_dict["components"]},
                        }
                        class_defs = schema_to_ast(
                            f"{sdk_name}_{content.get_id()}", combined_schema
                        )
                        if isinstance(class_defs, list):
                            schema_class_defs.extend(class_defs)
                        if isinstance(class_defs, ast.AnnAssign):
                            schema_class_defs.append(class_defs)

    # path operations as sdk class methods
    sdk_class_def = ast_generate_sdk_class(sdk_name=sdk_name, base_url=base_url)
    for path_item in spec.paths:
        for operation in path_item.operations:
            method_def = ast_generate_class_method(
                path_item.pattern, operation, sdk_name, spec
            )
            sdk_class_def.body[0].body.append(method_def)

    # sdk assignment
    sdk_assign = ast.parse(f"{sdk_name} = {case_snake_to_pascal(sdk_name)}()")

    body = [import_stmt]
    body.extend(schema_class_defs)
    body.append(sdk_class_def)
    body.append(sdk_assign)
    root = ast.Module(body=body, type_ignores=[])

    return root


def ast_generate_sdk_class(sdk_name: str, base_url: str):
    return ast.parse(
        source=f"""
class {case_snake_to_pascal(sdk_name)}:
    def __init__(self):
        self.client = httpx.Client(
            base_url="{base_url}",
            headers={{'user-agent': '{sdk_name}', 'accept': 'application/json'}},
            timeout=10,
    )

    def auth(self, scheme: str, value: str):
        self.client.headers['authorization'] = f"{{scheme}} {{value}}"

    def deauth(self):
        self.client.headers.pop('authorization', None)

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


def ast_generate_class_method(
    pattern: str, operation: APISpecPathOperation, sdk_name: str, spec: APISpec
):
    """
    Generates fully-typed function definitions to add to the generated sdk class.

    :param pattern: URL parh
    :param operation: APISpecPathOperation object
    :return: Ast node of a function definition
    """

    # function name is the snake cased operation_id
    function_name = operation.operation_id

    # function should return either combination of pascal cased content ids or str
    function_return_types: list[str] = []
    for response in operation.responses:
        for content in response.contents:
            if "json" in content.media_type:
                function_return_types.append(
                    case_snake_to_pascal(f"{sdk_name}_{content.get_id()}")
                )
            elif "text/plain" in content.media_type:
                function_return_types.append("str")
    does_function_return_str = True if "str" in function_return_types else False

    # collect fully-typed function arguments
    function_arguments = [ast.arg(arg="self", annotation=None)]
    function_arguments_defaults = []
    # json from request body
    if operation.request_body:
        for content in operation.request_body.contents:
            if "json" in content.media_type:
                py_type = case_snake_to_pascal(f"{sdk_name}_{content.get_id()}")
                function_arguments.append(
                    ast.arg(arg="json", annotation=ast.Name(id=py_type, ctx=ast.Load()))
                )
    # path and query parameters from parameters
    for parameter in operation.parameters:
        if parameter.kind == "path" or parameter.kind == "query":
            combined_schema = {
                **parameter.schema,
                **{"components": spec.schema_dict["components"]},
            }
            py_types = collect_py_types_from_schema(combined_schema)
            function_arguments.append(
                ast.arg(arg=parameter.name, annotation=ast_create_annotation(py_types))
            )
            # NOTE might have to use .insert depending on the existence of the default value
            if parameter.required:
                function_arguments_defaults.append(
                    ast.Constant(value=find_default_value_from_types(py_types))
                )
            if "default" in parameter.schema:
                function_arguments_defaults.append(
                    ast.Constant(value=parameter.schema["default"])
                )
    # headers argument for extra, endpoint specific headers
    function_arguments.append(
        ast.arg(arg="headers", annotation=ast_create_annotation(["dict[str, str]"]))
    )
    function_arguments_defaults.append(ast.Constant(value=None))

    # create function body
    function_body = []
    if does_function_return_str:
        # set accept header to plain text for text kind responses
        function_body.append(ast.parse("self.client.headers['accept'] = 'text/plain'"))
    # apply endpoint specific headers if specified
    function_body.append(
        ast.parse(
            "headers_combined = self.client.headers if headers is None else {**self.client.headers, **headers}"
        )
    )
    # build request call
    build_request_keywords = []
    if operation.request_body:
        for content in operation.request_body.contents:
            if "json" in content.media_type:
                build_request_keywords.append(
                    ast.keyword(arg="json", value=ast.Name(id="json", ctx=ast.Load()))
                )
    query_params = [x.name for x in operation.parameters if x.kind == "query"]
    if len(query_params) > 0:
        build_request_keywords.append(
            ast.keyword(
                arg="params",
                value=ast.Dict(
                    keys=[ast.Constant(value=_param) for _param in query_params],
                    values=[
                        ast.Name(id=_param, ctx=ast.Load()) for _param in query_params
                    ],
                ),
            )
        )
    build_request_keywords.append(
        ast.keyword(
            arg="headers", value=ast.Name(id="headers_combined", ctx=ast.Load())
        )
    )
    build_request_arguments = [
        # request method
        ast.Constant(value=operation.method),
        # either simply a url path or parameterized path pattern
        (
            ast.parse('f"' + pattern + '"')
            if len(re.findall(r"\{([^}]+)\}", pattern)) > 0
            else ast.Constant(value=pattern)
        ),
    ]
    build_request_call = ast.Attribute(
        value=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()), attr="client", ctx=ast.Load()
        ),
        attr="build_request",
        ctx=ast.Load(),
    )
    request_var = ast.Assign(
        targets=[ast.Name(id="request", ctx=ast.Store())],
        value=ast.Call(
            func=build_request_call,
            args=build_request_arguments,
            keywords=build_request_keywords,
        ),
        lineno=1,
    )
    function_body.append(request_var)
    # send request call
    response_var = ast.Assign(
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
    function_body.append(response_var)
    if does_function_return_str:
        function_return_statement = ast.Return(
            value=ast.Attribute(
                value=ast.Name(id="response", ctx=ast.Load()),
                attr="text",
                ctx=ast.Load(),
            )
        )
    else:
        function_return_statement = ast.Return(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="response", ctx=ast.Load()),
                    attr="json",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            )
        )
    function_body.append(function_return_statement)

    return ast.FunctionDef(
        name=function_name,
        args=ast.arguments(
            args=function_arguments,
            defaults=function_arguments_defaults,
            posonlyargs=[],
            kwonlyargs=[],
        ),
        body=function_body,
        decorator_list=[],
        returns=ast_create_annotation(function_return_types),
        lineno=1,
    )


def collect_py_types_from_schema(schema: dict[str, Any]):
    result: list[str] = []

    if "$ref" in schema:
        schema, _trace = schema_resolve_ref(schema, schema["$ref"])
        if schema is None:
            raise ValueError(f"failed to resolve ref. {_trace}")

    if "type" not in schema:
        return result

    t = schema["type"]

    if "anyOf" in schema:
        for child_schema in schema["anyOf"]:
            result.extend(collect_py_types_from_schema(child_schema))
    elif t in ["string", "integer", "boolean", "null"]:
        return result.append(schema_type_to_py_type(t))
    elif t == "array" and "items" in schema:
        result.append(f"list[{collect_py_types_from_schema(schema["items"])}]")
    elif t == "object":
        result.append("dict")
    else:
        raise Exception("invalid schema.")

    return result
