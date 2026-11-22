# R4080 结果：资产管理页内操作完成后留在资产管理页（13 处写死的页码 2 改为按阶段名取页码，并立守卫）
<!-- round-evidence: {"commit_base": "5c85dd13", "credential_hits": 0, "evidence_sha256": "eab88e74b2bd8eeb", "exit": 0, "failed": 0, "passed": 141, "round": 4080, "tests": "run_selftests.py -k stage_display_boundary asset_page_services test_assets reference_wall asset_skill_batch"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮。任务卡 W4-UX-B6（队列项 UX-B6），车道 codex/ux-assets-stay，基准 5c85dd13。来源：查用户报的「发送后跳页」时读代码发现的（来源 562cdbb1），没有在真实界面上点出来过。按代码推断的现象：在资产管理页删除参考图、删除资产图、批量删除、改名、导入或移除参考图、确认背景角色、关闭参考图墙之后，以及资产批量生成结束时，页面被切到「初步分镜」。根因：这 13 处写的是 `show(2)`。页码 2 现在是初步分镜，资产管理是 4（`pet_state.PAGE_OF`）。版本库第一次提交（c00a5f87，2026-10-02）里这 13 处已经是 `show(2)`，当时页面顺序已经是「01 剧本准备、02 剧本整理、03 初步分镜、04 资产管理」，而 `desktop.py` 的 `show` 里还留着一句注释「资产详情页与资产清单页都是『03 资产管理』的子路由」——资产管理曾经排在第 03 页（页码 2），后来前面加了页面，这 13 处没有跟着改；同一文件里别的资产页调用当时已经写成 `show(PAGE['assets'])`。也就是说这个问题在有版本记录之前就存在，不是最近改出来的。另有 1 处同源的比较：`ui/asset_skill_batch.py` 里 `page_index==2` 才重画——本意是用户停在资产页时重画资产页，实际成了停在初步分镜时重画初步分镜、停在资产页时不重画。复现：先写测试，把产品改动撤掉后跑，8 条失败（见「命令与结果」）。
- （二）测试跑了吗、三个基线：定向共 20 条（三个测试模块整个跑，加 `tests.test_reference_wall` 里新增的一个类；其中本轮新增 10 条），撤掉产品改动时 8 条失败，恢复后 20 条全过；架构门禁在全部改动之后整套跑过，698 条全过（其中 2 条是本轮加在守卫文件里的）；默认冒烟没有单独跑；全量自测没跑。带界面的 `run_selftests.py -k stage_display_boundary asset_page_services test_assets reference_wall asset_skill_batch` 由提交工具在提交时跑，结果以本文件的证据行为准。
- （三）欠账少了吗：少了一条（资产页操作后被带到初步分镜，13 处调用加 1 处比较）。新立一条守卫：产品模块里再出现写死的非 0 阶段页码，架构测试会失败。没有新增欠账；没做的事见「如实说明」第（一）（三）条。

## 改了哪些文件

- ui/desktop_asset_pages.py：`delete_asset_references`、`delete_asset_image`、`delete_asset_images`、`rename_asset` 四处 `self.show(2)` 改为 `self.show(PAGE['assets'])`（本模块已有 `PAGE = pet_state.PAGE_OF`）。4 行新增、4 行删除。
- asset_reference_images.py：加 `from infra.pet_state import PAGE_OF`；`changed()` 和编辑窗口的保存回调两处改为 `app.show(PAGE_OF['assets'])`。3 行新增、2 行删除。
- ui/asset_batch.py：加导入；批量生成结束回调 `done` 里一处。2 行新增、1 行删除。
- ui/native_assets.py：加导入；`finished` 里一处。2 行新增、1 行删除。
- ui/asset_skill_batch.py：加导入；`watch` 的定时回调里 `getattr(app,'page_index',None)==2` 和 `app.show(2)` 两个 2 都改为 `PAGE_OF['assets']`。3 行新增、2 行删除。
- ui/background_characters.py：加导入；`confirm` 里一处。2 行新增、1 行删除。
- ui/asset_reference_import.py：加导入；`commit`、`remove_refs` 两处。3 行新增、2 行删除。
- ui/reference_wall.py：加导入；`_ReferenceWall.finish` 里一处。2 行新增、1 行删除。
- tests/test_asset_page_services.py：新增 `AssetPageStaysOnAssetsTests` 4 条（删除参考图、删除资产图、批量删除、改名之后重画的是资产页）。57 行新增。
- tests/test_asset_skill_batch.py：新增 `AssetSkillBatchRefreshTests` 2 条（用户停在资产页时自动导入后重画资产页；停在别的页时不动）。40 行新增。
- tests/test_reference_wall.py：新增 `FinishTests` 2 条（没有回调时回资产页；有回调时不换页）。22 行新增。
- tests/architecture/test_stage_display_boundary.py：新增守卫 `test_page_switches_do_not_hardcode_stage_page_numbers`（扫产品模块：`x.show(n)`／`x.go_page(n)` 的 n，以及和 `page_index` 比较的数，不许是非 0 的整数字面量）和它的自检 `test_literal_page_use_recognises_each_form`（5 种应报、7 种不应报的写法）。53 行新增。
- tasks_round/tasks_round_4080_result.md 是本文件。

## 命令与结果

下表里的 `-m unittest` 都是在车道的 程序 目录下、环境变量 PYTHONPATH=tests 时跑的。

| 命令 | 结果 |
| --- | --- |
| python.exe -B scripts\dev.py claim | 领到轮次 4080 |
| git diff --output=（临时补丁文件） -- （8 个产品文件），再 git apply -R （临时补丁文件） | 产品改动撤掉，工作区只剩 4 个测试文件的改动 |
| python.exe -B -m unittest tests.test_asset_page_services tests.test_asset_skill_batch tests.architecture.test_stage_display_boundary（产品改动撤掉时） | 「Ran 18 tests」「FAILED (failures=7)」：删除参考图、删除资产图、批量删除、改名 4 条「Lists differ: [2] != [4]」；停在资产页该重画却没动 1 条「[] != [4]」；停在初步分镜不该动却重画了 1 条「[2] != []」；守卫 1 条，列出 14 处（13 处 show、1 处比较） |
| python.exe -B -m unittest tests.test_reference_wall.FinishTests（产品改动撤掉时） | 「Ran 2 tests」「FAILED (failures=1)」：「[2] != [4]」 |
| git apply （临时补丁文件），再 git diff --numstat | 产品改动恢复：8 个产品文件 21 行新增、14 行删除，和撤掉之前一致 |
| 上面两条 unittest 命令（全部改动之后） | 「Ran 18 tests」「OK」；「Ran 2 tests」「OK」 |
| python.exe -B smoke_test.py --architecture（全部改动之后；进程优先级降到 BelowNormal 跑，19:36:42–19:43:21） | 「Ran 698 tests in 397.446s」「OK」「✅ 架构治理测试：tests/architecture」，退出码 0 |
| git diff --shortstat | 12 个文件，193 行新增、14 行删除（不含本文件） |

## 如实说明

- （一）本轮只换了页码的取法，13 处调用原有的判断条件一条没动。所以资产批量生成结束的两处（`ui/asset_batch.py` 的 `done`、`ui/native_assets.py` 的 `finished`）现在的行为是：批次所属项目就是当前项目时切到资产管理页，不管用户此刻停在哪一页；修复前是切到初步分镜。这是恢复原来的写法。要不要改成「用户停在别的页时不切页」是设计取舍，留给用户定（随本轮的完成汇报一起提），本轮没有做。
- （二）13 处里有行为测试的是 6 处，加那 1 处比较：`ui/desktop_asset_pages.py` 4 处、`ui/asset_skill_batch.py` 1 处（连同比较）、`ui/reference_wall.py` 1 处。其余 7 处（`asset_reference_images.py` 2 处、`ui/asset_reference_import.py` 2 处、`ui/background_characters.py` 1 处、`ui/asset_batch.py` 1 处、`ui/native_assets.py` 1 处）只有守卫覆盖：守卫保证它们不再写死数字，不验证调用时机（时机本轮没有动）。
- （三）守卫不查 0。`show(0)` 是「回到第一页」的既有写法（`desktop.py` 3 处、`ui/desktop_project_pages.py` 1 处），本轮没有动。`维护记录/基准脚本/` 下 3 处 `d.show(2)`（基准_内存长跑.py 1 处、基准_启动与页面.py 2 处）不在守卫扫的产品模块范围里，也没有动：它们量的是「第 2 页」的耗时和内存，现在量到的是初步分镜页；要不要改成按阶段名取（改了以后的数字和旧基线不可比）留给维护基准的人决定。
- （四）没有在真实界面上点过。本轮的验证都是单元级的：宿主用桩对象，`show` 换成记录页码的列表。
- （五）没有改阶段文档。在 docs/stages、docs/specs 里搜过「回到资产／跳到资产／切到资产／留在资产」和「批量（批次、生成）结束或完成后切页、刷新」这类说法，没有命中：文档没有规定这些操作之后停在哪一页，所以没有要同步的条文。没有翻既有测试的断言：资产相关的测试文件里没有钉「操作后去第 2 页」的用例。
- （六）本轮由需求受理／机动执行窗口直接写代码。按四窗口协调第 10 条，除验收窗口复核和 `verify` 外，还要加一张只读审查卡。
- （七）基准是 5c85dd13，写本文件时主干已经前移到 7ea1ddeb（R4081 合并轮）。主干这次前移改的 13 个文件和本轮的 12 个文件没有重叠；在主干上用 git grep 搜 `show(非 0 数字)`／`go_page(非 0 数字)` 和 `page_index` 与数字的比较，除本轮改掉的 13 加 1 处和基准脚本 3 处外没有别的。本轮没有把车道换到新主干上重跑。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；未 push、未 merge。
- 7 处调用只有守卫覆盖，没有行为测试（见「如实说明」第（二）条）。
- 「批量生成结束时要不要把用户带回资产页」等用户裁决，不在本轮。
- 基准脚本 3 处 `show(2)` 没有动。
