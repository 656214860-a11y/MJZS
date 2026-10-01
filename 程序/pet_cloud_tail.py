# -*- coding: utf-8 -*-
"""云朵框尾巴的无界面曲线计算。"""

TAIL_BULGE = 0.07
TAIL_STEPS = 5
TAIL_BASE = 16
TAIL_CURVE_MAX = TAIL_BASE * 0.6


def _side_curve(start, end, opposite, bulge=TAIL_BULGE, steps=TAIL_STEPS):
    """返回从 start 到 end、背离 opposite 的二次曲线折线。"""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
    nx, ny = -dy / length, dx / length
    mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    if (opposite[0] - mid[0]) * nx + (opposite[1] - mid[1]) * ny > 0:
        nx, ny = -nx, -ny
    curve = min(abs(bulge) * length, TAIL_CURVE_MAX)
    control = (mid[0] + nx * 2.0 * curve, mid[1] + ny * 2.0 * curve)
    points = []
    for index in range(1, int(steps) + 1):
        t = index / float(steps)
        u = 1.0 - t
        points.append((u * u * start[0] + 2 * u * t * control[0] + t * t * end[0],
                       u * u * start[1] + 2 * u * t * control[1] + t * t * end[1]))
    return points


def tail_points(base_a, base_b, tip, bulge=TAIL_BULGE, steps=TAIL_STEPS):
    """返回由两条向外弯曲边组成的尖角尾巴轮廓。"""
    return ([tuple(base_a)] + _side_curve(base_a, tip, base_b, bulge, steps)
            + _side_curve(tip, base_b, base_a, bulge, steps))
