# R1357：O32 剪辑输出规格不能固定替代项目规格

类型：功能轮（§3.1；本项为「事实」→ 实现＋回归）。承接 R1267 清单 O32（O01—O31 已完成）。中央轮次 1357。本轮非五轮全量欠账点（上次绿全量 1356），按 O06—O48 验证策略只跑定向＋默认冒烟。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k output_spec` 15/15；关联 `-k production_lock idea_inline_brief idea_local_brief stage_prompt_governance script_contract workflow_settings animatic_timeline animatic_service` 136/136；架构与端到端 `-k integration edit_publication_boundary unification_ratchet coverage_audit_ratchet layers round_baselines todo_comment_snapshot skip_hygiene copy_rules` 66/66；`-k editing_page_controller stage_execution ui_edges media` 153/153；`-k asset_contract aspect_ratio stage_completion final_viewer handoff delivery skill_tools engine_probe` 120/120；默认冒烟全绿，0 红。主树唯一红为已知环境项 `test_workflow` 桌面模型用例（主树本地忽略配置 `程序/配置/宠物/配置.json` 指向不存在的 Claude 桌面路径），同一用例在干净 master 工作树绿，与本轮改动无关。
- 欠账：O32 关闭，清单剩 O33—O48；1357 − 1356 = 1 < 5，且未命中 §5（未改启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表），本轮不跑全量。

## 目标（R1267 清单 O32）
- 证据：`engine.py` 拼接滤镜固定 1280×720、30fps；`edit_service.py` Animatic 使用另一预览规格。
- 建议：预览规格与正式交付规格分开，正式输出来自项目/brief 中的比例、分辨率、帧率；明确裁切、留边或适配方式。预演低清是合理选择。
- 验收：横屏、竖屏、不同比例输入均不被默默压成横屏；字幕安全区和音量规则跟随输出配置；导出前显示实际规格。

## 实现（`script_contract.py`，L0）
- 新增 `OUTPUT_SPEC_DEFAULTS`（16:9／1920x1080／30）、`PREVIEW_SHORT_EDGE=720`、`PREVIEW_FPS=24`、`LOUDNESS_DEFAULTS`。
- 新增纯函数 `parse_ratio`／`parse_resolution`／`resolve_output_spec(locks)`（画幅→分辨率按 1080 短边推算、宽高取偶；`resolution`／`fps` 有显式值就用，非法或越界回退默认）、`preview_spec(locks)`（画幅跟项目，分辨率与帧率降到 720 短边／24）、`output_filter(spec)`（等比缩小＋居中留边 letterbox，绝不裁切）、`loudness_filter(spec)`、`overlay_metrics(spec)`（内嵌字幕字号与安全边距随输出高度等比）、`describe_output_spec(spec)`。
- `PRODUCTION_LOCK_DEFINITIONS` 增加 `resolution`（分辨率／输出分辨率）与 `fps`（帧率／输出帧率）：brief 与统筹锁现在能一并声明比例、分辨率、帧率。

## 实现（`engine.py`，L3）
- `_encode` 不再写死 1280×720/30：`spec=self.output_spec()`（读 `stage_config.workflow_lock`），视频过滤器用 `output_filter(spec)`，内嵌说明字幕用 `overlay_metrics(spec)`，音量用 `loudness_filter(spec)`；质检报告写入 `output_spec`（随 `qc.json` 落盘）。
- 新增 `output_spec()`／`output_spec_text()`：正式交付规格与界面一行实际规格。

## 实现（`edit_service.py` L2／`animatic_service.py` L2／`stage_execution_service.py` L3）
- `assemble_image_timeline(..., spec=None)` 改用 `preview_filter`／`preview_fps`；不给规格时回到历史 1280×720／24。
- `build_bundle(..., spec=None)` 把规格透传给合成器；`run_animatic` 用 `animatic_preview_spec(project)`（画幅跟制作锁、低配）传给预演。

## 实现（`desktop.py` L4／`editing_page_controller.py`）
- 后期页导出前显示「本次输出规格：…（等比缩放＋居中留边，不裁切）」；`EditingPageController.output_spec_text()` 拿不到就留空，页面照常可用。

## 验证
- `tests/test_output_spec.py`（新）15 条：默认/竖屏/方屏/宽幅规格推算；显式 `resolution`／`fps` 覆盖；非法值与越界帧率回退；奇数分辨率取偶；预演低清且画幅跟项目；过滤器含 scale/pad 且无 crop；字幕字号与安全边距随高度等比；音量规则字符串；规格一行文本；锁定义与提取标签；Studio 读锁与缺锁回退；预演合成使用给定规格（竖屏 720x1280）与默认 1280x720；Animatic 把 spec 透传给合成器。
- 真实 ffmpeg 端到端（临时项目）：9:16 项目成片 1080x1920@30fps、16:9 成片 1920x1080@30fps（源 640x360 被等比缩放＋留边，未裁切）；`qc.json` 记录 `output_spec`，`edit_manifest.json` 仍是有序镜头列表。
- 台账：`stage_execution_service.py` 因新增一行使 4 处裸 `json.loads` 行号 +1（108→109、1039→1040、1070→1071、1086→1087），已同步 `维护记录/架构统一基数.json` 第四项；`edit_service.py`（95）与 `animatic_service.py`（27）行号未变；未新增架构豁免、未新增 `skipTest`、未新增顶层模块；`desktop.py` 唯一 TODO 仍在 2753。
- 更新既有用例 `test_production_lock_ui` 的锁行控件数断言（3→`len(PRODUCTION_LOCK_DEFINITIONS)`），因为新增了分辨率／帧率两个锁字段。

## 边界
- 分辨率缺省按画幅与 1080 短边推算（16:9→1920x1080、9:16→1080x1920、21:9→2520x1080、1:1→1080x1080）；要非 1080 级或非常规帧率时，可在制作锁里用 `resolution`／`fps` 键显式覆盖（统筹锁第二层键由统筹定义，契约不列举）。
- 适配方式固定为「等比缩小＋居中留边（letterbox）」，不裁切、不拉伸；未提供裁切或填充选项。
- 音量归一化与字幕边距已随规格走；本轮未引入按平台分档的音量／字幕规范库。
- 预演仍是低清（720 短边／24fps）但画幅跟项目；未改预演清单结构与确认语义。
- 未实发模型请求、未重启应用；真实 ffmpeg 端到端为本地临时项目，非用户工程。
- 未命中 §5：未改启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表（`script_contract` L0、`edit_service`／`animatic_service` L2、`engine`／`stage_execution_service`／`editing_page_controller` L3、`desktop` L4 均在表内）。
