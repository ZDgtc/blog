# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import os
import time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from www.handlers import COOKIE_NAME, cookie2user
from db import orm
from www.config.config import configs
from www.coroweb import add_routes, add_static

logging.basicConfig(level=logging.INFO)


def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape=kw.get('autoescape', True),
        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%}'),
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env

# 用于记录时间
def datetime_filter(t):
    delta = int(time.time()-t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


# 以下为middleware，用于URL在被某个函数处理前，对URL的处理
# 改变URL的输入、输出，或者直接返回
# 接受一个app实例和一个handler作为参数，返回一个新的handler
@asyncio.coroutine
def logger_factory(app, handler):
    @asyncio.coroutine
    def logger(request):
        # 记录request的方法和路径
        logging.info('Request: %s %s' % (request.method, request.path))
        # 继续处理请求
        return (yield from handler(request))
    return logger


# 该middleware用于把handler处理过后的结果格式化为可正确显示的Response对象
@asyncio.coroutine
def response_factory(app, handler):
    @asyncio.coroutine
    def response(request):
        logging.info('Response handler...')
        r = yield from handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            # 对重定向的处理
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            # 若不含模板，JSON序列化结果输出
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                # 若返回值包含jinja2模板，绑定用户，渲染模板
                # 注意渲染语句Environment.get_template().render(dict).encode('utf-8)
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(status=r)
        if isinstance(r, tuple) and len(r) == 2:
            status, message = r
            if isinstance(status, int) and 100 <= status < 600:
                return web.Response(status=status, text=str(message))
        # 默认返回结果
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response


# 改middleware用于在处理url之前解析cookie，并将登录用户绑定到request上，后续的url处理函数可以直接拿到登录用户
@asyncio.coroutine
def auth_factory(app, handler):
    @asyncio.coroutine
    def auth(request):
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        # 取出本站登录cookie
        cookie_str = request.cookies.get(COOKIE_NAME)
        # 判断是否为合法cookie
        if cookie_str:
            user = yield from cookie2user(cookie_str)
            # 若是，将user信息写入request
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        # 访问/manage/，检查是否为管理员
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return (yield from  handler(request))
    return auth


@asyncio.coroutine
def init(loop):
    yield from orm.create_pool(loop=loop, **configs['db'])
    app = web.Application(loop=loop, middlewares=[logger_factory, auth_factory, response_factory])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()


