# R2407 结果：弹窗比例 92%→78%，设置页与模型管理弹窗统一尺寸

## 三个必答（§7）

- **轮次类型**：修复轮（§3.2）——修「模型管理弹窗最大（逼近主界面）、设置页与主界面比例不协调」的视觉缺陷；用户拍板「主界面最大、两个弹窗一样大、都随主界面缩放」。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 弹窗几何测试 `tests.test_pet_settings.ManagerGeometryTests`：**4/4 通过**（单进程 unittest 实测 `OK`）。
  - 全量：未跑（不命中 §5 强制全量条件）。
- **project_status.md 的欠账少了吗**：无新增欠账；本轮为 R2405 弹窗任务的尺寸微调延续。

## 根因与最小修复

- **根因**：R2405 方案 B 把弹窗比例设为 `OVERLAY_RATIO=0.92`（92%），主界面 1280×800 下模型管理弹窗 1177×736（逼近主界面）；而设置页 `HUB_GEOMETRY='880x620'` 固定写死、不随主界面缩放，导致「模型管理最大、设置页偏小、三者比例不协调」。
- **修复**（用户拍板 78% 比例、两弹窗一样大）：
  1. `ui_tokens.OVERLAY_RATIO`：0.92 → **0.78**。
  2. `pet_models_ui.fit_to_main`：新增 `floor`（内容兜底）与 `cap`（可选绝对上限）参数；`cap=None` 时去掉绝对上限、超大屏也严格 78% 覆盖。
  3. `pet_settings_ui.open_hub`：设置页从固定 `HUB_GEOMETRY` 改为复用 `fit_to_main`（`floor=HUB_MIN`），与模型管理同比例居中。

## 效果（边界脚本实测）

主界面 1280×800（默认）下：
- 主界面 = 1280×800（最大）
- 模型管理 = 998×624（78%）✓
- 设置页   = 998×624（78%）✓ **两弹窗一样大**

主界面缩小时两弹窗分别按各自内容兜底（模型管理 `MANAGER_MIN=820×620`、设置页 `HUB_MIN=760×560`）保住可读性，均永不超主界面。超大屏（1920×1080）下两弹窗严格 78%（1497×842），不再被旧 1180 绝对上限封顶。

## 改动文件

- `ui_tokens.py`：`OVERLAY_RATIO` 0.92→0.78，注释更新。
- `pet_models_ui.py`：`fit_to_main` 加 `floor`/`cap` 参数。
- `pet_settings_ui.py`：`open_hub` 复用 `fit_to_main`。
- `tests/test_pet_settings.py`：几何测试期望值更新（92%→78%），`test_a_big_main_window_only_caps_the_fixed_size` 改为 `test_a_big_main_window_stays_a_fixed_ratio_not_an_absolute_cap`（去掉绝对上限语义）。

## 遗留欠账

无新增。R2398 页签化 2 条列表测试迁移欠账仍遗留（见 R2405 结果文件），非本轮范围。

## 提交

- 已提交：是。commit hash 见 git log。
- 提交信息：`R2407: 弹窗比例 92%→78%，设置页与模型管理弹窗统一尺寸`。
