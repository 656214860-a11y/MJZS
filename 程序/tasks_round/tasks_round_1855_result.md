# R1855 结果：写 4 页高危路径评审说明（验证/基线轮）

- 三问：本轮是 §3.10 验证/基线轮：只读代码、写评审文档，未改 `.py`；测试见“验证”；`project_status.md` 欠账未变（分支不写状态页）。
- 计划来源：vibe coding 体检计划批次 3；队列无对应 ID。

## 产出
新目录 `docs/review/`，给用户本人审阅：
- `README.md`：用途和阅读口径（“推断”“无测试”的含义）。
- `01_阶段启动与产物发布.md`、`02_阶段完成判定.md`、`03_回收删除.md`、`04_三虎续跑台账.md`：每页包含时序（带 `文件:行`）、失败模式表（现状／证据／测试）、建议跟进。

同步：`docs/README.md` 加一句目录说明；`distribution_manifest.md` 把 `程序/docs/review/**` 列为开发文档（发布清单门禁要求）。

## 方法
四条路径各派一个只读子代理追踪调用链，我按源码抽查了影响最大的结论再写入：
- 总线幂等键不含时间（`pet_bus.py:86-90`），pump 时去重（`:236`）；
- `ExecutionControl` 默认 3600 秒，监管线程停止后不结束子进程（`desktop_automation_service.py:413-444`）；
- `_move_record` 用 `shutil.move`（`storage_maintenance.py:141`）；
- `storyboard_recycle_service.recycle_files` 自带一套回收逻辑；
- 结构剧本两套完成口径（`skill_orchestrator.py:63-64` 对 `stage_completion_service.py:610`）；
- `resume_record` 遇到读不到的 queued 记录返回 None（`asset_batch_execution.py:71-82`）。

其余条目按子代理给出的行号写入；没跑过复现的一律标“推断”。

## 评审中发现、值得优先处理的问题（本轮未修，待用户拍板）
1. 回收删除：文件被占用时，`shutil.move` 退回为“复制＋删源”，目录可能被删掉一半（03 页）。
2. 资产续跑：项目移动后，queued 资产会被重新提交；批次台账损坏时被当作空台账。两种情况都可能重复扣费（04 页）。
3. 完成判定：同一阶段、同一文案的第二次完成事件可能被总线去重吞掉；三虎路径不查结构剧本清单（02 页）。
4. 引擎：监管期限（1 小时）短于引擎超时（2 小时），普通取消不结束子进程（01 页）。
5. 三虎：残留的 running 状态会让自动推进一直卡住（04 页）。

## 验证
- `run_selftests.py -k test_distribution_selfcheck test_agents_md test_requirement_traceability`（隐藏桌面）：23 条，仅 1 条红，即已知环境红 `test_agents_md.test_performance_history_is_declared_as_historical_only`（未跟踪的 `维护记录/基准历史.json`）。
- 默认冒烟 `smoke_test.py`：通过 8 项，失败 0 项。全量在 R1856 跑。

- 已提交：见提交记录。未 push。
