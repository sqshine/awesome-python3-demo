#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import logging

import aiomysql


def log(sql, args=()):
    """ 记录sql操作 """
    logging.info('SQL: %s' % sql)


async def create_pool(loop, **kw):
    """ 创建全局连接池，**kw 关键字参数集，用于传递host port user password db等的数据库连接参数 """
    logging.info('create db connection pool...')
    global __pool  # 将__pool定义为全局变量
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),  # 主机ip，默认本机
        port=kw.get('port', 3306),  # 端口，默认3306
        user=kw['user'],  # 用户
        password=kw['password'],  # 用户口令
        db=kw['db'],  # 选择数据库
        charset=kw.get('charset', 'utf8'),  # 设置数据库编码，默认utf8
        autocommit=kw.get('autocommit', True),  # 设置自动提交事务，默认打开
        maxsize=kw.get('maxsize', 10),  # 设置最大连接数，默认10
        minsize=kw.get('minsize', 1),  # 设置最少连接数，默认1
        loop=loop  # 需要传递一个事件循环实例，若无特别声明，默认使用asyncio.get_event_loop()
    )


async def select(sql, args, size=None):
    """实现SQL语句：SELECT。
    传入参数为：SQL语句，SQL语句中占位符对应的参数集，返回记录行数。
    执行为：从连接池获取连接->创建游标用来执行MySQL命令->用游标执行MySQL命令->返回查询结果。
    """
    log(sql, args)
    # global __pool  # 使用全局变量__pool
    async with __pool.get() as conn:  # 从连接池中获取一个连接，使用完后自动释放。
        async with conn.cursor(aiomysql.DictCursor) as cur:  # 创建一个游标，返回由dict组成的list，使用完后自动释放
            await cur.execute(sql.replace('?', '%s'),
                              args or ())  # 执行SQL，mysql的占位符是%s，和python一样，为了coding的便利，先用SQL的占位符？写SQL语句，最后执行时在转换过来
            if size:
                rs = await cur.fetchmany(size)  # 只读取size条记录
            else:
                rs = await cur.fetchall()  # 返回的rs是一个list，每个元素是一个dict，一个dict代表一行记录
        logging.info('rows returned: %s' % len(rs))  # 有多少个dict就是多行记录
        return rs


async def execute(sql, args, autocommit=True):
    """实现SQL语句：INSERT、UPDATE、DELETE。
    传入参数分别为：SQL语句、SQL语句中占位符对应的参数集、默认打开MySQL的自动提交事务。
    定义通用的execute()函数来执行增删改。
    """
    log(sql, args)
    async with __pool.acquire() as conn:  # 获取一个连接
        if not autocommit:
            await conn.begin()  # 协程开始启动
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:  # 创建一个字典游标，返回字典类型为元素的list
                await cur.execute(sql.replace('?', '%s'), args)  # 执行SQL
                affected = cur.rowcount  # 获得影响的行数
            if not autocommit:
                await conn.commit()  # 提交事务
        except BaseException as e:
            if not autocommit:
                await conn.rollback()  # 回滚当前启动的协程
            raise
        return affected


def create_args_string(num):
    """ 按参数个数制作占位符字符串，用于生成SQL语句 """
    L = []
    for n in range(num):  # SQL的占位符是？，num是多少就插入多少个占位符
        L.append('?')
    return ', '.join(L)  # 将L拼接成字符串返回，例如num=3时："?, ?, ?"


class Field(object):
    """定义一个数据类型的基类。
    用于衍生各种在ORM中对应数据库的数据类型的类。
    描述字段的字段名，数据类型，键信息，默认值。
    """

    def __init__(self, name, column_type, primary_key, default):
        """ 传入参数对应列名、数据类型、主键、默认值 """
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        """ print(Field_object)时，返回类名Field，数据类型，列名 """
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):
    """ 从Field继承，定义一个字符类，在ORM中对应数据库的字符类型，默认‘变长100字节’ """

    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        """ 可传入参数列名、主键、默认值、数据类型 """
        super().__init__(name, ddl, primary_key, default)  # 对应列名、数据类型、主键、默认值


class BooleanField(Field):
    """ 从Field继承，定义一个布尔类，在ORM中对应数据库的布尔类型 """

    def __init__(self, name=None, default=False):
        """ 可传入参数列名、默认值 """
        super().__init__(name, 'boolean', False, default)  # 对应列名、数据类型、主键、默认值


class IntegerField(Field):
    """ 从Field继承，定义一个整数类，在ORM中对应数据库的 BIGINT 整数类型，默认值为0 """

    def __init__(self, name=None, primary_key=False, default=0):
        """ 可传入参数列名、主键、默认值 """
        super().__init__(name, 'bigint', primary_key, default)


class FloatField(Field):
    """ 从Field继承，定义一个浮点数类，在ORM中对应数据库的 REAL 双精度浮点数类型 """

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):
    """ 从Field继承，定义一个文本类，在ORM中对应数据库的 TEXT 长文本数类型 """

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


# metaclass是类的模板，所以必须从`type`类型派生：
class ModelMetaclass(type):
    """定义一个元类，定制类与数据库的各种映射关系，让继承这个元类的类实现ORM。
    首先，拦截类的创建；然后，修改类；最后，返回修改后的类。
    """

    def __new__(cls, name, bases, attrs):
        """ 用metaclass=ModelMetaclass创建类时，通过这个方法生成类 """
        if name == 'Model':  # 定制Model类
            return type.__new__(cls, name, bases, attrs)  # 当前准备创建的类的对象、类的名字model、类继承的父类集合、类的方法集合
        tableName = attrs.get('__table__', None) or name  # 获取表名，默认为None，或为类名
        print('found model: %s (table: %s)' % (name, tableName))  # 类名、表名
        mappings = dict()  # 用于存储列名和对应的数据类型
        fields = []  # 用于存储非主键的列
        primaryKey = None  # 用于主键查重，默认为None
        for k, v in attrs.items():  # 遍历attrs方法集合
            if isinstance(v, Field):  # 提取数据类的列
                print('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v  # 存储列名和数据类型
                if v.primary_key:  # 查找主键和查重，有重复则抛出异常
                    if primaryKey:
                        raise Exception('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)  # 存储非主键的列名
        if not primaryKey:  # 整个表不存在主键时抛出异常
            raise Exception('Primary key not found.')
        for k in mappings.keys():  # 过滤掉列，只剩方法
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))  # 给非主键列加``（可执行命令）区别于''（字符串效果）
        attrs['__mappings__'] = mappings  # 保持属性和列的映射关系
        attrs['__table__'] = tableName  # 表名
        attrs['__primary_key__'] = primaryKey  # 主键属性名
        attrs['__fields__'] = fields  # 除主键外的属性名
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (
            primaryKey, ', '.join(escaped_fields), tableName)  # 构造select执行语句，查整个表
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (
            tableName, ', '.join(escaped_fields), primaryKey,
            create_args_string(len(escaped_fields) + 1))  # 构造insert执行语句，？作为占位符
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (
            tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)),
            primaryKey)  # 构造update执行语句，根据主键值更新对应一行的记录，？作为占位符，待传入更新值和主键值
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)  # 构建delete执行语句，更加主键值删除对应行
        return type.__new__(cls, name, bases, attrs)  # 返回当前准备创建的类的对象、类的名字、类继承的父类集合、类的方法集合（经过以上代码处理过的总集合）


class Model(dict, metaclass=ModelMetaclass):
    """定义一个对应数据库数据类型的模板类。通过继承，获得dict的特性和元类的类与数据库的映射关系
    附加方法：以属性形式获取值，拦截私设属性
    由模板类衍生其他类时，这个模板类没有重新定义__new__()方法，因此会使用父类ModelMetaclass的__new__()来生成衍生类，从而实现ORM
    """

    # 由模板类衍生其他类时，这个模板类没重新定义__new__()方法，因此会使用父类ModelMetaclass的__new__()来生成衍生类，从而实现ORM
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        """ getattr、settattr实现属性动态绑定和获取 """
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        """ 返回属性值，默认None """
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        """ 返回属性值，空则返回默认值 """
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]  # 查取属性对应的列的数量类型默认值
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                # logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    @classmethod  # ORM框架下，每条记录作为对象返回;@classmethod定义类方法，类对象cls便完成某些操作;添加类方法，对应查表，默认查整个表，可通过where limit设置查找条件。
    async def findAll(cls, where=None, args=None, **kw):
        """ find objects by where clause. """
        sql = [cls.__select__]  # 用一个列表存储select语句
        if where:  # 添加where条件
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)  # 对查询结果排序排序
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)  # 截取查询结果
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):  # 截取前limit条记录
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:  # 略过前limit[0]条记录，开始截取limit[1]条记录
                sql.append('?, ?')
                args.extend(limit)  # 将limit合并到args列表的末尾
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args)  # 构造更新后的select语句，并执行，返回属性值[{},{},{}]
        return [cls(**r) for r in rs]  # 返回一个列表。每个元素都是一个dict，相当于一行记录

    @classmethod  # 添加类方法，查找特定列，可通过where设置条件
    async def findNumber(cls, selectField, where=None, args=None):
        """ find number by select and where. """
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]  # _num_是SQL的一个字段别名用法，AS关键字可以省略
        if where:  # 添加where字段
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)  # 更新select语句并执行，返回由dict组成的list
        if len(rs) == 0:
            return None
        return rs[0]['_num_']  # 根据别名key取值

    @classmethod  # 类方法，根据主键查询一条记录
    async def find(cls, pk):
        """ find object by primary key. """
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])  # 将dict作为关键字参数传入当前类的对象

    async def save(self):
        """ 实例方法，映射插入记录 """
        args = list(map(self.getValueOrDefault, self.__fields__))  # 非主键列的值列表
        args.append(self.getValueOrDefault(self.__primary_key__))  # 添加主键值
        rows = await execute(self.__insert__, args)  # 执行insert语句
        if rows != 1:
            logging.warning('failed to insert record: affected rows: %s' % rows)

    async def update(self):
        """ 实例方法，映射更新记录 """
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warning('failed to update by primary key : affected rows: %s' % rows)

    async def remove(self):
        """ 实例方法，映射根据主键值删除记录 """
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warning('failed to remove by primary key: affected rows: %s' % rows)
