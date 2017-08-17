# -*- coding: utf-8 -*-
import asyncio
import time
import re
import hashlib
import json
import logging

from .coroweb import get, post
from db.models import User, Blog, next_id
from .apis import APIError, APIPermissionError, APIResourceNotFoundError, APIValueError, Page
from aiohttp import web
from .config.config import configs

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


# 解析cookie，返回user对象
@asyncio.coroutine
def cookie2user(cookie_str):
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if float(expires) < time.time():
            return None
        user = yield from User.find(uid)
        if not user:
            return None
        # 根据cookie的uid，找到对应的user，根据user信息，组织字符串，再与cookie的最后一个字段比较
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = "******"
        return user
    except Exception as e:
        logging.exception(e)
        return None


# 检查目前登录用户是否为admin
def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()


# 页面选择函数，取整数
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


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
        'blogs': blogs,
        '__user__': request.__user__ if request.__user__ else None
    }


# 渲染注册页面
@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }


# 渲染登录页面
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }


# 登出
@get('/signout')
def signout(request):
    # 获取链接页面
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    # 设置max age为0，使其在cookie2user函数返回None
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user sign out.')
    return r


# 渲染博客创建页面
@get('/manage/blogs/create')
def manage_create_blog(request):
    return {
        '__template__' : 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs',
        '__user__' : request.__user__
    }


# 渲染管理页面


# 用户注册api
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


# 用户登录api
@post('/api/authenticate')
@asyncio.coroutine
def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email')
    if not passwd:
        raise APIValueError('passwd')
    # 根据email取出相应的用户
    users = yield from User.findAll(where='email=?', args=[email])
    if len(users) == 0:
        raise APIValueError('email', 'email not exist.')
    user = users[0]
    # 验证密码，根据email找到userid，组织passwd并与数据库中的passwd进行比对
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # 认证通过，设置cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


# 博客创建api
@post('/api/blogs')
@asyncio.coroutine
def api_create_blogs(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,
                name=name.strip(), summary=summary.strip(), content=content.strip())
    yield from blog.save()
    return blog


# 获取博客列表api
@get('/api/blogs')
@asyncio.coroutine
def api_blogs(*, page='1'):
    # 把page转化为整型
    page_index = get_page_index(page)
    # 查询日志条数
    num = yield from Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    # 根据limit选出当前页展示的博客
    blogs = yield from Blog.findAll(orderBy='created_at desc',limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)


