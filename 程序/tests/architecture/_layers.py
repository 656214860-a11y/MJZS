"""来自 architecture.md 第 3 节的模块分层登记。"""
from __future__ import annotations

LAYER_NAMES = {0: "L0 契约与事实层", 1: "L1 基础设施层", 2: "L2 领域服务层",
               3: "L3 编排与阶段层", 4: "L4 UI 层", 5: "L5 启动层"}
LAYERS: dict[str, int] = {}

def _register(layer: int, *names: str) -> None:
    for name in names:
        LAYERS[name] = layer

_register(2, "video_source_evidence")
_register(0, "pet_bus", "script_contract", "script_brief", "script_manifest_contract", "script_manifest_schema", "script_output_spec", "script_natural_gate", "asset_contract", "episode_contract", "service_contract", "error_codes", "project_context", "stage_layout", "stage_path_service", "storyboard_paths", "project_stages", "platform_tools",
          "prompt_templates", "shot_batches", "production_model_contract", "app_metadata")
# R1647：stage_model_value 只依赖 file_cache／pet_bus（无 Tk、无编排状态），按实际依赖登记为 L1，
# 纠正原先按名字后缀落在 L3 的旧账；L2 领域服务不该为读一个阶段模型名反向依赖编排层。
_register(1, "client_profiles", "model_pool", "model_secrets", "config_snapshot", "pet_llm", "request_ledger", "file_cache", "hash_backend",
          "storage_maintenance", "log_maintenance", "workspace_maintenance", "diagnostic_capture", "app_logging", "line_endings", "app_icon", "workflow_process_registry", "script_text_reader", "stage_model_value", "native_asset_codec", "comfy_runtime", "ui_tokens", "continuity_ledger",
          "aigc_lint")
_register(2, "task_center_service", "keyframe_evidence", "animatic_service", "writing_files", "writing_workflow", "idea_chat", "idea_brief_form", "idea_attachments", "idea_script_heuristic", "idea_document_paths", "idea_transcript", "download_inbox",
          "storyboard_lifecycle", "storyboard_catalog_service",
          "storyboard_edit_service",
          "asset_context", "asset_gating", "asset_batch_lifecycle",
          "asset_batch_service", "asset_batch_state_service", "asset_batch_selection_service", "asset_generated_import_service", "asset_detail_service",
          "keyframe", "keyframe_api", "keyframe_batch", "keyframe_lifecycle_service", "cloud_video_service", "white_model_service", "storyboard_source_service", "tts_api", "speech_api", "subtitle_timing", "pet_test_service", "pet_performance_service", "local_video_settings_service",
          "previs", "previs_routing", "previs_progress_service", "handoff_service", "edit_service", "final_service", "storyboard_adoption_service", "delivery_import_service", "confirm_gates", "recycle_recovery_service",
          "recon_service")
# R1649：删除 3 个既无实体文件、也无采用方的僵尸登记名（project_storage／asset_detail_ui／workflow）；
# 登记表每一名须满足「有实体 .py ∨ 在 TOOLS ∨ 在 historical_name_audit.entrypoints」，由 test_layers 断言。
_register(3, "exit_maintenance", "pet_chat_coordinator", "project_context_factory", "stage_flow", "stage_exec", "stage_parallel", "stage_config", "stage_models",
          "skill_notes", "skill_orchestrator", "skill_registry", "codex_skill_sync", "workflow_tasks",
          "agent_dispatch", "engine", "stage_contract_report", "stage_execution_service", "stage_asset_gateways", "stage_animatic_gateways", "stage_previs_gateways", "stage_gate_gateways", "stage_handoff_gateways", "stage_publication", "stage_write_preparation_service", "stage_download_inbox_service", "desktop_startup_service", "desktop_automation_service", "desktop_auto_state", "pet_broadcast_state", "idea_chat_controller", "idea_semantic_brief_service",
          "writing_api", "writing_unconfirm", "script_skill_report", "storyboard_plan_service", "storyboard_final", "storyboard_final_controller", "storyboard_page_controller", "keyframe_page_controller", "storyboard_selection", "storyboard_direct_api", "audio_direct_api", "video_prompt_direct_api", "image_direct", "storyboard_catalog", "asset_batch_controller", "asset_page_controller", "editing_page_controller", "page_navigation_controller", "media_page_controller",
          "previs_automation", "previs_batch_service", "previs_monitor", "asset_auto_batch_service", "asset_batch_execution", "stage_completion_service", "white_model_persistence_controller")
_register(4, "desktop", "pet_ui", "pet_cloud", "pet_cloud_text", "pet_cloud_geometry", "pet_cloud_shape", "pet_cloud_tail", "pet_cloud_timing", "pet_cloud_hint", "pet_cloud_place", "pet_cloud_move_guard", "responsive_ui", "ui_theme", "ui_popup", "ui_widgets", "ui_composer_style", "ui_splash", "ui_tooltip", "ui_stage_popups", "ui_rounded", "ui_motion", "ui_scroll", "ui_hover_fade", "ui_dialogs", "ui_shortcuts", "ui_icons", "cell_hover", "prompt_window", "asset_detail", "asset_batch", "native_assets", "storyboard_files", "storyboard_table_ui", "cloud_video", "local_video", "local_previs", "previs_progress", "white_model", "production_lock_fields", "skill_panel", "skill_panel_presets", "skill_panel_support", "stage_model_picker", "skill_panel_workflow", "skill_note_render", "script_view_style", "app")
_register(5, "app_shortcut")

# R741：顶层运行期模块必须逐一入表。层级按实际静态依赖和职责判断，不能以名称后缀代替。
_register(0, "artifact_schema", "api_models", "frame_checks", "model_protocol", "pet_settings_contract",
          "prop_assets", "shot_selection", "storyboard_contract", "workflow_context_budget")
_register(1, "api_endpoints", "broadcaster", "clipboard_lock",
          "comfy_service", "engine_probe", "h3_reference_adapter", "http_client", "model_diagnostics", "model_router",
          "native_apps", "seedream_api", "token_saver", "tk_timers")
_register(2, "asset_batch_settings_service", "asset_plan", "asset_resume", "audio_import_service", "edit_export", "usage_overview",
          "desktop_settings_service", "legacy_adoption_service", "project_naming",
          "projects", "script_preview_service", "script_structure_edit_controller", "script_workspace_service", "stage_workspace_service",
          "storyboard_adoption_contract", "storyboard_rows_service",
          "storyboard_storage", "subtitle_export_service", "video_lifecycle_service", "video_prompt_publication",
          "video_task_state", "workflow_context", "writing", "writing_tools", "writing_quality", "writing_stream")
_register(3, "image_agent_runner", "keyframe_model_service", "skill_budget", "skill_templates", "subtitle_export_controller",
          "stage_handler_registry", "storyboard_recycle_service", "workflow_context_controller", "workflow_engines", "recycle_recovery_controller")
_register(4, "desktop_auto_flows", "desktop_direct_dispatch", "desktop_storyboard_direct", "desktop_audio_direct", "desktop_video_prompt_direct", "desktop_image_direct", "desktop_file_card", "desktop_idea_bubbles", "desktop_idea_attachments", "desktop_page_registry", "desktop_tk_gc", "desktop_tray", "desktop_automation_tick", "desktop_layout", "desktop_layout_resize", "desktop_pet_bridge", "desktop_async_tasks", "desktop_idea_chat", "desktop_idea_deferred", "desktop_writing_page", "desktop_storyboard_page", "desktop_idea_menus", "pet_ui_support", "pet_ui_stages", "pet_ui_settings", "pet_ui_voice", "pet_ui_view", "pet_ui_popup", "desktop_asset_pages", "desktop_script_pages", "desktop_media_pages", "desktop_project_pages", "desktop_page_support", "task_center_ui", "environment_check", "version_picker", "skill_import_service", "master_skill", "master_import_service", "asset_reference_images", "asset_reference_import", 
          "asset_reference_search", "asset_skill_batch", "background_characters", "keyframe_comfy",
          "keyframe_import", "pet_agent", "pet_models_ui", "pet_models_tabs", "speech_settings_ui", "pet_report", "pet_settings_ui",
          "reference_wall", "responsive_ui", "seedream_settings",
          "shared_video_controls", "shot_numbering", "skill_tools", "tts_settings",
          "video_navigation", "video_progress", "video_prompt_results", "white_model_ref", "workflow_agents",
          "writing_page_controller")
_register(5, "desktop_launcher")
# R1895：账户会员客户端（设计文档 说明/账户会员云端设计.md §5.1）。
_register(1, "lease_verifier", "account_store", "update_notice")
_register(2, "entitlement_service", "account_client")
_register(3, "account_controller")
_register(4, "account_inputs", "desktop_account_page", "desktop_login_gate", "desktop_master_update", "desktop_page_nav", "desktop_lifecycle", "master_skill_update")
_register(3, "edit_habits")
_register(4, "edit_habits_dialog")
# R2184：工作流调用设置窗口从 workflow_settings 拆出（R2178 J1），workflow_settings 自身不再导入 Tk。
_register(4, "workflow_settings_dialog")
# R2311（J 路线 #20）：缩略图缓存要 tk.PhotoImage，调用方全是 L4，改登记 L4；「选择分镜」下拉框从 storyboard_selection 拆出。
_register(4, "asset_thumbs", "storyboard_source_selector")
# R2313：商店包与 Claude Desktop 图形程序定位自 workflow_settings 拆出，只依赖注册表适配与标准库。
_register(1, "store_program_locator")
# R2189：Qwen「API 设置」窗口从 qwen_setup 拆出（R2178 J2），qwen_setup 自身不再导入 Tk。
_register(4, "qwen_setup_dialog")

# R2191（R2178 J3）：按真实静态依赖重登记，纠正按名字后缀落在 L3／L4 的旧账，不改任何生产代码。
# artifact_lineage 无依赖且被 L0 契约引用 → L0；pet_state／ui_plugin_registry／integrations 只依赖 L0／L1 → L1；
# qwen_setup 只依赖 L1（连接设置与密钥读写，与 model_secrets 同类）→ L1；qwen_adapter 是引擎适配器，与 workflow_engines 同层 → L3；
# workflow_settings／legacy_compat 依赖 L3 的配置与技能注册 → L3。（登记 L2 会触发 L2 返回契约与发布债务门禁，故不选 L2。）
_register(0, "artifact_lineage")
_register(1, "pet_state", "ui_plugin_registry", "integrations", "qwen_setup")
_register(3, "workflow_settings", "legacy_compat", "qwen_adapter", "skill_inline")
# R2202（R2178 J5–J7）：Tk 弹窗拆进 L4 对话模块后，这四个模块只剩数据与规则，按真实依赖登记：
# project_settings／cloud_assets／asset_prompt_rules 只依赖 L0／L1 → L1；
# asset_reference_prompts 懒加载 L2 的 storyboard_catalog_service → L2。
_register(1, "project_settings", "cloud_assets", "asset_prompt_rules")
_register(2, "asset_reference_prompts")
_register(4, "project_settings_dialog", "cloud_assets_dialog", "asset_prompt_check_dialog", "asset_reference_prompts_dialog")
# R2203（R2178 J10）：模型调用计量序列只依赖传入的台账对象，无导入 → L1。
_register(1, "model_metering")
_register(3, "desktop_send_ledger")
_register(4, "desktop_send_choice")

# 非运行期外围脚本：它们不会作为产品层导入；显式留名可防止新增顶层脚本绕过审计。
TOOLS: dict[str, str] = {
    "blender_previs_template": "Blender 独立模板脚本，依赖 bpy，不在桌面产品运行期。",
    "codex_paste": "Codex 外围粘贴工具，不在桌面产品运行期。",
    "codex_tasks": "Codex 外围任务工具，不在桌面产品运行期。",
    "console_submit": "控制台提交工具，不在桌面产品运行期。",
    "batch_frames_tool": "独立批处理工具包；其子模块不属于顶层产品模块扫描范围。",
}

ALLOWED_EXCEPTIONS: frozenset[tuple[str, str]] = frozenset()
IGNORE = frozenset({"__future__", "ast", "collections", "concurrent", "contextlib", "csv", "dataclasses",
                    "datetime", "enum", "functools", "hashlib", "html", "importlib", "io", "json",
                    "logging", "math", "os", "pathlib", "queue", "re", "shutil", "subprocess", "sys",
                    "tempfile", "threading", "time", "traceback", "typing", "unittest", "uuid"})
