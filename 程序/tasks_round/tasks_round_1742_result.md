# R1742：契约轮——recon_service 写入口迁到 service_contract（RECON）

任务书：`RECON_taskbook.md`（派发执行，不领号、不提交、不改 `project_status.md`／`AGENTS.md`）。
工作树：`D:\漫剧制作助手\.wt\lane_recon\程序`。解释器：`D:\漫剧制作助手\运行环境\Python\python.exe -B`。

## 三个问题

- **轮次类型**：契约迁移轮（结构治理执行口径）：只把 `recon_service` 三个写入口的返回形状收口到 L0 `service_contract`，并同步调用方、台账、棘轮测试与定向测试。
- **测试跑了吗、三个基线过了吗**：跑了。定向 68 条 0 红；`test_service_return_contract` 9/9；架构门禁 374/374、0 红；默认冒烟 8/8、0 红。
- **`project_status.md` 的欠账少了吗**：未动状态页（任务禁止）。本轮只清掉 `架构统一基数.json` 第一项的 `scope_audit_pending: ["recon_service"]`；全量安全欠账口径不在本轮授权内。

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `recon_service.py` | 引入 `UserError`／`success`；`save_request`、`save_card`、`run` 三个写入口返回 `ServiceResult`。`save_card` 的 schema 校验失败改为返回 `UserError`，不再抛裸 `ValueError`。成功时 `data` 保留原返回内容。 |
| `skill_tools.py` | `_recon_card` 改读 `save_card(...).data`；失败时抛 `ToolError(result.reason)`，保持原来异常向上冒泡后用户看到的错误文案与失败路径不变。`ToolNeedsInput` 分支未动。 |
| `desktop_writing_page.py` | 未改。`collect_recon` 原来就忽略 `save_request` 返回值，符合任务书“如继续忽略返回值则不改”。 |
| `维护记录/架构统一基数.json` | 第一项 `adopters` 增加 `recon_service`（第 22 行）；`scope_audit_pending` 改为空数组（第 35 行）。`exempt_count` 仍为 43，未新增豁免。 |
| `tests/test_recon_service.py` | 旧返回形状断言改读 `.ok`／`.data`；新增两个契约用例（校验失败返回 `UserError`、`run` 返回 `ServiceResult`）。 |
| `tests/architecture/test_service_return_contract.py` | 采用方棘轮期望集合加入 `recon_service`（第 142 行），与台账一致。 |

## 先红证据（实现前）

命令：

```text
python -B -m unittest tests.test_recon_service.SavingTests tests.test_recon_service.RequestTests -v
```

实际结果：`Ran 8 tests ... FAILED (errors=5)`。

- `test_card_lands_as_input_json_and_docs_markdown`：`AttributeError: 'dict' object has no attribute 'ok'`（`saved` 仍是 dict）
- `test_invalid_card_returns_user_error_instead_of_raising`：`ValueError: recon_card 缺少必备字段：target`（旧实现仍在抛异常）
- `test_run_returns_service_result`：`AttributeError: 'dict' object has no attribute 'ok'`（`run` 仍返回 dict）
- `test_request_roundtrip_and_target_precedence`：`AttributeError: 'WindowsPath' object has no attribute 'ok'`（`save_request` 仍返回 Path）
- `test_topic_request_without_name_falls_back_to_the_brief`：同上（仍返回 Path）

## 测试改动逐条（文件:行，改前 → 改后）

1. `tests/test_recon_service.py:349-352`
   - 改前：`saved = recon.save_card(...)`；`Path(saved['card'])`／`Path(saved['doc'])`
   - 改后：先断言 `saved.ok`，再 `Path(saved.data['card'])`／`Path(saved.data['doc'])`
   - 等价性：文件位置、schema 版本、kind、来源 URL、MD 内容断言全部保留，只把结果读取层从 dict 换成 `ServiceResult.data`，并额外要求成功标志。
2. `tests/test_recon_service.py:452-454`
   - 改前：`target = recon.save_request(...)`；`assertEqual(target, recon.request_path(root))`
   - 改后：`assertTrue(target.ok)`；`assertEqual(target.data, recon.request_path(root))`
   - 等价性：仍断言写入后返回的请求路径等于权威 `request_path()`，没有放宽路径比较。
3. `tests/test_recon_service.py:464-465`
   - 改前：`recon.save_request(root, {...})`（返回值被丢弃）
   - 改后：`saved = recon.save_request(...)`；`assertTrue(saved.ok)`
   - 等价性：原用例只验证文件效果；新增成功标志断言，属于加强。
4. `tests/test_recon_service.py:365-375`（新增）
   - `save_card(root, {'sources': []})` 返回 `UserError`、`ok is False`、`reason` 含「缺少必备字段」、卡片与人读版均未落盘。
   - 覆盖任务书第 1 条“校验失败改返回 UserError，不再抛异常”。
5. `tests/test_recon_service.py:377-388`（新增）
   - `run(...)` 返回 `ServiceResult`，`ok` 为真，`data['card']` 是 `recon_card.json`，`data['sources']==1`，卡片文件存在。
   - 覆盖第三个写入口的返回契约。
6. `tests/architecture/test_service_return_contract.py:142`
   - 改前：采用方集合不含 `recon_service`
   - 改后：加入 `recon_service`
   - 等价性：棘轮仍要求“实际 import `service_contract` 的 L2 模块集合 == 台账 adopters”，只是把本轮新采用方登记进去。
7. `维护记录/架构统一基数.json:22,35`
   - 改前：`recon_service` 在 `scope_audit_pending`
   - 改后：移入 `adopters`；`scope_audit_pending` 为空
   - 未改 `exempt_items`／`exempt_count`。

## 实现要点

- `save_request`：`return success(target)`，`data` 是原返回的 `Path`。
- `save_card`：校验问题 → `return UserError('；'.join(problems))`；成功 → `success({'card','doc','problems'})`。
- `run`：`save_card` 失败时原样返回该失败结果；成功时 `success` 包装原 7 个字段（`card/doc/problems/sources/queries/not_found/budget`）。
- `skill_tools._recon_card`：成功读 `saved.data`；失败 `raise ToolError(saved.reason)`。原 `ValueError` 在桌面页由 `async_` 的通用异常处理接住并 `notifier.error(str(e))`，在编排器由通用 `except Exception` 记为 FAILED；改用 `ToolError` 后两条路径与文案保持不变，且不会被误判为 DONE。

## 实际验证计数

| 命令 | 实际结果 |
| --- | --- |
| `python -B run_selftests.py -k recon skill_tools` | 4 个匹配测试文件／7 路工作单元；`test_recon_service` 共 48 条 + `test_skill_tools` 5 条 + `test_project_rename_reconcile` 14 条 + `test_ui_writing_recon` 1 条 = **68 条，4.9 秒，0 个文件有红**；`ALL TESTS PASSED` |
| `python -B -m unittest tests.architecture.test_service_return_contract`（`PYTHONPATH=.;tests`） | **9 条，OK**，`EXIT:0` |
| `python -B smoke_test.py --architecture` | **374 条，144.8 秒，OK，0 红**，`EXIT:0` |
| `python -B smoke_test.py`（补充 §5 每轮冒烟） | **通过 8 项，失败 0 项**，`EXIT:0` |

说明：架构输出中的 `skills/00全流程SKILL/.../check_package.py:2239 SyntaxWarning` 是既有跨仓扫描副产物，不是本轮失败；本次 374 条全绿。

## 需裁决事项

1. **失败路径的表达方式**：`_recon_card` 在 `save_card` 返回 `UserError` 后选择 `raise ToolError(reason)`，以复刻原 `ValueError` 冒泡后的用户可见效果（桌面 `notifier.error`、编排器 FAILED）。若审查方希望工具层改为返回 `{'ok': False, 'reason': ...}`，会让编排器把该工具记成 DONE，属于行为变更，需另行裁决。
2. **`save_request.data` 形状**：按任务书“data 保留原来返回的内容”，`data` 是 `Path` 而非 dict；已在测试中按 Path 断言。
3. **`save_card` 的非 dict 入参**：`artifact_schema.stamp()` 对非 dict 仍抛 `TypeError`（原行为）；本轮只把 `validate()` 的问题清单改为 `UserError`。若要求“任何校验异常都不抛”，需再明确范围。

无阻塞项；未执行任何 git 写命令、未领号、未提交、未改 `project_status.md`／`AGENTS.md`，未读写 `private\`／`.env`，未打开真实用户项目。

## 独立验收（Claude，主工作区）

- 来源：AUDIT 只读审计判定 recon_service 有写操作、非只读，需迁移。
- 主树 `run_selftests -k recon skill_tools` 全绿；`test_service_return_contract` 9 条 OK；`smoke_test --architecture` OK。
- 红证：把 `save_card` 改回 `raise ValueError` → `test_invalid_card_returns_user_error_instead_of_raising` ERROR，已还原。
- 生产调用方核对：`desktop_writing_page.collect_recon` 忽略 `save_request` 返回值，无需改；`run` 生产无调用方。
- 裁决：①`_recon_card` 失败仍抛 `ToolError`，保持编排器记 FAILED、页面报错的原行为，接受；②`save_request.data` 为 Path，接受；③非 dict 入参的 `TypeError` 维持原样，不扩大范围。
- 测试改动只把结果读取从 dict 换成 `.data` 并加 `.ok` 断言，断言未动（未弱化）。
