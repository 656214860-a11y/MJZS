# R1756：文档精简——根 CLAUDE.md 去矛盾、去重复、改陈旧事实（CLAUDEMD）

## 三个问题

1. **本轮类型**：结构治理轮（仅改根 `CLAUDE.md`，不改任何 `.py`、测试、用户数据）。用户直接指示"优化 CLAUDE.md：精简文字，删除矛盾项、重复项，只保留最准确最直接的规则"，并明确此任务由调度方亲自执行。
2. **测试与基线**：纯文档，未跑默认冒烟／全量。定向跑了引用 `CLAUDE.md` 的测试与文档门禁：`tests/test_dev_entry.py` 3/3、`tests/test_root_layout.py` 1/1、`tests.architecture.test_agents_md`＋`test_requirement_traceability` 20/20（需 `PYTHONPATH=tests`）。
3. **欠账**：无新增；不触及源码，不计源码轮。

## 改动（8026 → 5074 字节）

### 订正与实际不符的陈旧事实
- “12 个制作阶段”“`【阶段 X/12】`”“按 `01`—`12` 阶段目录”：实测 `pet_bus.STAGES` 为 **13** 个（含“分镜预演”），AGENTS.md §6 亦为 `X/13`、§2.2 为 `01—13`。阶段列表补上“分镜预演”，其余 12 处同类字样一并改正（播报前缀与 SKILL 目录两行随重复项删除）。
- “门禁链 SG-01~05”：实测 `stage_parallel.GATES` 还有 **SG-A、SG-B**（初步分镜→分镜预演→资产管理）。更正为：SG-A／SG-B 要求上游成果已就绪，SG-01～05 只拦“已开始但不完整”；“空项目放行”原先被写成对全部门禁成立，现限定为 SG-01～05（依据 R1630 的门禁语义记录）。
- “约 200 个模块”→“约 280 个顶层模块”（`程序\` 根目录 `*.py` 实测 284 个）。
- “`desktop.py`（39 万+ 字节）”：实测已拆分到 1420 行，删去该尺寸表述，只保留拆分模式。
- “`tests\architecture\` 下 100+ 个门禁”：数字随时间漂移，删去。

### 去重复（与 AGENTS.md 重复的内容改为指向权威）
- “唯一权威源”11 行大表与 AGENTS.md §2.2 重复且已漂移：压缩为最常碰的 6 条并明示完整表在 §2.2。
- 删：播报前缀行（AGENTS.md §6）、并行与重试／动态导入两行（§2.2）、五类剧本 manifest 名单（PROJECT_MAP.md）、“每轮收尾”整段（§2.6／§7）、“治理和审计按实际风险触发”（规则 25）、“不改用户项目数据”（与“数据边界”重复）、“耗时以报告为准…”免责声明、英文模板句、对 `scripts\dev.py` 子命令的逐个枚举（`dev.py` 无参自列，且旧枚举已漏 `shots`）。
- 命令块从 12 行减到 4 行（启动、`dev.py`、冒烟、`-k` 筛选），其余选项统一指向 AGENTS.md §5。

### 去矛盾
- “Claude（调度兼审查）…领号与提交”改为与现行调度总则一致：Claude 只写任务书、经 magpie 派发、独立验收、领号与提交，不亲手改产品或测试文件。
- “阅读范围见 §0”与“本入口不另设只读头部例外”两句并存、互相绕：合并为一句“顺序、范围、完成条件唯一以 AGENTS.md §0 为准”。
- 文首补一句“与 AGENTS.md 冲突时以 AGENTS.md 为准”，消除两处规则不一致时的歧义。

### 保留不动
- `scripts\dev.py` 字样（`tests/test_dev_entry.py::test_claude_md_documents_the_entry` 要求）；分层链、数据边界、“断言未动”、启动路径禁止递归扫描目录等硬规则原意不变。

## 断言未动
未触及任何测试文件；既有断言均未修改、未弱化、未跳过。

## 调度方说明（Claude）

- 用户 2026-10-20 明确指示“这个任务由你执行”，本轮 CLAUDE.md 由调度方亲自编辑，属用户授权的例外，未经 magpie 派发。
- 事实核对均来自实测：`pet_bus.STAGES` 13 项、`stage_parallel.GATES` 含 SG-A/SG-B、根 `*.py` 284 个、`desktop.py` 1420 行、`scripts/dev.py` 10 个子命令。
- 验证：`test_dev_entry` 3/3、`test_root_layout` 1/1、`architecture.test_agents_md`＋`test_requirement_traceability` 20/20（PYTHONPATH=tests）。纯文档，未跑冒烟／架构全量。
