"""The app's JSON delivery contract, shared by new and resumed storyboard tasks."""
from pathlib import Path

from contract.episode_contract import (SHOT_DURATION_RANGE, SHOT_FIELD_SPECS,
                                       SHOT_ID_SAMPLE, VIDEO_PROMPT_RANGE)


def _field_text(*names):
    """镜头字段的提示词写法：从契约事实表（episode_contract.SHOT_FIELD_SPECS）
    取 ``name（note）``（无 note 裸写 name），多字段按事实表次序以顿号连接。
    事实表里没有的名字由 ``order`` 索引抛 KeyError——提示词字段枚举不允许静默缺项。"""
    notes = {name: note for name, note, _fragment in SHOT_FIELD_SPECS}
    order = {name: index for index, (name, _note, _fragment) in enumerate(SHOT_FIELD_SPECS)}
    return '、'.join(
        name + ('（%s）' % notes[name] if notes[name] else '')
        for name in sorted(names, key=order.__getitem__))


def prompt_lines():
    """第 61 期 v0.8 任务 12：视频提示词只写动作、运镜与物理交互。句子从 prompt_templates 取。"""
    from contract.prompt_templates import contract_lines
    return ''.join(contract_lines())


def rules():
    # 校验器实体在 程序/writing.py（顶层门面再导出 domain.writing）；写进提示词的
    # sys.path 目录必须是它所在的 程序/ 根。文件缺失时不写校验指令，避免给模型
    # 一条必然 import 失败的指令。
    validator=Path(__file__).resolve().parents[1]/'writing.py'
    validation=(
        '使用 JSON 序列化器写文件，重新读取每份成果并调用助手校验函数：'
        f'将 {validator.parent} 加入 Python 模块搜索路径，'
        'from writing import validate_episode; from contract.storyboard_paths import media_root; '
        'validate_episode(已读取的JSON对象, media_root(JSON文件路径))。'
        '该校验仅检查本地数据，不调用模型；必须修复全部错误后才能报告完成，未生成参考图属于待制作警告。'
    ) if validator.is_file() else ''
    return (
        '【制作 JSON 必须通过助手校验】沿用已完成剧本、已确认角色固定外观和资产编号；仅补齐当前剧本缺少的场景、临时角色及关键道具。'
        '任何分镜 Skill 的 Markdown 或通用 JSON 都是创作中间稿，还需交付以下可导入的 JSON。'
        '顶层必须有 episode_id、title、duration、source_script、shots（非空数组）。'
        '顶层 prompt_language 必须为 "zh"；所有 frame_prompt、video_prompt、dialogue、图片提示词与自然语言描述一律使用简体中文，'
        '不沿用任何 Skill 的英文默认输出。技术字段名、资产/镜头编号、模型ID、文件路径等专有标识保留原文。'
        '每镜必须有 ' + _field_text('id', 'title', 'duration') + '、'
        '每镜先写清镜头三元组：核心人物／画面主体、可见动作、景别机位与运镜；人物主导权变化、动作起止、转场或情绪转折必须按动作闭合点切镜，'
        '不要把结构剧本的角色／场景／道具档案重复写入分镜初稿。'
        '多集任务按集号从小到大连续编号：集号最小的集从 ' + SHOT_ID_SAMPLE + ' 起，下一集的编号紧接上一集最后一个编号；'
        '不得按处理或保存先后、也不得按并行完成顺序分配编号；保存每集前核对本集全部编号大于所有更小集号的镜头编号，发现错位先修正再保存。'
        + _field_text('characters', 'location', 'props', 'frame',
                      'frame_prompt', 'video_prompt', 'dialogue') + '。'
        'frame_prompt 写静止的动作起点；video_prompt 是独立的非空字符串，'
        + '%d–%d' % VIDEO_PROMPT_RANGE + ' 个字符，'
        '必须整合本镜景别机位、动作起止、运镜、原对白和声音，不得仅写首帧提示词或把视频提示词留在对话里。'
        'dialogue 沿用原剧本台词；有时间标注时使用本镜内 start/end，不能重叠或超出 duration。'
        '动作或对白超过' + str(SHOT_DURATION_RANGE[1]) + '秒，按动作闭合点拆镜并补齐每个子镜的首帧和视频提示词；'
        '不得直接把超长镜头截成' + str(SHOT_DURATION_RANGE[1]) + '秒、加速台词或放宽校验。'
        '保留整集目标时长，各镜编辑时长合计等于顶层duration；使用剪辑字段时须满足'
        '0<=trim_in<trim_out<=duration、edit_duration=trim_out-trim_in。'
        '普通道具用 ' + _field_text('ordinary_props') + '=[{"name":"名称","description":"本镜数量、外观、位置和初始状态"}]，不分配PROP编号。'
        '背景人物、群演、路人、不露脸或一次性角色不写进 characters、不分配 CHAR 编号；'
        '在 frame_prompt 和 video_prompt 中直接描述其人数、服装、姿态和状态即可。'
        '每镜补充 ' + _field_text('action_complexity') + '及 ' + _field_text('complexity_reason') + '：'
        '固定站位、对白、简单姿态为simple，无需白模；少量走位或物件操作为medium，线上简单白模；'
        '快速或多角色交互、物件交接、多段连续动作、人物与摄像机协同运动为complex，由Agent制作白模。'
        +validation
        +'通过校验并采用后，该 JSON 的用户名称为“分镜初稿”（“分镜定稿”是第 07 阶段的批次划分与定稿产物，不在本阶段）：它记录来源剧本、角色／场景／道具编号、镜头编号、时长、动作起止、台词和连续性约束；修改必须走明确的修订流程。'
        +prompt_lines()          # 第 61 期 v0.8 任务 12：图片/视频提示词分开，锚点逐字复用
    )
