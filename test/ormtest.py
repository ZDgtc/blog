# -*- coding: utf-8 -*-
import asyncio

import db.orm as orm
from db.models import User


@asyncio.coroutine
def test(loop):
    yield from orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
    u = User(id='1', name='Administrator', passwd='admin', email='admin@blog.com', admin=True,
             image='about:blank')
    yield from u.save()

loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
loop.close()


