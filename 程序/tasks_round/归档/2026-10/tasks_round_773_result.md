# R773｜静默失败可见化（可靠性轮）

## 结果

新增 L1 `diagnostic_capture`，用于在不改动现有容错语义的前提下采集可导出的现场证据：

- 降级异常保留异常类别、脱敏信息、页面、阶段、项目名/路径和当天自动打开标记；
- 记录桌面壳启动耗时与最近门禁结果；Tk 未处理异常仍合并至既有 `logs/启动错误.log`，不新建崩溃日志；
- 所有状态与 ZIP 写入经 `agent.core` 原子发布；读取使用 `agent.core.read_json`；不写项目阶段目录；
- 项目首页的唯一“导出诊断包…”动作先展示将包含的固定日志白名单，再生成单个 ZIP；不递归枚举目录，逐行脱敏 `KEY/SECRET/TOKEN/password/credential` 与 Bearer 凭据，并拒绝 `.env`、`.dpapi`、private/等受保护项。

`desktop.safe()` 与后台 `async_()` 的既有异常分支只附加采集，不改变原有提示或队列语义。新模块已登记为 L1，未引入层级盲区。

## 验证

| 命令 | 结果 |
| --- | --- |
| `python -m unittest tests.test_diagnostic_capture tests.test_confirm_gates tests.architecture.test_layers -v` | 29/29 通过 |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --architecture` | 140/140 通过 |
| `python run_selftests.py -k diagnostics secrets layers --safe` | 13 条／0 红（筛选词未匹配单数文件名，故新诊断测试已由上项直接执行） |
| `python run_selftests.py --all --safe` | 3,523 条；2 个既有红项 |

完整安全全量的两项失败均非本轮变更：R771 已存在的 `app.py:import_json` 引用了未定义的 `project_registry_gateway`；`test_perf_baseline` 的环境滚动测量为 176.8ms，超过 150ms 灾难线（最慢 429.2ms）。因此不虚报全绿，`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 保持 **769**。

## 新增回归

- 假凭据进入待采集日志后，导出的 ZIP 不含原文；同时断言从不递归扫描日志目录。
- 不依赖 Tk 的降级记录可在控件已销毁场景安全运行。
- 未处理异常写入既有 `启动错误.log`。
- `Path.rglob`/`Path.iterdir` 被禁止时，采集预览仍正常运行。

## 后续

先修复 R771 的静态名称错误并重跑完整安全全量；全量通过后方可推进完整安全基线。未执行 Git 提交；commit hash：无。
