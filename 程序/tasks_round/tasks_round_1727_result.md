# R1727：修复轮——阶段配置页下拉框布局＋最小窗口与布局令牌（SP＋SPTOKEN）

## 结论

- 先红后绿已完成：新布局测试改前红，改后 6/6 绿；受影响面冒烟 152 条 0 红。
- 标签贴近、按行填满、内容完整、SKILL 右侧无空白均已通过真 Tk 几何断言。
- 架构门禁仍有既有欠账（见「验证计数」与「需裁决」），本次未越权修改 `desktop.py`、`project_status.md`。

## 改前红输出（摘要）

```text
Ran 6 tests in 17.668s; FAILED (failures=9, errors=4)
- 预设 标签与下拉框相距 62px
- SKILL 操作行右侧仍留空白：wide 703px / mid 343px / min 205px
- 下拉框内容 7px < 56px
- 新布局 API 尚不存在，相关用例 errors
```

## 第 5 条：1280×800 高度

| 指标 | 改前 | 改后 | 判定 |
|---|---:|---:|---|
| 配置区高度 | 451px | 382px | 改后更矮 |
| 技能说明区高度 | 310px | 379px | 改后更高 |

补充：折叠态改前 397px / 364px，改后 347px / 414px（配置区 / 说明区）。

## 改动

- `skill_panel.py`：移除固定标签宽 `FORM_LABEL_WIDTH`；总控与全部制作锁合并到单一 `ProductionLockFields`，选填锁原位显示/隐藏；SKILL 操作行改为 `FlowFields`，下拉框与提示吃掉剩余宽度；表单高度按窗口余量封顶，矮窗口出现滚动。
- `production_lock_fields.py`：新增 `FlowFields` 自动换行/按行填满布局；保留 `inputs/hints/values/set_values/refresh_states/changed`，新增 `leading/visible_keys/field_visible/set_visible`；新增 `CompactLabel`，保留旧 `width=10` 契约但真实请求宽度为文字宽度。
- `tests/test_skill_panel_dropdown_layout.py`：新增 6 个真 Tk 用例，覆盖标签间距、锁定行顺序与填充、三档内容完整、SKILL 右侧空白、配置/说明高度、既有保存与批量操作。

## 既有测试契约变更（未弱化断言）

- `tests/test_production_lock_ui.py`：布局契约由「前 5 项横排 + 其余竖排 + 可选项」三块 grid，改为单一 `ProductionLockFields` 流式容器；仍断言全部锁输入、保存、失焦事件、折叠/展开与依赖状态。
- `tests/test_skill_panel_layout_fit.py`：坐标容器从 `new_lock_row.master` 改为 `workflow_coordinator`，重叠与越界检查保留。
- `tests/test_skills.py` 未修改；通过 `CompactLabel` 保留 `width=10` 的既有可读契约，实际排版仍贴近下拉框。

## 验证计数

1. `python -B run_selftests.py -k skill_panel production_lock test_skill_panel_dropdown_layout`
   - 7 个测试文件，26 条用例，0 红，77.0 秒。
   - 沙箱禁止写共享 `.git`，GUI 锁无法建立；本次用临时 `GIT_DIR` 承载自测锁与缓存，测试仍指向真实工作树。
2. `python -B smoke_test.py --affected skill_panel production_lock_fields`
   - 9/9 检查项通过；`test_skills` 152 条用例，0 红；门禁 200 秒。
3. `python -B smoke_test.py --architecture`
   - `Ran 368 tests in 288.177s; FAILED (failures=2)`。
   - 两条均为既有欠账：`R1722` 欠完整安全全量；`desktop.py` TODO 行号快照 1087 与审查快照 1019 不一致。
   - 补充：撤销越权 skip 台账条目后，`tests.architecture.test_skip_hygiene` 单独运行 3 条中 1 条红（台账 240 / 源码 241），是原树已有的未登记 skip；按任务书只允许追加本测试文件条目，未修。

## 截图（三档，改前/改后）

- `D:\漫剧制作助手\工作流任务\probe_SP\before_wide.png`
- `D:\漫剧制作助手\工作流任务\probe_SP\before_mid.png`
- `D:\漫剧制作助手\工作流任务\probe_SP\before_min.png`
- `D:\漫剧制作助手\工作流任务\probe_SP\after_wide.png`
- `D:\漫剧制作助手\工作流任务\probe_SP\after_mid.png`
- `D:\漫剧制作助手\工作流任务\probe_SP\after_min.png`

改后 1280×800 实测：标签最大间距 8px，锁定行尾空白 5px，SKILL 行尾空白 0px；三档内容完整。

## 需裁决

- 阶段配置窗口实际 `minsize` 为 `(1,1)`，无法从控件读取任务书所称的「允许的最小尺寸」；本次最小档按 `560×430` 测量，是否应显式设置最小窗口尺寸请裁决。
- 未新增 `ui_tokens` 令牌：本次复用现有 `SPACING['xs']/['md']` 与字体，若要求把行尾空白等参数令牌化，请裁决。
- `.git` 写入受沙箱限制，GUI 令牌改用临时 `GIT_DIR`；这是验证环境适配，不是产品行为变更。
- 架构门禁的 R1722 全量欠账、TODO 快照行号、`test_ui_batch6_pages` 未登记 skip 均不在本次允许文件内，需另行按治理流程处理。

## G 裁决落地（SPTOKEN）

两条裁决（最小窗口尺寸 + 布局参数令牌化）已按用户 2026-10-19 的裁决落地。

### 改动

1. `ui_tokens.py` 新增 `STAGE_PANEL_LAYOUT` 字典（参照 `DESKTOP_LAYOUT` 写法），键与值：

   | 键 | 值 | 含义 |
   | --- | --- | --- |
   | `min_width` | 560 | 阶段配置窗口最小宽 |
   | `min_height` | 430 | 阶段配置窗口最小高 |
   | `field_gap` | `SPACING['xs']`=4 | 标签与下拉框／字段间距 |
   | `row_gap` | `SPACING['xs']`=4 | FlowFields 行间距 |
   | `row_end_tolerance` | `SPACING['md']`=12 | 行尾允许空白容差 |
   | `label_width` | 10 | CompactLabel 旧契约宽度 |

2. 各键替换的代码处（文件:行）：

   - `min_width`/`min_height` → `skill_panel.py` `show()`（原 `window.minsize(1, 1)` 处）；取 `min(令牌, winfo_screenwidth/height)`，屏幕可用区更小时按可用区收缩，不让窗口超出屏幕。
   - `field_gap` → `production_lock_fields.py` `FlowFields.__init__`（`gap` 默认）、`_add_leading`、`_add_lock`（label-entry `padx` 与 hint `padx`）；`skill_panel.py` 预设行（`self.presets`/`self.preset_actions`）、厂商行（`self.providers`/`self.models`）、`self.lock_notice`。
   - `row_gap` → `production_lock_fields.py` `FlowFields.__init__`（`row_gap` 默认）。
   - `label_width` → `production_lock_fields.py` `CompactLabel.__init__`（原 `kwargs.setdefault('width', 10)`）。
   - `row_end_tolerance` → 供真 Tk 几何断言读取（「填满」容差）；本次未改生产填充逻辑，值保持不变。

3. `tests/test_skill_panel_dropdown_layout.py` 新增 3 条真 Tk 用例：窗口 `minsize()` 等于令牌、`geometry('400x300')` 后实际宽高不小于令牌最小值、FlowFields/CompactLabel 间距取自令牌（含对两个布局模块引用 `STAGE_PANEL_LAYOUT` 的静态检查）。

4. `tests/test_skills.py` 仅改 `test_stage_config_window_is_smaller_than_its_main_window` 一条：把「缩到 400×300」的旧断言（R1160 契约 `(400,300)`）改为「实际尺寸不小于令牌最小值」；「能放大到 1250×850」的断言保留。**其余断言一律未动。**

### 先红后绿

- 红：改代码前 `test_skill_panel_dropdown_layout.py` 因 `ImportError: cannot import name 'STAGE_PANEL_LAYOUT'` 而整体 `ERROR`（令牌尚未存在；SP 结果 §需裁决 已记录原 `minsize=(1,1)`）。
- 绿：改后该文件 9 条用例（SP 原有 6 + 新增 3）全绿；`test_skills` 相关断言由红转绿。

### 验证计数

1. `python -B -m unittest tests.test_skill_panel_dropdown_layout tests.test_skill_panel_layout_fit tests.test_production_lock_ui tests.test_skills` → `Ran 166 tests ... OK`（需 `PYTHONPATH=tests` 承载 `skip_reasons`，与 `run_selftests.py` 注入一致；未加该路径时 `test_skills` 因 `ModuleNotFoundError: skip_reasons` 在 import 阶段报错，属既有路径依赖，非本次改动引入）。
2. `python -B smoke_test.py` → 8/8 通过，0 失败。
3. 单独 `-m unittest tests.test_skill_panel_dropdown_layout` → `Ran 9 tests ... OK`（含新增 3 条）。

### 需裁决（无）

无新增需裁决项。运行中出现的 `pkgIndex.tcl: unknown encoding "cp1252"` 为随附 Tcl 的无害告警，不影响测试判定（最终 `OK`）。

## 独立验收（Claude，主工作区四批同树）

- 四批同树合测：`run_selftests.py -k`（smoke --affected 选出的 97 个文件）共 2364 条，3 个文件红：`test_idea_inline_brief`（SP 改契约，mock 缺 `lock_fields`）、`test_ui_batch9`（`winfo_containing` 被桌面上 Chrome 窗口挡住）——均已修复复跑 0 红；`test_writing_api` 1 条在干净 HEAD 绿、主树红，因读取本机真实模型配置，与本批无关。
- `smoke_test.py` 默认 8/8；`--architecture` 368 条 4 红：模块体积（skill_panel 1503>1500，已压回 1500）、skip 台账漏登 UI6、TODO 快照行号 1019→1087（UI3 平移）——已修复，单跑 9/9；全量欠账为后台自动补跑项，不阻断。
- 消费者复跑：`-k test_skill_panel test_skills test_idea_inline_brief test_production_lock test_ui_batch5` 210 条 0 红。
