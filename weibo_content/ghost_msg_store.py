#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import codecs

__all__ = ['MessageStore']

class MessageStore:

    CACHE_FILE_NAME = 'msg_store_cache.txt'

    CACHE_ITEM_PATTERN = re.compile(r'^(?P<mid>[0-9]+)', re.MULTILINE)

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self._load_settings()
        self.chunks = [ ]
        self.cache_list = [ ]
        self.cache_set = set()
        self._load_cache()

    def _load_settings(self):
        key = 'out_file_path'
        path = self.config.get(key)
        if not path:
            print('Error: missing config option "%s"' % key)
            sys.exit(1)
        if not os.path.isdir(path):
            print('Error: path not found %s' % path)
            sys.exit(1)
        self.store_path = path

        key = 'sys_file_path'
        path = self.config.get(key)
        if not path:
            print('Error: missing config option "%s"' % key)
            sys.exit(1)
        if not os.path.isdir(path):
            print('Error: path not found %s' % path)
            sys.exit(1)
        self.cache_file_path = os.path.join(path, self.CACHE_FILE_NAME)

        key = 'msg_cache_size'
        self.cache_size = self.config.get_int(key, 100)

    def has(self, msg):
        if msg.mid in self.cache_set:
            return True
        else:
            return False
        
    def _format_message_text(self, text):
        return re.sub(r'[\r\n]+', '', text.strip())
        
    def add(self, msg):
        if msg.mid in self.cache_set:
            return
        self.cache_set.add(msg.mid)
        self.cache_list.append(msg.mid)
        if len(self.cache_set) > self.cache_size:
            oldest = self.cache_list.pop(0)
            self.cache_set.remove(oldest)
        text = self._format_message_text(msg.text)
        if text:
            line = text + '\n'
            self.chunks.append(line.encode('utf_8', errors='ignore'))

    def flush(self, name):
        path = os.path.join(self.store_path, name + '_msg.txt')
        self._flush_store(path)
        self._save_cache()
        
    def _flush_store(self, path):
        data = b''.join(self.chunks)
        try:
            open(path, 'w+b').write(data)
        except (OSError, IOError):
            self.log.write('ERR: failed to save %s' % path)
        else:
            self.log.write('msg store: save file %s' % path)
        self.chunks = []

    def _save_cache(self):
        path = self.cache_file_path
        text = ''.join(['%d\n' % mid for mid in self.cache_list])
        data = text.encode('utf_8', errors='ignore')
        try:
            open(path, 'w+b').write(data)
        except (OSError, IOError):
            self.log.write('ERR: failed to save %s' % path)
        else:
            self.log.write('msg store cache: save file %s' % path)

    def _load_cache(self):
        path = self.cache_file_path
        if not os.path.isfile(path):
            return
        try:
            data = open(path, 'r+b').read()
        except (OSError, IOError):
            self.log.write('ERR: failed to load %s' % path)
        else:
            self.log.write('msg store cache: load file %s' % path)
        text = data.decode('utf_8', errors='ignore')
        for match in self.CACHE_ITEM_PATTERN.finditer(text):
            mid = int(match.group('mid'))
            if not (mid in self.cache_set):
                self.cache_set.add(mid)
                self.cache_list.append(mid)
                if len(self.cache_set) >= self.cache_size:
                    break
        self.log.write('msg store cache: %d items loaded' % len(self.cache_set))
