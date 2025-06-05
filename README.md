# sdk-ops

Generates fully typed python SDK modules by reading OpenAPI schemas.
- Basic component and $ref resolving in the schema.
- Request body, url query and path parameters are supported.
- Response types.
- Uses Python's native ast module.
- Fully typed output.

**This project is not feature complete and is not available on pypi yet, use it with caution.**

Areas that needs improvement and fixes:
- Better error handling.
- OpenAPI and JSONSchema specs aren't fully supported.
- SDK class should accept headers and configuration from the user.
- JSON and plain text are the only supported kind of responses.

-----

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Example](#example)
- [Algorithm](#algorithm)
- [License](#license)
- [Support](#support)

## Installation

```sh
pip install -e "sdkops @ git+https://github.com/harboorio/sdk-ops.git"
```

## Usage

The help command output:
```sh
$ sdkops --help

Usage: sdkops [OPTIONS] FILE

  FILE is an open api schema file path or a url endpoint to fetch the schema.

Options:
  -n, --name TEXT  sdk package name.  [required]
  -d, --dest TEXT  directory to save the sdk package.  [required]
  --help           Show this message and exit.

```

An example with local schema path:
```sh
sdkops -n my_sdk -d ../sdk-out ./path/to/schema
```

Another example with url schema path:
```sh
sdkops -n my_sdk -d ../sdk-out http://localhost:8000/openapi.json
```

## Example

Given [this open api schema](./tests/schema_sample1.json), and
cli flags `-n stela_sdk -u http://localhost:8000` the generated SDK would be:
```python
import httpx


class StelaSdkOtpEmailRequestBody(dict):

    def __init__(self, email: str):
        super().__init__(email=email)
        self.email: str = email


class StelaSdkOtpEmailResponse200(dict):

    def __init__(self, success: bool):
        super().__init__(success=success)
        self.success: bool = success


class StelaSdkOtpEmailResponse422Error(dict):

    def __init__(self, code: str):
        super().__init__(code=code)
        self.code: str = code


class StelaSdkOtpEmailResponse422(dict):

    def __init__(self, error: StelaSdkOtpEmailResponse422Error):
        super().__init__(error=error)
        self.error: StelaSdkOtpEmailResponse422Error = error


class StelaSdkOtpEmailVerifyRequestBody(dict):

    def __init__(self, otp: str, email: str):
        super().__init__(email=email, otp=otp)
        self.email: str = email
        self.otp: str = otp


class StelaSdkOtpEmailVerifyResponse200(dict):

    def __init__(self, token: str):
        super().__init__(token=token)
        self.token: str = token


class StelaSdkOtpEmailVerifyResponse422Error(dict):

    def __init__(self, code: str):
        super().__init__(code=code)
        self.code: str = code


class StelaSdkOtpEmailVerifyResponse422(dict):

    def __init__(self, error: StelaSdkOtpEmailVerifyResponse422Error):
        super().__init__(error=error)
        self.error: StelaSdkOtpEmailVerifyResponse422Error = error


class StelaSdkUserStatusResponse200(dict):

    def __init__(self, email: str, authenticated: bool):
        super().__init__(authenticated=authenticated, email=email)
        self.authenticated: bool = authenticated
        self.email: str = email


class StelaSdkProjectListResponse200Projects(dict):

    def __init__(
        self,
        removed_at: str,
        updated_at: str,
        git_repo_url: str,
        name: str,
        rid: str,
        created_at: str = "",
    ):
        super().__init__(
            rid=rid,
            name=name,
            git_repo_url=git_repo_url,
            created_at=created_at,
            updated_at=updated_at,
            removed_at=removed_at,
        )
        self.rid: str = rid
        self.name: str = name
        self.git_repo_url: str = git_repo_url
        self.created_at: str = created_at
        self.updated_at: str = updated_at
        self.removed_at: str = removed_at


class StelaSdkProjectListResponse200(dict):

    def __init__(self, projects: list[StelaSdkProjectListResponse200Projects]):
        super().__init__(projects=projects)
        self.projects: list[StelaSdkProjectListResponse200Projects] = projects


class StelaSdkProjectListResponse422Error(dict):

    def __init__(self, code: str):
        super().__init__(code=code)
        self.code: str = code


class StelaSdkProjectListResponse422(dict):

    def __init__(self, error: StelaSdkProjectListResponse422Error):
        super().__init__(error=error)
        self.error: StelaSdkProjectListResponse422Error = error


class StelaSdkProjectGetResponse200(dict):

    def __init__(self, project: None):
        super().__init__(project=project)
        self.project: None = project


class StelaSdkProjectGetResponse422Error(dict):

    def __init__(self, code: str):
        super().__init__(code=code)
        self.code: str = code


class StelaSdkProjectGetResponse422(dict):

    def __init__(self, error: StelaSdkProjectGetResponse422Error):
        super().__init__(error=error)
        self.error: StelaSdkProjectGetResponse422Error = error


stela_sdk_home_response_200: str


class StelaSdk:

    def __init__(self):
        self.client = httpx.Client(
            base_url="http://localhost:8000",
            headers={"user-agent": "stela_sdk", "accept": "application/json"},
            timeout=10,
        )

    def auth(self, scheme: str, value: str):
        self.client.headers["authorization"] = f"{scheme} {value}"

    def deauth(self):
        self.client.headers.pop("authorization", None)

    def _cleanup(self):
        if not self.client.is_closed:
            self.client.close()

    def _send_request(self, request: httpx.Request) -> httpx.Response:
        try:
            response = self.client.send(request)
            return response
        except httpx.HTTPError as e:
            message = f"An unexpected error occurred while handling request to {e.request.url}. {e}"
            return httpx.Response(
                status_code=500,
                json={"error": {"code": "unexpected", "message": message}},
            )

    def otp_email(
        self, json: StelaSdkOtpEmailRequestBody, headers: dict[str, str] = None
    ) -> StelaSdkOtpEmailResponse200 | StelaSdkOtpEmailResponse422:
        headers_combined = (
            self.client.headers
            if headers is None
            else {**self.client.headers, **headers}
        )
        request = self.client.build_request(
            "post", "/otp/email", json=json, headers=headers_combined
        )
        response = self._send_request(request)
        return response.json()

    def otp_email_verify(
        self, json: StelaSdkOtpEmailVerifyRequestBody, headers: dict[str, str] = None
    ) -> StelaSdkOtpEmailVerifyResponse200 | StelaSdkOtpEmailVerifyResponse422:
        headers_combined = (
            self.client.headers
            if headers is None
            else {**self.client.headers, **headers}
        )
        request = self.client.build_request(
            "post", "/otp/email/verify", json=json, headers=headers_combined
        )
        response = self._send_request(request)
        return response.json()

    def user_status(
        self, headers: dict[str, str] = None
    ) -> StelaSdkUserStatusResponse200:
        headers_combined = (
            self.client.headers
            if headers is None
            else {**self.client.headers, **headers}
        )
        request = self.client.build_request(
            "get", "/user/status", headers=headers_combined
        )
        response = self._send_request(request)
        return response.json()

    def project_list(
        self, cwd_hash, headers: dict[str, str] = None
    ) -> StelaSdkProjectListResponse200 | StelaSdkProjectListResponse422:
        headers_combined = (
            self.client.headers
            if headers is None
            else {**self.client.headers, **headers}
        )
        request = self.client.build_request(
            "get",
            "/project/list",
            params={"cwd_hash": cwd_hash},
            headers=headers_combined,
        )
        response = self._send_request(request)
        return response.json()

    def project_get(
        self, name=None, headers: dict[str, str] = None
    ) -> StelaSdkProjectGetResponse200 | StelaSdkProjectGetResponse422:
        headers_combined = (
            self.client.headers
            if headers is None
            else {**self.client.headers, **headers}
        )
        request = self.client.build_request(
            "get", f"/project/{name}", headers=headers_combined
        )
        response = self._send_request(request)
        return response.json()

    def home(self, headers: dict[str, str] = None) -> str:
        self.client.headers["accept"] = "text/plain"
        headers_combined = (
            self.client.headers
            if headers is None
            else {**self.client.headers, **headers}
        )
        request = self.client.build_request("get", "/", headers=headers_combined)
        response = self._send_request(request)
        return response.text


stela_sdk = StelaSdk()
```

## Algorithm

**Parse OpenAPI schema:** It parses the given schema into it's corresponding python classes.
A single `APISpec` object will be holding all the schema data at the end of parsing.

**Models into ast:** A spec model is sent to the ast generator function to generate an ast model of the sdk.
All request and response definition classes, sdk methods are all structured at this phase.

**Naming:**
- SDK methods names are primarily based on operationId field in the schema. If operationId doesn't exist then a combination of path and method names are used.
- Request and response class names are based on operationId field too, but they are pascal cased.
- The name of the main SDK class is determined by the `-n, --name` flag passed. It is transformed to pascal case too.

## License

`sdk-ops` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Support

Any amount of support on [patreon](https://patreon.com/muratgozel?utm_medium=organic&utm_source=github_repo&utm_campaign=github&utm_content=join_link) or [github](https://github.com/sponsors/muratgozel) is much appreciated, and they will return you back as bug fixes, new features and bits and bytes.
