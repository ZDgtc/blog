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


# 储存分页信息
class Page(object):
    # 参数依次为数据库内博客总数，当前页，每页显示博客数
    def __init__(self, item_count, page_index=1, page_size=10):
        self.item_count = item_count
        self.page_size = page_size
        # 计算总页数，若博客总数除以每页博客数有余数，则增加一页
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        # 若数据库中无博客，或者页数小于1
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            self.page_index = page_index
            # 当前页面显示博客的开始序列，第一页开始为0，第二页开始为每页博客数乘以页数减一，以此类推
            self.offset = self.page_size * (page_index - 1)
            # 根据当前页面显示的博客数，决定sql操作的limit值
            self.limit = self.page_size
        self.has_next = self.page_index < self.page_count
        self.has_previous = self.page_index > 1
    # 如果要把一个类的实例变成 str，就需要实现特殊方法__str__()，这里把Page变成一个字符串
    def __str__(self):
        return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' \
               % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)
    __repr__ = __str__
