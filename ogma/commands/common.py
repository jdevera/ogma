#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ---------------------------------------------------------------------------
# Standard imports:
import collections
from enum import Enum

# Third party imports
import sqlalchemy

# Local imports
from .. import modelutils

# ---------------------------------------------------------------------------


def get_db_connection_string(dbsettings):
    db = dbsettings
    return f"mysql+pymysql://{db.user}:{db.password}@{db.host}:{db.port}/{db.name}"


def get_db_engine(dbsettings):
    return sqlalchemy.create_engine(get_db_connection_string(dbsettings))


class TypeFamilies(Enum):
    enum = 1
    boolean = 2
    binary = 3


def get_type_mappings(metadata, filter_types=None):
    """
    Return a double nested mapping of:
        table -> column -> type
    """
    if filter_types is None:
        filter_types = [TypeFamilies.enum, TypeFamilies.boolean]
    column_types = collections.defaultdict(dict)

    def visitor(column_name, column):
        # ENUMS
        if TypeFamilies.enum in filter_types and isinstance(
            column.type, modelutils.IntegerEnum
        ):
            column_types[column.table.name][column.name] = column.type.field_data.name
            return
        # BOOLEANS
        if TypeFamilies.boolean in filter_types and isinstance(
            column.type, modelutils.Boolean
        ):
            column_types[column.table.name][column.name] = "BOOLEAN"
            return
        # BINARIES
        if TypeFamilies.binary in filter_types and isinstance(
            column.type, modelutils.BINARY
        ):
            column_types[column.table.name][column.name] = "BINARY"

    metadata.visit_columns(visitor)

    def sort_by_keys(d):
        """
        Return an OrderedDict with the elements inserted according to the
        sorted keys.
        """
        return collections.OrderedDict(((k, d[k]) for k in sorted(d.keys())))

    # Sort by table name
    ordered_types = sort_by_keys(column_types)

    # And each table by column name
    for name in ordered_types:
        ordered_types[name] = sort_by_keys(column_types[name])

    return ordered_types
