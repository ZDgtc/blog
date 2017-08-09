# -*- coding: utf-8 -*-

from www import config_default


def merge(defaults, override):
    r = {}
    for name, value in defaults.items():
        # 若覆盖配置与默认配置有相同项
        if name in override:
            # 若值为字典类型
            if isinstance(value, dict):
                # 递归调用自身，两个参数都为字典类型，返回值也是一个字典类型
                r[name] = merge(value, override[name])
            else:
                # 若不为字典类型，将覆盖配置的值写入r的相应项
                r[name] = override[name]
        else:
            # 若无相同项，使用默认值
            r[name] = defaults[name]
        return r


configs = config_default.configs
try:
    from www import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass
