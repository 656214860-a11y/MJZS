# R4113 结果：更正 R4100 结果文件里「切到资产管理页的调用有几处」的两个数和一句话（UX-B6B，只改结果文件）
<!-- round-evidence: {"commit_base": "9be7e2d4", "credential_hits": 0, "evidence_sha256": "f315861c43ffb082", "exit": 0, "failed": 0, "passed": 16, "round": 4113, "tests": "run_selftests.py -k asset_batch_window native_run"} -->

## 开头三问

- （一）本轮属于哪种类型：更正轮，只改结果文件。卡 W6B-UX-B6B，车道目录 ux-assets-stay，分支 codex/ux-batch-stay，接在 R4100 的提交 9be7e2d4 后面（主干基线 f624a5fc）。来源：编码窗口 23:00 的只读复核（`.agent-tmp/093883fa-UX-B6B-RO.md`，结论「通过，有不阻塞的建议」）第 1、2 条建议；验收窗口 23:32 心跳要求补一笔只改结果文件的更正。产品代码、测试、阶段文档都没有动。
- （二）测试跑了吗、三个基线各是什么结果：本轮没有改代码和测试，没有「改前红」。定向——提交工具在提交时点名跑 `asset_batch_window native_run`（R4100 加用例的两个测试文件），结果记在本文件第二行的戳和 `tasks_round/evidence/R4113.json` 里。架构门禁、默认冒烟、全量自测——本轮没跑：只动了 `tasks_round` 下两个 Markdown 文件；R4100 的架构门禁结果（700 条全过）写在它自己的结果文件里，验收窗口 23:30 已在试合并后验证并登记验收，这一笔不改变那些结果所依据的任何代码。
- （三）欠账少了吗：少了一条——R4100 结果文件「如实说明」第（五）条的两个数和一句概括不准，已改准。没有新增欠账。带出一个候选项（不是本卡的欠账）：`ui/reference_wall.py` 的后台任务结束回调会把用户拉回资产管理页，已请需求机动窗口登记。

## 改了什么

只改 `tasks_round/tasks_round_4100_result.md`「如实说明」第（五）条这一行，别的行没动，第二行的机器戳没动：

| 原来写的 | 改成 | 依据 |
|---|---|---|
| 「在 ui 等产品目录里搜……共 19 处」 | 「在产品代码里（不含测试和 `维护记录` 下的基准脚本）搜……共 21 处」 | 漏数了 程序 根目录 `asset_reference_images.py` 的 2 处（第 427、570 行） |
| 「其余 15 处是用户自己在资产管理页上操作后的重画」 | 「其余 17 处里，16 处在用户操作的入口里……另 1 处是后台任务的结束回调」 | 17 处里 `ui/reference_wall.py` 第 183 行不是用户操作后的重画，见下 |

### 21 处是怎么数的

2026-11-22 23:26 至 23:27，在主仓库里对提交 9be7e2d4 用 `git grep -n -E` 搜两种写法（只读），去掉 `tests` 目录：

- `show(PAGE['assets'])` 12 处：`ui/desktop_asset_pages.py` 11 处（第 213、218、226、242、245、479、504、531、551、563、573 行），`ui/desktop_auto_flows.py` 1 处（第 243 行）。
- `show(PAGE_OF['assets'])` 9 处：程序 根目录 `asset_reference_images.py` 2 处（第 427、570 行），`ui/asset_batch.py` 1 处（第 357 行），`ui/asset_reference_import.py` 2 处（第 84、110 行），`ui/asset_skill_batch.py` 1 处（第 89 行），`ui/background_characters.py` 1 处（第 171 行），`ui/native_assets.py` 1 处（第 508 行），`ui/reference_wall.py` 1 处（第 183 行）。
- 另有 2 处在 `维护记录/基准脚本/基准_长列表.py`（第 125、131 行），是基准脚本，不算产品代码。

12 + 9 = 21。分类：本卡改的 2 处（`ui/asset_batch.py`、`ui/native_assets.py`）；本来就先判断页码的 2 处（`ui/asset_skill_batch.py`、`ui/desktop_auto_flows.py`）；其余 17 处。

### `ui/reference_wall.py` 这一处

第 175 至 184 行的 `_ReferenceWall.finish` 是候选图墙「下载并入库」后台任务的结束回调（第 195、196 行经 `self.app.async_(..., self.finish)` 调起）：有 `on_saved` 就调它，没有就无条件 `self.app.show(PAGE_OF['assets'])`。产品代码里只有一处打开图墙（`ui/desktop_asset_pages.py` 第 267 行的「候选图墙」按钮），没有传 `on_saved`；图墙窗口不是模态的（第 63、64 行 `modal=False`）。按代码推：用户在下载期间去了别的页，下载一结束会被拉回资产管理页。没有在界面上试。

它是「参考图入库」，不是 REQ-S05-24 说的「资产图片制作结束」，不在 UX-B6B 的范围里，本卡没有改。23:29 的心跳里已请需求机动窗口登记成候选项；要改的话做法和本卡一样，`tests/test_reference_wall.py` 里钉着现在行为的用例 `test_finish_without_callback_shows_the_assets_page` 要一起改（用例名取自编码窗口的复核，我没有打开那个测试文件）。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `tasks_round/tasks_round_4100_result.md` | 1 增 1 删：「如实说明」第（五）条这一行，行末注明是 R4113 的更正和原来写的是什么。第二行的机器戳和其余各行没动 |
| `tasks_round/tasks_round_4113_result.md` | 本文件 |
| `tasks_round/evidence/R4113.json` | 提交工具生成的证据文件 |

## 如实说明

- 16 处「用户操作的入口」我只核对了处数和所在文件，没有逐处读调用时机；「都是用户点了按钮以后当场重画」是编码窗口只读复核的结论。它还记了一笔：参考图导入窗、背景人物窗、参考图窗都不是模态窗口，窗口开着时用户切到别的页再在窗口里点保存，主窗口会翻回资产管理页；这是用户自己操作的结果，要不要也改成不翻页由需求机动窗口定。
- `ui/reference_wall.py` 那一处的后果是读代码推出来的，没有在界面上试，也没有写测试。
- R4100 结果文件其余各条没有重新核对；编码窗口的复核说其余内容和代码一致。
- 验收窗口 23:30 登记验收时依据的是提交 9be7e2d4；这一笔叠在它上面，差异只有上表三个文件，都在 `tasks_round` 下。
- 没有新建工作目录；测试进程降到 BelowNormal 优先级；没有推送，没有合并。

## 命令与退出码

工作目录除注明外都是车道的 `程序`；时间是 2026-11-22 本机时钟。

| 命令 | 退出码 | 结果 |
|---|---|---|
| 主仓库里 `git grep -n -E` 搜两种写法（对提交 9be7e2d4，只读，23:26 至 23:27） | 0 | 12 处加 9 处，另有基准脚本里 2 处，见上 |
| `git status --short`（23:34，改动之前） | 0 | 无输出；HEAD 是 9be7e2d4，没有进行中的合并 |
| `python.exe -X utf8 -B scripts\dev.py claim`（23:35） | 0 | 领到轮次 4113 |
| 提交工具点名 `asset_batch_window native_run` | 见第二行的戳 | 提交时由工具跑 |

## 未覆盖项

- 未跑架构门禁、默认冒烟和全量自测（本轮只改两个 Markdown 文件；用户 2026-11-22 19:52 决定验证期间不跑全量）。
- `ui/reference_wall.py` 那一处没有改，等需求机动窗口登记和排期。
- 未 push、未 merge、未改主工作区；复核、合入归验收窗口。

## 提交

本文件随 R4113 的提交一起入库（分支 `codex/ux-batch-stay`）。写本文件时提交号还没有产生，提交号见 `git log` 和会话接续记录里推进预备窗口一节。
