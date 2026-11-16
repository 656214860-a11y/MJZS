"""字幕文本发布的 L3 编排入口。"""


def subtitle_export_gateway():
    """装配统一的行尾校验文本发布器。"""
    import infra.line_endings as line_endings
    return {'publish_text': line_endings.write_text}


def publish_stage_srt_text(target, text):
    """SKILL 生成字幕的唯一 L3 文本发布入口。"""
    from domain.subtitle_export_service import publish_srt_text
    return publish_srt_text(target, text, publish=subtitle_export_gateway()['publish_text'])
