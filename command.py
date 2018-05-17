#!/usr/bin/env python

import os, sys
import shlex

class Command:
    """Parse a text command into command name and arguments, both positional and keyword"""
    def __init__(self, string):
        self.name = None
        self.args = []
        self.kwargs = {}

        self.chunks = [] # Raw splitted chunks

        self.parse(string)

    def name(self):
        return self.name

    def get(self, key, value=None):
        return self.kwargs.get(key, value)

    def has_key(self, key):
        return self.kwargs.has_key(key)

    def parse(self, string):
        self.chunks = shlex.split(string)

        for i,chunk in enumerate(self.chunks):
            if '=' not in chunk:
                if i == 0:
                    self.name = chunk
                else:
                    self.args.append(chunk)
            else:
                pos = chunk.find('=')
                self.kwargs[chunk[:pos]] = chunk[pos+1:]
