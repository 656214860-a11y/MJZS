"""C08：性能用例在并发全量里变红时，串行单跑复核一次再判红（断言不变）。"""


def recheck_perf_reds(got, perf_units, runner):
    """并发池里 CPU 比率类断言会被别的用例抢慢；复核只替换性能单元的结果，
    复核后仍红才保留为红，其它单元的结果原样保留。
    """
    perf_by_name = {payload[0]: payload for payload in perf_units}
    red_perf = [perf_by_name[item[0]] for item in got
                if item[3] and item[0] in perf_by_name]
    if not red_perf:
        return got
    print('性能用例并发下有红：%s；串行单跑复核一次' %
          ' '.join(payload[0] for payload in red_perf), flush=True)
    rechecked = {item[0]: item for item in runner(red_perf)}
    for name, item in rechecked.items():
        print('  复核 %-26s %s' % (name, '仍红' if item[3] else '转绿（判为并发抖动）'))
    return [rechecked.get(item[0], item) if item[3] else item for item in got]
