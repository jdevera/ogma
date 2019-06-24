#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import colored
import sys


def colstr(color, string):
    return f"{color}{string}{colored.style.RESET}"


def li(item, bullet=" *", color=colored.fore.LIGHT_GREEN, printer=print):
    """Print a list item"""
    printer(colstr(color, bullet), item)


def print_action(action, printer=print):
    li(action, bullet="===>", printer=printer)


def print_end_action(error=None, printer=print):
    color = colored.fore.DARK_GREEN if error is None else colored.fore.LIGHT_RED
    if error is None:
        error = ""
    li(error, color=color, bullet="===<", printer=printer)


def print_generated_file(file_path, printer=print):
    li(file_path, bullet="@", color=colored.fore.LIGHT_YELLOW, printer=printer)


def print_section_header(name, printer=print):
    line = colstr(colored.fore.LIGHT_BLUE, "=" * 80)
    printer()
    printer(line)
    printer("    " + name)
    printer(line)


def error(message, rc=1, printer=print):
    printer(colstr(colored.fore.LIGHT_RED, "ERROR:"), message)
    sys.exit(rc)
