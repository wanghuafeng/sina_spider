#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys

import zlib
import gzip
import struct

import socket
import urllib.error
import urllib.request

import ghost_url_filter

__all__ = ['PageCrawler']

CFG_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml',
    'Accept-Encoding': 'gzip,deflate',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64)',
    }

class HttpRequest:

    def __init__(self, url):
        self.initial_url = url
        self.timeout = 10
        self.content_length_limit = 0
        self._reset()

    def _reset(self):
        self.error = ''
        self.resolved_url = self.initial_url
        self.http_code = 0
        self.http_reason = 'N/A'
        self.http_req = None
        self.http_err = None
        self.http_rsp = None
        self.http_raw = None
        self.recv_data = None
        
    def commit(self):
        self._reset()
    
        # make connection
        
        self.http_req = urllib.request.Request(self.initial_url, headers=CFG_REQUEST_HEADERS)

        try:
            self.http_rsp = urllib.request.urlopen(self.http_req, timeout=self.timeout)
        except urllib.error.URLError as err:
            self.http_err = err
            self._parser_response(self.http_err)
            self.error = 'ERR: connection failed'
            return
        except socket.timeout:
            self.error = 'ERR: connection timed out'
            return
        except:
            exc_type, exc_value, exc_trace = sys.exc_info()
            str_type = self._format(exc_type)
            str_value = self._format(exc_value)
            self.error = 'ERR: url open exception, type=%s, value=%s' % (str_type, str_value)
            return
        
        # check response

        self._parser_response(self.http_rsp)
        
        if self.http_code != 200:
            self.error = 'ERR: connection failed'
            return

        if self.resolved_url != self.initial_url:
            if not ghost_url_filter.is_html_url(self.resolved_url):
                self.http_rsp.close()
                self.error = 'ERR: non html url'
                return

        if self.content_length_limit != 0:
            text = self.http_rsp.getheader('Content-Length')
            if isinstance(text, str):
                try:
                    clen = int(text)
                except ValueError:
                    clen = 0
                if clen > self.content_length_limit:
                    self.http_rsp.close()
                    self.error = 'ERR: content length exceed limit'
                    return

        # read response data
        
        try:
            self.http_raw = self.http_rsp.read()
        except socket.timeout:
            self.error = 'ERR: connection timed out'
            return
        except:
            exc_type, exc_value, exc_trace = sys.exc_info()
            str_type = self._format(exc_type)
            str_value = self._format(exc_value)
            self.error = 'ERR: response read exception, type=%s, value=%s' % (str_type, str_value)
            return

        # decompress response data

        data = self.http_raw
        if self.http_rsp.getheader('Content-Encoding') and len(data) > 0:
            data = self._decompress_response(data)
            if not data:
                self.error = 'ERR: failed to decompress response data'
                return

        if len(data) > 0:
            self.recv_data = data
        
    def _format(self, obj):
        return re.sub(r'[\r\n]+', '', str(obj).strip())
        
    def _parser_response(self, rsp):
        if hasattr(rsp, 'url') and isinstance(rsp.url, str):
            self.resolved_url = rsp.url
        if hasattr(rsp, 'code') and isinstance(rsp.code, int):
            self.http_code = rsp.code
        if hasattr(rsp, 'reason'):
            self.http_reason = self._format(rsp.reason)

    def _decompress_response(self, data):
        try:
            return gzip.decompress(data)
        except (IOError, struct.error):
            pass
        try:
            return zlib.decompressobj(-zlib.MAX_WBITS).decompress(data)
        except zlib.error:
            pass

    def dump(self):
        lines = [ ]
        if self.error:
            lines.append(self.error)
        lines.append('  URL=%s' % self.initial_url)
        if self.resolved_url != self.initial_url:
            lines.append('  RESOLVED=%s' % self.resolved_url)
        lines.append('  HTTP_STATUS=%d, %s' % (self.http_code, self.http_reason))
        return lines
        
class PageCrawler:

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self._load_settings()
        
    def _load_settings(self):
        key = 'connection_timeout'
        self.cfg_connection_timeout = self.config.get_int(key, 10)
        key = 'content_length_limit'
        self.cfg_content_length_limit = self.config.get_int(key, 1024 * 1024 * 2)

    def _build_request(self, url):
        req = HttpRequest(url)
        req.timeout = self.cfg_connection_timeout
        req.content_length_limit = self.cfg_content_length_limit
        return req

    def _commit_request(self, req):
        req.commit()
        
    def request(self, url):
        req = self._build_request(url)
        self._commit_request(req)
        if req.error:
            self.log.write(req.dump())
        return (req.resolved_url, req.recv_data)
