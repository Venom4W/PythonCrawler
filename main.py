#!/usr/bin/env python
#-*- coding:utf-8 -*-
from __future__ import with_statement
from bs4 import BeautifulSoup
from urllib2 import urlopen, Request, URLError, HTTPError
from time import sleep
import socket
import smtplib
from email.mime.text import MIMEText
import sqlite3
import os
import ConfigParser
from ConfigParser import NoOptionError

# info
base_url = ''
start_page = 1
max_page = 500
db_path = ''
try_time = 10

# mail info
mail_host = 'smtp.qq.com'
mail_user = '435129504@qq.com'
mail_pass = '************'
mail_postfix = 'qq.com'
mailer = 'rebot_mailer'
mail_to = []

# Email Services
class MailService():
    def __init__(self, mail_user=mail_user):
        self.s = smtplib.SMTP()
        self.s.connect(mail_host)
        self.s.login(mail_user, mail_pass)

    #发送邮件，to：发给谁，title：标题， content：内容，
    def send_mail(self, to, title, content, mail_user=mail_user, sub_type='plain', charset='utf-8'):
        # subType  plain|html
        me = mailer + "<" + mail_user + ">"   # +"@"+mail_postfix+">"
        msg = MIMEText(content, sub_type, charset)
        msg['Subject'] = title
        msg['From'] = me
        if type(to) == list:
            msg['To'] = ";".join(to)
        else:
            msg['To'] = to
        try:
            self.s.sendmail(me, to, msg.as_string())
            return True
        except Exception, e:
            print str(e)
            return False


def make_soup(url):
    # """打开指定url 获取BeautifulSoup对象"""
    try:
        req = Request(url)
        response = urlopen(req, timeout=20)
        html = response.read()
    except URLError, e:
        if hasattr(e, 'code'):
            print '错误码: ', e.code, ',无法完成请求.'
        elif hasattr(e, 'reason'):
            print '请求失败: ', e.reason, '无法连接服务器'
        return None
    except socket.timeout:
        return None
    else:
        return BeautifulSoup(html)


def get_page_info(url):
    """
        获取页面链接
    """
    tar_soup = make_soup(url)
    if not tar_soup:
        return 'TIMEOUT', None
    product_details = tar_soup.select("form#frmCompare > ul.ProductList > li > div.ProductDetails > strong > a")
    if product_details:
        return 'NORMAL', product_details
    else:
        return 'NOMORE', None


def get_data_from_url():
    global try_time
    time_out_pages = []
    name_list = []
    for i in range(start_page, max_page + 1):
        status, content = get_page_info(base_url+str(i))
        if status == 'TIMEOUT':
            #print 'page', i, ' time out.'
            time_out_pages.append(i)
        elif status == 'NOMORE':
            #print 'tried ', i, "pages, no more!"
            break
        else:
            name_list.extend(content)
            print 'scraping page:', i
        sleep(0.5)
        # 超时页面 继续尝试
    print 'fixing timeout pages, all:', len(time_out_pages)
    while time_out_pages and try_time:
        i = time_out_pages[0]
        try_time -= 1
        status, content = get_page_info(base_url+str(i))
        if status == 'TIMEOUT':
            time_out_pages.append(i)
        elif content:
            print 'fixed time out page', i
            name_list.extend(content)
            time_out_pages.remove(i)
    return name_list

def get_mail_content(updated_product, outdated_product):
    result = ""
    result += '新上架商品列表 : '+"<br/>"
    for x in updated_product:
        result += x + "<br/>"
    result += '已下架商品列表 : ' + "<br/>"
    for x in outdated_product:
        result += x + "<br/>"
    print 'send email done.'
    return result


def save_data(name_list):
    conn = sqlite3.connect(db_path)
    conn.text_factory = lambda x: unicode(x,'utf-8', 'ignore')
    cur = conn.cursor()
    for name in name_list:
        cur.execute("insert into product(name) values (?)", (str(name),))
    conn.commit()
    conn.close()


def compare_data():
    if not os.path.exists(db_path):
        create_table()
        name_set = {unicode(x).encode('utf-8') for x in get_data_from_url()}
        save_data(name_set)
        print 'the first time run! done.'
    else:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("select name from product")

        history_name_set = {unicode(x[0]).encode('utf-8') for x in cur.fetchall()}
        current_name_set = {unicode(x).encode('utf-8') for x in get_data_from_url()}

        common_product = current_name_set.intersection(history_name_set)
        updated_product = current_name_set.difference(common_product)
        outdated_product = history_name_set.difference(common_product)

        mail_content = get_mail_content(updated_product, outdated_product)
        ms = MailService()
        ms.send_mail(to=mail_to, title="产品信息", content=mail_content, sub_type="html")

        delete_data()
        save_data(current_name_set)
        conn.close()


def create_table():
    conn = sqlite3.connect(db_path)
    conn.execute('''create table product (name text not null);''')


def delete_data():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("delete from product")
    conn.commit()
    conn.close()

def main():
    __init__()
    compare_data()
    print 'done.'

def __init__():
    global mail_host, mail_user, mail_pass, \
        mail_postfix, mailer, base_url, start_page, max_page, db_path, try_time, mail_to

    # read config
    config = ConfigParser.ConfigParser()
    with open('config.cfg', "r") as cfg:
        config.readfp(cfg)
    try:
        mail_host = config.get('mail_config', 'mail_host')
        mail_user = config.get('mail_config', 'mail_user')
        mail_pass = config.get('mail_config', 'mail_pass')
        mail_postfix = config.get('mail_config', 'mail_postfix')
        mailer = config.get('mail_config', 'mailer')
        str_mail_to = config.get('mail_config', 'mail_to')
        mail_to = str_mail_to.split(',')

        base_url = config.get('crawler_config', 'base_url')
        start_page = config.getint('crawler_config', 'start_page')
        max_page = config.getint('crawler_config', 'max_page')
        db_path = config.get('crawler_config', 'db_path')
        try_time = config.getint('crawler_config', 'try_time')
    except NoOptionError, e:
        print 'missing option ', e.option
        exit(-1)


if __name__ == "__main__":
    main()
