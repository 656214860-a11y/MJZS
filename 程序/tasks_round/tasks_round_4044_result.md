# R4044 修复轮结果（任务卡 L4-U6）
<!-- round-evidence: {"commit_base": "45f2662b", "credential_hits": 0, "evidence_sha256": "d94d5e4205f4af8e", "exit": 0, "failed": 0, "passed": 3, "round": 4044, "tests": "run_selftests.py -k desktop_media_pages"} -->

- 轮次类型：修复轮（P0，L4-B2）。先写能复现的失败测试，再按「前置不满足走引导分支」修。
- 测试：跑了。默认冒烟 8/8；架构门禁 685/685、失败集合为空；`--affected desktop_media_pages` 通过；新用例 3/3。全量未跑（分支不累计）。
- 欠账：少一项。空项目下 08 首帧、09 白模、12 剪辑、13 交付不再落进 `go()` 的错误提示，改为「一段说明＋一颗跳到补齐步骤的主按钮」。

## 复现（改前必红）

命令（`程序/` 下，隐藏桌面）：

```
PY -B scripts\gui_hidden.py logs\l4u6-red.log . -- PY -B -m unittest tests.test_desktop_media_pages -v
```

结果 `FAILED (failures=8)`：四页各红两条（T1 落进错误提示、T2 找不到说明），T3 改前即绿，留作回归。

```
FAIL ... (page=7)  AssertionError: Lists differ: [] != ['这个项目还没有分镜 JSON，请先到第03步采用一份。']
FAIL ... (page=8)  AssertionError: Lists differ: [] != ['这个项目还没有分镜 JSON，请先到第03步采用一份。']
FAIL ... (page=11) AssertionError: Lists differ: [] != ["'NoneType' object has no attribute 'state'"]
FAIL ... (page=12) AssertionError: Lists differ: [] != ["'NoneType' object has no attribute 'state'"]
FAIL ... test_guide_and_jump_button (page=7/8/11/12): AssertionError: [] is not true : 第NN页没有说明文字
```

## 改动

- `ui/desktop_media_pages.py`
  - 新增模块级 `NO_VIDEO_NOTE`、`storyboard_missing_text()`、`_storyboard_source()`、`empty_stage_guide()`。
  - `previs()`：没有分镜 JSON 时建引导页，跳 `PAGE['storyboard']`。
  - `editing()`、`delivery()`：`studio` 为空（空项目）时建引导页，跳 `PAGE['video']`；前置满足时原有布局、按钮与置灰逻辑一字未改。
  - `editing()` 里原来那句「还没有已下载的镜头视频……」抽成 `NO_VIDEO_NOTE`，句子未改。
- `ui/desktop_storyboard_page.py`：`storyboard()` 捕获解析器的 `ValueError`（`current_source` 用它表达「前置不满足」），改走引导页；正常路径仍走 `_FirstFramePage`。
- `tests/test_desktop_media_pages.py`（新增）：T1 15 页逐个打开、页码到位、无 Tk 回调异常、四页不落错误提示；T2 四页各有说明与主按钮、点按钮后 `page_index` 变成目标页；T3 补上分镜前置后四页不再显示引导。

引导页只画「说明＋主按钮」，不建依赖前置的操作按钮，所以不存在可点的操作按钮（与卡里「置灰」等效）；12/13 在 `studio` 为空时本来也建不出控制器。

## 与任务卡的偏差（请主控知悉）

1. **测试文件名**：卡里是 `tests/test_empty_project_pages.py`，实际用 `tests/test_desktop_media_pages.py`。
   - 原因：结构门禁 STR006 要求新增跨模块测试显式登记 `test_ownership`，而 `governance/*.json` 不在卡的允许文件里；登记会改协议摘要，必须重写 `governance/structure-baseline.json`，这条改动与活跃车道 `codex/doc-g1-relane`（R4043，尚未合入）在同一处三行上真实冲突，`dev.py commit` 直接拒绝（「请错开改动位置，或待对方合入后再提交」）。
   - 改法与源码同名后，门禁按同名模块自动归属（`governance/README.md` 第 37 行），不需要任何 governance 改动，文件范围反而回到卡的允许清单内。
   - 验收命令相应把模块名换成 `tests.test_desktop_media_pages`、`--tests desktop_media_pages`，其余不变。
2. **`tests/architecture/test_platform_process_boundary.py` 行号 873→902**：插入引导分支后进程启动点下移，按既有做法（R3590）同步豁免登记行号，无行为改动。这是卡外文件，但不改 `--architecture` 必红。

## 验证

```
PY -B scripts\gui_hidden.py logs\l4u6.log . -- PY -B -m unittest tests.test_desktop_media_pages -v   # OK, 3 tests
PY -B smoke_test.py                                                                                  # 8/8
PY -B smoke_test.py --affected desktop_media_pages                                                   # 退出码 0，ALL TESTS PASSED
PY -B smoke_test.py --architecture                                                                   # 685/685 OK，失败集合空
```

## 未完成项

- 全量未跑；按 §5 由 master 合并点累计触发。
- 09 白模页在前置满足时的既有行为未动（T3 已覆盖可打开）。
- 12/13 在 `studio` 不为空但还没有下载视频时，仍走原来的提示与置灰逻辑，未改。
