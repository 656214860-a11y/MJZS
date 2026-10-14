# R1437 结果：清掉 Windows 全量里其余 8 条红

- 本轮属于 §3.7 **修复轮**（测试夹具／契约同步，外加一处弹窗文案缩短）。用户 2026-10-15 要求"全部修复和清理"。独立工作树分支 `codex/r1437-fixes`。
- 来源：R1436 之后 Windows 随附解释器 `run_selftests --all --safe`（581 路）的 8 条非 R1433 红。逐条原因与处理：

| 失败 | 原因（来源） | 处理 |
| --- | --- | --- |
| `test_workflow` ×2 `gate_level` | R1431 让 `claude_pasted` 调 `self.gate_level()`，测试用 `SimpleNamespace` 面板缺该方法 | 两处替身补 `gate_level=lambda: 'manual'`；断言未动 |
| `test_copy_rules.test_no_popup_goes_over_the_limit` | R1431 的 `previs_automation.py:89` 弹窗 67 字，超 45 字上限 | 文案改为"白模自动制作需后台模型：请改用 Claude Code、Codex 或 API"（39 字，同一条件、同一行为） |
| `architecture.test_todo_comment_snapshot` | R1431 后 `desktop.py` 该注释从 2811 行移到 2846 行 | 快照行号 2811 → 2846（注释文字未变） |
| `test_script_agent_delivery_paths` | R1434 有意把提示词改为"本机绝对路径"，测试仍断言旧措辞 | 断言改成新措辞；API 默认不含路径的反向断言同步改成新措辞（否则成了空断言）。强度未减 |
| `test_idea_chat` ×4 | 并非单纯大小写：R1431 统一调色板后，用户气泡色 `#dff5e3`→`#DCFCE7`、危险色 `#c62828`→`#DC2626`；选中前景色 Windows 返回大写 | 改为引用 `ui_tokens.COLORS` 并忽略大小写比较，不再写死 hex |

- 更正 R1436 的说法：`test_idea_chat` 4 条不是"Windows 大小写差异"，其中 3 条是 R1431 调色板契约变更后的陈旧断言。

## 契约变化（§2.4）

只改测试夹具／快照与一条弹窗文案；无断言被弱化或删除。

## 测试

见本轮之后补记的 Windows 全量结果。
