#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handling of the enum-tables subcommand
"""
# ---------------------------------------------------------------------------
# Standard imports:
import collections
import re
from functools import lru_cache

# Third party imports
from sqlalchemy import MetaData, Table, Column, Integer, String

# Local imports
from .. import utils
from . import common

# ---------------------------------------------------------------------------

EnumTable = collections.namedtuple("EnumTable", "enum table values")
View = collections.namedtuple("View", "name table selects joins")


def _make_view(from_table):
    view_name = f"enumed_{from_table}_view"
    return View(view_name, from_table, [], [])


@lru_cache(maxsize=100)
def _camel_to_snake(name):
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


@lru_cache(maxsize=100)
def _table_name_from_enum(enum_name):
    return f"enum_{_camel_to_snake(enum_name)}"


def _create_enum_tables(engine, enums):
    metadata = MetaData()
    enum_tables = []
    for enum in enums:
        table_name = _table_name_from_enum(enum.name)
        table = Table(
            table_name,
            metadata,
            Column("value", Integer, nullable=False, unique=True),
            Column("name", String(50), nullable=False, unique=True),
        )
        values = [
            dict(value=value, name=name) for value, name in enumerate(enum._values)
        ]
        enum_tables.append(EnumTable(enum, table, values))

    utils.print_action("Generating tables for enums")
    metadata.drop_all(engine)
    metadata.create_all(engine)

    for enum_table in enum_tables:
        utils.li(f"Enum: {enum_table.enum.name} --> Table: {enum_table.table.name}")
    utils.print_end_action()

    return enum_tables


def _populate_enum_tables(engine, enum_tables, verbose=False):
    utils.print_action("Populating enum tables with values")
    with engine.connect() as conn:
        for enum_table in enum_tables:
            num_values = len(enum_table.values)
            utils.li(f"Table {enum_table.table.name}: {num_values} values")
            if verbose:
                for value in enum_table.values:
                    utils.li(f"    - {value['value']:2}: {value['name']}")
            conn.execute(enum_table.table.insert(), enum_table.values)
    utils.print_end_action()


def _generate_views(engine, enum_tables, enum_usage):
    enum_table_lookup = {et.enum.name: et.table.name for et in enum_tables}
    utils.print_action("Creating views with enum names")
    with engine.connect() as conn:
        for table, fields in enum_usage.items():
            view = _make_view(table)
            for column, enum_name in fields.items():
                enum_table = enum_table_lookup.get(enum_name)
                view.selects.append(f"{enum_table}.name as {column}_name")
                view.joins.append(
                    f"LEFT JOIN {enum_table} ON t.{column} = {enum_table}.value"
                )
            query = "CREATE OR REPLACE VIEW {name} AS SELECT t.*, {selects} FROM {table} t {joins}".format(
                name=view.name,
                table=view.table,
                selects=", ".join(view.selects),
                joins=" ".join(view.joins),
            )

            conn.execute(query)
            utils.li(
                f"View {view.name} to combine table {view.table} with its enum values"
            )
    utils.print_end_action()


def enum_tables(args):

    enums = args.dbmodel.metadata.enums
    if not enums:
        print("No enums found in the given model")
        return

    engine = common.get_db_engine(args.dbsettings)

    # Step 1: Create enum tables
    enum_tables = _create_enum_tables(engine, enums.values())

    # Step 2: Populate enum tables
    _populate_enum_tables(engine, enum_tables, args.verbose)

    # Step 3: Generate views
    eusage = common.get_type_mappings(args.dbmodel.metadata, [common.TypeFamilies.enum])
    _generate_views(engine, enum_tables, eusage)
