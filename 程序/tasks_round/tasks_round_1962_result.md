# R1962：功能轮——猫爪列底边对齐三虎图像，内容框再上移

## 三个问题

- 轮次类型：功能轮（UI 布局调整，用户明确要求「猫爪还可以往上移，底部对齐三虎图像」）。
- 测试：默认冒烟 8/8 通过；定向 25/25 通过；受影响模块门禁 1302 条中 3 个红文件与 R1961 基线一致（云位置 1 + 登录闸门 5 + BriefTint 2，已在基线 worktree c5a85eed 复现）。架构门禁与全量安全回归未触发、未运行。
- 欠账：未新增欠账。

## 改动内容

- 竖向猫爪间距从 `PAW_SIZE + PAW_GAP`（18）改为 `PAW_SIZE`（16，取消 2px 缝）：三只爪的视觉底边正好落在头像底边，列顶与头像顶平齐（`PAW_COL_Y = 0`）。
- 猫爪列画布高 50px（3×16 + 2px 弯弧余量），最下面那只爪底边 = 头像底边（48px）。
- `PATCH_ROOM` 由 72 降到 58：标题行再矮 14px，**下方内容框继续上移**（相对最初横排布局共上移 28px）。
- 中间那只爪仍保留 2px 下坠弧（`paw_dy` 不变）；三只爪仍各有一个 36×36 键盘/鼠标承接区，Tab 顺序与键盘操作不变。
- 命中区采样测试改为只采标题行内的可见段（列顶平齐后第一只爪的命中区上沿高出标题行顶，属窗口外不可点区域）。

## 改动文件

- `程序/pet_ui_support.py`：PAW_STEP 改为 PAW_SIZE；PAW_COL_Y 改为头像底边对齐公式；PATCH_ROOM 随之下调。
- `程序/tests/test_pet_ui.py`：点击/悬停/弧线测试改用 PAW_STEP 与爪中心坐标；compact 与重叠测试补「列底边与头像底边对齐」断言。
- `程序/tests/test_ui_batch9_pet_accessibility.py`：命中区中心与采样步长改用 PAW_STEP；点击采样限制在标题行可见段。

## 验证

- 定向（经 `工作流任务/gui_hidden.py` 隐藏桌面）：GeometryTests + PawTests + 宠物可达性 + compact 布局 **25/25 OK**。
- 默认冒烟：**8/8 通过**。
- 受影响模块门禁 `smoke_test.py --affected pet_ui_support pet_ui_view pet_ui`：1302 条，3 个红文件（test_pet_ui 云位置 1 + 登录闸门 5、test_ui_edges BriefTint 2），与 R1961 已在基线 worktree `c5a85eed` 复现的红完全一致，非本轮引入。
- 架构门禁：未触发，未运行。
- 全量安全回归：未触发，未运行。

## 提交

- 已提交：分支 `codex/wip-R1962`；提交包含上述 4 个文件，最终 commit 以 `git log -1` 为准。

## 备注

- 工作树开轮前已有未提交改动：`程序/project_status.md`、`.claude/settings.local.json`（用户既有改动），本轮未触碰。
- 认领：`round_claim.py next` → R1962，分支 `codex/wip-R1962`。
