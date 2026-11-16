# -*- coding: utf-8 -*-
"""云朵框形状配置的无界面查询规则。"""

# 四种框的名字：第 57 期第 1 条之后它们只指「用哪两个颜色、多宽」，不再是四种外形。
# 从 pet_cloud 迁到这里（R1624）：pet_cloud_timing 也要引用，留在 pet_cloud 里会与它成环。
SHAPE_CLOUD, SHAPE_PUFF, SHAPE_ROUND, SHAPE_TAG = 'cloud', 'puff', 'round', 'tag'
SHAPES = (SHAPE_CLOUD, SHAPE_PUFF, SHAPE_ROUND, SHAPE_TAG)


def normalized(shape, shapes, default):
    """返回受支持的形状名；未知值回退到默认形状。"""
    return shape if shape in shapes else default


def configured_value(shape, shapes, default, values):
    """按形状读取配置，并保证未知形状走默认值。"""
    shape = normalized(shape, shapes, default)
    return values[shape]


def text_box(width, height, pad):
    """返回留出内边距后可写字的最小文本区域。"""
    return (pad, pad, max(40, width - 2 * pad), max(20, height - 2 * pad))
