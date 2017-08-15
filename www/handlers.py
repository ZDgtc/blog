# -*- coding: utf-8 -*-
import asyncio
import time
import re
import hashlib
import json

from www.coroweb import get, post
from db.models import User, Blog, next_id
from www.apis import APIError, APIPermissionError, APIResourceNotFoundError, APIValueError
from aiohttp import web
from www.config.config import configs

_RE_EMAIL = re.compile(r'^[a-zA-Z0-9._-]+@([a-zA-Z0-9_-])+(\.[a-zA-Z0-9_-]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')
COOKIE_NAME = 'zdblog'
_COOKIE_KEY = configs['session']['secret']


# 返回一个COOKIE_NAME对应的值
def user2cookie(user, max_age):
    # 计算到期时间
    expires = str(time.time() + max_age)
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY )
    # 将s用sha1加密，组织返回值
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


# 首页渲染
@get('/')
@asyncio.coroutine
def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, ' \
              'sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }


@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }



@post('/api/users')
@asyncio.coroutine
def api_register_user(*, email, name, passwd):
    # 检查是否传入参数，以及是否与相应的正则表达式匹配
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    # 检查是否已经注册过
    users = yield from User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    # 用uid:passwd的形式二次加密passwd
    sha1_passwd = '%s:%s' % (uid, passwd)
    # 构造sql语句，保存到数据库
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from user.save()
    # 设置cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    # 这里的passwd是个fake值
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

