# R2413 结果：阶段配置／设置页／模型管理三弹窗尺寸＝主界面（100% 覆盖）

## 三个必答（§7）

- **轮次类型**：修复轮（§3.2）——用户拍板把三个高频弹窗尺寸从 78% 改为 100%（＝主界面），视觉上像切换页面；不涉及「放大按钮」（用户已取消该需求）。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 定向 `run_selftests.py -k "test_skills test_pet_settings test_ui_batch7_settings_models"`：229 条，**仅 test_pet_settings 2 条红**（R2398 页签化遗留 `KeyError: 'ChatGPT Desktop · Codex'`，与本轮无关）。
  - 几何测试 `test_pet_settings.ManagerGeometryTests`：**4/4 通过**。
  - 全量：未跑（不命中 §5 强制全量条件）。
- **project_status.md 的欠账少了吗**：无新增欠账；R2398 页签化 2 条列表测试迁移欠账仍遗留。

## 根因与修复

- **需求**：阶段配置／设置页／模型管理三个弹窗尺寸与主界面保持一致（100% 覆盖，视觉上像切换页面）。
- **修复**：
  1. `ui_tokens.OVERLAY_RATIO`：0.78 → **1.0**（弹窗尺寸＝主界面）。
  2. `skill_panel_support.panel_window_size`：去掉硬编码 880×720 绝对上限，让阶段配置弹窗＝主界面尺寸。

## 效果（边界脚本实测）

主界面任意尺寸下，三个弹窗尺寸均＝主界面：

```
主界面 1280x800: 模型管理=1280x800 设置页=1280x800 阶段配置=1280x800
主界面 940x640 : 模型管理=940x640  设置页=940x640  阶段配置=940x640
主界面 1600x1000: 模型管理=1600x1000 设置页=1600x1000 阶段配置=1600x1000
```

## 契约变更

- 弹窗初始尺寸由「78% 覆盖」改为「100% 覆盖（＝主界面）」，属有意 UI 行为变更。
- `test_pet_settings.py` 几何测试断言由 78% 值更新为 100% 值；测试名 `test_the_window_is_a_ring_smaller...` 改为 `test_the_window_covers_the_main_one_exactly_and_centred`。
- `test_skills.py` `test_stage_config_window_is_smaller_than_its_main_window` 改为 `test_stage_config_window_covers_its_main_window`，断言 `assertLess` → `assertEqual`（弹窗＝主界面）。

## 改动文件

- `ui_tokens.py`：`OVERLAY_RATIO` 0.78 → 1.0。
- `skill_panel_support.py`：`panel_window_size` 去掉 880×720 上限。
- `tests/test_pet_settings.py`：几何测试断言与测试名更新。
- `tests/test_skills.py`：阶段配置窗口尺寸测试断言与测试名更新。

## 遗留欠账

R2398 页签化 2 条列表测试迁移欠账（`KeyError: 'ChatGPT Desktop · Codex'`）仍遗留，非本轮范围。

## 提交

- 已提交：是。commit hash 见 git log。
- 提交信息：`R2413: 阶段配置/设置页/模型管理三弹窗尺寸＝主界面（100%覆盖）`。
