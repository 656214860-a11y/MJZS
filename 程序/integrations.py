"""Launch installed applications without invoking generation APIs."""
import os
from pathlib import Path

SKILLS={'screenplay':('万能工作流','coconah-ai-short-drama-agent-skill','短剧剧本创作万能工作流 (Short Drama Screenplay Workflow)'),
        'drama-skills':('Drama分镜','short-drama-storyboard','short-drama-storyboard'),
        'jingju-skills':('鲸剧工作流','jingju-skills','jingju-skills')}

from contract.platform_tools import tool_path, _TOOL_CACHE


def skill_file(folder,skill_home=None):
    directory=SKILLS[folder][1]
    home=Path(skill_home) if skill_home else Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'
    path=(home/directory/'SKILL.md').resolve()
    if not path.is_file():raise ValueError('未找到Codex已安装技能：'+str(path))
    return path

from script_text_reader import script_text


def comfy_executable(settings):
    choices=[settings.get('comfy_exe',''),r'C:\Program Files\Comfy Desktop\Comfy Desktop.exe',str(Path(os.environ.get('LOCALAPPDATA',''))/'Programs/ComfyUI/ComfyUI.exe')]
    return next((Path(p) for p in choices if p and Path(p).is_file()),None)
