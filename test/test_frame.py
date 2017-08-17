import asyncio
import logging

from aiohttp import web
from www.coroweb import add_routes, add_static
from www.app import init_jinja2, datetime_filter, logger_factory, response_factory, auth_factory
from db import orm
from www.config.config import configs

logging.basicConfig(level=logging.INFO)


@asyncio.coroutine
def init(loop):
    # 创建数据库连接池，从config导入配置
    yield from orm.create_pool(loop, **configs['db'])
    # 指定拦截器
    app = web.Application(loop=loop, middlewares=[logger_factory, response_factory, auth_factory])
    # 初始化jinja2，
    init_jinja2(
        app,
        filters=dict(datetime=datetime_filter),
        path=r'C:\Users\zhuangda\Desktop\programing\blog\www\templates')
    add_routes(app, 'www.handlers')
    add_static(app, path=r'C:\Users\zhuangda\Desktop\programing\blog\www\static')
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('Server started at http://127.0.0.1:9000...')
    return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
