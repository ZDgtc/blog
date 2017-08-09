import asyncio
from www.coroweb import get, post


@get('/')
@asyncio.coroutine
def handler_url_index(request):
    body = '<h1>Awesome</h1>'
    return body


@get('/greeting')
@asyncio.coroutine
def handler_url_greeting(request):
    body = '<h1>Greetings!</h1>'
    return body