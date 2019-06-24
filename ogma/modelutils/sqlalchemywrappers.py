#!/usr/bin/env python3
# encoding: utf-8

from contextlib import contextmanager as _contextmanager
import copy as _copy
import collections as _collections
from typing import NamedTuple as _NamedTuple

import sqlalchemy as _sqlalchemy
import sqlalchemy.dialects.mysql as _mysql
from sqlalchemy import event as _event


def multiline_rstrip(s: str) -> str:
    """
    Takes a multiline string and returns a copy with trailing spaces from all lines
    removed.
    """
    return "\n".join((l.rstrip() for l in s.splitlines()))


class DatabaseModelException(Exception):
    """
    The base exception for all problems with the model file
    """

    pass


class IntegerEnum(_sqlalchemy.types.TypeDecorator):
    """
    A SqlAlchemy column type that encodes an enum values as an integer
    """

    impl = _sqlalchemy.Integer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_data = None

    def get_constraint(self, column_name):
        return self.field_data.get_constraint(column_name)


class Column(_sqlalchemy.Column):
    """
    Wrapper around sqlalchemy Column to replace 'default' argument, which is
    more succinct and readable, with server_default, which is the one that will
    determine the DDL output.

    The value of the default parameter is also wrapped in a `literal` when
    necessary, so it does not appear quoted in the DDL
    """

    def __init__(self, *args, **kwargs):
        if "server_default" in kwargs:
            raise DatabaseModelException(
                "server_default should not be used directly in columns. Use default instead"
            )
        default = kwargs.pop("default", None)
        if default is not None:
            kwargs["server_default"] = self._wrap_default(default)

        if "autoincrement" not in kwargs:
            kwargs["autoincrement"] = False

        super().__init__(*args, **kwargs)

    @staticmethod
    def _wrap_default(default):
        if type(default) in (bool, int):
            default = _sqlalchemy.literal(default)
        return default


class Table(_sqlalchemy.Table):

    """
    Wrapper around sqlalchemy Table to add object-like access to the column
    names to use in foreign keys

    Once a table is defined, the name of a column in the form
    `table_name.column_name` can be obtained from the model as:
        tables.table_name.column_name
    """

    def __new__(cls, *args, **kwargs):
        return _sqlalchemy.Table.__new__(
            Table, *args, **Table.add_default_settings(kwargs)
        )

    def __init__(self, name, metadata, *args, **kwargs):
        super().__init__(name, metadata, *args, **kwargs)

        # Create an ad-hoc object to represent the table name and its column
        # names
        columns = type("ColumnNames", (object,), {"_table_name": name})
        metadata._table_names.add_table(columns)

        for column in self.columns.values():
            # Add all column names as attributes to the name container
            setattr(columns, column.name, f"{self.name}.{column.name}")

            # Add a constraint for enums (so the integer value is one of the
            # defined enum values)
            if type(column.type) is IntegerEnum:
                self.append_constraint(column.type.get_constraint(column))

    @staticmethod
    def add_default_settings(kwargs):
        # Make sure we have a stable order of settings across runs:
        kwargs = _collections.OrderedDict(**kwargs)

        def set_default(kw, names, default):
            if not set(names).intersection(kw):
                kw[names[0]] = default

        set_default(kwargs, ("mysql_engine",), "InnoDB")
        set_default(
            kwargs,
            (
                "mysql_character_set",
                "mysql_charset",
                "mysql_default_character_set",
                "mysql_default_charset",
            ),
            "utf8mb4",
        )
        set_default(
            kwargs,
            ("mysql_collate", "mysql_default_collate", "mysql_collation"),
            "utf8mb4_general_ci",
        )
        set_default(kwargs, ("mysql_row_format",), "DYNAMIC")

        return kwargs


class DbSettings(_NamedTuple):
    host: str
    name: str
    port: int
    user: str
    password: str


class Enum:
    """
    Database enum (interger backed). Used indirectly in the model files to define
    enumerations that can later be used as table column types.
    """

    def __init__(self, name, metadata, *args, **kwargs):
        """
        Add all values as attributes for object-like access
        """
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self._values = []
        metadata.add_enum(self)

        for index, element in enumerate(args, start=0):
            if hasattr(self, element):
                raise DatabaseModelException(
                    f"{element} enum value already defined for enum {self.name}"
                )
            setattr(self, element, index)
            self._values.append(element)

    def __call__(self):
        """
        Use the sqlalchemy-like syntax of calling the types, and return the
        underlying Enum at this point.
        """
        column_type = IntegerEnum()
        column_type.field_data = self
        return column_type

    def get_constraint(self, column):
        values = ",".join([str(v) for v in range(len(self._values))])
        check_text = f"{column.name} in ({values})"
        check_name = f"ck_{column.table.name}_{column.name}"
        return _sqlalchemy.CheckConstraint(check_text, name=check_name)

    def __repr__(self):
        return f"""Enum('{self.name}', {", ".join(self._values)})"""


def _visitor_mysql_datetime(column_name, column):
    """
    A column visitor to change the type of all DateTimes to MySQL specific DATETIME
    with 3 as parameter
    :param column_name:  The name of the visited column
    :param column: The column object being visited
    """
    if type(column.type) == _sqlalchemy.DateTime:
        column.type = _mysql.DATETIME(fsp=3)


def _adapt_model_to_engine(model, engine, for_text=False):
    """
    Modify the model according to the required changes for each database engine
    :param model: The model module
    :param engine: The name of the target database engine
    :param for_text: Whether this adaptation is happening to generate a text
                     representation of the model (DDL)
    :return: The adapted model
    """
    visitors_per_engine = {"mysql": [_visitor_mysql_datetime]}
    visitors = visitors_per_engine.get(engine)
    if not visitors:
        return model

    model_copy = _copy.deepcopy(model)
    for v in visitors:
        model_copy.visit_columns(v)

    for proc in model_copy.stored_procedures:
        # Emit the delimiter change only when output is text
        ddl = proc.creation_statement if for_text else proc.sql

        # Add the DDL in the queue to run after all the schema has been created
        _event.listen(model_copy, "after_create", _sqlalchemy.DDL(ddl))

    return model_copy


class _EnumCollection(_collections.OrderedDict):
    """
    Provide dictionary and object semantics for an enum collection
    When an enum is added, it will be accessible as:
    >>> enums = _EnumCollection()
    >>> Enum("MyEnumName", enums, "value1", "value2")
    Enum('MyEnumName', value1, value2)
    >>> enums.MyEnumName is enums["MyEnumName"]
    True

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_enum(self, enum):
        if hasattr(self, enum.name):
            raise DatabaseModelException(f"{enum.name} enum already defined")
        setattr(self, enum.name, enum)
        self[enum.name] = enum


class _TableCollection:
    """
    An object that holds, as attributes, each table in the model
    """

    def add_table(self, table):
        if hasattr(self, table._table_name):
            raise DatabaseModelException(f"{table._table_name} table already defined")
        setattr(self, table._table_name, table)


class MetaData(_sqlalchemy.MetaData):
    """
    An augmentation of SqlAlchemy's default MetaaData class to provide some additional
    attributes such as:
     - A collection of all defined tables so far
     - A collection of all defined enums so far
    """

    def __init__(self, *args, **kwargs):
        self.enums = _EnumCollection()

        self._table_names = _TableCollection()
        """A collection with the sole purpose of storing a dummy object for
        each table that contains object-like access to column names"""

        self.stored_procedures = []

        super().__init__(*args, **kwargs)

    def __getstate__(self):
        """
        Control what gets copied with copy.deepcopy.

        __getstate__ must return a dictionary with what will be copied from the
        current instance.

        This is necessary because the parent defines one and it does not include the
        additional attributes of this class.
        """
        parent = super().__getstate__()
        parent.update(
            {
                "enums": self.enums,
                "_table_names": self._table_names,
                "stored_procedures": self.stored_procedures,
            }
        )
        return parent

    def __setstate__(self, state):
        """
        Control what gets copied with copy.deepcopy.

        __setstate__ takes a dictionary (like the one returned from __getstate__)
        with what will be copied from the original instance.

        This is necessary because the parent defines one and it does not include the
        additional attributes of this class.
        """
        super().__setstate__(state)
        self.enums = state["enums"]
        self._table_names = state["_table_names"]
        self.stored_procedures = state["stored_procedures"]

    def add_enum(self, enum):
        self.enums.add_enum(enum)

    def add_stored_procedure(self, stored_procedure):
        self.stored_procedures.append(stored_procedure)

    def visit_columns(self, *visitors):
        """
        Call all given column visitors with every column of every defined table

        The interface of the visitors is:
        def visitor(column_name: str, column: Column) -> None
        """
        for table in self.sorted_tables:
            for column_name, column in table.columns.items():
                for visit in visitors:
                    visit(column_name, column)

    def ddl(self, engine_name="mysql"):
        """
        Generate the DDL text for the currently defined model with the given
        database engine
        """

        class DdlDumper(object):
            def __init__(self):
                self._ddl = []

            def __call__(self, sql, *multiparams, **params):
                self._ddl.append(str(sql.compile(dialect=engine.dialect)).strip())

            @property
            def ddl(self):
                code = ";\n\n".join(self._ddl)
                return multiline_rstrip(code)

        ddl_dumper = DdlDumper()
        engine = _sqlalchemy.create_engine(
            f"{engine_name}://", strategy="mock", executor=ddl_dumper
        )
        model = _adapt_model_to_engine(self, engine_name, for_text=True)
        sorted_tables = [model.tables[t.name] for t in model.sorted_tables]
        model.create_all(engine, checkfirst=False, tables=sorted_tables)
        return ddl_dumper.ddl

    @staticmethod
    def _create_database(engine, database):
        engine.execute(f"CREATE DATABASE {database}")
        engine.execute(f"USE {database}")

    @staticmethod
    def _drop_database(engine, database):
        engine.execute(f"DROP DATABASE {database}")

    def save(self, dbsettings):
        """
        Create the current model, attached to this MetaData instance, in the database
        given in dbsettings.
        """
        db = dbsettings
        connect_string = f"mysql+pymysql://{db.user}:{db.password}@{db.host}:{db.port}"
        engine = _sqlalchemy.create_engine(connect_string)
        self._create_database(engine, dbsettings.name)
        model = _adapt_model_to_engine(self, "mysql")
        model.create_all(engine)
        return engine

    @_contextmanager
    def db_instance(self, dbsettings, drop_after=True):
        """
        A context manager that starts with a created database schema according to the
        model file and drops the whole database after it is exited.
        :param dbsettings: A DbSettings object with the parameters to connect to a
                           database
        :param drop_after: A bool (defaults to True) that triggers the deletion of the
                           database after exiting the context

        The intended usage is:
        >>> with metadata.db_instance(dbsettings):
        >>>     do_operations_with_schema_in_db(dbsettings)
        >>> # The database is deleted here
        """
        engine = self.save(dbsettings)
        try:
            yield
        finally:
            if drop_after:
                self._drop_database(engine, dbsettings.name)
