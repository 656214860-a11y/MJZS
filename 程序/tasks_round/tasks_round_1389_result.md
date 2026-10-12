# R1389：UI 统一入口覆盖轮 — 设计 token 内联常量棘轮门禁（test_token_boundary）

类型：修复轮（§3.2，2026-10-12）。中央轮次：1389（`.git/round-counter.json` 的 `last_claimed=1389`）。范围＝路线图 v1 §一 第 2 项「设计 token」的第二步（承接 R1388 只读审计）：给内联视觉常量加**棘轮门禁**，**不改任何生产代码**。

## 三个必答
- 本轮类型：修复轮（§3.2）——只新增架构门禁文件并同步 `AGENTS.md` §5 清单，不改生产代码／阶段／路径／分层。
- 测试：定向 `python -m unittest tests.architecture.test_token_boundary` **5/5**；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **336/336**（331→336，+5）。
- 欠账：本轮不清欠账；`1389−1386=3<5` 且未命中 §5 升级条件（无启动路径／Tk 控件生命周期／删除语义／层级登记表改动）→ **不跑全量**（最近绿全量 R1387 `tree=000477da…`、`last_full_safe_all_round=1386`）。

## 实现
新文件 `tests/architecture/test_token_boundary.py`（5 条）：
- 谓词 `hex_color_count`（字符串常量里 `#rrggbb`）与 `numeric_padding_count`（`padx/pady/ipadx/ipady` 取数字），各配 canary。
- `test_inline_hex_colors_do_not_increase`：递归扫描生产模块（排除 tests／tasks_round／维护记录／skills 与权威 `ui_tokens.py`／`ui_theme.py`／`ui_widgets.py`／`ui_icons.py`），按文件**棘轮**——计数 `>` 基线即失败，新增文件视基线 0 即违规。基线＝R1388 审计值（hex **111 处/8 文件**）。
- `test_numeric_padding_do_not_increase`：同上，数字 padx/pady **213 处/19 文件**。
- `test_authority_files_are_exempt`。
- 语义＝**只减不增**：把内联常量迁成 token 取值后，直接下调或删除对应基线即可，无需改断言。
- **未纳入棘轮（只审计、另议）**：数字 `font/wraplength/width/height` 候选 189 处/32 文件（`width/height` 部分属布局非纯视觉）。
- `程序/AGENTS.md` §5 架构门禁清单补 `test_token_boundary.py`。

## 测试契约同步（§2.4）
- 无既有断言被改；`维护记录/架构统一基数.json` 无行号平移。

## 验证
- 定向：`tests.architecture.test_token_boundary` **5/5、OK**。
- 架构：`smoke_test.py --architecture` **336/336、0 红**（131.1 秒；331→336）。
- 默认冒烟：**8/8、0 失败**。
- 全量：**不跑**（见「三个必答」；本轮无生产改动、欠账 3<5）。

## 提交
- 内容＋报告＋接力：**`c8dbdb0`**（9 files：`test_token_boundary.py`＋`AGENTS.md`＋本结果文件＋`project_status.md`＋`.agent-handoff/` snapshot／backlog／risks／work-log／validation）。

## 复盘：路线图 v1 §一 第 2 项「设计 token」
- 完成判据原文「页面是否仍内联视觉常量待审计」。本轮把「待审计」升级为「受棘轮约束」：内联 hex 与数字 padx/pady 两类**不允许新增**，为后续逐页迁移提供可测目标。
- **未做（说明理由）**：① 迁移本身（111 hex ＋ 213 padx/pady → token）按用户要求「分批、不机械替换全仓库」，留待后续按单页粒度推进；② 调色板统一（`ui_theme.py` 复用 `ui_tokens`）**可能改变视觉**，须先确认再动，本轮不擅自做。
