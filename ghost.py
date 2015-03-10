#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import glob
import urllib
import codecs
import logging
from bs4 import BeautifulSoup

import ghost_user_store
import ghost_account_store

import ghost_msg_store
import ghost_msg_crawler

import ghost_log
import ghost_config
import ghost_url_filter


SCRIPT_PATH = os.path.dirname(__file__)#F:/ghost/src

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_file = logging.FileHandler("crawl_comment.log")
log_file.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file.setFormatter(formatter)
logger.addHandler(log_file)

class Ghost:
    def __init__(self, config_file=None, verbose=False):
        self.crawl_comment_id_dic = {}
        self.comment_text_cache = []
        self.verbose = verbose
        self.config = self._load_config(config_file)
        self.log = ghost_log.Log(self.config)

        self.user_store = ghost_user_store.UserStore(self.config, self.log)
        self.account_store = ghost_account_store.AccountStore(self.config, self.log)

        self.msg_store = ghost_msg_store.MessageStore(self.config, self.log)
        self.msg_crawler = ghost_msg_crawler.MessageCrawler(self.config, self.log)

        # self.page_store = ghost_page_store.PageStore(self.config, self.log)
        # self.page_crawler = ghost_page_crawler.PageCrawler(self.config, self.log)

        self.cfg_store_flush_limit = self.config.get_int('store_flush_limit', 1000)#in ghost.ini "store_flush_limit"="500"
        self.cfg_re_login_fail_count = self.config.get_int('re_login_fail_count', 10)
        self.comment_out_file = self.config.get('out_file_path')
        # self.cfg_page_expired_time = self.config.get_int('page_expired_time', 2 * 24 * 60 * 60)
    def _load_config(self, path):
        if not path:
            try_path = os.path.join(SCRIPT_PATH, 'ghost.ini')
            if os.path.isfile(try_path):
                path = try_path
        if not path:
            try_path = os.path.join(SCRIPT_PATH, 'sys', 'ghost.ini')
            if os.path.isfile(try_path):
                path = try_path
        if not path:
            print('Error: config file not found')
            sys.exit(1)
        return ghost_config.Config(path)
    def load_account_file(self, path):
        accounts = set()
        for line in open(path):
            name = line.strip()
            if name:
                accounts.add(name)
        return sorted(accounts)
    def save_account_file(self, accounts, path):
        text = '\n'.join(accounts)
        try:
            open(path, 'w').write(text)
        except (IOError, OSError):
            print('Error: failed to save account file "%s"' % path)
    def add_user(self, name, nick, password):
        if self.user_store.has(name):
            print('Error: user %s: can not add new user, user already exist' % name)
            return
        token = self.msg_crawler.req_login(name, password)
        if not token:
            print('Error: user %s: login failed' % name)
            return
        print('user %s, login token %s' % (name, token))
        self.user_store.add(name, nick, password, token)
        self.user_store.save()
    def remove_user(self, name):
        if not self.user_store.has(name):
            print('Error: user %s: can not remove user, user not found' % name)
            return
        self.user_store.remove(name)
        self.user_store.save()
    def login_all_users(self):
        for name in sorted(self.user_store.users):
            user = self.user_store.users[name]
            token = self.msg_crawler.req_login(user.name, user.password)
            if token:
                user.token = token
                print('user %s, login token %s' % (user.name, user.token))
            else:
                 print('Error: user %s: login failed' % user.name)
        self.user_store.save()
    def read_url_get_ids(self):
        '''通过本地保存的url,获取热门微博的ID,新浪改版后需要登录才可以完成此步操作'''
        # import sina_login
        # sina_login.gen_htmls()#抓取热门微博的html，并写入到本地，利用正则提取html页面中的id信息
        all_ids_list = []
        html_pattern = os.path.join(os.path.dirname(__file__), 'sys', 'html', '*.html')
        html_list = glob.glob(html_pattern)
        for html_filename in html_list:
            with codecs.open(html_filename, encoding='utf-8') as f:
                html = f.read()
                try:
                    soup = BeautifulSoup(html)
                    div_level = soup.findAll('div', {'class':'WB_feed'})
                    time.sleep(1)
                    id_items = div_level[0].findAll('div', {'class':'WB_feed_type SW_fun type_intimate feed_list'})
                    id_list = [id_str.get('mid')+"\n" for id_str in id_items]
                    all_ids_list.extend(id_list)
                except:
                    continue
        # [os.remove(filename) for filename in html_list]
        ids_set = set(all_ids_list)
        msg_comment_filename = os.path.join(os.path.dirname(__file__), "sys", "hot_topic_ids")
        with codecs.open(msg_comment_filename, mode="wb",encoding="utf-8") as wf:
            wf.writelines(ids_set)
    def _write_comment_id(self):
        temp_comment_id_arr = []
        for msg_id in self.crawl_comment_id_dic:
            comment_id = self.crawl_comment_id_dic[msg_id]
            com_str = "\t".join((str(msg_id), str(comment_id)))
            com_str = com_str + "\n"
            temp_comment_id_arr.append(com_str)
        filename = os.path.join(SCRIPT_PATH, "sys", "msg_comment_ids")
        with codecs.open(filename, mode="wb", encoding="utf-8") as wf:
            # logger.debug('msg_id, max comment_id write into file...')
            # print('msg_id, max comment_id write into file...')
            wf.writelines(temp_comment_id_arr)
    def clear_crawl_comment_id_dict(self):
        self.crawl_comment_id_dic.clear()
        filename = os.path.join(SCRIPT_PATH, "sys", "msg_comment_ids")
        with codecs.open(filename, encoding="utf-8") as f:
            for line in f.readlines():
                spited_line = line.strip().split("\t")
                if len(spited_line) != 2:
                    raise ValueError("length of splited line is not 2 in file:msg_comment_ids")
                msg_id = spited_line[0]
                comment_id = spited_line[1]
                if comment_id != "0":
                    self.crawl_comment_id_dic[msg_id] = comment_id
    def start_crawl(self):
        users = list(self.user_store.users.values())
        num_users = len(users)#users.txt中的用户的数量
        if num_users == 0:
            print('Error: no user found')
            return
        next_user_index = 0

        accounts = sorted(self.account_store.accounts)
        num_accounts = len(accounts)#account.txt中的用户数量
        if num_accounts == 0:
            print('Error: no account found')
            return
        next_account_index = 0

        self.num_tapi_commit = 0
        self.num_tapi_failed = 0

        self.msg_id_flag = 1
        self.pop_msg_id = 0

        self.login_fail_count = 0
        while True:
            if not self.msg_crawler.hot_topic_ids_list:
                self._write_comment_id()#write comment_id data into file:msg_comment_ids
                self.read_url_get_ids()#read urls get new ids,write them into file:hot_topic_ids
                self.msg_crawler._load_hot_topic_file()#load file hot_topic_ids into list: hot_topic_ids_list
                self.msg_crawler._load_msg_comment_ids()#load file msg_comment_ids into dic:msg_comment_id_dic
                self.msg_crawler._reload_msg_comment_id()#keep old comment_id the same,set new msg_id as 0 in msg_comment_id_dic
                self.clear_crawl_comment_id_dict()
                continue
            else:
                if self.msg_id_flag:
                    msg_id = self.msg_crawler.hot_topic_ids_list.pop(0)
                    self.pop_msg_id = msg_id.strip()
                else:
                    msg_id = self.pop_msg_id

            user = users[next_user_index]
            next_user_index = (next_user_index + 1) % num_users
            account = accounts[next_account_index]
            next_account_index = (next_account_index + 1) % num_accounts

            # msg_id = "3691582068560320"
            self.msg_crawler.clear_comment_id_text_list()
            com_tuple = self.msg_crawler.req_timeline(user.name, user.token, account, msg_id)#rsp_obj['data']

            if com_tuple is not None:
                self.msg_id_flag = 1
                # print(com_tuple)
                (comment_id_list,comment_text_list) = com_tuple
                if not comment_id_list:
                    continue
                self.crawl_comment_id_dic[msg_id] = comment_id_list[0]
                self._handle_comment_data(comment_text_list)
                # print(len(comment_id_list))
            else:
                self.msg_id_flag = 0
                self.login_fail_count += 1

            if self.login_fail_count > self.cfg_re_login_fail_count:#5
                self.login_all_users()
                logger.debug("login faild for %s times ,reload the token data"%str(self.cfg_re_login_fail_count))
                self.login_fail_count = 0

                self.start_crawl()

            if len(self.comment_text_cache) >= self.cfg_store_flush_limit:#500
                self._handle_comment_data(self.comment_text_cache)
                self.comment_text_cache[:] = []
    def _handle_comment_data(self, comment_text_list):
        if len(comment_text_list) >= self.cfg_store_flush_limit:
            self._write_comment_id()
            timestamp = self.gen_timestamp()
            comment_text_list = [line.encode("utf-8") for line in comment_text_list]
            # filename = os.path.join(SCRIPT_PATH, "out", timestamp + '_comment.txt')
            filename = os.path.join(self.comment_out_file, timestamp + '_comment.txt')
            with open(filename, mode="wb") as wf:
                # logger.debug("count of comment_text_list reach 3000, write into timestamp_comment.txt")
                # print("write into file...")
                wf.writelines(comment_text_list)
        else:
            self.comment_text_cache.extend(comment_text_list)
    def gen_timestamp(self):
        timestamp = time.strftime('%Y_%m_%d_%H%M%S')
        return timestamp

if __name__ == '__main__':

    g = Ghost()
    # g.login_all_users()
    g.start_crawl()

