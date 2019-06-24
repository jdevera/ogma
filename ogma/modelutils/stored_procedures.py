#!/usr/bin/env python3
# encoding: utf-8
"""
Convenience methods to define store procedures in model files
"""

from . import ValueHolder
from textwrap import dedent, indent


class ProcParamDirection(ValueHolder):
    """
    Hold the direction of a parameter in a stored procedure
    """

    def __init__(self, value):
        assert value in ("IN", "OUT", "INOUT")
        super().__init__(value)


# The available parameter directions:
IN = ProcParamDirection("IN")
OUT = ProcParamDirection("OUT")
INOUT = ProcParamDirection("INOUT")


class ProcSqlBody(ValueHolder):
    """
    Hold the SQL code that makes up the body of a stored procedure
    """

    pass


class ProcComment(ValueHolder):
    """
    Hold the comment test of a store procedure
    """

    pass


class ProcParam(object):
    """
    A parameter in a stored procedure
    """

    def __init__(self, name, the_type, direction):
        self._name = name
        self._type = the_type
        self._direction = None

        self.direction = direction

    @property
    def direction(self):
        return self._direction

    @direction.setter
    def direction(self, value):
        """
        A custom setter to make sure the value is an instance of
        ProcParamDirection
        """
        assert isinstance(value, ProcParamDirection)
        self._direction = value

    @property
    def sql(self):
        """
        The representation of the parameter in SQL
        """
        return "{0.direction.value} {0._name} {0._type}".format(self)


class StoredProcedure(object):
    """
    Models a SQL store procedure
    """

    def __init__(self, name, *args):
        self.name = name
        self.comment = None
        self.params = []
        self.sqlbody = None
        self.process_arguments(args)

    def process_arguments(self, args):
        """
        Arguments to the constructor can come in any order and their semantics
        is determined through their type, following the way a Table in
        sqlalchemy is created.
        """

        for arg in args:
            if isinstance(arg, ProcComment):
                self.comment = arg()
            elif isinstance(arg, ProcSqlBody):
                self.sqlbody = arg()
            elif isinstance(arg, ProcParam):
                self.params.append(arg)
            else:
                raise ValueError(
                    "Unexpected argument type for StoredProcedure: {}".type(arg)
                )

    @property
    def sql(self):
        """
        MySQL statement of procedure creation based on the current procedure
        definition
        """
        indented = lambda x: indent(x, 4 * " ")
        statement = [f"CREATE OR REPLACE PROCEDURE {self.name}("]
        if self.params:
            params_text = ",\n".join((param.sql for param in self.params))
            statement += ["\n", indented(params_text), "\n"]
        statement.append(")\nLANGUAGE SQL")
        if self.comment:
            statement.append(f"\nCOMMENT '{self.comment}'")
        indented_sql = indented(dedent(self.sqlbody))
        statement.append(f"\nBEGIN\n{indented_sql}\nEND\n")
        return "".join(statement)

    @property
    def creation_statement(self):
        return "\n".join(["DELIMITER //", self.sql + "\n//", "DELIMITER ;"])


def test():
    """
    Simple test for definition and text output
    """
    proc = StoredProcedure(
        "topiccounter",
        ProcParam("count", "BIGINT", OUT),
        ProcParam("count2", "BIGINT", OUT),
        ProcComment("Count the topics"),
        ProcSqlBody(
            """
          SELECT COUNT(*) INTO count FROM topic;
        """
        ),
    )
    print(proc.creation_statement)


if __name__ == "__main__":
    test()
