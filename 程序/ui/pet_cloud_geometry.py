# -*- coding: utf-8 -*-
"""云朵框绘制所用的无界面几何运算。"""


def rounded_parts(x0, y0, x1, y1, radius):
    """把圆角矩形拆成矩形和圆形图元。"""
    radius = float(max(1.0, min(radius, (x1 - x0) / 2.0, (y1 - y0) / 2.0)))
    return [('rect', x0 + radius, y0, x1 - radius, y1),
            ('rect', x0, y0 + radius, x1, y1 - radius)] + \
           [('oval', cx, cy, radius) for cx, cy in ((x0 + radius, y0 + radius), (x1 - radius, y0 + radius),
                                                    (x0 + radius, y1 - radius), (x1 - radius, y1 - radius))]


def square_parts(width, height, round_ratio):
    """按给定圆角比例生成占满主体的方框图元。"""
    radius = max(3.0, round_ratio * height)
    return rounded_parts(0.02 * width, 0.02 * height, 0.98 * width, 0.98 * height, radius)


def shape_root(width, height, span_x, span_y):
    """返回尾巴在云身中的根部坐标。"""
    return (width * span_x, height * span_y)


def shift_part(part, dy):
    """将一个图元整体沿 y 轴移动。"""
    if not dy:
        return part
    kind = part[0]
    if kind == 'oval':
        return ('oval', part[1], part[2] + dy, part[3])
    if kind == 'ellipse':
        return ('ellipse', part[1], part[2] + dy, part[3], part[4])
    if kind == 'rect':
        return ('rect', part[1], part[2] + dy, part[3], part[4] + dy)
    return ('poly', [(x, y + dy) for x, y in part[1]])


def _inside_polygon(points, x, y):
    """射线法判断点是否位于多边形内。"""
    inside = False
    total = len(points)
    for index in range(total):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % total]
        if (y0 > y) != (y1 > y):
            if x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
                inside = not inside
    return inside


def inside_parts(parts, x, y):
    """判断坐标是否落在任一圆、椭圆、矩形或多边形图元内。"""
    for part in parts:
        kind = part[0]
        if kind == 'oval':
            _kind, cx, cy, radius = part
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                return True
        elif kind == 'ellipse':
            _kind, cx, cy, rx, ry = part
            if rx > 0 and ry > 0 and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                return True
        elif kind == 'rect':
            _kind, x0, y0, x1, y1 = part
            if x0 <= x <= x1 and y0 <= y <= y1:
                return True
        elif _inside_polygon(part[1], x, y):
            return True
    return False


def inflate(part, pad):
    """按图元类型向外扩展 pad 像素。"""
    kind = part[0]
    if kind == 'oval':
        return ('oval', part[1], part[2], part[3] + pad)
    if kind == 'ellipse':
        return ('ellipse', part[1], part[2], part[3] + pad, part[4] + pad)
    if kind == 'rect':
        return ('rect', part[1] - pad, part[2] - pad, part[3] + pad, part[4] + pad)
    points = list(part[1])
    cx = sum(x for x, _y in points) / float(len(points))
    cy = sum(y for _x, y in points) / float(len(points))
    span = max(8.0, sum(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for x, y in points) / float(len(points)))
    scale = 1.0 + pad / span
    return ('poly', [(cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in points])
