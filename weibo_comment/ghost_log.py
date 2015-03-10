#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------
#
# 日志处理模块
#
#-------------------------------------------------------------------------

import os
import sys
import time

__all__ = ['Log']

class Log:

    def __init__(self, config):
        self.config = config
        self.path = self._get_file_path()
        
    def write(self, message):
        if not message:
            return
        if isinstance(message, list):
            lines = message
        else:
            lines = [message]
        prefix = self._format_message_prefix()
        chunks = [ ]
        chunks.append(prefix + lines[0] + '\n')
        for line in lines[1:]:
            chunks.append(line + '\n')
        text = ''.join(chunks)
        data = text.encode('utf_8', errors='ignore')
        self._append(data)    

    def _append(self, data):
        if not data:
            return
        path = self._get_resolved_file_path()
        try:
            open(path, 'a+b').write(data)
        except (OSError, IOError):
            # file IO error ignored
            pass

    def _format_message_prefix(self):
        return time.strftime('[%Y-%m-%d %H:%M:%S] ')
    
    def _get_resolved_file_path(self):
        name = time.strftime('%Y_%m_%d.txt')
        return os.path.join(self.path, name)

    def _get_file_path(self):
        key = 'log_file_path'
        path = self.config.get(key)
        if not path:
            print('Error: missing config option "%s"' % key)
            sys.exit(1)
        if not os.path.isdir(path):
            print('Error: path not found %s' % path)
            sys.exit(1)
        return path
