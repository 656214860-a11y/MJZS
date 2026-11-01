# R1377：UI 统一入口覆盖轮 — 文案与复制（固定术语、复制反馈、脱敏回执）

类型：功能轮（§3.1，UI 统一入口：复制反馈术语收口；不改业务逻辑、阶段、路径与分层）。中央轮次 1377（`.git/round-counter.json` 的 `last_claimed=1377`）。范围＝`维护记录/UI统一入口路线图_v1.md` 待收口 4 项之第 4 项「文案与复制」（§二 第 14 项）。

## 三个必答
- 本轮类型：功能轮（§3.1）——复制反馈固定术语与不静默吞掉失败收口到可检查规则。
- 测试：架构 `smoke_test.py --architecture` **321/321**（原 320，只增不减；未增删门禁文件，只在既有 `test_copy_entry_boundary.py` 增 1 条方法，§5 清单不变）；定向 `run_selftests.py -k "copy pet_settings local_previs asset_detail ui_edges asset_reference"` **244 条 / 224.3 秒 / 0 文件红**；默认冒烟 `smoke_test.py` **8/8**；`py_compile` 4 文件 OK。0 红。
- 欠账：1377 − 1375 = 2 < 5；未命中 §5 升级条件。按用户「不因为是收尾就跑全量兜底」不跑全量。文案与复制路线图项「完成全量覆盖审计」，欠账减少。

## 范围与完成判据（路线图 §二 第 14 项，逐字）
- 完成判据：**固定术语、复制反馈与脱敏文本可按规则检查。**
- 权威入口（`ui_components.md` 文案与复制）：`prompt_window.copy_text()` 是写剪贴板唯一入口（R787 建立，R929 递归门禁），`copy_preview()` 只作状态回执并掩盖疑似凭据；固定动作术语「已复制…」与「复制失败：…」。
- 收口口径：复制写入口＝唯一且递归零容忍（既有门禁）；复制反馈术语＝成功只用「已复制…」、失败只用「复制失败：…」，失败不得静默吞掉、也不得被成功文案覆盖；脱敏＝状态回执经 `copy_preview` 掩码（既有门禁）。

## 实现
### 1. 失败术语统一为「复制失败：…」（3 处）
- `prompt_window.py`（唯一复制入口）：`"复制失败，请重试："+reason` → `"复制失败："+reason+"，请重试"`。
- `local_previs.py`：`'白模制作说明复制失败（'+reason+'），请手动选中复制…'` → `'白模制作说明复制失败：'+reason+'；请手动选中复制…'`。
- `pet_settings_ui.py`：`'复制失败，请手动选中复制：%s（%s）'` → `'复制失败：%s（%s）；请手动选中复制'`。

### 2. 复制失败不再被成功文案覆盖：`asset_detail.py`
- 原 `command=lambda: desktop.safe(lambda: (desktop.copy_text(anchor), desktop.status.set('锚点字符串已复制')))` 无条件把状态改写成「锚点字符串已复制」，会盖掉 `copy_text` 写入的「复制失败：reason」。改为先取 `reason`：失败显示「复制失败：reason」，成功显示「锚点字符串已复制」。

### 3. 门禁：`tests/architecture/test_copy_entry_boundary.py` 增 1 条
- `test_copy_feedback_uses_the_fixed_terms`：递归生产扫描（排除 tests／tasks_round／维护记录／skills），对非文档字符串的字面量要求：含「复制失败」必须使用「复制失败：…」；禁止「复制成功／成功复制」。
- 排除模块／类／函数首行文档字符串（说明性文字不算用户可见文案），避免把注释性「复制成功」误判为违规。
- 反向 canary 实证：旧 `prompt_window` 文案（`复制失败，请重试：`）与旧 `local_previs` 文案（`复制失败（`）均被命中；纯文档字符串（含「复制失败」「复制成功」）不命中。

## 验证
- 架构 `smoke_test.py --architecture`：**321/321、0 红**（124.1 秒；原 320，+1 为本轮新增方法）。未增删门禁文件，§5 清单不变。
- 定向 `run_selftests.py -k "copy pet_settings local_previs asset_detail ui_edges asset_reference"`：**244 条 / 224.3 秒 / 0 文件红**（ALL TESTS PASSED）。
- 默认冒烟 `smoke_test.py`：**8/8**；`py_compile prompt_window.py local_previs.py pet_settings_ui.py asset_detail.py` OK。
- 新增 `skipTest`：无。

## 边界
- 未改业务逻辑、阶段、路径、分层与用户数据；只统一复制反馈术语并修正一处失败文案被覆盖的缺陷。
- 「文案与复制」本项以「写入口唯一＋术语固定＋失败有反馈＋回执脱敏」为可检查口径；未把其他页面的一般文案（按钮命名、状态栏措辞）纳入本项，避免超出路线图该项范围。
- 既有测试未断言被改的三处原文案（`test_pet_settings` 只断言邮箱出现在提示里），故未改测试断言；保留原有断言强度。

## 全量判定
- 1377 − last_full_safe_all_round(1375) = 2 < 5；未命中 §5 升级条件（启动路径／Tk 控件销毁重建／删除语义／层级登记表均未改）。
- 本轮改了生产代码与测试，内容树变化，7 日内同树绿凭据不可复用。
- 按用户指令「测试按 §5 触发表执行，不因为是收尾就跑全量兜底」，**本轮不跑全量**。

## 提交
- 内容：`程序/prompt_window.py`、`程序/local_previs.py`、`程序/pet_settings_ui.py`、`程序/asset_detail.py`、`程序/tests/architecture/test_copy_entry_boundary.py`。
- 报告与状态页：`程序/tasks_round/tasks_round_1377_result.md`、`程序/project_status.md`（轮次头改为 1378）。
- 未触碰主树他人已暂存改动与未跟踪用户目录。
