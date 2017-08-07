# -*- coding: utf-8 -*-
import asyncio

import www.orm as orm
from www.model import User, Blog, Comment

@asyncio.coroutine
def test(loop):
    yield from orm.create_pool(loop=loop, user='root', password='123456', db='awesome')
    u = User(name='Test', email='test@example.com', passwd='123456',
             image='about:blank', admin=False, created_at='1502111285.44569',
             id='001502111285429762231d51f8e421cb8f4bac381ffd531000')
    yield from u.remove()

loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
loop.close()


