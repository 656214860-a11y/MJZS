# 当前快照

## 2026-10-12：O35 完成，继续 O36

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O34 已完成，**O35 已完成（R1360）**，下一项 O36（上下文预算从统一字符阈值升级为模型相关预估，P2／事实·建议，M）。
- O35（SKILL 引用闭包与依赖类型应明确）：`skill_registry.py`（L3）新增 `REFERENCE_SUFFIXES`／`reference_targets`（Markdown 行内链接按 markdown／other／remote／anchor 分类的纯文本解析）、`classify_dependencies`／`dependency_report`（在册技能依赖 vs 外部子模块·步骤，工具单列 tools），`external_references` 复用同一分类；`workflow_settings.py`（L4）把 `_inline_skill` 拆成 `_skill_blocks`＋`_inline_skill_report`＋`_inline_skill`（判定条件逐条等值、行为不变），每个直接引用记入闭包（inlined／duplicate／outside／missing／resource／remote／anchor／absolute），引用文件里再出现的链接记 depth=2 的 nested（不展开）／cycle（回指已加载文件）；缺失的直接 md 引用改为明确的「SKILL 引用缺失，已阻止发送」，`freeze_skills` 把闭包按技能归属汇总进请求快照 `skill_injection` 的 references 键。见 [R1360](../程序/tasks_round/tasks_round_1360_result.md)。
- 验证证据：定向 `-k skill_ skills workflow_writing stage_prompt_governance request_freeze stage_config codex_skill_sync` 241/241；新增 `tests/test_skill_reference_closure.py` 11/11；关联 `-k writing_api` 全绿；架构 `--layer architecture --all` 312/312（最终树复跑）；默认冒烟 8/8，0 红。1360 − 1356 = 4 < 5 且未命中 §5，本轮不跑全量。**上次绿全量：1356（tree 006d0295、4749/4749、425.3 秒、0 红），下一五轮欠账点 1361。**
- 渲染/环境观察（与本轮改动无关）：主树 `程序/desktop.py` 工作树为 LF，而 `.gitattributes` 钉 `程序/desktop.py text eol=crlf`，故主树 `test_line_endings` 的 victims 用例红；干净 master 工作树按 checkout 为 CRLF，同一用例 16/16 绿。提交后 blob 归一化，不影响产物。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py` 的 `receive_brief` 重复赋值删除、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`，不读取、不修改、不暂存、不覆盖；提交只点名自己的路径，且**不要把带他人改动的文件放进来**——O35 因此刻意不动 `程序/idea_chat.py`（气泡文案显示闭包留待后续）。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：中央号靠 `round_claim.py next`（R1360 已在干净 master 工作树领到，last_claimed 现为 1360）；`project_status.md` 的 `当前轮次` 须＝最新结果报告号＋1（现为 1361）。
- 提交：R1360 待提交，路径＝`程序/skill_registry.py`、`程序/workflow_settings.py`、`程序/tests/test_skill_reference_closure.py`（新）、`程序/tasks_round/tasks_round_1360_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog}.md`；门禁与提交姿势见 [work-log](work-log.md)。
- 下一步：O36——证据 `workflow_context_budget.py:3`／`37` 用 96,000 字符阈值（有无损重复段去重，不是没有限制）；建议在保留硬保护的前提下按模型窗口、输出预留、系统提示、附件、历史和 SKILL 分项估算，区分估算 token 与服务端实报 token，超限时说明主要占用及可选的拆分方案、不能静默截技能；验收：中／英／代码／图片、大小模型、四角色接力皆保留输出空间；预览与实际发送用同一快照；超限无网络请求。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑。`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
