#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ---------------------------------------------------------------------------
# Standard imports:

# Third party imports

# Local imports
from .. import modelutils
from .. import utils
from . import common

# Command implementations
from .generate import generate
from .enumtables import enum_tables
from .enumusage import enum_usage

# ---------------------------------------------------------------------------

__all__ = ["generate", "enum_usage", "enum_tables", "get_db_name"]


def get_db_name(args):
    print(modelutils.get_new_database_name())


def drop_db(args):
    utils.print_action(f"Dropping database: {args.database}")
    error = None
    try:
        args.dbsettings.name = "mysql"
        engine = common.get_db_engine(args.dbsettings)
        engine.execute(f"DROP DATABASE {args.database}")
    except Exception as ex:
        error = str(ex)
    finally:
        utils.print_end_action(error=error)


def create_db(args):
    utils.print_action(f"Creating database: {args.dbsettings.name}")
    error = None
    try:
        args.dbmodel.metadata.save(args.dbsettings)
    except Exception as ex:
        error = str(ex)
    finally:
        utils.print_end_action(error=error)
