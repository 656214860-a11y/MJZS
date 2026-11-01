# R1740：验证/基线轮——S09 白模预演补 11 条需求测试锚点（REQ09）

- **轮次类型**：验证／基线轮（只补测试锚点与基线删项，不改生产代码）。
- **测试跑了吗**：跑了任务书指定的定向测试与架构门禁，均 0 红；默认冒烟与全量安全回归本轮未运行（任务书未要求，且本轮只改测试与基线）。
- **三个基线**：默认冒烟未运行；架构门禁 `tests.architecture.test_requirement_traceability` 通过（23 条用例整体 OK）；全量回归未运行、无新增欠账。
- **欠账少了吗**：是。`维护记录/需求锚定基线.json` 删除 11 条 S09 编号；未改 `project_status.md`。

## 改动范围

| 文件 | 改动 |
| --- | --- |
| `tests/test_req_s09_anchors.py` | 新建，19 条锚点测试 |
| `tests/test_previs.py` | 仅给 `ClassifyTests`、`RoutingGateConsistencyTests` 加 `REQ-S09-11/13` docstring |
| `tests/test_previs_monitor.py` | 仅给 `ProgressTests`、`PageTests`、`DispatchTests` 加 `REQ-S09-23` docstring |
| `tests/test_white_model_identity.py` | 仅模块 docstring 加 `REQ-S09-32` |
| `维护记录/需求锚定基线.json` | 只删除 11 条 S09 编号 |
| `tasks_round/tasks_round_pending_REQ09_result.md` | 本结果文件 |

生产代码未改，未执行 git 写命令，未加 skip，未改 `docs/stages/S09_白模预演.md`（11 条实现均满足需求，无需降级为 🟡）。

## 逐条锚点与自证

| 编号 | 锚点测试 | 对应断言 → 需求原文 | 自证红的输出（临时改反实现后） | 结论 |
| --- | --- | --- | --- | --- |
| REQ-S09-11 | `tests.test_previs.ClassifyTests`（16 条） | 显式中英文标注优先、肢体互动／物件交接／快速运动／≥5 步为复杂、走位为中等、站定为简单、否定表述不算动作、信息不足中等 → “复杂度优先取分镜定稿的标注……无标注时按动作与机位文本规则自动判断……否定表述不算动作。” | 去掉否定短语剔除后：`FAIL: test_negated_action_not_complex` / `AssertionError: 'complex' != 'simple'`（16 条中 1 红） | 通过 |
| REQ-S09-13 | `tests.test_previs.RoutingGateConsistencyTests`（4 条） | 手工覆盖同时改变页面决策、调度分组和 SG-05 门禁；清除覆盖后三处一起退回自动分类 → “页面、调度与阶段门禁共用同一份有效决策……” | 关闭覆盖合并后：`AssertionError: Tuples differ: ('simple', 'complex') != ('complex', 'complex')` 等 4 红 | 通过 |
| REQ-S09-14 | `tests.test_req_s09_anchors.RoutingDispatchAnchorTests`（2 条） | 只把复杂镜头交给 Agent；简单标“无需白模，已跳过”、中等标“待线上制作／导入”；已就绪同样跳过；每次分流写 `工作流任务/白模分流记录/<时间戳>/分流结果.json` → 同条需求原文 | 对调简单／中等状态文案后：`AssertionError: '待线上制作／导入' != '无需白模，已跳过'` | 通过 |
| REQ-S09-20 | `tests.test_req_s09_anchors.StartPreconditionAnchorTests`（3 条） | 同一时刻只允许一批；`claude-desktop-app` 派发前拦下；找不到 Blender 拦下；派发前冻结 `分镜快照.json`／`调用配置.json`，此后改分镜不影响本批 → 同条需求原文 | 关闭 busy 互斥后：`ERROR: test_req_s09_20_a_second_batch_is_refused_while_one_is_running`（预期抛错但未抛） | 通过 |
| REQ-S09-21 | `tests.test_req_s09_anchors.VerifyAndWorkerAnchorTests`（4 条） | 逐镜顺序执行；可复用则记“已就绪（复用）”；否则引擎结束后必须文件存在非空、含视频流、时长误差 ≤0.5 秒；失败记失败并指向制作报告，不写完成 → 同条需求原文 | 把时长容差 `.5` 放大到 `5.0` 后：`FAIL: ... (name='wrong-duration')` / `AssertionError: True is not false` | 通过 |
| REQ-S09-22 | `tests.test_req_s09_anchors.StopAnchorTests`（3 条） | 强制停止只结束本项目登记进程；未做镜头记“已停止”；本机等待被停止时在途结果记“待核对” → 同条需求原文 | 把待核对文案改成“已强制停止”后：`AssertionError: '已强制停止' != '本机已停止等待；结果待核对'` | 通过 |
| REQ-S09-23 | `tests.test_req_s09_anchors.ProgressAndMonitorAnchorTests`（3 条）＋ `tests.test_previs_monitor` 的 `ProgressTests`／`PageTests`／`DispatchTests` | 进度只认 Blender 真实帧数；无效／缺失显示“Agent 制作中”；监视页每 5 秒刷新；手动派发开浏览器、无人值守不弹；批次结局进 `news` 队列由三虎播报 → 同条需求原文 | 把兜底文案改成“制作中”后：`Tuples differ: ('indeterminate', 0, '制作中') != ('indeterminate', 0, 'Agent 制作中')`；把 `announce` 的入队去掉后：`ERROR: test_req_s09_23_batch_result_is_queued_for_the_pet_announcer` | 通过 |
| REQ-S09-25 | `tests.test_req_s09_anchors.NotesAndEntryAnchorTests`（2 条） | 备注合并写入记录且不丢预览／工程；线上白模工具入口存在；页面能把当前镜头交给 Codex／Claude 通过 Blender 制作 → 同条需求原文 | 让 `save_previs_notes` 从空记录重写后：`ERROR: test_req_s09_25_notes_are_merged_into_the_record_and_media_is_kept` | 通过 |
| REQ-S09-32 | `tests.test_white_model_identity`（12 条） | 项目身份取 `config.json` 的 `project_id`；改名／移动不串目录；旧布局只读兼容；迁移可重复、不覆盖、失败回滚、找不到分镜整批不迁 → 同条需求原文 | 令 `project_identity` 恒返回 `None` 后：`AssertionError: '白模' != '<uuid>'`、`WindowsPath(...改名后的项目/SH001) != WindowsPath(...项目/SH001)` 等 5 红 | 通过 |
| REQ-S09-34 | `tests.test_req_s09_anchors.CompletionEvidenceAnchorTests`（1 条） | 阶段完成＝SG-05 的 `ok` 与 `started` 同时为真；`previs.json` 是否存在不算证据；没有复杂／中等镜头视为完成 → 同条需求原文 | 去掉 `started` 条件后：`AssertionError: True is not false : 白模还没开始：ok 为真但 started 为假也不算完成` | 通过 |
| REQ-S09-42 | `tests.test_req_s09_anchors.BatchPromptAnchorTests`（1 条） | 任务书只做简化白模与低分辨率预览，由 `blender --background` 后台渲染，不制作 4K 精片、不使用付费 API、不安装／卸载／移动 Blender → 同条需求原文 | 把“不制作4K精片”改成“制作4K精片”后：`AssertionError: '不制作4K精片' not found in '……只需要简化白模，制作4K精片……'` | 通过 |

## 验证命令与结果

```text
python -B -m unittest tests.test_req_s09_anchors tests.architecture.test_requirement_traceability
Ran 24 tests in 1.304s
OK

python -B run_selftests.py -k "test_previs test_previs_monitor test_white_model_identity test_req_s09"
159 条用例，5.4 秒；0 个文件有红
ALL TESTS PASSED
```

补充核对：

```text
python -B -m unittest tests.test_previs tests.test_previs_monitor tests.test_white_model_identity
Ran 98 tests in 5.895s
OK

python -B tests/architecture/test_requirement_traceability.py --find REQ-S09-11/13/14/20/21/22/23/25/32/34/42
11 条均能定位到上述测试（无“未找到锚定”输出）
```

## 备注

- 11 条需求实现均与文档一致，未触发“删测试 + ✅→🟡”分支。
- 新测试涉及 `threading` 的批次，均使用 `busy` 轮询等待并在 20 秒内收尾；未依赖本机 Blender、ffprobe 或真实用户项目。
- 临时改反实现只在自证期间发生，随后已原样恢复；`git diff` 确认生产 `.py` 无改动。

## 独立验收（Claude，主工作区）

- 主树 `test_req_s09_anchors`＋追溯门禁 24 条 OK；`run_selftests -k test_previs test_previs_monitor test_white_model_identity test_req_s09` 全绿。
- 抽查红证：把 `previs_routing.py:184` 的「无需白模，已跳过」改短 → `test_req_s09_14_...` FAIL，已还原。
- 基线冲突（车道基于旧 master）：以 HEAD 版为准只删 S09 编号，S05 11 条保留。
- 修正执行方一处 docstring：`DispatchTests` 保留原有「工作线程不再碰桌面 Blender」说明。
- 断言未动。
