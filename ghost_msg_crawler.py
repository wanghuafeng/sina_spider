#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------
#
# 新浪微博API
#
#-------------------------------------------------------------------------

import re
import os
import sys
import time
import json
import gzip
import codecs
import struct
import hashlib
import logging

import socket
import urllib.error
import urllib.request

__all__ = ['MessageCrawler']

CFG_BASE_URL = 'http://sina.komoxo.com/2/sina/'
CFG_SYS_SALT = 'TT.secu.rocks'

CFG_PKG_ID = '3'
CFG_REV_ID = '7165'

API_URL_LOGIN = 'k/login'
API_URL_COMMENTS = 'statuses/comments.json'
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
        #sorted(self.params)['count', 'id', 'pkg_id',
        # 'rev_id', 'salt', 'tick', 'user_id', 'user_name']
        for name in sorted(self.params):#just return sorted keys_list
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
        try:
            #print (self.post_data)
            #b'id=3658085715922582&pkg_id=3&rev_id=7165&tick=1395230407&user_id=1000440717&
            # user_name=ma12693%40126.com&md5=3a83af953ef147ec170b6074cebad7e1'
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
            # print(self.rsp_obj)#你想要的东西都在self.rsp_obj中
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
            #print(self.http_code)#200
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

    def __init__(self, weibo_id, comment_id, comment_text):
        self.weibo_id = weibo_id    # 消息唯一编号
        self.comment_id = comment_id
        self.text = comment_text  # 消息文本内容

PATH = os.path.dirname(__file__)
class MessageCrawler:
    def __init__(self, config, log):
        self.comment_ids_list = []
        self.comment_text_list = []
        self.msg_comment_id_dic = {}#key:msg_id, value:comment_id
        self.hot_topic_ids_list = []#msg_id
        self.config = config
        self.log = log
        self._load_settings()
        self._load_hot_topic_file()#load hot_topic_ids_list
        self._load_msg_comment_ids()#load msg_comment_ids
        self.last_req_time = 0  # the time when last request ended

    def _load_hot_topic_file(self):
        filename = os.path.join(PATH, "sys", "hot_topic_ids")
        if not os.path.isfile(filename):
            raise ValueError("No such file %s"%filename)
        with codecs.open(filename, encoding="utf-8") as f:#load hot_topic_ids_list
            for id in f.readlines():
                id = id.strip()
                self.hot_topic_ids_list.append(id)

    def _load_msg_comment_ids(self):
        msg_comment_filename = os.path.join(PATH, "sys", "msg_comment_ids")
        if not os.path.isfile(msg_comment_filename):
            raise ValueError("No such file %s"%msg_comment_filename)
        with codecs.open(msg_comment_filename, encoding="utf-8") as msgfile:
            for line in msgfile.readlines():#load msg_comment_id_dic
                splited_line = line.split("\t")
                if len(splited_line) is not 2:
                    raise ValueError("lenth of splited line is not 2 in file msg_comment_ids")
                msg_id = splited_line[0].strip()
                comment_id = splited_line[1].strip()
                self.msg_comment_id_dic[msg_id] = comment_id

    def _reload_msg_comment_id(self):
        temp_dic = self.msg_comment_id_dic
        self.msg_comment_id_dic = {}
        msg_comment_line_list = []
        for msg_id in self.hot_topic_ids_list:
            if msg_id not in temp_dic:
                self.msg_comment_id_dic[msg_id] = '0'
                com_str = "\t".join((msg_id, '0'))
            else:
                self.msg_comment_id_dic[msg_id] = temp_dic[msg_id]
                com_str = "\t".join((msg_id, temp_dic[msg_id]))
            com_str = com_str + "\n"
            msg_comment_line_list.append(com_str)
        filename = os.path.join(PATH, 'sys', 'msg_comment_ids')
        if not os.path.isfile(filename):
            raise ValueError("No such file %s"%filename)
        with codecs.open(filename, mode="wb", encoding="utf-8") as f:
            f.writelines(msg_comment_line_list)

    def _load_settings(self):
        key = 'msg_request_delay'
        self.cfg_msg_request_delay = self.config.get_int(key, 3)
        key = 'msg_page_size'
        self.cfg_msg_page_size = self.config.get_int(key, 1)
        key = 'msg_count_size'
        self.cfg_msg_count_size = self.config.get_int(key, 20)
        key = 'connection_timeout'
        self.cfg_connection_timeout = self.config.get_int(key, 10)

    def _build_login_request(self, name, password):
        req = self._create_request(API_URL_LOGIN)#API_URL_LOGIN = 'k/login'
        req.set_param('user_name', name)
        req.set_param('passwd', password)
        return req

    def req_login(self, name, password):
        # name = 'gsmice@sina.cn'
        # password = '997568'
        req = self._build_login_request(name, password)
        # print (req)
        self._commit_request(req )
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

    def _build_timeline_request(self, name, token, account, msg_id):
        # req = self._create_request(API_URL_TIMELINE)#'statuses/user_timeline.json'
        req = self._create_request(API_URL_COMMENTS)
        # req = self._create_request(API_URL_COUNT)
        req.set_param('user_name', name)
        req.set_param('salt', token)
        if re.match(r'\A[0-9]+\Z', account):
            req.set_param('user_id', account)
        else:
            req.set_param('screen_name', account)
        req.set_param('page', str(self.cfg_msg_page_size))#default,1
        req.set_param('count', str(self.cfg_msg_count_size))#config,
        req.set_param('id', msg_id)
        return req

    def clear_comment_id_text_list(self):
        self.comment_ids_list[:] = []
        self.comment_text_list[:] = []

    def req_timeline(self, name, token, account, msg_id):#start crawl call this fuction
        req = self._build_timeline_request(name, token, account, msg_id)
        self._commit_request(req)
        if req.error:
            # self.logger.debug("msg_id:{msg_id},err_info:{err_info}".format(msg_id=msg_id,err_info=req.error))
            return
        rsp = req.rsp_obj['data']#rsp微博网页内容
        weibo_id = req.params['id']
        # print(rsp)
        if isinstance(rsp, list):#此处rsp是dict元素的list
            comment_ids_arr = []
            comment_text_arr = []
            for obj in rsp:
                # print(obj)#obj为rsp中的dict元素
                self._parser_message(comment_ids_arr, comment_text_arr, obj, weibo_id)
            # print(msgs)
            # print(len(comment_ids_arr))
            self.comment_ids_list.extend(comment_ids_arr)
            self.comment_text_list.extend(comment_text_arr)

            # print(len(self.comment_ids_list))
            if len(comment_ids_arr) is self.cfg_msg_count_size:#20
                self.cfg_msg_page_size += 1
                self.req_timeline(name, token, account, msg_id)
            self.cfg_msg_page_size = 1
            com_tuple = (self.comment_ids_list, self.comment_text_list)
            # print(com_tuple)
            return com_tuple

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
        wait = self.cfg_msg_request_delay - delay #self.cfg_msg_request_delay相邻请求之间最少需要的时间间隔
        if wait > 0.05:
            time.sleep(wait)
        req.send()
        self.last_req_time = time.time()

    def _parser_message(self, comment_id_list, comment_text_list, obj, weiboId):
        if isinstance(obj, dict):
            # print(obj)
            if ('source' in obj) and \
               ('id' in obj) and isinstance(obj['id'], int) and \
               ('text' in obj) and isinstance(obj['text'], str):
                comment_id = obj['id']
                comment_text = obj['text']+"\n"
                # print(comment_text)
                try:
                    max_comment_id = int(self.msg_comment_id_dic[weiboId])
                except:
                    max_comment_id = 0
                if comment_id > max_comment_id:
                    comment_text_list.append(comment_text)
                    comment_id_list.append(comment_id)
            # for val in obj.values():
            #     self._parser_message(msgs, val, weiboId)#递归函数

