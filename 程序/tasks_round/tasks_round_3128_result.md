# R3128 功能轮结果：文件卡片与 HITL·轮 5/8——图片缩略图卡 + 代码高亮块 + 红绿 Diff
<!-- round-evidence: {"commit_base": "ffe95c14", "credential_hits": 0, "evidence_sha256": "b255000b94713e23", "exit": 0, "failed": 0, "passed": 6, "round": 3128, "tests": "run_selftests.py -k media_render code_highlight diff_view"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书《文件卡片与 HITL 交互任务书》轮 5/8）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`test_media_render.py`（2/2）、`test_code_highlight.py`（2/2）、`test_diff_view.py`（2/2）、button/token 边界（32/32）、默认冒烟、架构门禁（见下）。未跑全量 `--all --safe`（非 master 提交点）。
3. **欠账少了吗？** 无新增欠账；富媒体三件套（缩略图卡/Lightbox/多候选/收藏、代码高亮块、红绿 Diff）落成可复用 L4 组件。

## 改动

- 新增 `ui/ui_media.py`：
  - `build_thumbnail_card`：候选缩略图一排（序号按钮）、上一张/下一张切换、当前候选预览、「收藏入库」与「放大预览」；
  - `open_lightbox`：`BaseDialog` 置顶窗口显示缩略图（`asset_thumbs` 专用缓存；未就绪/不支持时退回占位文字）；
  - 收藏与打开经 `on_favorite`/`on_open` 回调注入（真实入库走 `asset_batch`／回收语义由调用方负责）。
- 新增 `ui/ui_code_block.py`：
  - `highlight_tokens`：JSON 词法切分（string/number/keyword/plain）；
  - `build_code_block`：`TextArea` 高亮正文 + 收起/展开 + 复制 + 应用此提示词（回调注入）。
- 新增 `ui/ui_diff.py`：
  - `diff_lines`：`difflib.SequenceMatcher` 行级 equal/delete/insert/replace；
  - `build_diff_view`：`TextArea` 红删绿增着色（`danger`/`success` token）+ 接受修改/拒绝（回调注入，复用 HITL DIFF 决策）。
- 新增测试 `tests/test_media_render.py`、`tests/test_code_highlight.py`、`tests/test_diff_view.py`（各 2 条，真 Tk）。
- 基线同步：覆盖率基线 537→540（三个新模块）；skip 台账 +3；`runbook §11` 同步。

## 测试证据

- `python -B tests/test_media_render.py` → `Ran 2 tests ... OK`。
- `python -B tests/test_code_highlight.py` → `Ran 2 tests ... OK`。
- `python -B tests/test_diff_view.py` → `Ran 2 tests ... OK`。
- `python -B -m unittest tests.architecture.test_button_boundary tests.architecture.test_token_boundary` → 32 tests OK（语义按钮 + token 间距/尺寸）。
- `python -B -m unittest tests.architecture.test_dialog_boundary tests.architecture.test_input_boundary tests.architecture.test_ui_icons_boundary tests.architecture.test_tooltip_boundary` → 13 tests OK（BaseDialog/TextArea/asset_thumbs 边界）。
- `python -B smoke_test.py` → `通过：9 项`、`失败：0 项`（退出码 0）。
- `python -B smoke_test.py --architecture` → `Ran 483 tests ... OK`（`✅ 架构治理测试：tests/architecture`；覆盖率基线 540、skip 台账 300 口径同步）。

## 契约变更（§2.4）

- 新增 L4 富媒体组件三件套；按钮走 `ui_widgets` 语义组件，尺寸/间距只取 token（`width=0` 自动宽度、颜色取 `COLORS`）。
- 零第三方依赖不变（图片用 Tk `PhotoImage`，Diff 用 stdlib `difflib`）。

## 范围外 / 已知缺口

- 「收藏入库」当前是回调位；真实写 `asset_batch` 入库管线与「收藏目标=项目资产库/正典」的接线留待产物卡与资产页联动轮。
- JPG 等非 Tk 原生格式的缩略图加载走占位（项目已有 `asset_thumbs` 可接）。
- 未跑全量 `--all --safe`（非 master 提交点）。

## 提交

- 分支 `codex/wip-R3128`；commit hash 见回填。
