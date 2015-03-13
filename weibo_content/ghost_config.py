#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------
#
# 配置文件分析器
#
#-------------------------------------------------------------------------

import os
import re
import sys
import codecs

__all__ = ['Config']

LINE_PATTERN = re.compile(r'\A\s*"(?P<key>.+?)"\s*=\s*"(?P<val>.+?)"\s*\Z')

def load_config(path):
    if not os.path.isfile(path):
        print('Error: file not found %s' % path)
        sys.exit(1)
    entries = { }
    line_num = 0
    for line in codecs.open(path, mode='r', encoding='utf_8', errors='ignore'):
        line_num += 1
        line = line.strip()
        if not line:
            continue # skip empty line
        if line[0] == ';':
            continue # skip comment line
        match = LINE_PATTERN.match(line)
        if not match:
            print('Warning(file %s, line %d): invalid entry' % (path, line_num))
            continue
        key = match.group('key')
        if key in entries:
            print('Warning(file %s, line %d): duplicated entry ignored for "%s"' % (path, line_num, key))
            continue
        entries[key] = match.group('val')
    return entries

class Config:

    def __init__(self, path):
        self.path = path
        self.entries = load_config(self.path)

    def get(self, key, default=None):
        if key in self.entries:
            return self.entries[key]
        return default

    def get_int(self, key, default=0):
        if key in self.entries:
            try:
                return int(self.entries[key])
            except ValueError:
                pass
        return default
