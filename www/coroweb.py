# -*- coding: utf-8 -*-

import functools
import asyncio
import os
import inspect
import logging

from urllib import parse
from aiohttp import web
from .apis import APIError


# 定义一个生成装饰器的模板，为装饰的函数添加URL信息
def de_generator(path, *, method):
    def decorator(func):
        @functools.wraps(func)  # 把func的__name__等属性复制到wrapper()函数
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = method
        wrapper.__route__ = path
        return wrapper
    return decorator


# 利用偏函数批量生成四个装饰器
get = functools.partial(de_generator,method='GET')
post = functools.partial(de_generator, method='POST')
put = functools.partial(de_generator, method='PUT')
delete = functools.partial(de_generator, method='DELETE')


# 获取无默认值的强制关键字参数，即带*参数之后的参数，必须以param=value传递
def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters  # 获取fn的参数、参数定义之间的映射的字典
    for name, param in params.items():
        # 若参数类型为强制关键字参数且没有默认值，则将其加入args列表
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)


# 获取强制关键字参数
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


# 判断是否存在强制关键字参数
def has_named_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True


# 判断是否存在关键字参数，例如**kw
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True


# 判断是否存在request参数，且是否为最后一个参数
def has_request_args(fn):
    params = inspect.signature(fn).parameters
    sig = inspect.signature(fn)
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL
                      and param.kind != inspect.Parameter.KEYWORD_ONLY
                      and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError(
                'request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig))
            )
    return found


# 封装一个URL处理函数
class RequestHandler(object):

    # fn是一个url处理函数，获取其需要的参数
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_args = has_request_args(fn)
        self._has_var_kw_args = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_arg(fn)
        self._name_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    # 定义一个__call__方法，可以将RequestHandler类的实例视为函数，传入的参数为request
    @asyncio.coroutine
    def __call__(self, request):
        kw = None
        if self._has_var_kw_args or self._has_named_kw_args or self._required_kw_args:
            # 对于POST方法
            if request.method == 'POST':
                # 必须要有数据提交格式
                if not request.content_type:
                    return web.HTTPBadRequest(text='Missing Content-Type')
                ct = request.content_type.lower()
                # 对于JSON格式的处理
                if ct.startswith('application/json'):
                    # decode为JSON dict，保存到params
                    params = yield from request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text='JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    # 对于以上两种格式，直接用post函数获取，并格式化为字典
                    params = yield from request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(text='Unsupported Content_Type: %s' % (request.content_type))
            if request.method == 'GET':
                # 获取url中的query部分
                qs = request.query_string
                if qs:
                    kw = dict()
                    # 解析查询字符串，作为字典返回，key为变量名，value为变量值
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            # match_info会返回一个包含request所有keyword_only类型参数的字典
            kw = dict(**request.match_info)
        else:
            # 若url处理函数不包含关键字参数，包含强制关键字参数,只保留kw从request获取的强制关键字参数和值
            if not self._has_var_kw_args and self._name_kw_args:
                copy = dict()
                # 仅保留强制关键字参数
                for name in self._name_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # 检查request是否包含最新的强制关键字参数
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        # 若url处理函数需要request参数，将request传入
        if self._has_request_args:
            kw['request'] = request
        # 若request没有提供无默认值的强制关键字参数需要的值，报错
        if self._required_kw_args:
            for name in self._required_kw_args:
                if name not in kw:
                    return web.HTTPBadRequest(text='Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        # 将收集好的kw传递给fn处理函数，异步调用
        try:
            r = yield from self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


# 用于注册URL处理函数
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if method is None or path is None:
        return ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' %
                 (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # RequestHandler的实例可以被直接调用
    app.router.add_route(method, path, RequestHandler(app, fn))


# 用于批量注册URL处理函数
def add_routes(app, module_name):
    # 查找'.'出现的位置
    n = module_name.rfind('.')
    # 未找到
    if n == -1:
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name], 0), name)
    # 对于mod模块里面的方法
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if path and method:
                add_route(app, fn)


# 静态文件路径
def add_static(app, path=None):
    if path:
        static_path = path
    else:
        static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
    app.router.add_static('/static/', static_path)
    logging.info('add static %s => %s' % ('/static/', path))