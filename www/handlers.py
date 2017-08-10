# -*- coding: utf-8 -*-

from www.coroweb import get, post
import asyncio
from db.models import User

@get('/')
@asyncio.coroutine
def index(request):
    users = yield from User.findAll()
    # 根据response_factory，若返回的字典类型包含__template__字段，则进行渲染
    return {
        '__template__': 'text.html',
        'users': users
    }