# R1624 出口脚本（静态＋架构＋冒烟）与两处拆分回归修复（Q10）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第一批 Q10）。
- 三基线：默认冒烟 **8/8**（本轮 `exit` 步骤 1 实测）；架构门禁 **356 项**（与上轮同数、不降；本轮按 AGENTS §5 去重未重复单跑，定性由 post-commit 全量覆盖）；全量安全全量**欠账未清**（见下节）。
- 欠账：本轮改源码，`project_status.md` 全量欠账计数 +1；d8d0fc5（R1623）的后台全量已跑，**退出码 1、未写绿凭据**。

## 做了什么

**1）Q10 出口脚本：复用 `程序/scripts/local_ci.py`，新增 `exit` 模式**

规则 28「一个动作一个入口」要求不另起第二套 CI。`local_ci.py` 本来就由根目录 `本地CI.cmd` 调用，本轮给它加一条机器可判定的出口：

| 步骤 | 内容 | 目的 |
| --- | --- | --- |
| 1 | 默认冒烟（`smoke_test.py`，8 项） | 最基本可用性 |
| 2 | 静态门禁（8 个 unittest 目标） | 秒级快速失败 |
| 3 | 架构门禁（`smoke_test.py --architecture`） | 分层／契约／棘轮 |

- 静态门禁单列在前是为了**快速失败**：无效转义、未定义名、裸 `print`、模块／函数行数上限、静默吞异常、TODO 快照、跳过项卫生，命中即退出，不必等完 3 分钟的架构全跑。
- 静态门禁 = `test_static_hygiene`／`test_print_ratchet`／`test_module_size_ratchet`／`test_function_size_ratchet`／`test_silent_exception_ratchet`／`test_todo_comment_snapshot`／`test_skip_hygiene`，**外加本轮补入的 `tests.test_static_names`**（理由见下节：它就是本轮抓出 NameError 的那道门，不该只在全量里跑）。
- `本地CI.cmd` 只加一行 usage 注释；退出码非 0 即失败（`main()` 已按步骤聚合）。
- 实测：约 4 分钟，步骤 1／2 绿，步骤 3 唯一红＝全量欠账账簿项（`test_round_baselines.test_full_safe_all_is_required_after_eight_source_rounds`：R1620 起改过 `tests/architecture/_layers.py`＝风险路径，宽限耗尽后欠一次全量），**退出码 1**——「非 0 即失败」正是要与不要的分界，已按设计生效。

**2）修 R1621 拆分引入的 NameError（云朵弹不出来）**

`pet_cloud_timing._fade_in`（R1621 从 `pet_cloud.Cloud` 原样迁出）用了 `SHAPE_ROUND`，但该模块既没定义也没导入它。`_fade_in` 是 `Cloud.show` 的必经一步，所以**每次弹云都抛 NameError**：对话框、贴纸、招呼、进度气泡全部打不开（用户侧看到的是「点了没反应」，因为异常发生在 `show` 内部、外层只兜 TclError）。

d8d0fc5 的后台全量实测：`test_pet_ui` 32 个分片共约 130 条红**全部**由它引起；`test_static_names.test_every_module_defines_the_names_it_uses` 报的也是同一处（`pet_cloud_timing.py：_fade_in 里用了没定义的 SHAPE_ROUND`）。这与 R1608 的 `save_bytes`→`save_file` 是同一类问题：机械拆分后名字没跟着搬。

修法（单一来源、不引入环）：四个形状名 `SHAPE_CLOUD／SHAPE_PUFF／SHAPE_ROUND／SHAPE_TAG／SHAPES` 从 `pet_cloud.py` 迁到 `pet_cloud_shape.py`（本来就是形状规则模块，L4），`pet_cloud.py` 改为从那里导入、继续按原名转出（`pet_cloud.SHAPE_ROUND` 等公开名与取值不变），`pet_cloud_timing.py` 从 `pet_cloud_shape` 导入 `SHAPE_ROUND`。`pet_cloud.py` 因此少 2 行（1900 上限只许下降，未受影响），`pet_cloud_shape.py` 增 6 行（无上限登记）。

**3）修 R1620 拆分打断的补丁点**

`workflow_note_text` 与它依赖的 `markdown_document` 一起迁进了 `skill_panel_support.py`，但 `tests/test_skill_notes.py` 仍 `patch.object(skill_panel, 'markdown_document')`：补丁打在被**转出**的名字上，而调用点在 `skill_panel_support` 自己的全局命名空间里解析，于是补丁不生效、真去读磁盘，`SkillNotesTests.test_workflow_note_hides_frontmatter_before_adding_label` 红。

修法：补丁改打在定义处 `skill_panel_support.markdown_document`，断言与行为一字未改，调用仍走 `skill_panel.workflow_note_text`（顺带证明转出路径仍是可用入口）。为确认不是孤例，另写脚本扫描全部测试的 `patch.object(模块, '名字')`，与本轮 6 个新模块的顶层名字求交：只有 `markdown_document`（已修）与 `program_of`（调用点仍在 `skill_panel.py`，补丁有效）两处，无同类漏网。

## 验证（本轮实跑）

| 项 | 结果 |
| --- | --- |
| `tests.test_pet_ui`（全部 598 项） | **OK**，76.5 秒 |
| `tests.test_skill_notes` + `tests.test_static_names` | **OK**，22 项 |
| 定向门禁 12 个文件（静态卫生／行数棘轮×2／无环导入／分层／门面清单／print 棘轮／导入错误边界／行尾／pet_cloud 契约×2／静态名字） | **OK**，58 项，19.8 秒 |
| `tests.test_desktop_startup_perf` 单跑 | **OK**，14 项，15.6 秒 |
| 自写 AST 未定义名扫描（等价 `test_static_names` 口径，覆盖 `程序/*.py` 全部生产模块） | **0 命中** |
| `local_ci.py exit` 链路 | 步骤 1／2 绿，步骤 3 仅账簿项红，退出码 1（设计如此） |

## 诚实边界

- 本轮**没有**用 `--all --safe` 全量当验收：全量由 post-commit 后台补跑，结果以 `.git/auto-full-safe-result.json` 与 `程序/logs/auto_full_safe.log` 为准；本轮提交后会自动触发（R1620–R1623 改过风险路径 `tests/architecture/_layers.py`，`full_safe_auto_due` 为真）。
- 架构门禁本轮未重复单跑（AGENTS §5：跑 `--all --safe` 的轮次不再单独跑 `smoke_test.py --architecture`）；步骤 3 的那条红是**账簿项**（欠全量），不是代码红。
- `test_desktop_startup_perf`（首日选择框须 1 秒内可见）在 d8d0fc5 的并发全量里红、单跑 14/14 绿：判为**并发负载抖动**（全量在 8 路并行池之后串行跑它，当时另有并发自检），非本轮代码；但该用例挂在 1 秒预算上，属于「并发＋慢机」敏感项，仍是风险（见交接 risks）。
- 补丁点审计只覆盖 `patch.object(module, 'name')` 一种写法，`patch('module.name')`、`setattr` 注入、`unittest.mock.patch.multiple` 未覆盖。
- 本轮未实机点按验证云朵恢复（GUI 会话在本环境不稳定），结论限于测试进程内 598 项全绿；未联网、未跑真实任务。

## 下一步

R1610 清单余下：Q11（数据模型字段字典、任务状态与尝试链说明、部署 runbook）、Q12（辅助依赖清单与解释器 alpha→稳定版迁移计划）。
