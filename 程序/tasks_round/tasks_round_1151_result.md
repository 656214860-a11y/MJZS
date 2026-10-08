# R1151 剧本准备提示拼装去重与四角色按需注入

## §7 三问

1. 本轮类型：修复轮，仅修改 `workflow_tasks.py` 根因逻辑及相关回归测试；按用户明确授权同步两处旧测试契约。
2. 测试与基线：最小定向 20 条通过；用户指定广范围定向复跑 406 条通过（103.3 秒）；`smoke_test.py --gate` 3197 条通过（739.5 秒），汇总 9/9（含默认 8 项）；工作流受影响冒烟 9/9。适用检查通过；未把历史全量或其他轮实测计为本轮通过，未运行独立全量架构。
3. 欠账：本轮提示重复/非四角色噪音已闭环；历史欠账不变。收尾时中央轮次已推进，旧号提交被门禁拒绝；重新领号 R1154 收尾，见对应结果，不回退轮次。

## 修改与调用点

- `workflow_tasks.script_prompt` 不再附加阶段输出契约；Agent 包装层 `workflow_engines.prompt_with_settings` 与 API 的 `writing_api.reply` system 各承担一份契约。
- 删除非 Agent 分支的固定四角色规则及节奏模板注入，并删除两个失用 import；四角色启用 API 仍由 `_hollmwood_reply` 调用 `hollmwood_roles.run`。
- 生产调用点为 `desktop.start_script_workflow`（writing、agent_delivery=True）与 `writing_api.reply`（writing、默认 False）。无 storyboard 生产调用，保留原 storyboard 主体，仅移除共用尾部重复契约。
- 未修改阶段契约文案、四角色规则文案、项目接续规则、SKILL 注入策略或工具读取白名单。

## 受影响断言逐项登记

1. `tests/test_hollmwood_agent_delivery.py`：原 `test_api_task_body_keeps_existing_default_rules` 更名为 `test_api_task_body_excludes_disabled_collaboration`。旧 `assertIn('单窗口四阶段协作', prompt)` 按新契约改为 `assertNotIn`，新增 `assertNotIn('节奏模板', prompt)`；原未启用摘要断言保留。不是直接删除旧行为测试。
2. `tests/test_stage_prompt_governance.py::test_writing_references_skill_once_and_excludes_media_locks`：显式配置启用 HOLLMWOOD，原有全部断言不变，继续检验启用时角色规则与 SKILL 引用。
3. 新增 `tests/test_script_agent_delivery_assembly.py`：Agent 两种引擎、首发/续发、开关组合契约计数；真实 API reply 拼装的一条 user 与 system 合并检查；启用 API 实际到 roles.run 的规则/节奏参数检查。模型与发布器打桩，不发网络请求。

## 实跑证据

- 修复前新测试：3 个方法、7 个子测试失败。其中 5 项为真实契约重复；另 2 项是新增测试把“节奏模板”在规则说明中的提及误当模板注入，已改成精确模板标题与测试正文计数，不改变既有断言。
- 直接 unittest 加载治理测试曾因缺少 runner 的 `skip_reasons` 路径报导入错误；切换项目规定 runner 后三个文件 20 条、0 红，1.6 秒，`ALL TESTS PASSED`。
- 用户指定广范围定向首次 406 条、1 个文件红（93.8 秒）：隔离工作树的两个 gitlink 目录为空，`test_script_contract.test_the_audit_covers_every_script_skill` 缺少 script-forging / 编剧技能集。按 gitlink 对应提交从本机仓库补齐，未改源仓库或断言；失败模块复验 47 条通过（1.1 秒），指定命令完整复跑 406 条通过（103.3 秒）。日志有 Tk after 回调警告，保留原文，执行器最终退出码为 0。
- 原始日志（未纳入 Git）：`%TEMP%/R1151-before.log`、`R1151-targeted.log`、`R1151-targeted-runner.log`、`R1151-requested-selftests.log`、`R1151-script-contract-retry.log`、`R1151-requested-selftests-retry.log`、`R1151-requested-gate.log`。
- 测试在隔离工作树以同一随附解释器的绝对路径执行（`D:/漫剧制作助手/运行环境/Python/python.exe`），参数与用户命令一致。未另建运行环境或使用全局 Python。
- 初始隔离基点 f83a9fe，主树另一轮全量期间不修改其 HEAD/文件；指定定向通过后快进到 687462f，保留本轮补丁，无冲突；在该集成基点执行增量门禁。
- 历史/其他轮证据：R1150 执行器凭据 `{tree: 519f1d25ee3f80673fb8c03d3a09f569057592ae, round: 1150, seconds: 447.4, at: 2026-10-09T01:26:43}`。本轮号差为 1，未触发 §5 五轮全量；不把该凭据算成本轮或新树的全量通过。
- `smoke_test.py --gate`：139 个增量文件、3197 条用例、739.5 秒、0 红，命令退出 0；默认 8 项加增量门禁，汇总通过 9 项、失败 0 项。`--gate` 是增量门禁，包含部分架构文件，不冒称独立全量架构。
- `smoke_test.py --affected workflow`：102 条、6.1 秒、0 红；汇总通过 9 项、失败 0 项，退出 0；原始日志 `%TEMP%/R1151-affected.log`。

用户指定命令最终汇总原文（完整输出见上述原始日志）：

```text
共 406 条用例，103.3 秒；0 个文件有红
ALL TESTS PASSED

    共 3197 条用例，739.5 秒；0 个文件有红
    ALL TESTS PASSED
✅ 门禁 run_selftests.py（增量串行）：748 秒 → 0 个文件有红
通过：9 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

## 未运行项

尚未真实调用 Codex/Claude/API 模型。本轮只验拼装及执行路由，不以模拟测试冒称实机创作成功。

## §4 自审与提交

1. 验收满足：首发/续发/API 契约计数及四角色开关路由均有新测试覆盖，指定命令最终通过。
2. 范围：生产仅 `workflow_tasks.py`；测试三文件及规定收尾记录。未改用户项目、SKILL、密钥或工具权限。
3. 验证：区分首跑失败、复验、本轮增量与其他轮全量，未虚报独立全量架构或真实模型调用。
4. 新问题：未引入依赖或接口变更；删除冗余注入与失用 import，`git diff --check` 通过、凭据形态扫描 0 命中。
5. 修复轮追加审：已核对 Agent 首发/续发及 API 开关路径，无本范围内遗漏；storyboard 无生产调用，保留其原主体而不新造契约。

清理按 post-task-cleanup 技能先 dry-run，核验绝对路径均位于本轮隔离树后，删除 9 个本轮生成的 `__pycache__` 目录（11,376,804 字节，可再生成）；源码无删除。本轮日志保留为验收证据，不清理其他任务资源。分支先提交实现与报告，主树合入后补录实现 hash；不推送。
