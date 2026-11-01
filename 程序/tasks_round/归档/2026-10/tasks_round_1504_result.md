# R1504 结构治理轮：拆分 desktop.py 步骤 3（第 2 页：首帧管理页 `storyboard`）

1. **本轮类型？** 结构治理轮（只搬代码，不改逻辑；一页一轮）。
2. **测试与基线？** 默认冒烟 8/8；架构门禁除他人车道的两项外全绿；keyframe／storyboard／frame／ui_edges／row_targets／asset_gating 等相关自检（329 条）通过，唯一的 `test_frame_checks` 因读 `desktop.py` 源码已改读合并源码；全量与干净检出验证见提交后记录。断言未动。
3. **是否欠账？** 改了层级登记表（风险路径），须全量转绿。

## 说明：`storyboard` 构建的是哪一页

`Desktop.show` 的构建器列表第 7 项（0 起）是 `self.storyboard`，对应阶段 `keyframe`（侧栏「07 首帧管理」）；方法名是历史沿用，真正的“初步分镜”页是 `storyboard_creation`。模块、类、注释里都写明了这一点。

## 改动

- 新增 `desktop_storyboard_page.py`（L4）：`StoryboardPageMixin` 原样承载 `storyboard`（323 行）；`Desktop(StoryboardPageMixin, WritingPageMixin, IdeaChatMixin, AutoFlowsMixin)`；`desktop.py` 5328 → 5003 行（累计自 7820 降 2817 行）。
- 新增 `desktop_page_support.py`（L4）：把 R1499 在剧本准备页模块里内嵌的“宿主转发”抽成共用——`confirm／open_path／ContextMenu／FileDialog／confirm_project_removal_from_last_script` 的转发函数（`desktop` 模块级 `bind_host` 登记自身，新模块不导入 `desktop`，无环），以及多页共用的 `THUMB_SIZE／ASSET_ROW_HEIGHT`（`desktop` 重新导入，资产页等仍在用）。`desktop_writing_page.py` 同步改用它。以后每页的 Mixin 都从这里取，不再各抄一份。
- 迁页用的脚本按“自由名解析”生成导入：迁出方法用到的模块级名字逐个解析，新模块无未使用导入（已核）。

## 架构门禁的调整（断言未动）

- `test_keyframe_replace_boundary`、`test_frame_checks`：被检的 `storyboard` 方法改在合并的 Desktop 源码里找。
- `_scan.DESKTOP_PARTS`、`_layers.py`（登记 `desktop_storyboard_page`、`desktop_page_support`）、`test_module_size_ratchet`（`desktop.py` 上限 5400 → 5100）、TODO 注释快照、`architecture.md`、`PROJECT_MAP.md` 同步。

## 与本轮无关的红（别的车道）

`test_layers`（`production_lock_fields` 未登记层级）、`test_skip_hygiene`（skip 台账 226 对 227）、`test_production_lock_ui`：均来自制作锁车道（R1496–R1500），在 069e8d1 的干净检出里已复现，不涉及 `desktop*.py`。

## 提交

已提交，见 git log 标题 `R1504:`。
