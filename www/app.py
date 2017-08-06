import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

#
def index(request):
    return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')

# 定义一个协程函数
@asyncio.coroutine
def init(loop):
    # 定义一个app
    app = web.Application(loop=loop)
    # 根目录的GET方法路由到index
    app.router.add_route('GET', '/', index)
    # 遇到io阻塞，中断返回
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

#获取一个事件循环
loop = asyncio.get_event_loop()
# 将loop作为参数传递给init，同时将协程函数init放入事件循环
loop.run_until_complete(init(loop))
loop.run_forever()