# -*- coding: utf-8 -*-
"""性能门禁与离线基准共用的绝对指标口径。"""

# 指令 3 的启动五项上限；测试不能各自复制数字。
SHOW_LOADED_PROJECT_SECONDS = 1.0
CHAT_FIRST_TEXT_SECONDS = 1.5
FIRST_EVENT_LOOP_SECONDS = 2.6
FIRST_DAY_SELECTOR_SECONDS = 1.0
AUTO_RESUME_TO_SCRIPT_SECONDS = 1.0
STARTUP_RECURSIVE_SCAN_COUNT = 0

# 三族离线基准的灾难线；已有门禁值原样迁入，未弱化。
STARTUP_FIRST_FRAME_MS = 1500.0
LONG_LIST_SCROLL_MEDIAN_MS = 150.0
MEMORY_DELTA_MB = 30.0

# R1633（阶段4 T6）本地批量／队列口径：只量我们自己代码的成本，供应商延迟与弱网是外因，不入门槛。
# 实测（2026-10-17，本机，见 tasks_round_1633_result.md）：批量首帧规划 0.47 ms／镜（200 镜约 93 ms）；
# 持久后台队列当时每项约 130 ms，几乎全是每次入队／领取外包的 agent.publication.transaction
# 要等的 4–5 次 fsync，不是目录扫描。R2192 起队列只加锁、原子替换、不等落盘：同机同一时段实测
# 入队、领取、收尾由各约 120 ms 降到约 6 ms。这两条只作退化报警，不是性能承诺。
BATCH_PLAN_PER_SHOT_MS = 5.0
QUEUE_ITEM_MS = 400.0

# R1638（阶段4 T6 余量）并发提交口径：持久队列的入队与领取都在 agent.publication 的进程级 RLock 内串行，
# 因此多线程并发提交不提高吞吐、只排队，吞吐上限约为 1／（入队＋领取）。实测（2026-10-17，本机）：
# 16 项／4 生产者／2 消费者实测 2.07 项／秒（7.7 秒）。只作退化报警（下限取观察值的一半），不是性能承诺。
CONCURRENT_SUBMIT_ITEMS_PER_SECOND = 1.0

# REL-07（性能基线轮）：发布门禁三族基线的口径。
#   冷启动：干净数据目录到首帧／首次事件循环，门槛仍用上面的 STARTUP_FIRST_FRAME_MS 与
#           FIRST_EVENT_LOOP_SECONDS，不放宽；实测值记录进 维护记录/性能基线.json。
#   长列表：约 3000 镜、2.1 万文件规模的「项目文件」停靠面板。本机三轮实测取最大
#           （2026-11-24，并行车道争用下波动超 20%，按卡面改三次取最大值）：
#           滚动中位 7.0 ms、关键字筛选整趟 34954.2 ms（含全量索引读盘＋逐行 stat，
#           每次 _apply_filters 都整趟重载）；类型筛选与关键字同走重载路径，
#           且整文件受安全串行单元 180 秒上限约束，只测关键字一趟代表筛选口径。
#           硬门槛＝实测上浮 20%：滚动中位 <8.4 ms、筛选整趟 <41945 ms；
#           填充耗时只记录不设门槛。
#   P95：打开项目／切页／保存三个本地操作各采样 P95_SAMPLE_COUNT 次取 P95 写进基线，
#        之后每次跑出的 P95 超过基线值 P95_REGRESSION_FACTOR 倍判回归。
LONG_LIST_3000_SCROLL_MEDIAN_MS = 8.4
LONG_LIST_3000_FILTER_MS = 41945.0
P95_SAMPLE_COUNT = 20
P95_REGRESSION_FACTOR = 1.2

# ── 归档指标 ↔ 契约口径对照（R2979，runbook §10 的落地表）────────────────────
# 基准历史.json 仍是「历史参考」，但下列指标名与本文件常量**同口径**，可横向比趋势；
# 名字刻意不与常量同名（test_agents_md 门禁禁止同名碰撞），对照靠这张表。
#   startup_page.first_frame_ms      ↔ STARTUP_FIRST_FRAME_MS（Desktop 构造＋首次 update）
#   long_list.*.scroll_median_ms     ↔ LONG_LIST_SCROLL_MEDIAN_MS（60 帧取中位，R2979 起探针才有）
#   startup_page.*_300_*ms／thumbs   ↔ 无契约常量：页面打开判的是 CPU 时间比（test_perf_baseline），
#                                     墙钟值只作机器忙闲旁证，不作判据
#   long_list.*.cold_ms/warm_ms/fill_ms、hotspot paths.*.first_ms
#                                   ↔ 无契约常量：只作期间趋势参考
#   内存 after_*_mb 绝对值          ↔ MEMORY_DELTA_MB 是「增量」口径，归档只存绝对值，
#                                     增量需同次记录内相减，不直接可比
