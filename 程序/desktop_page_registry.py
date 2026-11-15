"""桌面页登记表（从 desktop 原样迁出，R1622）。

page 常量被 Desktop 的多处方法共用；放在单独模块由 desktop 按原名转回，避免与某个 Mixin 绑死。
"""
import contract.pet_bus as pet_bus
import pet_state


# 制作页名称只从 pet_bus.STAGES／STAGE_NAMES 生成；「参考网站」是唯一非阶段工具页。
PAGES = [f'{index:02d}  {pet_bus.stage_name(stage)}'
         for index, stage in enumerate(pet_bus.STAGES, start=1)] + ['14  参考网站']

PAGE=pet_state.PAGE_OF

PAGE_SITES=len(PAGES)-1          # 「参考网站」是工具页，不进状态机

# 「00 会员账户」排在侧栏最上面，但不进 PAGES：01–13 的页序号与阶段表一一对应，不能被它挤动。
PAGE_ACCOUNT=len(PAGES)
ACCOUNT_TITLE='00  会员账户'


def page_title(index):
    """页序号 → 页标题；会员账户页不在 PAGES 里，单独给名。"""
    return ACCOUNT_TITLE if index==PAGE_ACCOUNT else PAGES[index]


# 侧栏图标轨：页序号 → assets/nav/<键>.png 语义名（图标由 scripts/build_nav_icons.py 生成）。
# 阶段页按 pet_bus.STAGES 顺序取 NAV_STAGE_ICONS；「参考网站」与会员账户是工具页。
NAV_STAGE_ICONS={
    'script':'script','script_structure':'structure','storyboard':'storyboard',
    'animatic':'animatic','assets':'assets','continuity':'continuity','final':'final',
    'keyframe':'keyframe','previs':'previs','video':'video','audio':'audio',
    'edit':'edit','delivery':'delivery',
}
PAGE_NAV_ICONS={index:NAV_STAGE_ICONS[stage] for index,stage in enumerate(pet_bus.STAGES)}
PAGE_NAV_ICONS[PAGE_SITES]='sites'
PAGE_NAV_ICONS[PAGE_ACCOUNT]='account'
ASSET_ROSTER_ICON='asset_list'
# 项目区小图标：在做／已完成分组筛选与新建、打开目录操作。
PROJECT_GROUP_ICONS={'making':'project_making','completed':'project_done'}
PROJECT_ACTION_ICONS={'new':'project_new','open':'project_open'}


def nav_label(index):
    """页序号 → 侧栏按钮上的短编号（'01'…'14'）；会员账户页给 '00'。"""
    return '00' if index==PAGE_ACCOUNT else PAGES[index].split(None,1)[0]

# 侧栏切回时复用：02 以内容签名校验，03 沿用后台目录监听。
CACHED_PAGES=frozenset({PAGE['script_structure'],PAGE['storyboard']})
