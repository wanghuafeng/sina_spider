#coding:utf-8
import re
import rsa
import time
import os
import codecs
import base64
import binascii
import urllib.parse
import urllib.request
import http.cookiejar

cj = http.cookiejar.LWPCookieJar()
cookie_support = urllib.request.HTTPCookieProcessor(cj)
opener = urllib.request.build_opener(cookie_support , urllib.request.HTTPHandler)
urllib.request.install_opener(opener)


LINE_PATTERN = \
    re.compile(r'\A\s*' + \
               r'(?P<name>[^\s:]+)' + \
               r'\s*:\s*' + \
               r'(?P<nick>[^\s:]+)' + \
               r'\s*:\s*' + \
               r'(?P<password>[^\s:]+)' + \
               r'\s*:\s*' + \
               r'(?P<token>[^\s:]+)' + \
               r'\s*\Z')

def getData(url) :
    request = urllib.request.Request(url)
    response = urllib.request.urlopen(request)
    text = response.read().decode('utf-8')
    return text

def postData(url , data) :
    headers = {'User-Agent' : 'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)'}
    data = urllib.parse.urlencode(data).encode('utf-8')
    request = urllib.request.Request(url , data , headers)
    response = urllib.request.urlopen(request)
    text = response.read().decode('gbk')
    return text

def login_weibo(nick , pwd, url_list) :
    prelogin_url = 'http://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su=%s&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.15)&_=1400822309846' % nick
    preLogin = getData(prelogin_url)
    servertime = re.findall('"servertime":(.*?),' , preLogin)[0]
    pubkey = re.findall('"pubkey":"(.*?)",' , preLogin)[0]
    rsakv = re.findall('"rsakv":"(.*?)",' , preLogin)[0]
    nonce = re.findall('"nonce":"(.*?)",' , preLogin)[0]
    su = base64.b64encode(bytes(urllib.request.quote(nick) , encoding = 'utf-8'))
    rsaPublickey = int(pubkey , 16)
    key = rsa.PublicKey(rsaPublickey , 65537)
    message = bytes(str(servertime) + '\t' + str(nonce) + '\n' + str(pwd) , encoding = 'utf-8')
    sp = binascii.b2a_hex(rsa.encrypt(message , key))
    param = {'entry' : 'weibo' , 'gateway' : 1 , 'from' : '' , 'savestate' : 7 , 'useticket' : 1 , 'pagerefer' : 'http://login.sina.com.cn/sso/logout.php?entry=miniblog&r=http%3A%2F%2Fweibo.com%2Flogout.php%3Fbackurl%3D' , 'vsnf' : 1 , 'su' : su , 'service' : 'miniblog' , 'servertime' : servertime , 'nonce' : nonce , 'pwencode' : 'rsa2' , 'rsakv' : rsakv , 'sp' : sp , 'sr' : '1680*1050' ,
             'encoding' : 'UTF-8' , 'prelt' : 961 , 'url' : 'http://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack'}
    s = postData('http://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.15)' , param)
    urll = re.findall("""location.replace\((?:"|')(.*?)(?:"|')\)""" , s)[0]
    getData(urll)
    ##############################抓取该页面信息#############################
    start_html_index = 1
    path = os.path.dirname(__file__)
    html_path = os.path.join(path, 'sys', 'html')
    for url in url_list:
        html = getData(url)
        codecs.open(os.path.join(html_path, '%s.html'%start_html_index), mode='wb', encoding='utf-8').write(html)
        start_html_index += 1
        time.sleep(15)
    return True
def gen_htmls():
    path = os.path.dirname(__file__)
    url_filename = os.path.join(path, "sys", "hot_topic_urls")
    with codecs.open(url_filename, encoding="utf-8") as f:
        url_list = [item.strip() for item in f.readlines()]
    path = os.path.dirname(os.path.abspath(__file__))
    user_filename = os.path.join(path, 'sys', 'users.txt')
    with codecs.open(user_filename, encoding='utf-8') as f:
        for line in f.readlines():
            match = LINE_PATTERN.search(line)
            name = match.group('name')
            password = match.group('password')
            if login_weibo(name, password, url_list):
                break
            else:
                continue

if __name__ == '__main__':
    # url_list = [u'http://hot.weibo.com/?v=9999&page=1']
    # login_weibo('username', 'password', url_list)
    gen_htmls()
