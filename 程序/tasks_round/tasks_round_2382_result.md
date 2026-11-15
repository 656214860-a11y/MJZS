# R2382 结构治理轮·执行（历史文档归档）

- **本轮类型**：结构治理轮·执行（AGENTS.md §3.3），子场景「执行」——归档已停更的历史文档，不新增功能、不改用户数据。
- **测试跑了吗**：跑了 `test_root_layout`、`test_app_metadata`、`test_line_endings` 共 22 条用例，全部通过（断言未弱化，仅同步路径定位）。
- **欠账少了吗**：无欠账变化（纯文档/移动，未改生产代码，不计源码轮）。

## 改动内容

按诊断报告 `程序/维护记录/项目整理诊断_20261113.md` 第 2 批执行，将三类已停更的历史文档用 `git mv` 归档到 `程序/tasks_round/归档/2026-11_历史文档/`，git 历史完整保留：

| 来源 | 数量 | 归档目标 |
|---|---|---|
| `.agent-handoff/`（根目录） | 29 | `agent-handoff/` 子目录 |
| `程序/HANDOFF*.md` | 9 | 直接放入 |
| `程序/crud_audit_20260926.md` | 1 | 直接放入 |

## 同步更新的活跃引用（避免死链）

1. `程序/distribution_manifest.md`：删除已移动的 `crud_audit_20260926.md`、`HANDOFF_*.md`、`.agent-handoff/**` 三个「必须排除」条目。
2. 根 `AGENTS.md`：补注 `.agent-handoff` 已归档至新位置。
3. `程序/project_status.md`：更新活跃待办区 `.agent-handoff/stage-eval-stage5.md` → 新路径。
4. `程序/维护记录/优化待办队列.md`、`程序/说明/账户会员云端立项前清单.md`：同步 `stage-eval-stage5.md` 引用。
5. `程序/tests/test_root_layout.py`：从 `ALLOWED` 删除 `.agent-handoff` 根入口（目录已移走，契约同步）。
6. `程序/tests/test_app_metadata.py`：`GLOSSARY.md` 标题校验路径从 `ROOT/.agent-handoff/GLOSSARY.md` 改为归档新路径。

## 保留不动的历史引用（不倒改历史）

- `程序/project_status.md:41,43`：2026-10-16 历史条目的 `.agent-handoff` 引用（当时的事实）。
- `程序/AGENTS.md:286`：规则陈述「不再写 `.agent-handoff/`」（行为规范，非路径引用）。
- `程序/tasks_round/R1446_name_audit.md`、`tasks_round_2326_result.md`：历史轮次结果，保留原始证据。

## 未做（按用户选择）

- 第 1 批未跟踪文件（`工作流任务/` 705 文件、重复图标、空目录）未处理——它们只存在于主 checkout（`D:\漫剧制作助手`），不在本 worktree，留待用户手动归档。
