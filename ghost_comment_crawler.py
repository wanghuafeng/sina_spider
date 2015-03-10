#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------
#
# 新浪微博API
#
#-------------------------------------------------------------------------

import re
import sys
import time
import json

import gzip
import struct
import hashlib

import socket
import urllib.error
import urllib.request

__all__ = ['MessageCrawler']

CFG_BASE_URL = 'http://sina.komoxo.com/2/sina/'
CFG_SYS_SALT = 'TT.secu.rocks'

CFG_PKG_ID = '3'
CFG_REV_ID = '7165'

API_URL_LOGIN = 'k/login'
API_URL_TIMELINE = 'statuses/user_timeline.json'
API_URL_COMMENT  = 'statuses/comments.json'

class MessageRequest:

    def __init__(self, url):#url ==>  http://sina.komoxo.com/2/sina/k/login
        self.url = url
        self.params = { }
        self.timeout = 10
        self._reset()

    def _reset(self):
        self.post_data = None
        self.error = None
        self.http_code = 0
        self.http_reason = 'N/A'
        self.http_rsp = None
        self.http_err = None
        self.rsp_txt = None
        self.rsp_obj = None
        self.rsp_err = None

    def set_param(self, key, val):
        self.params[key] = val

    def _build_post_data(self):
        chunks = [ ]
        salt = CFG_SYS_SALT#CFG_SYS_SALT = 'TT.secu.rocks'
        md5 = hashlib.md5()
        for name in sorted(self.params):
            if name == 'salt':
                salt = self.params[name]
                continue
            val = self.params[name].encode('utf_8')
            md5.update(val)
            quoted = urllib.parse.quote_from_bytes(val, safe='')
            chunks.append('%s=%s' % (name, quoted))
        md5.update(salt.encode('ascii'))
        chunks.append('md5=%s' % md5.hexdigest())
        self.post_data = '&'.join(chunks).encode('ascii')
        # print(self.post_data)
    RSP_ERR_PATTERN = re.compile(r'(?P<code1>[0-9]+)[^0-9]+(?P<code2>[0-9]+)')

    def send(self):
        self._reset()#clear all of the data
        self._build_post_data()#encode option

        # make connection

        try:
            # print(self.url)#http://sina.komoxo.com/2/sina/statuses/user_timeline.json
            # print(self.post_data)#b'page=20&pkg_id=3&rev_id=7165&tick=1395026273&user_id=
            # 1000440717&user_name=ma12694%40126.com&md5=c623de9a2254b4716dddeb7c6e235808'
            self.http_rsp = urllib.request.urlopen(self.url, data=self.post_data, timeout=self.timeout)
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
        #self.http_rsp类文件对象
        self._parser_response(self.http_rsp)#解析response返回状态

        if self.http_code != 200:
            self.error = 'ERR: connection failed'
            return

        # read response data

        try:
            rsp_raw = self.http_rsp.read()#获得网页的全部内容
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
        #data = gzip.decompress(rsp_raw).decode("utf_8")
        try:
            rsp_unzip = gzip.decompress(rsp_raw)
        except (IOError, struct.error):
            self.error = 'ERR: failed to decompress response data'
            return

        # decode response data, assume UTF8 encoding

        try:
            self.rsp_txt = rsp_unzip.decode('utf_8', errors='replace')
        except UnicodeError:
            self.error = 'ERR: failed to decode response text'
            return

        # parser response data, build response object

        try:
            self.rsp_obj = json.loads(self.rsp_txt)#返回json格式的数据
            print(self.rsp_obj)#你想要的东西都在self.rsp_obj中
        except ValueError:
            self.error = 'ERR: failed to parser response text'
            return

        # check response code and data

        if not isinstance(self.rsp_obj, dict):
            self.error = 'ERR: invalid response data format'
            return

        if not ('code' in self.rsp_obj):
            self.error = 'ERR: invalid response data format'
            return

        if not ('data' in self.rsp_obj):
            self.error = 'ERR: invalid response data format'
            return

        if self.rsp_obj['code'] != 0:
            self.error = 'ERR: non-zero response code'
            return

        # parse error code

        data_obj = self.rsp_obj['data']#微博正文的所有相关内容,data_obj也是一个字典
        if isinstance(data_obj, dict):
            if 'error' in data_obj:
                match = self.RSP_ERR_PATTERN.match(data_obj['error'])
                if match:
                    self.rsp_err = (int(match.group('code1')), int(match.group('code2')))

    def _format(self, obj):
        return re.sub(r'[\r\n]+', '', str(obj).strip())

    def _parser_response(self, rsp):
        # print(rsp)#<http.client.HTTPResponse object at 0x00000000032A97F0>
        if hasattr(rsp, 'code') and isinstance(rsp.code, int):
            self.http_code = rsp.code
            # print(self.http_code)#200
        if hasattr(rsp, 'reason'):
            self.http_reason = self._format(rsp.reason)
            # print(self.http_reason)#OK

    def dump(self):
        lines = [ ]
        if self.error:
            lines.append(self.error)
        lines.append('  REQ_URL=%s' % self.url)
        lines.append('  REQ_PARAM=%s' % str(self.params))
        lines.append('  REQ_DATA=%s' % self.post_data.decode('ascii'))
        lines.append('  HTTP_STATUS=%d, %s' % (self.http_code, self.http_reason))
        if self.rsp_txt != None:
            lines.append('  RSP_TXT=%s' % self._format(self.rsp_txt))
        return lines

class Message:

    def __init__(self, mid, text):
        self.mid = mid    # 消息唯一编号
        self.text = text  # 消息文本内容

class MessageCrawler:

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self._load_settings()
        self.last_req_time = 0  # the time when last request ended

    def _load_settings(self):
        key = 'msg_request_delay'
        self.cfg_msg_request_delay = self.config.get_int(key, 3)
        key = 'msg_page_size'
        self.cfg_msg_page_size = self.config.get_int(key, 20)
        key = 'connection_timeout'
        self.cfg_connection_timeout = self.config.get_int(key, 10)

    def _build_login_request(self, name, password):
        req = self._create_request(API_URL_LOGIN)#API_URL_LOGIN = 'k/login'
        req.set_param('user_name', name)
        req.set_param('passwd', password)
        return req

    def req_login(self, name, password):
        req = self._build_login_request(name, password)
        print(req)
        self._commit_request(req)
        if req.error:
            self.log.write(req.dump())
            return
        rsp = req.rsp_obj['data']
        if isinstance(rsp, dict) and ('token' in rsp):
            token = rsp['token']
            if isinstance(token, str) and token:
                return token
        req.error = 'Error: user %s: login failed' % name
        self.log.write(req.dump())

    def _build_timeline_request(self, name, token, account):
        # req = self._create_request(API_URL_TIMELINE)#'statuses/user_timeline.json'
        req = self._create_request(API_URL_COMMENT)#'statuses/user_timeline.json'
        req.set_param('user_name', name)
        req.set_param('salt', token)
        if re.match(r'\A[0-9]+\Z', account):
            req.set_param('user_id', account)
        else:
            req.set_param('screen_name', account)
        req.set_param('page', str(self.cfg_msg_page_size))#1
        return req

    def req_timeline(self, name, token, account):#start crawl call this fuction
        print(name,token,account)
        req = self._build_timeline_request(name, token, account)
        self._commit_request(req)
        if req.error:
            self.log.write(req.dump())
            return
        rsp = req.rsp_obj['data']#rsp微博网页内容
        # print(rsp)
        if isinstance(rsp, list):#此处rsp是dict元素的list
            msgs = [ ]
            for obj in rsp:
                # print(obj)#obj为rsp中的dict元素
                self._parser_message(msgs, obj)
            return msgs
        req.error = 'Error: timeline request failed'
        self.log.write(req.dump())

    def _create_request(self, api_url):
        req = MessageRequest(CFG_BASE_URL + api_url)#CFG_BASE_URL = 'http://sina.komoxo.com/2/sina/';api_url = 'k/login'
        req.timeout = self.cfg_connection_timeout#connection timeout param
        req.set_param('pkg_id', CFG_PKG_ID)#CFG_PKG_ID = '3'
        req.set_param('rev_id', CFG_REV_ID)#CFG_REV_ID = '7165'
        tick = int(time.time())
        req.set_param('tick', str(tick))
        return req

    def _commit_request(self, req):
        delay = time.time() - self.last_req_time # the time when last request ended
        wait = self.cfg_msg_request_delay - delay
        if wait > 0.05:
            time.sleep(wait)
        req.send()
        self.last_req_time = time.time()

    def _parser_message(self, msgs, obj):
        if isinstance(obj, dict):
            #'source': '新浪微博'
            #'id': 3601048323050154
            #'text': '小朋友们都放假了，挺想念他们，看看孩子们的照片，看看他们的稚嫩笑脸，也跟着笑一笑，感觉是极好的休息'
            if ('source' in obj) and \
               ('id' in obj) and isinstance(obj['id'], int) and \
               ('text' in obj) and isinstance(obj['text'], str):
                msg = Message(obj['id'], obj['text'])
                #self.mid  = obj['id']  # 消息唯一编号
                # self.text = obj['text']  # 消息文本内容
                msgs.append(msg)
            for val in obj.values():
                self._parser_message(msgs, val)#递归函数
