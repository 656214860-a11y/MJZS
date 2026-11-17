# tasks_round_3041_result.md — 测试隐藏桌面强制执行落地＋任务书闭环补闸（R3041，任务书轮 2 修复轮）
<!-- round-evidence: {"commit_base": "08e5c10d", "credential_hits": 0, "evidence_sha256": "8619f861fdf01240", "exit": 0, "failed": 0, "passed": 136, "round": 3041, "tests": "run_selftests.py -k hidden_desktop_gate taskbook_closure rule_guard_map round_baselines auto_full_safe selftests selftests_gui_token hover_card_states notice_dialog"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮。按《测试隐藏桌面强制执行任务书.md》轮 2 执行（含用户并行增补的决策 §2 第 12–15 条「规则 35 任务书闭环补闸」，本轮一并落地）。只改根因模块与配套文档，未动其他源码。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **9/9**（8 项＋新增隐藏桌面探测）；架构门禁 **483 条**：本轮负责的门禁全绿（`test_hidden_desktop_gate` 4/4、`test_taskbook_closure` 8/8、`test_rule_guard_map` 7/7、`test_agent_doc_budget` 转绿），余 6 红 1 错逐项归因于并行车道/工作树环境（见下表），非本轮引入；affected 定向 11 模块全绿（修完状态页轮次头后 `test_round_baselines` 5/5 复绿）。全量 `--all --safe` 留轮 3（验证基线轮，用户目击验收），分支不累计欠账。
3. **project_status.md 的欠账少了吗？** 无新增欠账；历史欠账不动（范围外）。状态页轮次头已同步 3027→3042（分支同步，合并轮入 master）。

## 改动清单

| 文件 | 改动 |
|------|------|
| `scripts/gui_hidden.py`（新增，入库） | 收编自主工作区未跟踪的 `工作流任务/gui_hidden.py`（CreateDesktopW 临时桌面＋lpDesktop 注入＋输出落盘＋超时透传），新增 `--probe` 秒级探测；随 git 分发到任何工作树/干净检出 |
| `run_selftests.py` | 自包装硬闸：`_scope_has_tk()` 静态扫本轮测试文件，命中且未置 `DRAMA_HIDDEN_DESKTOP=1` 时 `_run_hidden()` 以入库 helper 重新拉起自身；helper 缺失/创建失败即中止（退出码 3），绝不直跑；`--visible` 逃生舱（默认关＋醒目警告） |
| `smoke_test.py` | 每轮 `--probe` 秒级自检（失败记冒烟失败）；本轮检查项含 `widget` 时 `_smoke_hidden()` 自包装；`--visible` 解析并透传门禁 |
| `scripts/auto_full_safe.py` | 删除「helper 缺失则可见桌面直跑」静默 fallback；改引用入库模块（随 `.wt/ci` 干净检出走）；缺失或退出码 2/3/4 记 **BLOCKED**（环境阻塞不冒充测试红、不触发红冷却）；env 预置 `DRAMA_HIDDEN_DESKTOP=1` 防双重包装 |
| `scripts/taskbook_closure.py`（新增） | 任务书闭环共享校验器（规则 35 决策 13 五项机器检查：命名/孤儿、逐条覆盖、证据/处置标记、处置确认凭据、README 建档；豁免白名单只许减少） |
| `scripts/commit_round.py` | 增 `check_taskbook_closure`：声明「任务书收尾/完成」的提交（提交信息或暂存完成文件）必须通过校验器，不合格拒绝提交（exit 5，与 `check_test_move`/`check_scope_overlap` 同链） |
| `tests/architecture/test_hidden_desktop_gate.py`（新增） | 4 条静态守护：helper 入库且含关键实现/`--probe`；run_selftests 自包装硬闸在位；smoke 自包装＋探测在位；auto_full_safe 无静默直跑降级、不再引用未跟踪运行现场 |
| `tests/architecture/test_taskbook_closure.py`（新增） | 规则 35 守卫测试：五项检查的坏/好样本自审＋真实仓库状态＋豁免白名单棘轮 |
| `维护记录/规则守卫基线.json`、`维护记录/规则守卫对照.md` | 登记规则 35 ↔ `test_taskbook_closure.py`；`rule_guard_map.py --write` 刷新对照表 |
| `selftest_scheduling.py` | **未改**。诊断中「sink 断线」系误读：调用点在 `protect_tk()` 内（selftest_scheduling.py:332），worker 每单元生效；任务书已更正（核销轮 2 第 5 条） |
| 文档 | `AGENTS.md` §4/§5 强制口径（并压缩回 16 KB 预算内：17072→15954 字节）；`runbook.md` §3 细则（含 `~/.claude/hooks/gui_test_guard.py` 废弃声明）；`architecture.md` 门禁清单登记×2；`CLAUDE.md`/`README.md` 口径同步；4 个测试 docstring 改为「运行器自动隐藏桌面执行」；`tasks_round/测试隐藏桌面强制执行任务书.md`（用户增补决策 12–15 已并入执行＋sink 事实更正） |

## 验证记录

- `scripts/gui_hidden.py --probe`：exit 0（「隐藏桌面探测 OK」）。
- 默认冒烟：**9/9** exit 0（含探测项）。
- `run_selftests.py -k hover_card_states notice_dialog`：自包装横幅＋隐藏桌面运行，11 条 **0 红**。
- `run_selftests.py --visible -k notice_dialog`：打印 `[--visible]` 警告，1 条 0 红（逃生舱可用）。
- `run_selftests.py -k auto_full_safe selftests selftests_gui_token`：自包装隐藏桌面，101 条 **0 红**。
- `smoke_test.py --affected smoke_test run_selftests auto_full_safe`：11 模块，首跑仅 `test_round_number_continuous` 红（状态页头 3027 未同步）→ 同步 3042 后 `-k round_baselines` **5/5 绿**；其余全绿。
- 新门禁：`test_hidden_desktop_gate` 4/4、`test_taskbook_closure` 8/8（先红后绿：CHECKBOX_RE 缺 MULTILINE 修后转绿）、`test_rule_guard_map` 7/7。
- 架构门禁全量两轮：475 条（9F+1E）→ 483 条（6F+1E）；本轮的体积预算红（AGENTS.md 17072B→15954B）与规则 35 无守卫红均已修复。
- commit 闸 mock 验证：`check_taskbook_closure` 触发/放行逻辑由 `test_taskbook_closure.test_declares_closure_triggers` 覆盖；坏样本拒绝路径由校验器单测覆盖（提交闸拒绝需真实提交场景，轮 3 输出首个完成文件时以真实提交验证）。

## 架构门禁剩余红项归因（均非本轮引入）

| 失败项 | 归因 |
|------|------|
| `test_round_number_continuous`（已修复后复绿） | 状态页轮次头未同步（本轮已同步 3042） |
| `test_complexity_ratchet` ×2、`test_module_size_ratchet` | 并行车道改的 `cell_hover.py`（610/1028 行）与 `ui_tooltip.py`（9 参数），非本批文件 |
| `test_shared_state_does_not_grow` | 并行车道：Pet Mixin 55 个多写者属性 > 上限 54 |
| `test_script_stages_name_only_their_approved_00_references` | 工作树缺嵌套 skill 内容（`00全流程SKILL` gitlink 未填充，环境性） |
| `test_performance_history_is_declared_as_historical_only` | 工作树缺被忽略输入 `维护记录/基准历史.json`（干净检出由 auto_full_safe 补填，环境性） |

## 备注

- 主工作区存在他方遗留的 `project_status.md` 未提交改动（并行车道），本分支同步与其互不影响，合并轮注意冲突。
- `~/.claude/hooks/gui_test_guard.py`（R1837 仓库外钩子）已废弃：职责收敛到入库硬闸，runbook §3 已声明。
- 轮 3（验证基线轮）另领号：`--all --safe` 全量＋用户目击桌面零窗口＋输出《任务完成文件》（规则 35，通过新校验器与 commit 闸）。
- 提交：`R3041: 测试隐藏桌面强制执行·轮2 硬闸落地＋任务书闭环补闸`（commit hash 见 git log）。
