# sdk-ops

Generates fully typed python SDK modules by reading OpenAPI schemas.
- Basic component and $ref resolving in the schema.
- Request body, url query and path parameters are supported.
- Response types.
- Uses Python's native ast module.
- Fully typed output.

**This project is not feature complete and is not available on pypi yet, use with caution.**

Areas that needs improvement and fixes:
- Better error handling.
- Limited JSONSchema support. No support for complicated types such as allOf, anyOf, arrays etc.
- Basic schema $ref resolution.
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

  file is an open api schema file path or a url endpoint to fetch the schema.

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
cli flags `-n stela -u http://localhost:8000` the generated SDK would be:
```python
import httpx


class OtpEmailRequestBody:
    email: str


class OtpEmailResponse200:
    success: bool


class OtpEmailResponse422Error:
    code: str


class OtpEmailResponse422:
    error: OtpEmailResponse422Error


class OtpEmailVerifyRequestBody:
    email: str
    otp: str


class OtpEmailVerifyResponse200:
    token: str


class OtpEmailVerifyResponse422Error:
    code: str


class OtpEmailVerifyResponse422:
    error: OtpEmailVerifyResponse422Error


class Stela:
    client = httpx.Client(
        base_url="http://localhost:8000",
        headers={"user-agent": "stela", "accept": "application/json"},
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
            message = f"An unexpected error occurred while handling request to {e.request.url}. {e}"
            return httpx.Response(
                status_code=500,
                json={"error": {"code": "unexpected", "message": message}},
            )

    def otp_email(
        self, json: OtpEmailRequestBody
    ) -> OtpEmailResponse200 | OtpEmailResponse422:
        request = self.client.build_request("post", "/otp/email", json=json)
        response = self._send_request(request)
        return response.json()

    def otp_email_verify(
        self, json: OtpEmailVerifyRequestBody
    ) -> OtpEmailVerifyResponse200 | OtpEmailVerifyResponse422:
        request = self.client.build_request("post", "/otp/email/verify", json=json)
        response = self._send_request(request)
        return response.json()

    def home(self) -> str:
        request = self.client.build_request("get", "/")
        response = self._send_request(request)
        return response.text


stela = Stela()
```

## Algorithm

**Parse OpenAPI schema:** It parses the given schema into it's corresponding python classes.
A single `APISpec` object will be holding all the schema data at the end of parsing.

**Models into ast:** A spec model is sent to the ast generator function to generate an ast model of the sdk.
All request and response definition classes, sdk methods are all structured at this phase.

**Naming:**
- SDK methods names are primarily based on operationId field in the schema. If operationId doesn't exist then a combination of path and method names are used.
- Request and response class names are based on operationId field too but they are pascal cased.
- The name of the main SDK class is determined by the `-n, --name` flag passed. It is transformed to pascal case too.

## License

`sdk-ops` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Support

Any amount of support on [patreon](https://patreon.com/muratgozel?utm_medium=organic&utm_source=github_repo&utm_campaign=github&utm_content=join_link) or [github](https://github.com/sponsors/muratgozel) is much appreciated, and they will return you back as bug fixes, new features and bits and bytes.
