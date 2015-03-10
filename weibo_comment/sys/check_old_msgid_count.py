__author__ = 'wanghuafeng'
import os
import re
import codecs
path = os.path.dirname(__file__)
filename = os.path.join(path, "msg_comment_ids")
temp_list = []
with codecs.open(filename, encoding="utf-8")as f:
    for line in f.readlines():
        splited_line = line.strip().split("\t")
        if len(splited_line) is not 2:
            raise ValueError("length of splited line is not 2")
        msg_id = splited_line[0]
        comment_id = splited_line[1]
        if comment_id != '0':
            temp_list.append(comment_id)
print len(temp_list)
