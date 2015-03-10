#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------
#
# 微博文本内嵌URL分析器
#
#-------------------------------------------------------------------------

import re

__all__ = ['is_html_url', 'filter_html_urls']

# 常见的非html内容的URL类型
NON_HTML_EXTS = {
    # images
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.psd', '.ico',
    # videos
    '.swf', '.rmvb', '.mpg', '.avi', '.mp4', 'mkv',
    # audios
    '.mp3', '.wma',
    # others
    '.rar', '.zip', '.exe', '.dll', '.apk', '.msi', '.gz',
    '.pdf', '.xls', '.doc', '.ppt', '.iso', '.chm', '.docx',
    '.css', '.js',  '.ttf', '.otf',
    }

EXT_PATTERN = re.compile(r'\A.+(?P<ext>\.[a-z0-9]+)\Z', re.IGNORECASE)

URL_PATTERN = re.compile(r'https?\:\/\/[\_\.\-\?\=\/\&a-z0-9]+', re.IGNORECASE)

def filter_urls(text):
    """从普通文本中摘取URL, 返回URL列表"""
    return URL_PATTERN.findall(text)

def is_html_url(url):
    pos = url.rfind('?')
    if pos > 0:
        url = url[:pos]
    match = EXT_PATTERN.match(url)
    if match:
        ext = match.group('ext').lower()
        if ext in NON_HTML_EXTS:
            return False
    return True

def filter_html_urls(msg):
    return [u for u in filter_urls(msg.text) if is_html_url(u)]
