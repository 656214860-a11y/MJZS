# R2405 结果：弹窗改为 92% 覆盖主界面（方案 B）＋收尾 R2398/R2399 遗留欠账

## 三个必答（§7）

- **轮次类型**：修复轮（§3.2）——修「模型管理弹窗放大超主界面」「阶段配置弹窗骤缩突兀」两个视觉缺陷；附带收尾 R2398 页签化／R2399 合并轮遗留的 coverage 基线、轮次头、runbook 数字欠账。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 定向 `run_selftests.py -k "test_pet_settings test_skills test_ui_batch7_settings_models test_model_manager_actions"`：236 条，**仅 test_pet_settings 2 条红**（均为 R2398 页签化遗留 `KeyError: 'ChatGPT Desktop · Codex'`，见「遗留欠账」，与本轮弹窗改动无关）。
  - 弹窗几何测试 `tests.test_pet_settings.ManagerGeometryTests`：**4/4 通过**（单进程 unittest 实测 `OK`）。
  - coverage 门禁 + 轮次门禁 `tests.architecture.test_coverage_baseline`／`test_round_baselines`：**10/10 通过**（单进程 unittest 实测 `OK`）。
  - 架构门禁 `smoke_test.py --architecture`：本轮未整跑通过——存在并行会话 R2404 拆分前的 `writing_api.py` 超限（R2404 已拆分解决，见「遗留欠账」）。
  - 全量：未跑（不命中 §5 强制全量条件）。
- **project_status.md 的欠账少了吗**：本轮收口了 R2398 遗留的 coverage 基线未刷新、轮次头未同步两项欠账；R2398 页签化的 2 条列表测试迁移欠账仍遗留（如实登记，不弱化、不掩盖）。

## 根因与最小修复

### 1. 弹窗 92% 覆盖主界面（方案 B，用户拍板）

- **根因 A（模型管理放大超界）**：`pet_models_ui.py` `fit_to_main()` 原 `width = min(1180, max(820, int(parent_width*0.9)))`，`max(820, …)` 的绝对下限在主窗口 < 911px 时让弹窗 820 > 主窗口宽。
- **根因 B（阶段配置骤缩突兀）**：`skill_panel_support.py` `panel_window_size()` 原 `min(880, parent-48)`，主窗口缩小时弹窗跟着线性减 48px 骤缩到 560×430。
- **修复**：新增统一比例 `ui_tokens.OVERLAY_RATIO = 0.92`；两处都改为「主界面 × 92% 覆盖 + 内容兜底先被主界面封顶 + 绝对上限（1180×860／880×720）先被主界面封顶」，弹窗**永不超主界面**。关闭/模态语义不变（用户确认保持现状）。

### 2. 收尾 R2398/R2399 遗留欠账

- **coverage 基线**：R2398 新增 `pet_models_tabs.py` 生产模块但未刷新 `覆盖率基线.json`，重跑 `scripts/coverage_report.py` 刷新（modules_total 358→359，modules_covered 53→58），同步 `runbook.md` §11 数字。
- **轮次头**：`project_status.md` 轮次头 2397→2400，补记 R2398／R2399 合并轮摘要。
- **列头断言**：`test_pet_settings.py` 列表列头 6→7 列（页签化新增「功能」列），同步更新。

## 改动文件

- `ui_tokens.py`：新增 `OVERLAY_RATIO = 0.92`。
- `pet_models_ui.py`：`fit_to_main` 重写为 92% 覆盖＋永不超界；删 `MANAGER_RATIO`。
- `skill_panel_support.py`：`panel_window_size` 重写为同套比例。
- `tests/test_pet_settings.py`：几何测试断言更新（90%→92% 期望值）、列表列头 6→7 列、列索引 +1。
- `维护记录/覆盖率基线.json`：重跑工具刷新。
- `runbook.md`：§11 覆盖率数字同步。
- `project_status.md`：轮次头补记。

## 验证证据（边界行为脚本实测）

```
模型管理 fit_to_main:
  主窗口 1280x800 -> 1177x736  超界=False
  主窗口 940x640  -> 864x620   超界=False   ← 修复原 820>940 超界
  主窗口 800x600  -> 800x600   超界=False   ← 最小主窗口弹窗=主窗口
  主窗口 1600x1000 -> 1180x860 超界=False   ← 绝对上限封顶
阶段配置 panel_window_size:
  主窗口 1280x800 -> 880x720   超界=False
  主窗口 800x600  -> 736x552   超界=False   ← 修复原骤缩到 560
```

## 遗留欠账（如实登记，非本轮引入，不弱化断言）

1. **R2398 页签化测试迁移**：`test_pet_settings.py` 两条 `KeyError: 'ChatGPT Desktop · Codex'`。根因＝页签化 R2398 让列表「按调用方式分页签过滤」，默认 API 页签只显示 API 模型，`ChatGPT Desktop · Codex`（Desktop）与 `Claude Code`（CLI）不在其中；而这两个测试仍按「列表显示全部模型」的旧语义断言。需页签化任务重新设计断言（跨页签验证或改为「当前页签只显示本调用方式」）。
2. **并行会话 `writing_api.py` 超限**：`writing_api.py` 1383 行 > 上限 1372。并行会话已在 R2404（`fd581a45`）通过拆分 `confirm_preparation_document` 到 `writing_unconfirm.py` 解决；本结果文件写于 R2404 拆分提交之前，此处仅作记录。

## 提交

- 已提交：是。commit hash 见 git log。
- 提交信息：`R2405: 弹窗改为 92% 覆盖主界面 + 收尾 R2398/R2399 遗留欠账`。
