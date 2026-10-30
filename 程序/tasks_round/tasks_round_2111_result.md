# R2111 合入 claude/distracted-gagarin-2ffc8e（R2110：桌面模型长任务改附件＋短指令）到 master（合并轮）

- 本轮类型：合并轮（§3）。日期：2026-10-30。合并前 master `8d1d778e`，合入分支 `claude/distracted-gagarin-2ffc8e` 的 R2110（`6da8ad4a`）。
- 冲突：无。分支改动 8 个文件（`codex_paste.ps1`、`codex_paste.py`、`desktop_idea_chat.py`、`desktop_send_choice.py`、`docs/stages/S01_剧本准备.md`、`tests/test_client_profiles.py`、新增 `tests/test_desktop_attachment_send.py`、`tasks_round/tasks_round_2110_result.md`），master 自分支起点 `8a330a78` 以来的 R2106～R2109 未碰这些文件。
- 内容：Gemini 等 `desktop-app` 桌面程序任务正文超过 8,000 字时，任务文件作为附件粘贴、输入框只放短指令（REQ-S01-70／DES-S01-70），详见 `tasks_round_2110_result.md`。
- R2110 结果文件里记的历史红项 REQ-S01-68 无锚定，已由 R2107（随 `6e73cccf` 合入）在 master 上补上，合并后不再存在。

## 验证（本轮实际运行，主目录 master 合并结果，经 `工作流任务/gui_hidden.py`）

- `run_selftests.py -k desktop_attachment_send desktop_idea_chat_desktop_paste desktop_send_ledger client_profiles codex_paste complexity_ratchet`：58 条，1 红：`test_client_profiles.test_req_s01_56_builtin_catalog_covers_every_known_client` 读到本机运行数据 `data/客户端档案.json`（git 忽略）里的 `claude-2`、`claude-3`。与 R2108 记录的同一红项一致，用例未隔离本机数据，非本轮引入；R2110 在工作树（无该数据文件）中此用例通过。断言未动。
- `smoke_test.py`（默认）：8/8 通过。
- 未运行：`--architecture` 全部门禁、全量（交提交后后台全量）；真实 Gemini 窗口里附件粘贴的端到端效果（待用户重启助手后实测）。

## 状态页核对

`git diff 8d1d778e..HEAD -- 程序/project_status.md | grep '^-' | grep -v '^---' | grep -v '当前轮次：'`（合并暂存区上运行）：

```
（空）
```

`git show HEAD:程序/project_status.md | grep -oE '^R[0-9]+' | sort -u`（合并暂存区上运行）：

```
R1036 R1200 R1208 R1212 R1213 R1242 R1248 R1251 R1253 R1265 R1381 R1386 R1387 R1388 R1389 R1390 R1391 R1393 R1394 R1395 R1396 R1399 R1400 R1401 R1402 R1418 R1420 R1440 R1507 R1538 R1541 R1606 R1607 R1608 R1609 R1610 R1611 R1612 R1613 R1614 R1615 R1616 R1617 R1618 R1619 R1620 R1621 R1622 R1623 R1624 R1625 R1626 R1627 R1629 R1630 R1635 R1691 R1693 R1776 R1777 R1778 R1779 R1782 R1783 R1802 R1803 R1804 R1806 R1807 R1808 R1809 R1810 R1811 R1812 R1813 R1814 R1816 R1817 R1818 R1819 R1820 R1821 R1822 R1823 R1824 R1825 R1827 R1828 R1830 R1831 R1832 R1833 R1834 R1836 R1840 R1841 R1843 R1845 R1846 R504
```

分支不改状态页；R2110／R2111 的轮次头另起一个补记提交。

## 提交

`dev.py commit`；未 push。
