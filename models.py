#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Models for user, blog, comment.
"""

__author__ = 'Michael Liao'

import time
import uuid

from orm import Model, StringField, BooleanField, FloatField, TextField


def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)


class User(Model):
    """User类映射MySQL数据库中的User表"""
    __table__ = 'users'  # 表名

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')  # 主键
    email = StringField(ddl='varchar(50)')  # 作为登录账号
    passwd = StringField(ddl='varchar(50)')  # 列
    admin = BooleanField()  # 列
    name = StringField(ddl='varchar(50)')  # 列
    image = StringField(ddl='varchar(500)')  # 列
    created_at = FloatField(default=time.time)  # 列


class Blog(Model):
    """Blog类映射MySQL数据库中的blogs表"""
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)


class Comment(Model):
    """Comment类映射MySQL数据库中的comments表"""
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)
