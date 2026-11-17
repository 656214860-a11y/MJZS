"""The same asset JSON contract for Codex, Claude and ComfyUI."""
from pathlib import Path
import re
from contract.prop_assets import RULES as PROP_RULES, CHARACTER_RULES

def prompt_rules():
    """第 61 期 v0.8 任务 12：图片提示词＝锚点＋场景＋构图。规则句从 prompt_templates 取，只留一份真相。"""
    from contract.prompt_templates import common_lines
    return ''.join(common_lines())


COMMON = (f'结构化资产JSON格式规范：{Path(__file__).resolve().parents[1] / "asset_manifest.schema.json"}。'

    '资产交付必须同时输出结构化JSON，不能只写Markdown。统一清单为episode/assets/资产清单/assets.json，'
    '顶层直接是资产编号到对象的映射，不加assets数组包装。CHAR_###代表角色，LOC_###代表场景，PROP_###只代表需要单独制作的关键道具。'
    '先读取清单、episode/assets.json及已有分镜再分配编号；按身份与名称复用编号，新编号必须避开所有已用编号。'
    '按编号合并写入，保留其他集、已有图片登记、别名与未要求修改的字段，不把本集清单覆盖成整个项目清单。'
    '每个交付资产包含name、description（固定外观）、image_prompt（可直接生图的完整正向提示词）、'
    'negative_prompt（负向提示词，允许空字符串）、used_in（镜头编号数组）、prompt_stage（writing或storyboard）、'
    'appearance_locked（固定角色为true），prompt_source记录真实来源文件。未用于分镜时used_in为空数组。'
    'image_prompt必须独立完整，写明造型、材质、色彩、风格和参考图构图，不只写“参考角色卡”或让下游自行补充；'
    '资产参考图不描述连续动作或运镜，镜头动作仅写入镜头的frame_prompt/video_prompt。'
    '沿用用户确认的画风；局部角色只画指定局部，环境图不额外添加人物；道具文字、数量和初始状态以剧本为准。'
    '不要填写不存在的image图片路径，不修改episode/assets.json的登记图片。'
    '保留资产已有reference_images数组，这是用户绑定的真实参考图，路径相对episode资产库目录；不得虚构、串用或清除这些绑定。'
    '直接编写或修订结构化提示词时移除该条prompt_import_hash，避免旧Markdown导入覆盖新内容。'
    '采用临时文件写入后原子替换；保存前重新读取并合并其他新增编号，校验JSON可解析、编号唯一且无占位提示词。'
    '这些阶段只输出文本和JSON，不调用图像或视频生成；第3步只负责检查、生成和导入图片。'+PROP_RULES+CHARACTER_RULES+prompt_rules()
)


def rules(stage):
    if stage=='writing':
        return ('第1步资产职责：先读取已有角色设定和统一资产清单。已有固定角色原样复用，不重新确认、重新编写角色卡或输出重复的资产确认文档。'
                '只有新项目没有角色设定，或续集确实新增固定角色时，才确定其身份、体型、头脸、发型、服装、色彩、材质、特殊标记与禁止变化项。'
                '只为新增或缺失条目补写固定角色参考图提示词到统一资产清单，prompt_stage=writing、appearance_locked=true；已有完整条目不改写。'
                '不要提前虚构未确定的场景、道具或临时角色。已确认的固定角色未经用户要求不要改变外观。'+COMMON)
    if stage=='storyboard':
        return ('第2步资产职责：先读取第1步的固定角色提示词并原样复用；拆分镜时补齐本集场景、关键道具、临时角色和动物的完整参考图提示词。'
                '新增条目prompt_stage=storyboard，非固定资产appearance_locked=false。局部角色保持局部，不扩写成新的主角。'
                '固定角色提示词缺失时，读取对应角色设定补齐并标记writing来源；设定不明确则报告缺项，不重设计角色。'
                '每镜characters、location、props、first_frame_assets引用的编号，都必须在统一清单中存在且有name与image_prompt。'
                '合并各集used_in，核对镜头引用、名字和提示词属于同一资产；场景布局和道具初始状态要符合该集分镜。'+COMMON)
    raise ValueError('未知提示词准备阶段')


def positive(asset):
    return next((asset[key].strip() for key in ('image_prompt','positive_prompt','prompt')
                 if isinstance(asset.get(key),str) and asset[key].strip()),'')


def issues(aid,asset):
    problems=[]
    if not re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}',str(aid)):problems.append('资产编号格式错误')
    if not isinstance(asset,dict):return problems+['资产条目必须为对象']
    if not isinstance(asset.get('name'),str) or not asset['name'].strip() or asset['name']==aid:problems.append('缺少资产名称')
    prompt=positive(asset)
    if not prompt or prompt in ('待补充','待确认','待生成','待确认外观要求','待补充名称和外观要求','TODO'):problems.append('缺少完整生图提示词')
    if not isinstance(asset.get('negative_prompt',''),str):problems.append('负向提示词必须为文字')
    return problems
