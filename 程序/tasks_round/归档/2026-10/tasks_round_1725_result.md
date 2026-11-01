# R1725：结构治理轮——UI 批次 6：资产／连贯性／分镜页（表格、卡片、空态、窄窗不溢出）

## §7 三问

1. **本轮属于 §3 哪种类型？** 结构治理轮·UI 批次 6（执行）。只改任务书允许的
   `desktop_asset_pages.py`、`desktop_media_pages.py`、`asset_detail.py`、
   `desktop_storyboard_page.py`、新增测试、本结果文件与 `工作流任务\probe_ui6\`；未改
   `ui_tokens.py`／`ui_widgets.py`／`ui_theme.py`／共用文档／`project_status.md`／
   `AGENTS.md`／`architecture.md`／`skills/`，**未执行任何 git 写命令**。
2. **测试跑了吗？** 默认冒烟 **8/8 通过**；新增 `test_ui_batch6_pages.py` 真 Tk **7/7 通过**；
   `function_size_ratchet`＋`module_size_ratchet` **4/4 通过**；`test_skip_hygiene` **3/3 通过**。
   任务书 `run_selftests.py -k ...` 与 `smoke_test.py --affected ...` 均因并行批次占用跨树 GUI
   令牌而未拿到完整结果：一次持锁后 worker 超过 17 分钟未返回（已停止），一次等待 **900 秒**
   超时；按共用规矩未反复重跑，留给 Claude 验收时复跑。
3. **project_status.md 的欠账少了吗？** 没有。本批不改状态页、不领轮次；若并入提交，源码轮
   全量欠账由验收方计入。

## A 现状核对（先量后改）

- **800×600 改前几何（临时空项目根）**：资产页 `content actual=618x447`
  `content req=1098x409`，Treeview `req=1098`；分镜页 `content req=848x217`
  （1280 宽时），缩到 800 后 `content req=1098x256`、Treeview `req=1098`。
- **根因**：`DataTable` 用原始宽列宽建 Treeview；窗口变窄后列宽虽被
  `fit_current_columns` 收小，Tk 仍把旧的请求宽度钉住。最小复现确认：先用
  `MIN_COL` 建表、再 `remember_columns()`＋`auto_columns()`，Treeview 请求宽度可保持紧凑；
  另需在窄窗时重设 `displaycolumns` 让 Tk 重算请求宽度。
- **卡片 padding**：`desktop_media_pages.py` 原为 4／8／12／14／16 多档，
  `desktop_asset_pages.py` 参考网站分组为 8；本批统一为 `Card` 默认
  `SPACING['lg']`，卡片之间用 `SPACING['xs']`。
- **手写字号**：`asset_detail.py` 两处 13pt bold 标题；折行 760／640／520／230、
  视频页 600／650、参考网站 240。
- **分页**：四个文件里没有分页控件；资产页只有 `ASSET_FIRST_ROWS`／
  `ASSET_ROWS_PER_FRAME` 的分段插行（渐进渲染，不是分页）。因此本批不新增 pager，
  也没有可统一的“分页按钮组件”。
- **错误反馈**：可恢复错误默认走 `error()` 的非模态默认；`asset_detail.py` 四处保存／核对
  失败此前未显式写 `modal=False`，本批固定契约；删除状态变体仍走
  `ask_confirmation(..., dangerous=True)`，保持模态。

## B 改动（逐文件）

### `程序\desktop_asset_pages.py`

- 资产表改为先用 `(key, label, MIN_COL)` 建 `DataTable`，再用
  `remember_columns()` 记住原设计列宽并 `auto_columns()`；窄窗时列宽可收缩，
  宽窗时仍按原设计恢复。
- 新增 `_configure_table_style()`：表头／行字体取 `TABLE_HEADER_FONT`／
  `TABLE_ROW_FONT`，行高仍按缩略图尺寸计算。
- 新增 `_refresh_request_width()`：仅在 `reqwidth > 实际宽度` 且宽度变化时重设
  `displaycolumns`，让 Tk 重算请求宽度，避免旧宽度把内容区顶出窗口。
- 参考网站页卡片改用 `Card` 默认内边距；卡片间距统一
  `SPACING['xs']`；链接／说明折行取 `TEXT_HINT['wraplength']`。

### `程序\desktop_media_pages.py`

- 连贯性清单 `table_of()` 同样改为紧凑建表＋`remember_columns()`＋`auto_columns()`；
  新增表头／行字体设置与 `_refresh_request_width()`。
- 视频首页、连贯性页所有 `Card(padding=...)` 改为 `Card` 默认
  `SPACING['lg']`；卡片间距统一 `SPACING['xs']`；长说明统一
  `TEXT_DESC['wraplength']`。
- 视频页标题说明的手写 `wraplength=600`、9pt 字体改为
  `TEXT_DESC['wraplength']`／`TEXT_DESC['font']`；窄窗最小折行宽度由
  `SPACING['2xl']*5` 派生。
- 表格内边距、标签间距、按钮间距全部换成 `SPACING` 的 `none/xs/sm/md` 档。

### `程序\asset_detail.py`

- 两处 13pt bold 标题改用 `FONTS['heading_3']`（12pt bold，最接近的现有标题令牌）。
- 760／640／520 折行改 `TEXT_DESC['wraplength']`，230 改
  `TEXT_HINT['wraplength']`；`padx/pady` 的 1／2／4／6／8／10／12 全部换成
  `SPACING` 档位；TextArea 的 10px 内边距改 `SPACING['md']`。
- 四处可恢复保存／核对错误显式 `modal=False`；删除状态变体继续
  `ask_confirmation(..., dangerous=True)`。

### `程序\desktop_storyboard_page.py`

- 首帧镜头表改为 `MIN_COL` 紧凑建表，补 `empty_text='暂无镜头'`；表头／行字体
  走统一令牌。
- 新增 `_refresh_request_width()`；填行后无条件调用 `fit_frame_columns()`：
  未映射时先按内容记下期望列宽并绑定后续 `<Configure>` 重排（`fit_columns_by_content`
  内部已去抖），窄窗再按可用宽度收缩。
- 通过合并一行调用把 `storyboard()` 控制在既有 323 行棘轮上限内。

### 测试与台账

- 新增 `程序\tests\test_ui_batch6_pages.py`（docstring「UI 批次 6」）：真 Tk
  800×600 量资产页／首帧页主容器与表格、卡片 `cget('padding')`、表头字体、
  DataTable 空态、资产详情标题字体、可恢复错误非模态、删除确认模态。
- `程序\维护记录\skip台账.json` 只追加本测试 `FeedbackTests.setUp` 的
  `PLATFORM_TKINTER` 条目；既有条目未动。`PageLayoutTests.setUpClass` 使用
  `raise unittest.SkipTest(...)`（不是 `skipTest` 调用），按现有卫生门禁口径不登记。

## C 验证与截图路径

- `python -B smoke_test.py`：**8/8 通过，0 失败**。
- `python -B smoke_test.py --affected desktop_asset_pages desktop_media_pages asset_detail desktop_storyboard_page`：
  8 项快速检查通过；门禁在申请跨树 GUI 令牌时等待 **900 秒超时**（并行批次持锁），
  未得到测试结论。
- 任务书 `run_selftests.py -k asset storyboard desktop_media ui_edges video_ui test_layers function_size_ratchet module_size_ratchet test_ui_batch6`：
  首次运行持有 GUI 令牌后 worker 超过 17 分钟未返回，已停止；GUI 锁释放后重试一次，
  约 35 分钟无新增进度输出（进程仍在但日志停在 6:13），为避免阻塞其他批次已停止；
  未反复重跑，留给 Claude 验收时复跑。
- `python -B -m unittest discover -s tests -p 'test_ui_batch6_pages.py'`：**7 tests OK**。
- `python -B -m unittest test_ui_batch6_pages test_storyboard_page_loading test_video_ui`
  （带 `PYTHONPATH=程序\tests`）：**78 tests OK**。
- `python -B -m unittest test_asset_detail test_asset_gating test_assets`
  （带 `PYTHONPATH=程序\tests`）：**147 tests，1 红**。唯一红是
  `test_asset_detail.py::AnchorTests.test_an_empty_anchor_is_refused`：它仍断言
  空锚点会调用 `messagebox.showerror`，而本批按任务书第 5 条把可恢复保存错误改成
  `notify(..., modal=False)`（只落状态栏）。这是有意的契约变更，未自行改测试期望值。
- `python -B -m unittest tests.architecture.test_function_size_ratchet tests.architecture.test_module_size_ratchet`：**4 tests OK**。
- `python -B -m unittest tests.architecture.test_skip_hygiene`：**3 tests OK**。
- 四文件＋新测试 `py_compile`：**OK**。
- 改后 800×600 几何（临时空项目根）：
  - 资产页 `content req=613x411`、`actual=618x433`，Treeview `actual=618 req=613`，
    横向越界子控件 **0**。
  - 首帧页 `content req=660x256`、`actual=618x433`，Treeview `actual=618 req=660`，
    横向越界子控件 **0**。Tk 该表请求宽度含表头内部留白，实际显示宽度仍跟随内容区；
    若要求“请求宽度也必须≤内容实际宽”，需另批调整共享表头 padding。
  - 视频首页 `content req=619x530`、越界 **0**；连贯性页 `content req=369x542`，
    两张表 `actual=571`、越界 **0**。
- 截图（均为空临时项目根，800×600）：
  - `工作流任务\probe_ui6\assets_800x600.png`
  - `工作流任务\probe_ui6\storyboard_800x600.png`
- 探针：`工作流任务\probe_ui6\measure_800b.py`、`measure_story_800.py`、
  `measure_media_800.py`、`show_shot.py` 及根因复现脚本。

## D 断言未动与需裁决事项

**断言未动**：没有修改任何既有测试文件或断言，没有新增 skip 到既有用例；新测试只覆盖本批
行为。`skip台账.json` 仅追加本批新测试的一条平台限制登记。

**需 Claude 裁决／复跑**：

0. **`test_asset_detail.py::test_an_empty_anchor_is_refused` 1 红（本批有意契约变更）**：
   该用例 patch 的是 `asset_detail.messagebox.showerror`，期望空白锚点仍弹模态系统框；
   任务书第 5 条要求可恢复错误走非模态 `error()`，因此本批把四处保存／核对错误显式改为
   `notify(..., modal=False)`。按共用规矩未改既有断言；请 Claude 决定是把该用例改为断言
   `desktop.status`／非模态通知，还是允许本处保留模态例外（后者与任务书冲突）。
1. **任务书门禁未完成（两次尝试均未返回结论）**：首次因跨树 GUI 令牌等待超时，
   第二次锁释放后运行约 35 分钟仍无新增进度输出，已停止；请验收方复跑
   `run_selftests.py -k asset storyboard desktop_media ui_edges video_ui test_layers function_size_ratchet module_size_ratchet test_ui_batch6`。
   本批新增测试已用真 Tk 直接跑绿 7/7，两个棘轮与 skip 卫生也单独跑绿。
2. **首帧页 Treeview 请求宽度 660 > 内容实际宽 618**：内容区请求 660 仍 ≤ 窗口 800，
   实际宽度 618、无可见横向滚动条；Tk 的请求宽度额外包含表头内部留白。若验收要求
   “表格请求宽度也必须≤内容实际宽”，需要改共享表头 padding／列 floor，超出本批允许文件。
3. **分页控件缺失是现状而非遗漏**：资产页用分段插行（`ASSET_FIRST_ROWS`／
   `ASSET_ROWS_PER_FRAME`），没有上一页／下一页控件；本批没有凭空新增 pager。
4. **首帧空态**：页面已传 `empty_text='暂无镜头'`，但 `validate_episode()` 要求
   `shots` 非空，因此合法分镜走不到该空态；资产页空态已由测试覆盖。若产品要求首帧页
   在“无镜头”时显示空表，需要另批调整分镜校验契约。
5. **建议后续把 `_refresh_request_width()` 下沉到 `responsive_ui`**：本批在三个页面各留了
   一份等价实现（约 35 行，含销毁时取消挂起的 `after_idle`），避免改共用文件；后续统一时
   可由 Claude 合并为公共 helper。
6. **令牌选择（未新增共用令牌）**：卡片内边距 `SPACING['lg']`、卡片间距
   `SPACING['xs']`、长说明 `TEXT_DESC['wraplength']`、小字提示
   `TEXT_HINT['wraplength']`、页面标题 `FONTS['heading_3']`、表头／行字体
   `TABLE_HEADER_FONT`／`TABLE_ROW_FONT`、空态 padding `TABLE_EMPTY_PADDING`。
   若 Claude 认为需要区分“页面标题 13pt”，建议新增 `FONTS['page_heading']`（值
   `('Microsoft YaHei UI', 13, 'bold')`，用途：资产详情／资产清单标题），本批按
   “缺令牌先用最接近现牌”规则用了 `heading_3`。

## E 交付状态

**未提交，由 Claude 验收后提交。** 本批未执行任何 git 写命令；工作树中的其他批次文件
（`desktop.py`、`app.py`、`desktop_project_pages.py`、`desktop_script_pages.py`、
`keyframe_comfy.py`、`reference_wall.py`、`white_model.py` 等）未触碰、未回退。

## G RUI6b：空锚点断言同步到非模态口径

**结论**：`test_an_empty_anchor_is_refused` 已按 UI6 的有意契约变更改写。空锚点仍不写入
资产 JSON；提示文字仍含「不能为空」；提示改为断言非模态通知与状态栏可见。契约有意变更，
断言未弱化。

**改前断言**（已失效，原因是 UI6 把可恢复错误从模态框改为非模态）：

- patch `asset_detail.messagebox.showerror`，断言 `loudly.called` 为真，提示语
  「必须弹一句「不能为空」」。
- UI6 后 `edit_anchor` 调用 `notify(..., modal=False)`，不再触发 `showerror`，故该断言
  失败。

**改后断言**：

- patch `asset_detail.notify`（`wraps` 原函数），断言恰好调用 1 次。
- 断言通知正文包含「不能为空」。
- 断言 `modal=False`，且 `asset_detail.messagebox.showerror` 未被调用。
- 断言 `desktop.status` 状态栏文字包含「不能为空」，用户仍看得见提示。
- 保留 `assertIsNone(edit_anchor(...))` 与资产 JSON 中锚点为空，确认空值被拒绝、未保存。

**全文件同类断言排查**：

- `程序\tests\test_asset_detail.py`：仅 `test_an_empty_anchor_is_refused` 因本批非模态变更
  失效，已按上表改写。
- `程序\tests\test_ui_batch6_pages.py`：`test_recoverable_asset_error_is_non_modal` 已断言
  `notify(..., modal=False)`，与本批口径一致，无需改动。
- 其余 `showerror` 断言不涉及 `asset_detail` 的可恢复错误通道，未改。

**验证**：

- 单条：`test_asset_detail.AnchorTests.test_an_empty_anchor_is_refused` 通过（2.0 秒）。
- 逐模块等价回归（`--list` 选出的同一批 7 个模块，直接 unittest）：177 条，0 红。
  - `architecture.test_asset_detail_binding_boundary` 2 条 OK
  - `test_asset_detail` 36 条 OK（378.6 秒）
  - `test_asset_detail_service` 9 条 OK
  - `test_asset_gating` 18 条 OK
  - `test_assets` 93 条 OK
  - `test_assets_scope` 12 条 OK
  - `test_ui_batch6_pages` 7 条 OK
- 任务书原命令 `python -B run_selftests.py -k test_asset_detail asset_gating test_assets test_ui_batch6`
  连续 4 次（含 `--serial` 对照）在取锁／执行阶段被外部终止，仅输出取锁行后以 `EXIT=-1`
  结束，未产出测试报告；未将其记为通过。上述逐模块结果覆盖了同一 `--list` 选择集。

## 独立验收（Claude，主工作区四批同树）

- 四批同树合测：`run_selftests.py -k`（smoke --affected 选出的 97 个文件）共 2364 条，3 个文件红：`test_idea_inline_brief`（SP 改契约，mock 缺 `lock_fields`）、`test_ui_batch9`（`winfo_containing` 被桌面上 Chrome 窗口挡住）——均已修复复跑 0 红；`test_writing_api` 1 条在干净 HEAD 绿、主树红，因读取本机真实模型配置，与本批无关。
- `smoke_test.py` 默认 8/8；`--architecture` 368 条 4 红：模块体积（skill_panel 1503>1500，已压回 1500）、skip 台账漏登 UI6、TODO 快照行号 1019→1087（UI3 平移）——已修复，单跑 9/9；全量欠账为后台自动补跑项，不阻断。
