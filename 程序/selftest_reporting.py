# -*- coding: utf-8 -*-
"""自检的报告：最慢工作单元、实际跳过清单与逐单元结果行的格式化打印。"""

import selftest_env as env


def slowest_units(results, limit=env.SLOW_UNITS_LIMIT):
    """按耗时降序给出有限的工作单元摘要；不影响执行或成功判定。"""
    return sorted(results, key=lambda item: item[5], reverse=True)[:max(0, limit)]


def skip_summary(results):
    """实际跳过的用例清单：登记位不等于已跳过，只有跑起来才知道（T8 口径）。

    返回按模块与用例排序的 (模块, 用例, 原因)；工作单元是分块跑的，同一文件可能出现多次。
    """
    rows = []
    for item in results:
        for test, reason in item[7] if len(item) > 7 else []:
            rows.append((item[1], test, reason))
    return sorted(rows)


def print_unit_result(item):
    print('  %-26s %5d 条  %6.1f 秒%s' % (item[0], item[2], item[5],
                                          '  ✗ ' + str(len(item[3])) if item[3] else ''))
