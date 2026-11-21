# R4047 结果：剧本结构页按钮分区并保证主操作可见
<!-- round-evidence: {"commit_base": "130f6c70", "credential_hits": 0, "evidence_sha256": "2ffe5aba7c170fbb", "exit": 0, "failed": 0, "passed": 4, "round": 4047, "tests": "run_selftests.py -k script_page_layout"} -->

## 开头三问

- 本轮属于哪种类型：功能轮（L4 UI 契约变更，任务卡 B-L4-U7A，车道 `codex/l4-buttons-script`，基线 `130f6c70`）。本卡只领号与提交，页面实现、测试与两份 governance 登记均为上一会话已完成的工作树改动，本轮未再改其内容。
- 测试跑了吗、三个基线：跑了定向测试，`tests.test_script_page_layout` 4/4 通过（OK，EXIT=0）。改前同一测试为 `FAILED (failures=4)`（T1–T4 全红）。架构门禁 `smoke_test.py --architecture` 695 条 OK、EXIT=0，默认冒烟 `smoke_test.py` 通过，均为上一会话实测；按本卡禁止事项，本轮未重跑 `--architecture`，改由提交门禁跑 `--tests script_page_layout`。
- 欠账少了吗：没有新增欠账。`structure.json` 只补 `tests/test_script_page_layout.py` 的 `test_ownership` 一条；基线只重写 `source_commit`／`inventory_sha256`／`policy_sha256` 三行溯源字段，`violations` 集合未变。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `ui/desktop_script_pages.py` | 主操作行从等分网格末行移到内容区顶部，1280×800／880×600 下不再被裁掉；两块内容加「原剧本」「结构剧本」分区标题；两行文档下拉框右边缘按操作列最大需求宽度对齐 |
| `tests/test_script_page_layout.py` | 新增 4 条真 Tk 几何用例：主操作可见、分区标题与按钮分组、下拉框右边缘同列、空状态方位词与实际位置一致 |
| `governance/structure.json` | `test_ownership` 新增 `程序/tests/test_script_page_layout.py` 一条，targets 指向 `程序/ui/desktop_script_pages.py` |
| `governance/structure-baseline.json` | 仅 `source_commit`、`inventory_sha256`、`policy_sha256` 三行更新 |
| `tasks_round/tasks_round_4047_result.md` | 本文件 |

## 改前失败输出（先红）

改前 `tests.test_script_page_layout`（隐藏桌面执行）原文结论：

```
Ran 4 tests
FAILED (failures=4)
```

T1 主操作可见、T2 分区标题与按钮分组、T3 下拉框右边缘同列、T4 空状态方位词四条全红。

## 改后实测

命令（工作目录 `程序`）：

```
D:\漫剧制作助手\运行环境\Python\python.exe -B run_selftests.py -k test_script_page_layout
```

结果：

```
[隐藏桌面] 本轮有 Tk 测试，整轮迁到隐藏桌面运行
test_script_page_layout        4 条    5.7 秒
共 4 条用例，6.5 秒；0 个文件有错
ALL TESTS PASSED
EXIT=0
```

架构门禁（上一会话实测，本卡未重跑）：`smoke_test.py --architecture` 695 条 OK、EXIT=0。

## 命令与退出码

| 命令 | 退出码 | 结果 |
|---|---|---|
| `git rev-parse --abbrev-ref HEAD` / `git rev-parse HEAD` | 0 | `codex/l4-buttons-script` / `130f6c709d010cc60c1f9dfa014f6e26e583f2f6` |
| `git status --porcelain` | 0 | 只有 `ui/desktop_script_pages.py`、`tests/test_script_page_layout.py`、`governance/structure.json`、`governance/structure-baseline.json` 四处 |
| `python.exe -B scripts\dev.py claim` | 0 | 领到轮次 4047 |
| `python.exe -B run_selftests.py -k test_script_page_layout` | 0 | 4 条用例全过 |
| `python.exe -B scripts\dev.py commit -m "R4047: 剧本结构页按钮分区并保证主操作可见" --tests script_page_layout --agent opencode ...` | 见提交报告 | 提交门禁自动跑定向用例并生成 `tasks_round/evidence/R4047.json` |

## 未覆盖项

- 按卡面要求未重跑 `smoke_test.py --architecture`，未跑安全全量自检。
- 未 push、未 merge、未新建工作树；提交哈希见提交后 `git log -1`。
