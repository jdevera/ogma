#!/usr/bin/env python3
# encoding: utf-8


class ValueHolder(object):
    """
    Hold one arbitrary value per instance.
    This exists so that a module level variable can be propagated down through
    imports while keeping value changes.

    Instances are callables that return the held value
    """

    def __init__(self, value=None):
        self.value = value

    def __call__(self):
        return self.value
