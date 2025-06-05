#!/usr/bin/env python3

import httpx
import click
import rich
import rich.tree
import tempfile
import os
import sys
import json
import ast
import black
from sdkops.openapi import parse
from sdkops.generator import to_ast


@click.command("generate", short_help="generates a python sdk from openapi schema.")
@click.argument("file", nargs=1)
@click.option("-n", "--name", required=True, help="sdk package name.")
@click.option("-d", "--dest", required=True, help="directory to save the sdk package.")
@click.option(
    "-u",
    "--url",
    required=False,
    help="base url for the sdk endpoints. chosen from servers section of the schema by default.",
)
def generate(file: str, name: str, dest: str, url: str = None):
    """
    FILE is an open api schema file path or a url endpoint to fetch the schema.
    """
    click.echo("verifying sdk package name...")
    if not all(char in set("abcdefghijklmnopqrstuvwxyz0123456789_") for char in name):
        raise Exception(
            f"the name should be in snake case format. allowed characters are a-z_"
        )
    click.echo("verifying sdk package name... done.")

    click.echo("verifying destination directory...")
    if not os.path.isdir(dest):
        raise Exception(f"directory {dest} does not exist.")
    click.echo("verifying destination directory... done.")

    click.echo("verifying openapi schema file...")
    if not file.startswith("http") and not os.path.isfile(file):
        raise Exception(f"file {file} does not exist.")
    temp_file = None
    if file.startswith("http"):
        click.echo("    preparing to fetch it from an http endpoint.")
        r = httpx.get(file)
        if r.status_code < 200 or r.status_code >= 300:
            raise Exception(
                f'couldn\'t fetch the schema from "{file}". http request failed with status code {r.status_code}.'
            )
        try:
            json.loads(r.text)
        except:
            raise Exception(f'the schema fetched from "{file}" is not a json.')
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, delete_on_close=False
        ) as fp:
            fp.write(r.text)
            temp_file = fp.name
            file = fp.name
            click.echo(f'    the schema has been fetched and saved into "{file}".')
    schema_dict = None
    with open(file) as f:
        data = f.read()
        schema_dict = json.loads(data)
    click.echo("verifying openapi schema file... done.")

    click.echo("parsing schema...")
    success, spec = parse(schema_dict)
    if not success:
        click.echo(f"parsing schema... failed. {spec}")
        sys.exit(1)
    click.echo("parsing schema... done.")

    tree = rich.tree.Tree("spec")
    for _path in spec.paths:
        _path_tree = tree.add(_path.pattern)
        for _op in _path.operations:
            _op_tree = _path_tree.add(_op.operation_id)
            _request_tree = _op_tree.add("request")
            if _op.request_body:
                _request_tree.add("body").add(_op.request_body.contents[0].get_id())
            if _op.parameters:
                _params_tree = _request_tree.add("parameters")
                for _param in _op.parameters:
                    _params_tree.add(f"{_param.name}: {_param.kind}")
            _resp_tree = _op_tree.add("responses")
            for _resp in _op.responses:
                _resp_tree.add(
                    f"{_resp.status_code}: {', '.join([x.get_id() for x in _resp.contents])}"
                )
    rich.print(tree)

    click.echo("finding out the base url...")
    success, message, verified_base_url = spec.find_base_url(
        base_url=url, servers=spec.servers
    )
    if not success:
        click.echo(f"finding out the base url... failed. {message}")
        sys.exit(1)
    click.echo("finding out the base url... done.")

    click.echo("generating ast...")
    root = to_ast(spec, name, base_url=verified_base_url)
    click.echo("generating ast... done.")

    click.echo("saving ast output...")
    code = ast.unparse(root)
    code_formatted = black.format_str(code, mode=black.FileMode())
    with open(os.path.join(dest, f"{name}.py"), "w") as f:
        f.write(code_formatted)
    click.echo("saving ast output... done.")

    click.echo("cleaning up...")
    if temp_file is not None:
        os.remove(temp_file)
    click.echo("cleaning up... done.")


if __name__ == "__main__":
    generate()
