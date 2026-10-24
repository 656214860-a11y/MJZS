"""来自 architecture.md 第 3 节的模块分层登记。"""
from __future__ import annotations

LAYER_NAMES = {0: "L0 契约与事实层", 1: "L1 基础设施层", 2: "L2 领域服务层",
               3: "L3 编排与阶段层", 4: "L4 UI 层", 5: "L5 启动层"}
LAYERS: dict[str, int] = {}

def _register(layer: int, *names: str) -> None:
    for name in names:
        LAYERS[name] = layer

_register(2, "video_source_evidence")
_register(0, "pet_bus", "script_contract", "script_manifest_contract", "script_manifest_schema", "script_output_spec", "asset_contract", "episode_contract", "service_contract", "project_context", "stage_layout", "stage_path_service", "storyboard_paths", "project_stages", "platform_tools",
          "prompt_templates", "shot_batches", "production_model_contract", "app_metadata")
# R1647：stage_model_value 只依赖 file_cache／pet_bus（无 Tk、无编排状态），按实际依赖登记为 L1，
# 纠正原先按名字后缀落在 L3 的旧账；L2 领域服务不该为读一个阶段模型名反向依赖编排层。
_register(1, "client_profiles", "model_pool", "model_secrets", "pet_llm", "file_cache", "hash_backend",
          "storage_maintenance", "log_maintenance", "workspace_maintenance", "diagnostic_capture", "app_logging", "line_endings", "app_icon", "workflow_process_registry", "script_text_reader", "stage_model_value", "native_asset_codec", "comfy_runtime", "ui_tokens", "continuity_ledger")
_register(2, "task_center_service", "keyframe_evidence", "animatic_service", "writing_files", "writing_workflow", "idea_chat", "idea_brief_form", "idea_attachments", "idea_script_heuristic", "idea_document_paths", "idea_transcript", "download_inbox",
          "storyboard_lifecycle", "storyboard_catalog_service",
          "storyboard_edit_service",
          "asset_context", "asset_gating", "asset_batch_lifecycle",
          "asset_batch_service", "asset_batch_state_service", "asset_batch_selection_service", "asset_generated_import_service", "asset_detail_service",
          "keyframe", "keyframe_api", "keyframe_batch", "keyframe_lifecycle_service", "cloud_video_service", "white_model_service", "storyboard_source_service", "tts_api", "subtitle_timing", "pet_test_service", "pet_performance_service", "local_video_settings_service",
          "previs", "previs_routing", "previs_progress_service", "handoff_service", "edit_service", "final_service", "storyboard_adoption_service", "delivery_import_service", "confirm_gates", "recycle_recovery_service",
          "recon_service")
# R1649：删除 3 个既无实体文件、也无采用方的僵尸登记名（project_storage／asset_detail_ui／workflow）；
# 登记表每一名须满足「有实体 .py ∨ 在 TOOLS ∨ 在 historical_name_audit.entrypoints」，由 test_layers 断言。
_register(3, "exit_maintenance", "pet_chat_coordinator", "project_context_factory", "stage_flow", "stage_exec", "stage_parallel", "stage_config", "stage_models",
          "skill_notes", "skill_orchestrator", "skill_registry", "codex_skill_sync", "workflow_tasks",
          "agent_dispatch", "engine", "integrations", "stage_contract_report", "stage_execution_service", "stage_publication", "stage_write_preparation_service", "stage_download_inbox_service", "desktop_startup_service", "desktop_automation_service", "idea_chat_controller", "idea_semantic_brief_service",
          "writing_api", "script_skill_report", "storyboard_plan_service", "storyboard_final", "storyboard_final_controller", "storyboard_page_controller", "keyframe_page_controller", "storyboard_selection", "storyboard_catalog", "asset_batch_controller", "asset_page_controller", "editing_page_controller",
          "previs_automation", "previs_batch_service", "previs_monitor", "asset_auto_batch_service", "asset_batch_execution", "stage_completion_service", "white_model_persistence_controller")
_register(4, "desktop", "pet_ui", "pet_cloud", "pet_cloud_text", "pet_cloud_geometry", "pet_cloud_shape", "pet_cloud_tail", "pet_cloud_timing", "pet_cloud_hint", "pet_cloud_place", "pet_cloud_move_guard", "responsive_ui", "ui_theme", "ui_popup", "ui_widgets", "ui_stage_popups", "ui_rounded", "ui_motion", "ui_scroll", "ui_hover_fade", "ui_dialogs", "ui_shortcuts", "ui_icons", "cell_hover", "prompt_window", "asset_detail", "asset_batch", "native_assets", "storyboard_files", "storyboard_table_ui", "cloud_video", "local_video", "local_previs", "previs_progress", "white_model", "production_lock_fields", "skill_panel", "skill_panel_presets", "skill_panel_support", "skill_panel_workflow", "skill_note_render", "script_view_style", "app")
_register(5, "app_shortcut")

# R741：顶层运行期模块必须逐一入表。层级按实际静态依赖和职责判断，不能以名称后缀代替。
_register(0, "artifact_schema", "api_models", "frame_checks", "model_protocol", "pet_settings_contract",
          "prop_assets", "shot_selection", "storyboard_contract", "workflow_context_budget")
_register(1, "api_endpoints", "artifact_lineage", "asset_thumbs", "broadcaster", "clipboard_lock",
          "comfy_service", "engine_probe", "h3_reference_adapter", "model_diagnostics", "model_router",
          "native_apps", "seedream_api", "token_saver", "tk_timers")
_register(2, "asset_batch_settings_service", "asset_plan", "asset_resume", "audio_import_service", "edit_export", "usage_overview",
          "desktop_settings_service", "legacy_adoption_service", "project_naming",
          "projects", "script_preview_service", "script_structure_edit_controller", "script_workspace_service", "stage_workspace_service",
          "storyboard_adoption_contract", "storyboard_rows_service",
          "storyboard_storage", "subtitle_export_service", "video_lifecycle_service", "video_prompt_publication",
          "video_task_state", "workflow_context", "writing", "writing_tools", "writing_quality")
_register(3, "image_agent_runner", "keyframe_model_service", "skill_budget", "skill_templates", "subtitle_export_controller",
          "stage_handler_registry", "storyboard_recycle_service", "workflow_context_controller", "workflow_engines", "recycle_recovery_controller")
_register(4, "desktop_auto_flows", "desktop_file_card", "desktop_idea_bubbles", "desktop_page_registry", "desktop_tk_gc", "desktop_tray", "desktop_automation_tick", "desktop_layout", "desktop_layout_resize", "desktop_pet_bridge", "desktop_async_tasks", "desktop_idea_chat", "desktop_idea_deferred", "desktop_writing_page", "desktop_storyboard_page", "desktop_idea_menus", "pet_ui_support", "pet_ui_stages", "pet_ui_settings", "pet_ui_voice", "pet_ui_view", "pet_ui_popup", "desktop_asset_pages", "desktop_script_pages", "desktop_media_pages", "desktop_project_pages", "desktop_page_support", "task_center_ui", "environment_check", "version_picker", "skill_import_service", "master_skill", "asset_prompt_rules", "asset_reference_images", "asset_reference_import", "asset_reference_prompts",
          "asset_reference_search", "asset_skill_batch", "background_characters", "cloud_assets", "keyframe_comfy",
          "keyframe_import", "pet_agent", "pet_models_ui", "pet_report", "pet_settings_ui", "pet_state",
          "project_settings", "qwen_adapter", "qwen_setup", "reference_wall", "responsive_ui", "seedream_settings",
          "shared_video_controls", "shot_numbering", "skill_tools", "tts_settings", "ui_plugin_registry",
          "video_navigation", "video_progress", "video_prompt_results", "white_model_ref", "workflow_agents",
          "workflow_settings", "writing_page_controller", "legacy_compat")
_register(5, "desktop_launcher")
# R1895：账户会员客户端（设计文档 说明/账户会员云端设计.md §5.1）。
_register(1, "lease_verifier", "account_store", "update_notice")
_register(2, "entitlement_service", "account_client")
_register(3, "account_controller")
_register(4, "desktop_account_page", "desktop_master_update", "master_skill_update")

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
