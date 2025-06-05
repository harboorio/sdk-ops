import os
import re
from typing import Any, Union
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
        self.contents: list[APISpecPathOperationContent] = []


class APISpecPathOperationResponse:
    def __init__(self):
        self.status_code: int = 200
        self.description: str = ""
        self.contents: list[APISpecPathOperationContent] = []


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
        self.parameters: list[APISpecPathOperationParameter] = []
        self.request_body: APISpecPathOperationRequestBody | None = None
        self.responses: list[APISpecPathOperationResponse] = []


class APISpecPathItem:
    def __init__(self):
        self.pattern: str = ""
        self.operations: list[APISpecPathOperation] = []


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
        self.paths: list[APISpecPathItem] = []
        self.components: list[APISpecComponentSchema] = []
        self.servers: list[APISpecServer] = []
        self.schema_dict: dict[str, Any] = {}

    def update_info(self, data: Union[APISpecApplicationInfo, dict[str, Any]]):
        data_dict = asdict(data) if isinstance(data, APISpecApplicationInfo) else data
        for k, v in data_dict.items():
            if hasattr(APISpecApplicationInfo, k):
                setattr(self.info, k, v)

        return True

    def find_base_url(self, base_url: str | None, servers: list[APISpecServer] = ()):
        if base_url is not None:
            return True, "", base_url

        if len(servers) == 1:
            return True, "", servers[0].url

        if (len(servers)) > 1:
            localhost_url = next(
                (x.url for x in servers if "localhost" in x.url or "192" in x.url),
                None,
            )
            is_local = bool(os.environ.get("DEBUG")) or (
                "dev" in os.environ.get("PYTHON_ENV")
            )
            if localhost_url and is_local:
                return True, "", localhost_url

        return (
            False,
            "couldn't find base url. specify the -u, --url option, please.",
            None,
        )


def parse(schema_dict: dict[str, Any]):
    spec = APISpec()
    spec.schema_dict = schema_dict

    if "openapi" in schema_dict:
        spec.version_openapi = schema_dict["openapi"]

    if "info" in schema_dict:
        spec.update_info(schema_dict["info"])

    if "servers" in schema_dict:
        for server in schema_dict["servers"]:
            spec.servers.append(APISpecServer(server["url"], server["description"]))

    if "paths" in schema_dict:
        for pattern, operations_dict in schema_dict["paths"].items():
            path_item = APISpecPathItem()
            path_item.pattern = pattern
            for method, operation_dict in operations_dict.items():
                path_op = APISpecPathOperation()
                path_op.method = method

                if "operationId" in operation_dict:
                    path_op.operation_id = operation_dict["operationId"]
                else:
                    path_op.operation_id = f"{path_pattern_to_snake_case(path_item.pattern)}_{path_op.method}"

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


def parse_content(
    contents_dict: dict[str, Any], op_id: str
) -> list[APISpecPathOperationContent]:
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
                # content.set_id(op_id)  # could be content_id too
                # schema_resolved = spec.find_component_schema(schema_resolved["$ref"])
            else:
                content.set_id(op_id)

            content.set_id(op_id)
            content.schema = content_dict["schema"]

        result.append(content)
    return result


def path_pattern_to_snake_case(text: str) -> str:
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
