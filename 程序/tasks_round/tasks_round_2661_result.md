# R2661 结果：每晚代码审查收口——流式回调吞错截断、死代码块、增量台账漏检删除、会话绑定落盘韧性
<!-- round-evidence: {"commit_base": "d098f24e", "credential_hits": 0, "evidence_sha256": "5783d47748739d12", "exit": 0, "failed": 0, "passed": 41, "round": 2661, "tests": "run_selftests.py -k cli_streaming selftest_incremental mutation_sample production_locks workflow_engines"} -->

## 三问

- 轮次类型：§3.2 修复轮（每晚 /simplify 审查确认的高置信问题批量收口；根因已定位，改动均在当日审查范围内）。
- 测试：已跑。定向 `run_selftests.py -k cli_streaming selftest_incremental mutation_sample production_locks workflow_engines` 41/41；`smoke_test.py --affected platform_tools --affected workflow_engines --affected selftest_receipts` 冒烟 9/9＋定向 52 文件 747 条 0 红。架构门禁未跑（未改分层/跨层/删文件，仅函数体内改动）。全量未跑（欠账口径由 `full-safe-receipts.json` 判定，本轮不到阈值）。
- 欠账变化：无新增欠账；本期审查发现的 4 处确认问题已修，其余不确定项仅记入日报待人工确认。

## 修复清单

1. `platform_tools.py::_stream_communicate_or_kill`：`return process.returncode` 之后残留一段 26 行不可达重复代码（旧函数体尾部，含不带 stream 名的旧式 pump 调用），删除；`pump` 中 `on_output` 回调改逐行 try/except——原实现一次回调异常即终结整路输出，且会连带截断 `run_registered.forward` 对运行日志文件的回写，与 docstring「回调抛异常只吞掉并继续」不符。
2. `selftest_receipts.py::incremental`：`data_moved` 只按现存文件集合比对，SKILL 说明文件被**删除**时探测不到，增量台账会把应全跑的测试判为跳过（漏检）。改为新旧键集合并比对。
3. `workflow_engines.py::save_background_session`：绑定文件 `后台引擎会话.json` 损坏（手改/半写）时 `read()` 抛 `ValueError`，会使一次已成功的后台制作在收尾处报错；同理 `save()` 落盘失败也不应把成功的一轮判失败。会话绑定是失败重试的辅助记录，损坏按空记录重建、写失败记 swallowed。
4. `scripts/mutation_sample.py::run_sites`：子进程超时 `TimeoutExpired` 未捕获会中断整个抽样；改为记 verdict「错误」继续。
5. `production_lock_fields.py`：删除从未读写的死字段 `self.tooltips`（提示已改挂 `self.hints` 的 Tooltip）。

## 未改动的审查结论（记录项，详见日报）

- `run_background` 每次后台运行都自动 resume 上次成功会话（不止失败重试），且无时效上限：服务端会话过期后 resume 必败且绑定不被清除，可能形成永久失败；含上下文污染风险。需要产品决策（resume 失败是否回退新会话、是否加时效），本轮只记录。
- `previs_automation.engine_output` 不按 stream 过滤：claude 引擎 stdout 的 JSONL 响应行会进监视页日志。展示层取舍，只记录。
- `http_client` 把 Content-Length 超限等协议错误计入主机熔断计数（`E-NET-UNREACHABLE` 口径），分类轻微失真，只记录。
- `gui_test_module` 只看直接 import（间接拉 Tk 的依赖不判 GUI 层）；`project_modules()` 对 `agent/*.py` 双扫导致裸短名（如 `core`）误映射到 `agent.core`。均为拆分前既有行为，只记录。

## 环境备注

- 本工作树检出时 4 个无 `.gitmodules` 的 gitlink 目录（`程序/reference/HoLLMwood`、`程序/skills/00全流程SKILL/AIGC创作全流程`、`程序/skills/01 剧本准备SKILL/剧本锻造`、`程序/skills/01 剧本准备SKILL/编剧技能集`）无内容，曾致 SKILL 引用解析类测试 4 文件红；从主工作区复制内容后全绿。该现象属新工作树环境限制，与本轮改动无关。
- 断言未动；测试契约未变更。
