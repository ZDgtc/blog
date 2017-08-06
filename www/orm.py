# -*- coding: utf-8 -*-

import asyncio
import logging; logging.basicConfig(level=logging.INFO)
import aiomysql


def log(sql, args=()):
    logging.info('SQL: %s' % sql)


# 创建一个连接池
@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('creating database connection pool...')
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', '3306'),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )


# 定义select操作
@asyncio.coroutine
def select(sql, args, size=None):
    log(sql. args)
    global __pool
    with (yield from __pool) as conn:
        # 从连接池获取一个cursor
        cur = yield from conn.cursor(aiomysql.DictCursor)
        # 执行sql语句
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs


# Insert, Update, Delete操作，相同的参数
@asyncio.coroutine
def execute(sql, args):
    log(sql)
    with (yield from __pool) as conn:
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?', '%s'))
            # 用于返回结果数
            affected = cur.rowcount
            yield from cur.close()
        except BaseException:
            raise
        return affected


# 用于返回__insert__语句的占位符
def create_args_string(num):
    l = []
    for n in range(num):
        l.append('?')
    return ', '.join(l)


class Field(object):

    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        # 对Model类不做处理
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # 获取table名
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        # 获取所有的field和主键名
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            # 对于Field类型的类属性，做如下处理
            if isinstance(v, Field):
                logging.info('Found mapping: %s ==> %s' % (k, v))
                # 以mappings字典保存类属性和Field的映射关系
                mappings[k] = v
                # 获取主键，并把除主键外的类属性保存到fields
                if v.primary_key:
                    # 若之前主键已赋值，会抛出错误
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        # 没有定义主键，同样会抛出错误
        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        # 从类属性中删除Field类型的属性
        for k in mappings.keys():
            attrs.pop(k)
        # 把fields保存的类属性转换为``形式，map参数第一个为函数，将参数f以`f`打印出来，第二个为list类型
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings        # 保存属性和列的映射
        attrs['__table__'] = tableName          # 保存表名
        attrs['__primary_key__'] = primaryKey   # 保存主键属性名
        attrs['__fields__'] = fields            # 保存除主键外的属性名
        # 构造默认的增删改查语句
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ','.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ','.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])


