"""来自 architecture.md 第 3 节的模块分层登记。"""
from __future__ import annotations

LAYER_NAMES = {0: "L0 契约与事实层", 1: "L1 基础设施层", 2: "L2 领域服务层",
               3: "L3 编排与阶段层", 4: "L4 UI 层", 5: "L5 启动层"}
LAYERS: dict[str, int] = {}

def _register(layer: int, *names: str) -> None:
    for name in names:
        LAYERS[name] = layer

_register(0, "pet_bus", "script_contract", "script_manifest_contract", "asset_contract", "episode_contract", "service_contract", "project_context", "stage_layout", "stage_path_service", "storyboard_paths", "project_stages",
          "prompt_templates", "shot_batches", "continuity_ledger", "production_model_contract", "app_metadata")
_register(1, "model_pool", "model_secrets", "pet_llm", "file_cache", "hash_backend",
          "storage_maintenance", "log_maintenance", "diagnostic_capture", "line_endings", "app_icon", "workflow_process_registry", "platform_tools", "script_text_reader", "native_asset_codec", "comfy_runtime", "ui_tokens")
_register(2, "writing_files", "writing_roles", "writing_workflow", "idea_chat", "idea_attachments",
          "storyboard_lifecycle", "storyboard_catalog_service",
          "storyboard_edit_service",
          "asset_context", "asset_gating", "asset_batch_lifecycle",
          "asset_batch_service", "asset_batch_state_service", "asset_batch_selection_service", "asset_generated_import_service", "asset_detail_service",
          "keyframe", "keyframe_api", "keyframe_batch", "keyframe_lifecycle_service", "cloud_video_service", "white_model_service", "storyboard_source_service", "tts_api", "subtitle_timing", "pet_test_service", "pet_performance_service", "local_video_settings_service",
          "previs", "previs_routing", "previs_progress_service", "handoff_service", "edit_service", "final_service", "storyboard_adoption_service", "delivery_import_service", "confirm_gates", "recycle_recovery_service")
_register(3, "stage_flow", "stage_exec", "stage_parallel", "stage_config", "stage_models",
          "skill_orchestrator", "skill_registry", "workflow", "workflow_tasks",
          "agent_dispatch", "engine", "integrations", "project_storage", "stage_contract_report", "stage_execution_service", "desktop_startup_service", "desktop_automation_service", "idea_chat_controller",
          "writing_api", "script_skill_report", "storyboard_plan_service", "storyboard_final", "storyboard_final_controller", "storyboard_page_controller", "keyframe_page_controller", "storyboard_selection", "storyboard_catalog", "asset_batch_controller", "asset_page_controller", "editing_page_controller",
          "previs_automation", "previs_batch_service", "previs_monitor", "asset_auto_batch_service", "asset_batch_execution", "stage_completion_service", "white_model_persistence_controller")
_register(4, "desktop", "pet_ui", "pet_cloud", "pet_cloud_text", "pet_cloud_geometry", "pet_cloud_shape", "pet_cloud_tail", "responsive_ui", "ui_theme", "ui_widgets", "ui_dialogs", "ui_shortcuts", "ui_icons", "cell_hover", "prompt_window", "asset_detail_ui", "asset_detail", "asset_batch", "native_assets", "storyboard_files", "storyboard_table_ui", "cloud_video", "local_video", "local_previs", "previs_progress", "white_model", "skill_panel", "app")
_register(5, "app_shortcut")

# R741：顶层运行期模块必须逐一入表。层级按实际静态依赖和职责判断，不能以名称后缀代替。
_register(0, "api_models", "frame_checks", "model_protocol", "pet_settings_contract",
          "prop_assets", "shot_selection", "storyboard_contract", "workflow_context_budget")
_register(1, "api_endpoints", "artifact_lineage", "asset_thumbs", "broadcaster", "clipboard_lock",
          "comfy_service", "engine_probe", "h3_reference_adapter", "model_diagnostics", "model_router",
          "native_apps", "seedream_api", "token_saver", "tk_timers")
_register(2, "asset_batch_settings_service", "asset_plan", "asset_resume", "audio_import_service",
          "desktop_settings_service", "legacy_adoption_service", "project_naming",
          "projects", "script_preview_service", "script_workspace_service", "stage_workspace_service",
          "storyboard_adoption_contract", "storyboard_rows_service",
          "storyboard_storage", "subtitle_export_service", "video_lifecycle_service", "video_prompt_publication",
          "video_task_state", "workflow_context", "writing", "writing_tools", "hollmwood_roles")
_register(3, "image_agent_runner", "keyframe_model_service", "skill_budget", "skill_templates",
          "stage_handler_registry", "stage_model_value", "storyboard_recycle_service", "workflow_engines", "recycle_recovery_controller")
_register(4, "asset_prompt_rules", "asset_reference_images", "asset_reference_import", "asset_reference_prompts",
          "asset_reference_search", "asset_skill_batch", "background_characters", "cloud_assets", "keyframe_comfy",
          "keyframe_import", "pet_agent", "pet_models_ui", "pet_report", "pet_settings_ui", "pet_state",
          "project_settings", "qwen_adapter", "qwen_setup", "reference_wall", "responsive_ui", "seedream_settings",
          "shared_video_controls", "shot_numbering", "skill_tools", "tts_settings", "ui_plugin_registry",
          "video_navigation", "video_progress", "video_prompt_results", "white_model_ref", "workflow_agents",
          "workflow_settings", "writing_page_controller", "legacy_compat")
_register(5, "desktop_launcher")

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
