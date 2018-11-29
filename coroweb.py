#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import asyncio
import functools
import inspect
import logging
import os
from urllib import parse

from aiohttp import web

from apis import APIError


def get(path):
    """Define decorator @get('/path')
    @get装饰器，给处理函数绑定URL和HTTP method-GET的属性
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper

    return decorator


def post(path):
    """Define decorator @post('/path')"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper

    return decorator


def get_required_kw_args(fn):
    """将函数所有 没默认值的 命名关键字参数名 作为一个tuple返回"""
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)


def get_named_kw_args(fn):
    """将函数所有的 命名关键字参数名 作为一个tuple返回"""
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


def has_named_kw_args(fn):
    """检查函数是否有命名关键字参数"""
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True


def has_var_kw_arg(fn):
    """检查函数是否有关键字参数集"""
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True


def has_request_arg(fn):
    """检查函数是否有request参数，返回布尔值。若有request参数，检查该参数是否为该函数的最后一个参数，否则抛出异常。"""
    params = inspect.signature(fn).parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (  # 如果找到'request'参数后，还出现位置参数，就会抛出异常
                param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError(
                'request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(params)))
    return found


class RequestHandler(object):
    """请求处理器，用来封装处理函数"""

    def __init__(self, app, fn):
        self._app = app  # app: an application instance for registering the fn
        self._func = fn  # fn: a request handler with a particular HTTP method and path
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    async def __call__(self, request):
        """分析请求
        A request handler can be any callable that accepts a Request instance as its only argument
        and returns a StreamResponse derived (e.g. Response) instance.
        A handler may also be a coroutine, in which case aiohttp.web will await the handler.
        """
        kw = None
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:  # 当传入的处理函数具有 关键字参数集 或 命名关键字参数 或 request参数
            if request.method == 'POST':
                if not request.content_type:  # 无正文类型信息时返回
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):  # 处理JSON类型的数据，传入参数字典中
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith(
                        'multipart/form-data'):  # 处理表单类型的数据，传入参数字典中
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:  # 获取URL中的请求参数，如 name=James, id=007
                    kw = dict()  # 将请求参数传入参数字典中
                    for k, v in parse.parse_qs(qs, True).items():
                        r"""
                        parse a query string, data are returned as a dict. the dict keys are the unique query variable
                        names and the values are lists of values for each name 
                        a True value indicates that blanks should be retained as blank strings 
                        """
                        kw[k] = v[0]
        if kw is None:
            # 请求无请求参数时
            kw = dict(**request.match_info)
            # Read-only property with AbstractMatchInfo instance for result of route resolving
        else:
            # 参数字典收集请求参数
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:  # 当存在关键字参数未被赋值时返回，例如：一般的账号注册时，没填入密码就提交注册申请时，提示密码未输入
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)  # 最后调用处理函数，并传入请求参数，进行请求处理
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


def add_static(app):
    """添加静态资源路径"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')  # 返回脚本所在目录的绝对路径，加上static
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))


def add_route(app, fn):
    """将处理函数注册到Web服务程序的路由当中"""
    method = getattr(fn, '__method__', None)  # 获取 fn 的 __method__ 属性的值，无则为None
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):  # 当处理函数不是协程时，封装为协程函数
        fn = asyncio.coroutine(fn)
    logging.info(
        'add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))


def add_routes(app, module_name):
    """自动把handler模块符合条件的函数注册"""
    n = module_name.rfind('.')
    if n == (-1):  # 没有匹配项时
        mod = __import__(module_name, globals(), locals())  # import一个模块，获取模块名 __name__
    else:
        name = module_name[n + 1:]  # 添加模块属性 name，并赋值给mod
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):  # dir(mod) 获取模块所有属性
        if attr.startswith('_'):  # 略过所有私有属性
            continue
        fn = getattr(mod, attr)
        if callable(fn):  # 获取属性的值，可以是一个method
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)  # 对已经修饰过的URL处理函数注册到Web服务的路由中
