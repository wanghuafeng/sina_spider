#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import codecs

__all__ = ['UserStore']

class User:

    def __init__(self, name):
        self.name = name
        self.nick = ''
        self.token = ''
        self.password = ''

class UserStore:

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self.users = { }
        self.load()

    def has(self, name):
        if name in self.users:
            return True
        else:
            return False
        
    def add(self, name, nick, password, token):
        user = User(name)
        user.nick = nick
        user.password = password
        user.token = token
        self.users[name] = user

    def remove(self, name):
        if name in self.users:
            del self.users[name]

    def _get_file_path(self):
        key = 'sys_file_path'
        path = self.config.get(key)
        if not path:
            print('Error: missing config option "%s"' % key)
            sys.exit(1)
        if not os.path.isdir(path):
            print('Error: path not found %s' % path)
            sys.exit(1)
        return os.path.join(path, 'users.txt')#/mnt/data/ghost/src/sys/users.txt
    
    LINE_PATTERN = \
        re.compile(r'\A\s*' + \
                   r'(?P<name>[^\s:]+)' + \
                   r'\s*:\s*' + \
                   r'(?P<nick>[^\s:]+)' + \
                   r'\s*:\s*' + \
                   r'(?P<password>[^\s:]+)' + \
                   r'\s*:\s*' + \
                   r'(?P<token>[^\s:]+)' + \
                   r'\s*\Z')

    def load(self):
        path = self._get_file_path()##/mnt/data/ghost/src/sys/users.txt
        if not os.path.isfile(path):
            print('Error: file not found %s' % path)
            sys.exit(1)
        line_num = 0
        for line in codecs.open(path, mode='r', encoding='utf_8', errors='ignore'):#read users.txt
            line_num += 1
            line = line.strip()
            if not line:
                continue # skip empty line
            if line[0] == ';':
                continue # skip comment line
            match = self.LINE_PATTERN.match(line)
            if not match:
                print('Warning(file %s, line %d): invalid entry' % (path, line_num))
                continue
            name = match.group('name')
            if name in self.users:
                print('Warning(file %s, line %d): duplicated entry ignored for "%s"' % (path, line_num, name))
                continue
            user = User(name)
            user.nick = match.group('nick')
            user.password = match.group('password')
            user.token = match.group('token')
            self.users[name] = user

    def save(self):
        path = self._get_file_path()
        chunks = [ ]
        for name in sorted(self.users):
            user = self.users[name]
            chunks.append('%s : %s : %s : %s' % (user.name, user.nick, user.password, user.token))
        text = '\n'.join(chunks)
        data = text.encode('utf_8', errors='ignore')
        try:
            open(path, 'w+b').write(data)
        except (IOError, OSError):
            print('Error: failed to save file %s' % path)
            sys.exit(1)
