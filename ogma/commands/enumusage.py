#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handling of the enum-usage subcommand
"""

# ---------------------------------------------------------------------------
# Standard imports:
import collections

# Third party imports

# Local imports
from .. import utils
from . import common

# ---------------------------------------------------------------------------


def enum_usage(args):
    eusage = common.get_type_mappings(args.dbmodel.metadata, [common.TypeFamilies.enum])
    enums = collections.defaultdict(list)
    for table, fields in eusage.items():
        for column, enum in fields.items():
            enums[enum].append((table, column))
    for enum, usages in enums.items():
        print(f"Enum: {enum}")
        for table, column in usages:
            utils.li(f"{table}.{column}")
