"""Production-model names shared by stage orchestration and frame generation.

Keeping these facts outside either caller prevents the configuration layer and
the frame UI/service from importing one another merely to compare a label.
"""

LOCAL_KEYFRAME_MODEL = '本地 FLUX.2 Klein（ComfyUI）'
SEEDREAM_KEYFRAME_MODEL = 'Seedream 5.0 Pro'
KEYFRAME_MODELS = (LOCAL_KEYFRAME_MODEL, SEEDREAM_KEYFRAME_MODEL)
