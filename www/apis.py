# -*- coding: utf-8 -*-


# 定义一个APIError的基类
class APIError(Exception):
    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message


# 提示输入值错误,data为输入字段
class APIValueError(APIError):
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value: invalid', field, message)


# 提示资源未找到错误，data为资源名
class APIResourceNotFoundError(APIError):
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value: notfound', field, message)


# 提示无权限错误
class APIPermissionError(APIError):
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission: forbidden', message)