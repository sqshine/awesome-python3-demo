import asyncio
import logging
from collections import *

from aiohttp import web

import orm
import models2
# from app import logger_factory, auth_factory, response_factory
from config import configs

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')


def index(request):
    return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')


async def init1(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', index)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv


async def init(loop):  # 定义init函数，标记为协程，传入loop协程参数
    """服务器运行程序：创建web实例程序，该实例程序绑定路由和处理函数，运行服务器，监听端口请求，送到路由处理"""
    await orm.create_pool(loop=loop, **configs.db)
    app = web.Application(loop=loop)
    # app = web.Application(loop=loop, middlewares=[
    #     logger_factory, auth_factory, response_factory
    # ])  # 创建一个web服务器实例，用于处理URL，HTTP协议
    # init_jinja2(app, filters=dict(datetime=datetime_filter))
    # add_routes(app, 'handlers')  # 将URL注册进route，将URL和index处理函数绑定，当浏览器敲击URL时，返回处理函数的内容，也就是返回一个HTTP响应
    # add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)  # 创建一个监听服务
    logging.info('server started at http://127.0.0.1:9000...')
    return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
