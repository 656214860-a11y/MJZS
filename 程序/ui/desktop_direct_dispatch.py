# -*- coding: utf-8 -*-
"""API 模型直连的唯一分流点（L4）：_FlowAgentLaunch.build 在起 Agent 前调一次，命中就由程序直连、不经 Qwen Code。"""


def dispatch(host, stage, config, direct, intake_only):
    """命中直连条件则起对应后台作业并返回 True；白模预演选了 API 模型则直接抛提示。"""
    if stage == 'storyboard' and not intake_only:       # REQ-S03-53
        from orchestrator.storyboard_direct_api import direct_model
        if direct_model(config):
            from ui.desktop_storyboard_direct import run_storyboard_direct
            run_storyboard_direct(host, config)
            return True
    if stage == 'audio' and not intake_only:            # REQ-S11-50
        from orchestrator.audio_direct_api import direct_model
        if direct_model(config) and hasattr(host, 'current_frame_json'):
            from ui.desktop_audio_direct import run_audio_direct
            run_audio_direct(host, config)
            return True
    if stage == 'video_prompt' and direct and not intake_only:      # REQ-S10-50
        from orchestrator.video_prompt_direct_api import direct_model
        if direct_model(config):
            from ui.desktop_video_prompt_direct import run_video_prompt_direct
            run_video_prompt_direct(host, config, direct)
            return True
    if stage == 'assets' and direct and not intake_only and config['engine'] == 'qwen':   # REQ-S05-50／REQ-S08-52
        from ui.desktop_image_direct import run_image_direct
        run_image_direct(host, direct)
        return True
    if stage == 'previs':                               # REQ-S09-50：白模预演只走本地 Agent
        from orchestrator.previs_automation import require_local_agent
        require_local_agent(config)
    return False
