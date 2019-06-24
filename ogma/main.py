#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Contains the minimal necessary set of routines to run Ogma.
"""

# ---------------------------------------------------------------------------
# Standard imports:
import sys
import argparse
import os
import importlib
import importlib.util

# Third party imports
try:
    import colored_traceback

    colored_traceback.add_hook(style="native")
except ImportError:
    pass

import colorama
import argcomplete


# Local imports
from . import modelutils
from . import utils
from . import commands
from . import version

# ---------------------------------------------------------------------------

colorama.init()

__description__ = "Ogma: A Database Access Code Generator for Java"

# An attempt to find a default output directory.
DEFAULT_OUTPUT_DIR = os.path.abspath(os.path.join(".", "output"))

# Default base package for generated code
DEFAULT_BASE_PACKAGE = "com.example.dbutils"


def completion_code(args):
    print(argcomplete.shellcode([args.program], args.shell))


def add_modelutils(model):
    if hasattr(modelutils, "__all__"):
        all_names = modelutils.__all__
    else:
        all_names = [name for name in dir(modelutils) if not name.startswith("_")]

    globs = vars(model)
    globs.update({name: getattr(modelutils, name) for name in all_names})


def load_module(file_path, name, decorator=None, delete_cache=False):
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    if decorator is not None:
        decorator(module)
    spec.loader.exec_module(module)
    if delete_cache:
        # Delete the cache for future invocations
        cache = getattr(module, "__cached__", None)
        if cache and os.path.exists(cache):
            os.remove(cache)
    return module


def load_dbmodel(file_path, allow_imports):
    """
    Load a give python file as the dbmodel module
    """

    utils.print_action("Loading database model")
    try:
        modelutils.validation.validate_model_file(file_path, allow_imports)
        utils.li(os.path.abspath(file_path))
        # Make sure the module is always loaded
        importlib.invalidate_caches()
        dbmodel = load_module(
            file_path, "dbmodel", decorator=add_modelutils, delete_cache=True
        )
        return dbmodel
    except modelutils.validation.DatabaseModelException as dbmex:
        utils.error(str(dbmex))
    except Exception as ex:
        utils.print_end_action(str(ex))
        raise
    else:
        utils.print_end_action()


def parse_args(argv):
    """
    Parse and validate command line arguments
    """

    parser = argparse.ArgumentParser(description=__description__)

    parser.add_argument(
        "--version", action="version", version="%(prog)s {}".format(version.VERSION)
    )
    subparsers = parser.add_subparsers(title="Subcommands", dest="command_name")

    # A parent parser for common database access parameters
    # ------------------------------------------------------------------------
    dbopts_parser = argparse.ArgumentParser(add_help=False)
    dbopts_group = dbopts_parser.add_argument_group(title="Database access parameters")
    dbopts_group.add_argument(
        "--db-user",
        "-u",
        required=True,
        help="The database user to connect to the database",
    )
    dbopts_group.add_argument(
        "--db-password",
        "-p",
        required=True,
        help="The database password to connect to the database",
    )
    dbopts_group.add_argument(
        "--db-host", "-H", default="localhost", help="The host holding the database"
    )
    dbopts_group.add_argument(
        "--db-name", help="The name of the database to create or read"
    )
    dbopts_group.add_argument(
        "--db-port", "-P", type=int, default=3306, help="The database port"
    )

    # A parent parser for subcommands that take a model file
    # ------------------------------------------------------------------------
    model_parser = argparse.ArgumentParser(add_help=False)
    # Hidden argument to override the schema from the model:
    model_parser.add_argument("--schema", help=argparse.SUPPRESS)
    model_parser.add_argument(
        "--allow-imports",
        action="store_true",
        help="Allow import statements in the model file",
    )
    model_parser.add_argument(
        "model_file", metavar="MODEL_FILE", help="The file with the DB model"
    )

    # Subcommand: generate
    # ------------------------------------------------------------------------
    gen_parser = subparsers.add_parser(
        "generate", parents=[dbopts_parser, model_parser], help="Generate database code"
    )

    outdir_parser = gen_parser.add_argument_group("Output directories")

    # Output directories
    outdir_parser.add_argument(
        "--code-dir",
        "-c",
        default=DEFAULT_OUTPUT_DIR,
        help="The directory under which generated code should be",
    )
    outdir_parser.add_argument(
        "--sql-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="The directory under which generated SQL should be",
    )
    outdir_parser.add_argument(
        "--config-dir",
        "-x",
        default=DEFAULT_OUTPUT_DIR,
        help="The directory under which generated config should be",
    )

    # Java / JOOQ specific
    gen_parser.add_argument(
        "--java", default=None, help="The path to the java binary that will run jOOQ"
    )
    gen_parser.add_argument(
        "--java-package",
        default=DEFAULT_BASE_PACKAGE,
        help="The base Java package of generated database code",
    )
    gen_parser.add_argument(
        "--classpath", help="The classpath, where to find jOOQ and the DB connector"
    )
    gen_parser.add_argument(
        "--no-jooq",
        default=False,
        action="store_true",
        help="Skip jooq code generation",
    )

    gen_parser.add_argument(
        "--keep-db",
        default=False,
        action="store_true",
        help="Do not delete the temporary database afterwards",
    )
    gen_parser.set_defaults(function=commands.generate)

    # Subcommand: enum-tables
    # ------------------------------------------------------------------------
    etab = subparsers.add_parser(
        "enum-tables",
        parents=[dbopts_parser, model_parser],
        help="Create tables with enum names",
    )
    etab.set_defaults(function=commands.enum_tables)
    etab.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show more information about what is happening",
    )

    # Subcommand: enum-usage
    # ------------------------------------------------------------------------
    eusg = subparsers.add_parser(
        "enum-usage", parents=[model_parser], help="Report enum usage"
    )
    eusg.set_defaults(function=commands.enum_usage)

    # Subcommand: get-db-name
    # ------------------------------------------------------------------------
    gdbn = subparsers.add_parser(
        "get-db-name", help="Get a unique database name (for temp db)"
    )
    gdbn.set_defaults(function=commands.get_db_name)

    # Subcommand: create-db
    # ------------------------------------------------------------------------
    cdb = subparsers.add_parser(
        "create-db",
        parents=[dbopts_parser, model_parser],
        help="Create the database from the model",
    )
    cdb.set_defaults(function=commands.create_db)

    # Subcommand: drop-db
    # ------------------------------------------------------------------------
    ddb = subparsers.add_parser(
        "drop-db", parents=[dbopts_parser], help="Drop a given database"
    )
    ddb.set_defaults(function=commands.drop_db)
    ddb.add_argument("database")

    # Subcommand: completion
    # ------------------------------------------------------------------------
    compl = subparsers.add_parser("completion", help="Provide shell completion code")
    compl.set_defaults(function=completion_code)
    compl.add_argument(
        "shell", choices=["bash", "fish", "tcsh"], help="Name of the shell"
    )

    # ------------------------------------------------------------------------
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv[1:])
    if not hasattr(args, "function"):
        parser.error("Subcommand is missing")

    # If DB access is required, build a DbSettings object with the connection
    # parameters.
    if hasattr(args, "db_host"):
        args.dbsettings = modelutils.DbSettings(
            host=args.db_host,
            name=(
                args.db_name
                if args.db_name is not None
                else modelutils.get_new_database_name()
            ),
            user=args.db_user,
            password=args.db_password,
            port=args.db_port,
        )

    # Booleans starting with "no" end here!
    if hasattr(args, "no_jooq"):
        args.do_jooq = not args.no_jooq
        del args.no_jooq

    # If a model file was provided, load it as a python module
    if hasattr(args, "model_file"):
        args.dbmodel = load_dbmodel(args.model_file, args.allow_imports)

        # Override the schema if the hidden --schema option was provided.
        # WARNING: This hides problems in invalid models
        if hasattr(args, "schema") and args.schema is not None:
            args.dbmodel.schema_name.value = args.schema

    # Load the classpath from the environment if one was not provided in the
    # command line
    if not hasattr(args, "classpath") and "CLASSPATH" in os.environ:
        args.classpath = os.environ["CLASSPATH"]

    args.program = parser.prog
    return args


def main(argv=None):
    """ Run this program """
    if argv is None:
        argv = sys.argv
    args = parse_args(argv)
    try:
        args.function(args)
    except KeyboardInterrupt:
        sys.exit(-1)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
