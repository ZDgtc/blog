import functools
import asyncio
import os
import inspect
import logging

from urllib import parse
from aiohttp import web


# 定义一个get装饰器，为装饰的函数添加GET URL信息
def get(path):
    def decorator(func):
        @functools.wraps(func)  # 把func的__name__等属性复制到wrapper()函数
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator


# 定义一个POST装饰器，为装饰的函数添加POST URL信息
def post(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator


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

    # 初始化参数
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_args = has_request_args(fn)
        self._has_var_kw_args = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_arg(fn)
        self._name_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    # 定义一个__call__方法，可以将RequestHandler类的实例视为函数
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
            # match_info 会返回一个包含request所有keyword_only类型参数的字典
            kw = dict(**request.match_info)
        else:
            # 若kw之前已经被赋值，且fn函数不包含关键字参数，包含强制关键字
            if not self._has_var_kw_args and self._name_kw_args:
                copy = dict()
                # 仅保留强制关键字参数
                for name in self._name_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # 检查强制关键字参数
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_args:
            kw['request'] = request
        # 检查无默认值的强制关键字参数是否存在kw中
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest(text='Missing argument: %s' % name)