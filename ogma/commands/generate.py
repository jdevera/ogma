#!/usr/bin/env python
# encoding: utf-8
"""
Handling of the generate subcommand
"""
# ---------------------------------------------------------------------------
# Standard imports:
import os
import subprocess
import shutil

# Local imports
from .. import codegen
from .. import modelutils
from .. import utils
from . import common


# ---------------------------------------------------------------------------

ENUM_PACKAGE_TPL = "{base}.{schema}.enums"
ENUM_CONVERTER_PACKAGE_TPL = ENUM_PACKAGE_TPL + ".converters"
DB_QUERY_PACKAGE_TPL = "{base}.{schema}.db"


def _generate_db_schema_ddl(metadata, schema, output_dir):
    utils.print_section_header("Database Creation DDL")
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    engines = ("mysql",)
    for engine in engines:
        file_name = f"full_ddl.{schema.lower()}.{engine}.sql"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "w") as fsqlout:
            fsqlout.write(metadata.ddl(engine))
        utils.print_action(f"Generating database schema for {engine}")
        utils.print_generated_file(file_name)
        utils.print_end_action()


def _find_java():
    """
    Provide the java executable path, searching first in JAVA_HOME, then in the
    PATH
    """
    java_home = os.environ.get("JAVA_HOME", None)
    if java_home is not None:
        java_path = os.path.join(java_home, "bin", "java")
        if os.path.isfile(java_path) and os.access(java_path, os.X_OK):
            return java_path
    java_path = shutil.which("java")
    return java_path


def _run_jooq(java, config_file, classpath=None):
    """
    Run the jOOQ generator with the give configuration file and classpath
    """
    if java is None:
        # No java path was explicitly provided, so search
        java = _find_java()
    command = [java]
    if classpath is not None:
        command.append("-classpath")
        command.append(classpath)
    command.append("org.jooq.util.GenerationTool")
    command.append(config_file)
    print(" ".join(command))
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as cpe:
        return cpe


def generate(args):
    modelutils.validate_model(args.dbmodel)

    schema_name = args.dbmodel.schema_name()
    package_schema_name = schema_name.lower()

    # Add schema to packages
    enum_package = ENUM_PACKAGE_TPL.format(
        base=args.java_package, schema=package_schema_name
    )
    enum_conv_package = ENUM_CONVERTER_PACKAGE_TPL.format(
        base=args.java_package, schema=package_schema_name
    )
    db_query_package = DB_QUERY_PACKAGE_TPL.format(
        base=args.java_package, schema=package_schema_name
    )

    code_generator = codegen.EnumCodeGenerator(
        enums=args.dbmodel.enums,
        code_dir=args.code_dir,
        config_dir=args.config_dir,
        enum_package=enum_package,
        converter_package=enum_conv_package,
        model_file=args.model_file,
    )

    # Generate Java enums and Converters for jOOQ
    code_generator.generate_enum_java_code()

    # Generate DB scripts for all used engines
    _generate_db_schema_ddl(args.dbmodel.metadata, package_schema_name, args.sql_dir)

    # Find the columns that use enum, boolean, etc. types to create a jOOQ mapping for them
    type_mappings = common.get_type_mappings(args.dbmodel.metadata)

    # Generate the XML config for the jOOQ code generator
    jooq_config_file = code_generator.generate_jooq_config(
        type_mappings, args.dbsettings, schema_name, db_query_package
    )

    if args.do_jooq:
        # Create a temporary database, run the jOOQ generator on it, then remove it
        with args.dbmodel.metadata.db_instance(args.dbsettings, not args.keep_db):
            utils.print_action(
                f"Running jOOQ generator on temporary database {args.dbsettings.name}"
            )

            error = _run_jooq(args.java, jooq_config_file, args.classpath)
            utils.print_end_action(error)
            if error is not None:
                raise error
