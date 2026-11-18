# R3269 结果：L1 基础设施层优化任务书 · 轮 2（无界增长）

## 三问

1. **轮次类型**：可靠性轮（runbook §15／AGENTS §3.11）——L1 任务书轮 2，八个无界增长与持久化缺陷治理。
2. **测试跑了吗、三个基线过了吗**：新增 `tests/test_l1_bounded_growth_r3269.py` 21 条全绿；任务书指定定向（pet_llm／file_cache／model_diagnostics／storage_maintenance／request_ledger／usage／model_router／usage_snapshot）180 条全绿、pet_ui 全套 612 条全绿；默认冒烟 9/9；架构门禁结果见验证记录。
3. **欠账少了吗**：少了。R2-a～R2-h 全部落地：两个文本/字节缓存与项目快照表改有界 LRU、`pet_llm.calls` 改 `deque(maxlen=256)`、台账 `_find` 加懒索引、诊断事件按 `log_maintenance` 30 天口径清理、熔断改单调时钟、遗留临时文件按 L-H1 在项目打开后台线程清扫、台账每日首载刷 `.bak` 且损坏报错指明路径与恢复法。

## 交付（对应任务书 R2-a～R2-h）

- **R2-a `infra/file_cache.py`**：`_TEXT_CACHE`／`_BYTES_CACHE` 改 `OrderedDict`，经 `_read_through` 新增 `limit` 参数限容 32 项（`_CACHE_LIMIT`）；命中 `_touch` 提到最近端、超限 `popitem(last=False)` 淘汰最旧。`_CACHE`（正式 JSON）与 `_DIGEST_CACHE` 按任务书不动。
- **R2-b `infra/usage_snapshot.py`**：`_snapshots` 改 `OrderedDict` 限 32 项（`SNAPSHOT_LIMIT`），`get_snapshot` 命中 `move_to_end`、插入后淘汰最旧。选「加上限」而非「切项目释放」：快照含当日内存明细，释放会丢未归档的今日行；上限只挡住「打开过的项目无限累积」这一缺陷本身。
- **R2-c `infra/pet_llm.py`＋`ui/pet_ui.py`**：`self.calls` 改 `deque(maxlen=CALLS_LIMIT=256)`；保存格式未动（L-H4）。唯一消费方 `ui/pet_ui.py` 原按 `len(calls) != _flushed` 判新调用——deque 封顶后 len 恒为 256，该判定会永久失效（连带 `ledger.save()` 停摆），改为以 `calls[-1]` 记录对象身份比较（`_flushed` 存最近记录对象而非计数），对 list／deque 同样成立。
- **R2-d `infra/request_ledger.py`**：`_find` 改走懒索引 `_entries_index()`——`{请求号: [条目…]}`，以 `(id(self.entries), len(self.entries))` 为失效标记：追加、整体替换、测试直改 `entries` 都能正确重建；`kind=None` 仍按 entries 顺序返回首个匹配，与原线性扫描语义逐条等价（含非字符串 id 不误配）。按 L-N9 只加索引，不裁剪不归档；`:217` 等对账全量遍历不受影响。
- **R2-e `infra/model_diagnostics.py`**：新增 `prune_events(directory, now, retention_days)`——只删 `*.json` 普通文件、保留期取 `log_maintenance.RETENTION_DAYS`（30 天）；`record()` 内 `_maybe_prune` 按目录每天最多清扫一次，失败静默。写入格式与文件命名不变（`test_writing_api.py:685` 的单文件断言不受影响：新事件是新文件，旧文件满 30 天才删）。
- **R2-f `infra/model_router.py`**：熔断 `opened_at` 赋值与 `elapsed` 计算由 `time.time()` 改 `time.monotonic()`（`:59`、`:76` 两处）；`opened_at` 无外部消费者（全库 grep 仅测试直接回拨），墙钟校时不再影响 open/half_open 判定。
- **R2-g `infra/temporary_sweep.py`（新模块）＋`desktop.py`**：新增 `is_stale_temporary_name`／`sweep_stale_temporary_files`／`schedule_stale_temporary_sweep`。只匹配 `<原名>.<32位十六进制>.(tmp|download|recover|partial.mp4)`（`agent.core.temporary_path` 的全部后缀），mtime 早于 24 小时（L-H1）才删；`os.walk(followlinks=False)`＋符号链接目录剔除。**落点偏离任务书点名文件的说明**：清扫代码先写在 `storage_maintenance.py`，但该文件已达模块行数上限 1000（棘轮禁抬），遂拆为独立 L1 模块 `temporary_sweep`（已登记 `_layers.py` L1、`architecture.md` L1 表、`PROJECT_MAP.md`、分支覆盖率下限 57.0）；物理删除不自写 `unlink`（删除白名单门禁），统一走 `file_cache.remove_temporary_file`。`desktop.load()` 在 `_schedule_stage_model_sync` 旁调 `schedule_stale_temporary_sweep(self.root)`——守护线程执行，遍历不在启动／UI 路径（规则 33）。
- **R2-h `infra/request_ledger.py`**：`load()` 成功后 `_refresh_daily_backup`——模块级 `_BACKUP_REFRESH` 按路径记日序（`clock()//86400`），每天第一次成功加载把台账 `shutil.copyfile` 成 `请求台账.bak`（`with_suffix('.bak')`）；文件不存在不标记、复制失败下次加载重试。损坏报错重写为 `_corrupt_message`：JSON 解析失败（`ValueError`）与结构不完整都给出台账路径、`.bak` 路径与恢复方法；`OSError` 与锁忙 `RuntimeError` 原样上抛，不误报损坏（与 R3-d 同一陷阱）。

## 测试

- 新测试 `tests/test_l1_bounded_growth_r3269.py` 21 条：缓存淘汰后再读正确、快照上限、calls 有界且最新记录恒在尾部、索引顺序与直改重建、`.bak` 每日刷新与损坏报错含路径、熔断单调时钟、诊断清理只删旧 json（含默认保留期／glob 失败／条目级失败／删除失败不计数／清扫异常吞掉／每日至多一次六个分支）、清扫只删匹配且超龄文件、清扫跑在非调用线程。
- 任务书指定命令：`run_selftests.py -k pet_llm file_cache model_diagnostics storage_maintenance request_ledger usage`（本轮扩展 model_router／usage_snapshot）——结果见验证记录。
- `smoke_test.py`：9/9 通过。
- `smoke_test.py --architecture`：结果见验证记录（合并树口径）。

## 验证记录

- `run_selftests.py -k l1_bounded_growth_r3269`：21 条 / 0 红 / 约 0.8 秒。
- `run_selftests.py -k pet_llm file_cache model_diagnostics storage_maintenance request_ledger usage model_router usage_snapshot` 及关联文件：10 个匹配文件 / 180 条 / 0 失败 / 0 跳过 / 约 264.9 秒；另 `pet_ui` 全套 612 条与本文件合并跑 633 条 / 0 红 / 55.5 秒（验证 `_flushed` 身份比较改动）。
- `smoke_test.py`：9/9 通过。
- `smoke_test.py --architecture`：**502/502 全绿**（257.1 秒；首轮 5 红逐一修复后复测，处置见下）。
- 分支覆盖率重测（`branch_coverage_report.py`，目标集＝79 关联用例＋`test_l1_reliability_r3248`＋`test_l1_bounded_growth_r3269`）：1463 条用例全过，85 模块 / 1288/2390 决策点；`model_diagnostics` 补齐六个分支用例后回到 **100%（10/10）**，`temporary_sweep` 首测 57.1%（下限按实测向下取整登记 57.0）。
- 主覆盖率基线重测（`coverage_report.py`，基线既有 9 组目标用例）：97 条全过，654 模块 / 74 有覆盖；核心路径下限全部达标（request_ledger 84.6%≥50、usage_snapshot 72.6%、keyframe 82.2%≥65、video 94.0%≥75、asset_batch 41.6%≥28、publication 89.9%≥70、automation 44.2%≥30）；runbook §11 模块数同步 653→654、84→85。

### 架构门禁首轮 5 红的处置（如实记录）

1. `usage_snapshot` 基线决策点 30≠31 → 重测覆盖率基线后消。
2. `RequestLedger` 类 665 行 > 上限 639 → `backup_path`／`_corrupt_message`／`_refresh_daily_backup` 移出类为模块级函数（`ledger_backup_path`／`_corrupt_message`／`_refresh_daily_backup`），类内索引与查找再压缩 4 行，回到上限内。
3. `storage_maintenance.py` 1032 行 > 上限 1000 → 清扫拆为新模块 `infra/temporary_sweep.py`（见 R2-g 偏离说明），storage_maintenance 复原与 HEAD 一致。
4. `model_diagnostics.py:93 entry.unlink` 违反物理删除白名单 → 改 `file_cache.remove_temporary_file`。
5. `test_round_number_continuous` 3269≠3270 → 状态页轮次头按先例临时同步为 3270（不提交，合并轮在 master 侧维护）。

## 范围与取舍说明

- `_DIGEST_CACHE` 未限容：任务书 R2-a 点名只改 `_TEXT_CACHE`／`_BYTES_CACHE`；摘要条目仅约 70 字节，量级可忽略，记为已知余量不扩大范围。
- `usage_snapshot` 选上限而非切项目释放：见 R2-b 说明；`DETAIL_LIMIT=10000` 的 deque 本就在快照内有界。
- 临时文件清扫跟随目录联接与否取决于 `os.walk` 对 junction 的识别；文件名形态（32 位 hex＋固定后缀）是硬护栏，用户命名文件不可能命中。
- `model_diagnostics` 清理挂在 `record()` 内按日节流，而非新调度器：写入方唯一、目录即所写目录，零新增跨层接线；代价是每目录每天一次 glob。
- 台账 `.bak` 为字节级副本（`copyfile`），不走 `agent.core.save`——它是灾备快照不是正式 JSON 读写路径。

## 提交

- 分支 `codex/wip-R3269`（领号 R3269，基座 wip-R3248 尖 `b55a46c9`＝master@`00e3938b`＋结果补记）。
- commit：待补记。
- 合入 master：待补记。
