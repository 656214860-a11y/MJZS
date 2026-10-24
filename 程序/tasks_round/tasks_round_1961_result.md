# R1961：功能轮——三虎猫爪移到图像右侧竖向排列，内容框上移

## 三个问题

- 轮次类型：功能轮（UI 布局调整，用户明确要求）。
- 测试：默认冒烟 8/8 通过；定向 25/25 通过；受影响模块门禁 1302 条中 3 个红文件均已在基线复现（非本轮引入）。架构门禁与全量安全回归本轮未触发、未运行。
- 欠账：未新增欠账；`project_status.md` 的既有待办与本轮无关。

## 改动内容

- 三个猫爪按钮从三虎图像**下方横排**改为**右侧竖排**：绘制画布 16×54（含 2px 弧余量），`place` 到头像右沿再往右 `PAW_COL_GAP`（10px）。
- `PAW_COL_GAP = PAW_HIT_SIZE//2 - PAW_COL_WIDTH//2`：36px 命中区比 16px 猫爪列每侧宽 10px，列两侧间距都取 10px，命中区左沿正好贴住头像右沿、右沿正好贴住等级小字左沿，任何点击都不会被头像或小字截走。
- `PATCH_X` 由 -76 左移到 -108（头像给右侧猫爪列让位）；`HEAD_PAD` 相应放宽到 164，标题文字仍不压到三虎整簇。
- `PATCH_ROOM` 由 86 降到 72（旧：头像 48 + 爪下 2 + 命中区 36；新：命中区从标题行顶排到 72）。标题行矮 14px，**下方内容框随之上移 14px**。
- 命中区竖向重叠但三只爪仍各有一个 32×32 承接区（`CONTROL_HIT_MIN`=36，实际 36×36），Tab 顺序与键盘回车/空格不变；点击按屏幕纵坐标取最近的爪（`paw_nearest_at_root` 改用 y）。
- 绘制不变：`paw_parts`/`paw_dy` 未动，中间那只爪仍保留 2px 的下坠弧。

## 改动文件

- `程序/pet_ui.py`：导入清单换新名（PAW_COL_*／PAW_STEP）。
- `程序/pet_ui_support.py`：新增 PAW_COL_WIDTH／PAW_COL_HEIGHT／PAW_COL_GAP／PAW_COL_X／PAW_COL_Y，重定义 PATCH_X／PATCH_ROOM／HEAD_PAD；PAW_ARC 定义前移。
- `程序/pet_ui_view.py`：`_build_paws` 改为竖排命中区；`draw_paws` 竖向绘制与竖向焦点框；`paw_at`／`paw_nearest_at_root`／`paw_click`／`paw_hover` 改用纵坐标。
- `程序/tests/test_pet_ui.py`：`_Point` 改为只带 y；猫爪位置/重叠/弧线/点击测试同步竖向几何。
- `程序/tests/test_ui_batch9_pet_accessibility.py`：命中区中心与点击采样改为纵向。

## 验证

- 定向（经 `工作流任务/gui_hidden.py` 隐藏桌面）：`tests.test_pet_ui.GeometryTests` + `tests.test_pet_ui.PawTests` + `tests.test_ui_batch9_pet_accessibility.PetAccessibilityBatch9Tests` + `tests.test_desktop_compact_layout` → **25/25 OK**。
- 默认冒烟：**8/8 通过**。
- 受影响模块门禁 `smoke_test.py --affected pet_ui_support pet_ui_view pet_ui`：1302 条，3 个文件红——`test_pet_ui`（云位置 1 条 + 登录闸门 5 条）、`test_ui_edges`（BriefTint 2 条）。这三组红已在基线 worktree `c5a85eed` 上逐条复现（2/2 FAIL），确认非本轮引入。
- 架构门禁：本轮改动为 L4 层内（pet_ui*），未触发，未运行。
- 全量安全回归：未触发，未运行。

## 提交

- 已提交：分支 `codex/wip-R1961`；提交包含上述 6 个文件，最终 commit 以 `git log -1` 为准。

## 备注

- 工作树开轮前已有未提交改动：`程序/project_status.md`、`.claude/settings.local.json`（用户既有改动），本轮未触碰。
- 认领：`round_claim.py next` → R1961，分支 `codex/wip-R1961`（脏树按新契约自动带分支）。
