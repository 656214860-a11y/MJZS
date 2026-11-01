# R1379：UI 统一入口覆盖轮 — 卡片容器（第 2 批：首帧 ComfyUI 窗 / 桌面六区，收口）

类型：功能轮（§3.1，UI 统一入口：卡片容器覆盖；不改业务逻辑、阶段、路径与分层）。中央轮次 1379（`.git/round-counter.json` 的 `last_claimed=1379`）。范围＝`维护记录/UI统一入口路线图_v1.md` 待收口 4 项之「卡片容器」收口轮（§一 第 3 项，完成判据「组件与样式已存在；旧页面覆盖率待审计。」）。

## 三个必答
- 本轮类型：功能轮（§3.1）——页面级信息／操作单元承载区从 `ttk.LabelFrame` 迁移到统一 `ui_widgets.Card`；本轮为分批迁移第 2 批（收口）。
- 测试：架构 `smoke_test.py --architecture` **325/325**（原 323，只增不减；只在既有 `test_card_boundary.py` 增 2 条方法，未增删门禁文件，§5 清单不变）；定向 `run_selftests.py -k "keyframe_comfy keyframe video_ui video batch_frames desktop ui_edges"` **468 条 / 0 文件红 / 234.5 秒**（含 `test_keyframe_comfy`、`test_video_ui`、`test_ui_edges`、`test_desktop_startup_perf` 14/14）；默认冒烟 `smoke_test.py` **8/8**；`py_compile` 5 文件 OK。
- 欠账：1379 − 1375 = 4 < 5；未命中 §5 第 350 行的「全量升级条件」（启动路径／Tk 控件生命周期／删除语义／层级登记表均未改）。按用户「不因为是收尾就跑全量兜底」不跑全量。卡片容器**完成全量覆盖审计**（全站点已用 Card 或列明豁免，见审计表）。

## 范围与口径（`ui_components.md` §卡片）
- 卡片规格：背景 `color.background.card`、边框 1px `color.border.default`、圆角 `radius.lg`、内边距 `space.lg`；「卡片承载一个完整的信息或操作单元」。
- 收口口径：页面／对话框里承载一组相关字段或说明、构成一个完整信息／操作单元的最外层容器，用 `ui_widgets.Card`（标题用卡内普通标签，卡片不用 LabelFrame 的标题行——与 `test_ui_edges` 既有「无标签行卡片」一致）。
- 本轮参照 R932–R960「单页粒度」分批：只迁移首帧 ComfyUI 窗两窗 + 桌面六区，不整仓机械替换。

## 实现（迁移的 8 处）
### 1. `keyframe_comfy.py`：`show` 的两窗
- `model_box`「生成模型与接口」、`local_box`「ComfyUI 连接与模型接口」由 `ttk.LabelFrame(form,text=…,padding=8)` → `Card(form)` ＋ 卡内标题 `ttk.Label`（`grid(row=0,columnspan=…)`）；原 grid 行顺移（模型/画幅/批次意图 row 0→1、hint 1→2、按钮行 2→3；图片格式行 0→1、循环字段 `index`→`index+1`、保存/启动检测/删除模型 1/2/3→2/3/4）。导入补 `Card`。`local_box.pack(fill='x',padx=14,pady=6,after=model_box)` 与 `pack_forget()` 逻辑不变。
### 2. `desktop.py`：六区
- `reference_sites`：分类导航组 `ttk.LabelFrame(self.content,text=category,padding=8)` → `Card(self.content,padding=8)` ＋ 卡内标题 `grid(row=0,column=0,columnspan=2)`；卡片 `arrange` 与首挂载的行号 `index//2`→`index//2+1`（`box.site_layout`、`<Configure>` 绑定、`columnconfigure`、`uniform='sites'` 不变）。
- `continuity_page.table_of`：表格框 `ttk.LabelFrame(self.content,text=title,padding=4)` → `Card(self.content,padding=4)` ＋ 标题 `ttk.Label(frame,text=title).pack(anchor='w')`（`DataTable.pack(fill='both',expand=True)` 不变）。
- `continuity_page`：`foot`「待办与裁决」→ `Card(self.content,padding=4)` ＋ 标题 pack。
- `video_home`：`facts`「开工前先确认」→ `Card(self.content,padding=14)` ＋ 标题 `grid(row=0,columnspan=2)`，确认行 `row`→`row+1`；`local`「本地生成」、`cloud`「线上生成」→ `Card(self.content,padding=16)` ＋ 标题 pack。
- 导入 `ui_widgets` 补 `Card`。

## 测试契约同步（§2.4：有意 UI 契约变化）
- `tests/test_keyframe_comfy.py`：`frames` 文字扫描 `ttk.LabelFrame`→`ttk.Label`（该窗不再有 LabelFrame；`any("ComfyUI"…)` 仍成立——标题现为卡内标签；`any("Agent"…)` 仍为假）。
- `tests/test_video_ui.py`：`"开工前先确认" in widget_texts(d.content, ttk.LabelFrame)` → `ttk.Label`。
- `tests/architecture/test_card_boundary.py` 增 2 条：`test_keyframe_comfy_windows_use_card`（首帧窗 ≥2 Card）、`test_desktop_pages_use_card_for_content_groups`（桌面页 ≥6 Card）。文件已在 §5 清单内，不新增门禁文件。

## 验证
- 架构 `smoke_test.py --architecture`：**325/325、0 红**（原 323，+2 为本轮新增方法；第 1 次通过，无 TODO 快照漂移）。
- 定向 `run_selftests.py -k "keyframe_comfy keyframe video_ui video batch_frames desktop ui_edges"`：**468 条、0 文件红、234.5 秒**（`test_desktop_startup_perf` 14/14 本轮通过——最近两次全量里抖动的阈值断言未复现）。
- 默认冒烟 `smoke_test.py`：**8/8**；`py_compile desktop.py keyframe_comfy.py tests/test_keyframe_comfy.py tests/test_video_ui.py tests/architecture/test_card_boundary.py` OK。
- 新增 `skipTest`：无。

## 卡片容器覆盖审计表（全量站点，收口）
- 已用 Card（门禁固化，共 21 页）：云端视频、本地视频、云端工作室(app.settings)、资产参考导入、云端资产、背景角色、参考墙、Qwen、TTS、Seedream、提示词优化器、工作流设置、宠物设置中心、宠物模型窗、白模选择、白模工作区、资产详情页、原生资产窗、批量资产表单、**首帧 ComfyUI 窗**、**桌面页（分类导航／表格框／待办与裁决／开工前先确认／本地生成／线上生成 六区）**。
- 明确豁免（并说明理由，不属「页面级单元容器」）：`white_model.py:124/132`（本地/线上白模小节）、`workflow_settings.py:775`（自定义模型/Skill/API 小节）、`cloud_video.py:218`（说明与限制小节）三处 LabelFrame 均位于**已用 Card 的窗口内部**（`white_model.py:37`、`workflow_settings.py:764`、`cloud_video.py:46` 的 `body=Card(…)`），是卡内小节；`skill_panel.py:1305` 技能说明是锁定几何传播的列表＋正文阅读区（`grid_propagate(False)`，R934 曾回退类似改动），不属配置卡；`batch_frames_tool/启动批量首帧.pyw:29` 是独立工具脚本，不属桌面主界面页面。

## 全量判定
- 1379 − last_full_safe_all_round(1375) = 4 < 5；未命中 §5 第 350 行「全量升级条件」（启动路径／Tk 控件销毁重建／删除语义／层级登记表均未改：Card 仅改容器类与 Style，不销毁重建控件；本轮均为普通 `grid`/`pack` 与 `<Configure>` 事件绑定，未改 Tk 控件生命周期）。
- 本轮改了生产代码与测试，内容树变化，7 日内同树绿凭据不可复用；按用户指令「不因为是收尾就跑全量兜底」不跑全量。
- 备注：§5 第 343 行全量触发表另列「路线图条目收口」一项；本轮为卡片容器条目收口，按用户本轮口径（要求 4）不据此跑全量，已在收尾说明中明示，供用户复核。

## 提交
- 内容：`程序/keyframe_comfy.py`、`程序/desktop.py`、`程序/tests/test_keyframe_comfy.py`、`程序/tests/test_video_ui.py`、`程序/tests/architecture/test_card_boundary.py`。
- 报告与状态页：`程序/tasks_round/tasks_round_1379_result.md`、`程序/project_status.md`（轮次头改为 1380）。
- 未触碰主树他人已暂存改动与未跟踪用户目录。
