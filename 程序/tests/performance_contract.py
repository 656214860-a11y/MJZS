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
