#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import os
import time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from config import configs
from coroweb import add_routes, add_static
from handlers import cookie2user, COOKIE_NAME

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')


def init_jinja2(app, **kw):
    """模板引擎初始化"""
    logging.info('init jinja2...')
    options = dict(
        autoescape=kw.get('autoescape', True),  # 默认打开自动转义 转义字符
        block_start_string=kw.get('block_start_string', '{%'),  # 模板控制块的字符串 {% block %}
        block_end_string=kw.get('block_end_string', '%}'),
        variable_start_string=kw.get('variable_start_string', '{{'),  # 模板变量的字符串 {{ var/func }}
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')  # 获得模板路径
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)  # 用文件系统加载器加载模板
    filters = kw.get('filters', None)  # 尝试获取过滤器
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env  # Web实例程序绑定模板属性


async def logger_factory(app, handler):
    """中间件，可以在处理请求前，对请求进行验证、筛选、记录等操作"""

    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))  # 记录日志
        # await asyncio.sleep(0.3)
        return await handler(request)  # 继续处理请求

    return logger


async def auth_factory(app, handler):
    async def auth(request):
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return await handler(request)

    return auth


async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return await handler(request)

    return parse_data


async def response_factory(app, handler):
    async def response(request):
        """对处理函数的响应进行处理"""
        logging.info('Response handler...')
        r = await handler(request)
        if isinstance(r, web.StreamResponse):  # 处理响应流
            return r
        if isinstance(r, bytes):  # 处理字节类响应
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):  # 处理字符串类响应
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])  # 返回重定向响应
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp  # 返回HTML
        if isinstance(r, dict):
            template = r.get('__template__')  # 处理字典类响应
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda
                    o: o.__dict__).encode('utf-8'))  # 返回json类响应
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                r['__user__'] = request.__user__
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode(
                    'utf-8'))  # 获取模板，并传入响应参数进行渲染，生成HTML
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and 100 <= r < 600:
            return web.Response(r)  # 处理响应码
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r  # 处理有描述信息的效应码
            if isinstance(t, int) and 100 <= t < 600:
                return web.Response(t, str(m))
        # default: 其他的响应返回
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp

    return response


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


async def init(loop):  # 定义init函数，标记为协程，传入loop协程参数
    """服务器运行程序：创建web实例程序，该实例程序绑定路由和处理函数，运行服务器，监听端口请求，送到路由处理"""
    await orm.create_pool(loop=loop, **configs.db)
    app = web.Application(loop=loop, middlewares=(
        logger_factory, auth_factory, response_factory
    ))  # 创建一个web服务器实例，用于处理URL，HTTP协议
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')  # 将URL注册进route，将URL和index处理函数绑定，当浏览器敲击URL时，返回处理函数的内容，也就是返回一个HTTP响应
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)  # 创建一个监听服务
    logging.info('server started at http://127.0.0.1:9000...')
    return srv


loop = asyncio.get_event_loop()  # get_event_loop创建一个事件循环，然后使用run_until_complete将协程注册到事件循环，并启动事件循环
loop.run_until_complete(init(loop))  # run_until_complete()是一个阻塞调用，将协程注册到事件循环，并启动事件循环，直到返回结果
loop.run_forever()  # run_forever()指一直运行协程，直到调用stop()函数，保证服务器一直开启监听状态
