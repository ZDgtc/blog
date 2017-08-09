import asyncio
import logging

from aiohttp import web
from www.coroweb import add_routes, add_static
from www.app import init_jinja2, datetime_filter, logger_factory, response_factory


logging.basicConfig(level=logging.INFO)


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop, middlewares=[logger_factory, response_factory])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'www.test_handler')
    add_static(app)
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('Server started at http://127.0.0.1:9000...')
    return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
