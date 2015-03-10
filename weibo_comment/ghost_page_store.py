#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import io
import sys
import time
import codecs
import zipfile

__all__ = ['PageStore']

class PageStore:

    CACHE_FILE_NAME = 'page_store_cache.txt'

    CACHE_ITEM_PATTERN = re.compile(r'^(?P<timestamp>[0-9]+)\s+(?P<url>.+)', re.MULTILINE)

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self._load_settings()
        self.cache_list = [ ]
        self.cache_dict = { }
        self._load_cache()
        self.next_page_id = int(time.time())
        self._reset_zip_file()

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

        key = 'page_cache_size'
        self.cache_size = self.config.get_int(key, 100)

    def _reset_zip_file(self):
        self.mem_file = io.BytesIO()
        self.zip_file = zipfile.ZipFile(self.mem_file, mode='w', \
            compression=zipfile.ZIP_DEFLATED)
        
    def get_timestamp(self, url):
        if url in self.cache_dict:
            return self.cache_dict[url]
        else:
            return 0
    
    def update(self, url, page_data, timestamp):
        if url in self.cache_dict:
            self.cache_dict[url] = timestamp
            self.cache_list.remove(url)
            self.cache_list.append(url)
        else:
            self.cache_dict[url] = timestamp
            self.cache_list.append(url)
            if len(self.cache_dict) > self.cache_size:
                oldest = self.cache_list.pop(0)
                del self.cache_dict[oldest]
        if page_data:
            name = '%012d' % self.next_page_id
            self.next_page_id += 1
            meta_data = url.encode('utf_8', errors='ignore')
            self.zip_file.writestr(name + '.url', meta_data)
            self.zip_file.writestr(name + '.htm', page_data)
            
    def flush(self, name):
        path = os.path.join(self.store_path, name + '_page.zip')
        self._flush_store(path)
        self._save_cache()
        
    def _flush_store(self, path):
        self.zip_file.close()
        data = self.mem_file.getbuffer()
        try:
            open(path, 'w+b').write(data)
        except (OSError, IOError):
            self.log.write('ERR: failed to save %s' % path)
        else:
            self.log.write('page store: save file %s' % path)
        self._reset_zip_file()

    def _save_cache(self):
        path = self.cache_file_path
        chunks = [ ]
        for url in self.cache_list:
            timestamp = self.cache_dict[url]
            chunks.append('%d %s\n' % (timestamp, url))
        text = ''.join(chunks)
        data = text.encode('utf_8', errors='ignore')
        try:
            open(path, 'w+b').write(data)
        except (OSError, IOError):
            self.log.write('ERR: failed to save %s' % path)
        else:
            self.log.write('page store cache: save file %s' % path)

    def _load_cache(self):
        path = self.cache_file_path
        if not os.path.isfile(path):
            return
        try:
            data = open(path, 'r+b').read()
        except (OSError, IOError):
            self.log.write('ERR: failed to load %s' % path)
        else:
            self.log.write('page store cache: load file %s' % path)
        text = data.decode('utf_8', errors='ignore')
        for match in self.CACHE_ITEM_PATTERN.finditer(text):
            url = match.group('url')
            timestamp = int(match.group('timestamp'))
            if not (url in self.cache_dict):
                self.cache_dict[url] = timestamp
                self.cache_list.append(url)
                if len(self.cache_dict) >= self.cache_size:
                    break
        self.log.write('page store cache: %d items loaded' % len(self.cache_dict))
