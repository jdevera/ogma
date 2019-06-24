# Ogma

> According to legend, he is the inventor of Ogham, the runic language in which Irish Gaelic was first written. 

**Ogma** is a database access code generator for Java. It will take your database schema definition written in a Python-based DSL and generate (with jOOQ, among others) the necessary Java code to perform typed queries on that database.

It can also generate the necessary DDL to create the database structure according to spec.

*Ogma* has been written for MySQL and MariaDB, but could be made to work with other engines that are both supported by SQLAlchemy and jOOQ.

# How to install

Just run the usual for a Python package:

```bash
pip install ogma
```

Then you can run `ogma`.

# Code generation and other tools

*Ogma* obviously generates code, but it can also do other things. The tool is organized with subcommands.

## Generation

The `generate` subcommand is used to generate Java code from the model file. The model file is a Python with some restrictions and additions:

1. There is an implicit import of everything from `modelutils`
1. No imports are allowed

# For Developers
## Structure
 * `modelutils` contains all the code that is imported into the database model files and that internally deals with model operations.
 * `commands` contains the entry points for the tool's subcommands
 * `templates` contains *mustache* templates for jOOQ's configuration and additional generated Java code

