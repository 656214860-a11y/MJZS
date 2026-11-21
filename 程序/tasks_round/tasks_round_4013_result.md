# R4013 结果：阶段文件图标重画，文件标识叠在右下角（L4-U4）
<!-- round-evidence: {"commit_base": "d5a0476c", "credential_hits": 0, "evidence_sha256": "de9a145a60b68189", "exit": 0, "failed": 0, "passed": 142, "round": 4013, "tests": "run_selftests.py -k nav_icon files_panel"} -->

## 1. 三问

- 轮次类型：功能轮（§3.1，资源类）。任务卡 L4-U4，承接缺陷 L4-B5、决策 L4-D3、默认值 L4-Q4。
- 测试跑了吗、三个基线过了吗：
  - 默认冒烟：9/9 通过（当轮实际项数 9，输出「通过：9 项」）。
  - 架构门禁：当轮实际 684 条，全 OK、退出码 0（323.9 秒，logs\l4u4_arch.txt）；与改前（R3971 同轮次头 684 条全过）相比失败集合为空、无新增。
  - 全量回归：未跑（任务书规定执行者不跑，合入后由主控按欠账规则补跑，以 `full-safe-receipts.json` 为准）。
  - 定向：`tests.architecture.test_nav_icon_size_boundary`＋`tests.test_files_panel_stages` 共 134 条全过（135.8 秒）；`smoke_test.py --affected nav_icon files_panel` 选中 3 个测试文件、全过。
- 欠账少了吗：少了。修掉 P1 缺陷 L4-B5（阶段文件图标设计不合要求），未新增欠账。

## 2. 改动文件

| 文件 | 改动 |
| --- | --- |
| `scripts/build_nav_icons.py` | 主导航渲染抽出共用函数 `_nav_glyph_image()`（渲染逻辑逐行不变，重跑后主导航 PNG 字节不变可证）；`render_stage_file_icons()` 重写：固定 31×34 画布，阶段图形与导航图标同一管线、原大小贴左上 (0,0)，右下角 (18,20) 贴 12×13 折角纸形文件标识（`_file_badge_layer()`，白底＋1px `border_default` 描边＋`border_input` 折角）；删除不再使用的 `_glyph_layer()` 与 `FILE_BADGE_CODEPOINT`。 |
| `assets/nav/*_files.png`（13 张） | 由上述脚本重新生成：统一 31×34 画布；阶段图形恢复导航图标原大小（原来缩到约一半）；角标由约 6px 孤立字形换成 12×13 折角纸形。 |
| `tests/test_files_panel_stages.py` | 新增 `StageFileIconTests` 4 个用例（T1–T4，只新增，未动既有断言）。 |
| `tasks_round/tasks_round_4013_result.md` | 本文件。 |

`tests/architecture/test_nav_icon_size_boundary.py` 未改（不需要新增断言）；`project_files.png` 与各 `<阶段>.png` 未动（重跑生成脚本后 git 无改动可证）。

## 3. 角标尺寸与位置（任务卡交付物要求写明）

- 画布：13 张统一 31×34（任务卡接口契约「画布尺寸（31×34）不变」；改前各图实为 29–31×31–35 不等的 7 种尺寸，本轮统一为契约值）。
- 阶段图形：与 `assets/nav/<nav>.png` 逐像素一致，贴画布左上 (0,0)，nav 名按 `ui.desktop_page_registry.NAV_STAGE_ICONS` 取（如 `script_structure`→`structure.png`）。
- 文件标识：折角纸形 12×13px（宽占画布宽 38.7%、高占画布高 38.2%，均在 35%–45%），贴 (18,20)，占 x∈[18,30)、y∈[20,33)，全部落在右下 50%×50% 区域（x≥16、y≥17）内；白底 `#FFFFFF`＋四周 1px 浅色描边 `#DCE3E7`＋右上角 `#CFD9DE` 折角；13 张图的差异外接矩形完全相同：(18,20)-(30,33)。
- 对照图：`logs/l4u4_icons.png`（13 组「导航图标｜新文件图标」5 倍放大，不入库，logs 已忽略）。

## 4. 界面元素可见性变化（L4-D6 要求写明）

- 13 张阶段文件图标重画：阶段图形由约一半大小恢复为满幅（与侧栏导航图标一致）；右下角文件标识由约 6px 字形换成带浅色描边的折角纸形，更醒目。图标列入口、图标张数、文件名、`IconLoader.nav_icon(win, '<阶段>_files')` 调用方式均未变；无元素被隐藏或删除。

## 5. 改前失败输出（先红后绿证据）

`PY -B scripts\gui_hidden.py logs\l4u4_red.log . -- PY -B -m unittest tests.test_files_panel_stages.StageFileIconTests -v`（退出码 1，PYTHONPATH=tests;程序 按 runbook 规定）：

```
FAIL: test_badge_diff_box_identical_across_stages
AssertionError: 7 != 1 : 画布尺寸不统一: {(31, 34), (30, 33), (31, 33), (30, 35), (29, 34), (31, 31), (30, 34)}

FAIL: test_badge_diff_box_in_bottom_right_region
AssertionError: 1 not greater than or equal to 15 : script 差异越出右半区: (1, 1, 29, 32) (画布 (30, 33))

FAIL: test_stage_graphic_identical_to_nav_icon_outside_badge_region
AssertionError: Lists differ: [(1, 1), (2, 1), (3, 1), ...] != []
: script: 角标区域外 436 像素不同，首个 [(1, 1)]

FAILED (failures=3)   # T1、T2、T3 红；T4 生成可复现，改前已绿
```

## 6. 验收命令结果

| 命令 | 结果 |
| --- | --- |
| `PY -B scripts\build_nav_icons.py` | 退出码 0；37 个图标，13 张 `*_files.png` 统一 31×34，主导航 PNG 字节不变 |
| `PY -B scripts\gui_hidden.py logs\l4u4.log . -- PY -B -m unittest tests.architecture.test_nav_icon_size_boundary tests.test_files_panel_stages -v` | 退出码 0；134 条全过，末尾 `OK`（135.8 秒） |
| `PY -B smoke_test.py` | 9/9 通过 |
| `PY -B smoke_test.py --affected nav_icon files_panel` | 选中 3 个测试文件（architecture.test_nav_icon_size_boundary、test_files_panel、test_files_panel_stages），178 秒 0 个文件有红 |
| `PY -B smoke_test.py --architecture` | 684 条全 OK（323.9 秒），退出码 0，末尾 `OK`＋「✅ 架构治理测试：tests/architecture」 |

注：unittest 两条命令按 runbook 要求带 `PYTHONPATH=tests;程序` 运行（tests 内模块以顶层名互导）。

## 7. 其他

- 测试契约：只新增用例，未删除、未放宽、未跳过任何既有断言；`test_nav_icon_size_boundary.py` 未改。
- 图标只由 `scripts/build_nav_icons.py` 生成，未手工改图；T4 证明生成结果可复现。
- 提交：`scripts/dev.py commit`，文件清单与提交号见 git log。
