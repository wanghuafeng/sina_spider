#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import codecs

import ghost_user_store
import ghost_account_store

import ghost_msg_store
import ghost_msg_crawler

import ghost_page_store
import ghost_page_crawler

import ghost_log
import ghost_config
import ghost_url_filter

SCRIPT_PATH = os.path.dirname(__file__)

class Ghost:

    def __init__(self, config_file=None, verbose=False):
        self.verbose = verbose
        self.config = self._load_config(config_file)
        self.log = ghost_log.Log(self.config)

        self.user_store = ghost_user_store.UserStore(self.config, self.log)
        self.account_store = ghost_account_store.AccountStore(self.config, self.log)

        self.msg_store = ghost_msg_store.MessageStore(self.config, self.log)
        self.msg_crawler = ghost_msg_crawler.MessageCrawler(self.config, self.log)

        self.page_store = ghost_page_store.PageStore(self.config, self.log)
        self.page_crawler = ghost_page_crawler.PageCrawler(self.config, self.log)

        self.cfg_store_flush_limit = self.config.get_int('store_flush_limit', 2000)
        self.cfg_page_expired_time = self.config.get_int('page_expired_time', 2 * 24 * 60 * 60)
        
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
            
    def add_account(self, path):
        if not os.path.isfile(path):
            print('Error: file not found %s' % path)
            return
        accounts = set()
        for line in codecs.open(path, mode='r', encoding='utf_8', errors='ignore'):
            name = line.strip()
            if name:
                accounts.add(name)
        num_old_accounts = len(self.account_store.accounts)
        self.account_store.add(accounts)
        num_new_accounts = len(self.account_store.accounts)
        self.account_store.save()
        print('added %d, total %d' % (num_new_accounts - num_old_accounts, num_new_accounts))
        
    def start_crawl(self):
        users = list(self.user_store.users.values())
        num_users = len(users)
        if num_users == 0:
            print('Error: no user found')
            return
        next_user_index = 0

        accounts = sorted(self.account_store.accounts)
        num_accounts = len(accounts)
        if num_accounts == 0:
            print('Error: no account found')
            return
        next_account_index = 0

        self.num_tapi_commit = 0
        self.num_tapi_failed = 0
        self.num_page_commit = 0
        self.num_page_failed = 0

        while True:
            user = users[next_user_index]
            next_user_index = (next_user_index + 1) % num_users
            account = accounts[next_account_index]
            next_account_index = (next_account_index + 1) % num_accounts

            msgs = self.msg_crawler.req_timeline(user.name, user.token, account)
            self.num_tapi_commit += 1
            if msgs == None:
                self.num_tapi_failed += 1
            else:
                self._handle_message_data(msgs)
                
            if self.num_tapi_commit >= self.cfg_store_flush_limit:
                self.log.write('TAPI commit=%d failed=%d' % (self.num_tapi_commit, self.num_tapi_failed))
                self.log.write('PAGE commit=%d failed=%d' % (self.num_page_commit, self.num_page_failed))
                name = time.strftime('%Y_%m_%d_%H%M%S')
                self.msg_store.flush(name)
                self.page_store.flush(name)
                self.num_tapi_commit = 0
                self.num_tapi_failed = 0
                self.num_page_commit = 0
                self.num_page_failed = 0

    def _handle_message_data(self, msgs):
        urls = [ ]
        for msg in msgs:
            if self.msg_store.has(msg):
                continue
            self.msg_store.add(msg)
            urls.extend(ghost_url_filter.filter_html_urls(msg))
        timestamp = int(time.time())
        for url in urls:
            last_access_timestamp = self.page_store.get_timestamp(url)
            if timestamp - last_access_timestamp < self.cfg_page_expired_time:
                continue
            resolved_url, page_data = self.page_crawler.request(url)
            self.num_page_commit += 1
            if page_data == None:
                self.num_page_failed += 1
            if url != resolved_url:
                self.page_store.update(url, None, timestamp)
            self.page_store.update(resolved_url, page_data, timestamp)

##############################################################################

HELP = """usage: ghost [options] arguments

For help:            ghost --help
Add new user:        ghost user add NAME NICK PASSWORD
Remove user:         ghost user remove NAME
Login users:         ghost user login
Add accounts:        ghost account add FILE
Start crawl service: ghost crawl start

options:

-h, --help
  Print this message.

-v, --verbose
  Print detailed information.

-c FILE, --config FILE
  Specify configuration file."""

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(HELP)
        sys.exit(0)

    verbose = False
    config_file = None
    args = [ ]

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        i += 1
        if i < len(sys.argv):
            arg_next = sys.argv[i]
        else:
            arg_next = None
        if arg[0] in '-':
            if arg in ('-h', '--help'):
                print(HELP)
                sys.exit(0)
            elif arg in ('-v', '--verbose'):
                verbose = True
            elif arg in ('-c', '--config'):
                if config_file != None:
                    print('Error: duplicated config options')
                    sys.exit(1)
                if (arg_next == None) or (arg_next[0] == '-'):
                    print('Error: missing argument for option "%s"' % arg)
                    sys.exit(1)
                config_file = arg_next
                i += 1
            else:
                print('Error: unknown option "%s"' % arg)
                sys.exit(1)
        else:
            args.append(arg)

    ghost = Ghost(config_file, verbose)

    if (len(args) == 5) and (args[0] == 'user') and (args[1] == 'add'):
        ghost.add_user(args[2], args[3], args[4])

    elif (len(args) == 3) and (args[0] == 'user') and (args[1] == 'remove'):
        ghost.remove_user(args[2])

    elif (len(args) == 2) and (args[0] == 'user') and (args[1] == 'login'):
        ghost.login_all_users()

    elif (len(args) == 3) and (args[0] == 'account') and (args[1] == 'add'):
        ghost.add_account(args[2])

    elif (len(args) == 2) and (args[0] == 'crawl') and (args[1] == 'start'):
        ghost.start_crawl()

    else:
        print('Error: unknown argument')
        sys.exit(1)
