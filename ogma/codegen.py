#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ---------------------------------------------------------------------------
# Standard imports:
import os
from datetime import datetime, timezone

# Third party imports
from functools import lru_cache

import pystache

# Local imports
from . import utils
from . import version


# ---------------------------------------------------------------------------


def get_abs_path(relpath):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), relpath))


class NumericEnumTemplateData:
    """
    Hold all necessary data to render all Enum related templates
    """

    CONVERTER_SUFFIX = "TypeConverter"

    def __init__(self, name):
        self.name = name
        self._num = 0
        self._values = []
        self._package = None
        self._conv_package = None
        self._datetime_cache = None

    def compiler_version(self):
        return version.VERSION

    @lru_cache()
    def datetime(self):
        return datetime.now(timezone.utc).isoformat()

    def code_file_name(self):
        return f"{self.name}.java"

    def converter_class_name(self):
        return f"{self.name}{self.CONVERTER_SUFFIX}"

    def converter_file_name(self):
        return f"{self.name}{self.CONVERTER_SUFFIX}.java"

    def enum_fqn(self):
        return f"{self._package}.{self.name}"

    def converter_fqn(self):
        return f"{self._conv_package}.{self.name}{self.CONVERTER_SUFFIX}"

    def _add_value(self, name):
        """
        Add a value by its name and assign an increasing numeric value to it
        """
        self._values.append(dict(valname=name, valnum=self._num))
        self._num += 1
        return self

    def with_values(self, names):
        for name in names:
            self._add_value(name)
        return self

    def with_enum_package(self, package):
        self._package = package
        return self

    def with_enum_converter_package(self, package):
        self._conv_package = package
        return self

    def values(self):
        """
        Return all values as dictionaries of name and numeric value. Mark the last one
        with the 'last' key to help template rendering
        """
        return self._values[:-1] + [dict(self._values[-1], last=True)]

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name})"


class EnumCodeGenerator:
    """
    Code generation logic for Enums and Enum converters
    """

    ENUM_CODE_TEMPLATE = "java_enum"
    ENUM_CONV_CODE_TEMPLATE = "java_enum_converter"
    JOOQ_GEN_CONFIG_TEMPLATE = "jooq_generator_config"
    TEMPLATE_DIR = get_abs_path("./templates")

    def __init__(
        self, enums, code_dir, config_dir, enum_package, converter_package, model_file
    ):
        self.renderer = pystache.Renderer(search_dirs=self.TEMPLATE_DIR)
        self.code_dir = os.path.abspath(code_dir)
        self.config_dir = os.path.abspath(config_dir)
        self.enum_package = enum_package
        self.enum_converter_package = converter_package
        self.database_model_file_name = model_file

        self.enums = self._adjust_enums_from_model(enums)
        self.enums_by_name = {enum.name: enum for enum in self.enums}

    def _adjust_enums_from_model(self, enums):
        """
        Decorate the bare enum definitions from the model with additional attributes
        necessary for code generation
        """
        return [
            NumericEnumTemplateData(enum.name)
            .with_values(enum._values)
            .with_enum_package(self.enum_package)
            .with_enum_converter_package(self.enum_converter_package)
            for enum in enums.values()
        ]

    def _prepare_package_dir(self, package):
        elements = [self.code_dir] + package.split(".")
        directory = os.path.join(*elements)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        return directory

    def _new_java_file(self, package, file_name):
        directory = self._prepare_package_dir(package)
        if not file_name.endswith(".java"):
            file_name += ".java"
        path = os.path.join(directory, file_name)
        return open(path, "w")

    def _new_config_file(self, name):
        if not os.path.isdir(self.config_dir):
            os.makedirs(self.config_dir)
        path = os.path.join(self.config_dir, name)
        return open(path, "w")

    def _render_enum_code(self, enum, package, file_name, template):
        data = {
            "package": package,
            "database_model_file": self.database_model_file_name.replace("\\", "/"),
            "file_name": file_name,
        }
        with self._new_java_file(package, file_name) as jout:
            path = jout.name
            jout.write(self.renderer.render_name(template, enum, data))

        return path

    def render_enum(self, enum):
        return self._render_enum_code(
            enum=enum,
            package=self.enum_package,
            file_name=enum.code_file_name(),
            template=self.ENUM_CODE_TEMPLATE,
        )

    def render_enum_converter(self, enum):
        return self._render_enum_code(
            enum=enum,
            package=self.enum_converter_package,
            file_name=enum.converter_file_name(),
            template=self.ENUM_CONV_CODE_TEMPLATE,
        )

    def render_jooq_gen_config(self, template_data):
        return self.renderer.render_name(self.JOOQ_GEN_CONFIG_TEMPLATE, template_data)

    def _jooq_forced_type_data(self, table, field, type_name):
        return {"expression": f"{table}\\.{field}", "name": type_name}

    def generate_enum_java_code(self):
        utils.print_section_header("Java Enums And Converters")
        for enum in self.enums:
            utils.print_action(f"Generating files for enum: {enum.name}")
            utils.print_generated_file(self.render_enum(enum))
            utils.print_generated_file(self.render_enum_converter(enum))
            utils.print_end_action()

    def generate_jooq_config(self, type_mappings, dbsettings, schema_name, package):
        field_data = []
        for table, columns in type_mappings.items():
            for column, type_name in columns.items():
                type_fqn = type_name
                # If the type is an Enum, fully qualify the name
                enum = self.enums_by_name.get(type_name, None)
                if enum is not None:
                    type_fqn = enum.enum_fqn()
                field_data.append(self._jooq_forced_type_data(table, column, type_fqn))

        template_data = {
            "dbhost": dbsettings.host,
            "dbname": dbsettings.name,
            "dbuser": dbsettings.user,
            "dbpassword": dbsettings.password,
            "dbport": dbsettings.port,
            "schema_name": schema_name,
            "codedir": self.code_dir,
            "fields": field_data,
            "enums": self.enums,
            "package": package,
        }

        utils.print_section_header("jOOQ")
        utils.print_action("Generating jOOQ generator configuration file")
        config_file_name = "ogma_jooq_gen_config.{}.xml".format(schema_name.lower())
        with self._new_config_file(config_file_name) as xout:
            xout.write(self.render_jooq_gen_config(template_data))

        utils.print_generated_file(xout.name)
        utils.print_end_action()

        return xout.name
