from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys
import shlex

class Command:
    """Parse a text command into command name and arguments, both positional and keyword"""
    def __init__(self, string):
        self.name = None
        self.string = None
        self.body = None
        self.args = []
        self.kwargs = {}

        self.chunks = [] # Raw splitted chunks

        self.parse(string)

    def name(self):
        return self.name

    def get(self, key, value=None):
        return self.kwargs.get(key, value)

    def has_key(self, key):
        return key in self.kwargs

    def __contains__(self, key):
        return key in self.kwargs

    def parse(self, string):
        self.string = string
        self.body = string
        self.chunks = shlex.split(string)

        for i,chunk in enumerate(self.chunks):
            if '=' not in chunk:
                if i == 0:
                    self.name = chunk
                    self.body = self.string.strip()[len(chunk):].strip()
                else:
                    self.args.append(chunk)
            else:
                pos = chunk.find('=')
                self.kwargs[chunk[:pos]] = chunk[pos+1:]
