#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import codecs

__all__ = ['AccountStore']

class AccountStore:

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self.accounts = set()
        self.load()

    def add(self, accounts):
        self.accounts.update(accounts)

    def _get_file_path(self):
        key = 'sys_file_path'
        path = self.config.get(key)
        if not path:
            print('Error: missing config option "%s"' % key)
            sys.exit(1)
        if not os.path.isdir(path):
            print('Error: path not found %s' % path)
            sys.exit(1)
        return os.path.join(path, 'accounts.txt')

    def load(self):
        path = self._get_file_path()
        if not os.path.isfile(path):
            print('Error: file not found %s' % path)
            sys.exit(1)
        for line in codecs.open(path, mode='r', encoding='utf_8', errors='ignore'):
            name = line.strip()
            if name:
                self.accounts.add(name)

    def save(self):
        path = self._get_file_path()
        text = '\n'.join(sorted(self.accounts))
        data = text.encode('utf_8', errors='ignore')
        try:
            open(path, 'w+b').write(data)
        except (IOError, OSError):
            print('Error: failed to save file %s' % path)
            sys.exit(1)
