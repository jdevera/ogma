#!/usr/bin/env python3
# encoding: utf-8

import uuid as _uuid
from datetime import datetime as _datetime

# DDL elements
from sqlalchemy import (
    # Column,
    ForeignKey,
    ForeignKeyConstraint,
    CheckConstraint,
    UniqueConstraint,
    PrimaryKeyConstraint,
    Index,
    literal,
    text,
)

# Data types for columns
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    BigInteger,
    Numeric,
    String,
    Text,
    LargeBinary,
    VARBINARY,
    BINARY,
)

from .sqlalchemywrappers import (
    IntegerEnum,
    Column,
    Table as _Table,
    Enum as _Enum,
    MetaData,
    DbSettings,
)

from .validation import validate_model

from .value_holder import ValueHolder

from .stored_procedures import (
    StoredProcedure as _StoredProcedure,
    ProcComment,
    ProcSqlBody,
    ProcParam,
    IN,
    OUT,
    INOUT,
)

# Come predefined literals to avoid the use of literal strings for keywords in the
# model files.
CURRENT_TIMESTAMP = text("CURRENT_TIMESTAMP")
NULL = text("NULL")
CASCADE = "CASCADE"
SET_NULL = "SET NULL"
RESTRICT = "RESTRICT"


def get_new_database_name():
    return "_".join(
        ("ogma_db_", _datetime.utcnow().strftime("%Y%m%d%H%M%S"), _uuid.uuid4().hex)
    )


# Each run deals with a single model file for a single schema, so store at this level
# some model information that will be invisible to the model file, but available for
# processing.

# This holds the schema name for the processed model file, which is set by the Schema
# function below:
schema_name = ValueHolder(None)

# The default metadata object for all the Table objects created in the model file.
# SqlAlchemy needs this to be passed around, so this is stored here and used in the
# DDL object creators below to pass to the corresponding SqlAlchemy objects while
# not showing explicitly in the model file.
metadata = MetaData()

# Easy access to the previously defined tables, so one can create indexes or foreign
# keys in the model file without using the table names as strings.
enums = metadata.enums

# Easy programmatic access to the previously defined enums, so they can be referenced
# as column types when creating tables.
tables = metadata._table_names


def Schema(a_schema_name):
    """
    Declare (call only once, at the top) the schema name for the current model file.
    """
    schema_name.value = a_schema_name


def Table(*args, **kwargs):
    """
    Convenience wrapper for SqlAlchemy Table, which transparently passes the default
    metadata object for the current model file.
    """
    name, rest = args[0], args[1:]
    return _Table(name, metadata, *rest, **kwargs)


def Enum(*args, **kwargs):
    """
    A convenience wrapper for Ogma's numeric DB Enum, which transparently passes the
    default metadata object for the current model file.
    """
    name, rest = args[0], args[1:]
    return _Enum(name, metadata, *rest, **kwargs)


def StoredProcedure(*args, **kwargs):
    """
    A convenience wrapper for Ogma's StoredProcedure, which also adds the new
    StoredProcedure to the metadata object for the current model file.
    """
    sp = _StoredProcedure(*args, **kwargs)
    metadata.add_stored_procedure(sp)
    return sp
