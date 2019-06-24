#!/usr/bin/env python3
# encoding: utf-8

from ogma.utils import error
import re
from textwrap import dedent


def _validate_schema_exists(model):
    name = model.schema_name()
    if name is None:
        error(
            dedent(
                f"""\
            Schema name is required in DB model files but could not be found in:
                {model.__file__}
            Specify a schema with:
                Schema("name")"""
            )
        )


def _validate_schema_name(model):
    name = model.schema_name()
    invalid_chars = r"""-^<>/'"{}[\]~`"""
    valid_name = re.compile(fr"""^[^{invalid_chars}]+$""")
    chars = "." + invalid_chars
    if not valid_name.match(name) or "." in name:
        error(
            dedent(
                f"""\
            Invalid schema name:
                {name}
            was found in file:
                {model.__file__}
            A valid schema name cannot contain any of: {chars}"""
            )
        )


def validate_model(model):
    for validator in (_validate_schema_exists, _validate_schema_name):
        validator(model)


class DatabaseModelException(Exception):
    pass


def _get_line(model_content: str, lineno: int):
    assert lineno > 0
    lines = model_content.splitlines(keepends=False)
    return lines[lineno - 1]


def validate_model_file(model_file, allow_imports):
    """
    Take a model file, parse and look for instances of imports.
    :param model_file: The path for the model file
    :param allow_imports: Whether imports are allowed or not
    :raise DatabaseModelException if the model file contains imports and they are not
           allowed
    """
    if not allow_imports:
        import ast

        with open(model_file, "r") as fin:
            code = fin.read()
        tree = ast.parse(code, model_file)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                raise DatabaseModelException(
                    f"Invalid model: import statement found on line {node.lineno}:"
                    f"\n{_get_line(code, node.lineno)}"
                )
