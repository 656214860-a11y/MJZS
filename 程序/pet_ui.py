"""宠物窗口（方案 A：主窗口内贴片）＋与现有制作链路的三个接缝。

设计取舍：
- 贴片挂在标题栏右上角（place relx=1.0 anchor='ne'），随主窗口移动、不参与布局计算；标题栏两行文字
  按贴片宽度留白，文字不会被盖住。
- 手绘 Canvas（Q 版橙虎＋大眼＋眨眼），闲置 2fps、忙时 8fps；设计稿另存 assets/sanhu_chibi_avatar.png，运行时仍不加载位图资源。
- 气泡与进度面板是窗口内浮层（place），不是 Toplevel：ui_theme.install_window_placement 会给新建的
  Toplevel 设 -alpha 0 并在 <Map> 时 grab_set，浮层没有这些问题，也天然随窗移动。
- 原逻辑一行不改，只加薄封装：自动任务队列套 StageQueue（get_nowait 时顺手记一笔结果）、状态栏经
  watch_status() 挂一层（原文照旧写进变量，宠物顺手记一笔）、页面按钮经 tap() 调用（成功后上报「用户点了什么」）。
- 第 13 期再加两处：右键菜单／托盘菜单的动作一律经 act() 出去——先把事做完，再把结果说给用户听；
  过去只写 self.notice，而 notice 只有气泡打开时才看得见，「重试失败项」「切换自动化等级」这类动作
  看起来就是没反应。
- 第 14 期：说要说的那句话改成贴片旁边的云朵框（pet_cloud，同样是窗口内浮层）。上一版的对话窗是
  Toplevel，ui_theme 会给新 Toplevel 设 -alpha 0 并在 <Map> 时 grab_set：抓取留在手里，主窗口点哪都
  没反应（「卡死、关不掉」）。云朵框不新建窗口、不抓键盘，顺带承担播报：忙时 12 秒、闲时 60 秒说一次
  进度，未采用的分镜／缺首帧这类缺口一出现就立刻说。
- 第 15 期：云朵框挪到助手界面内容区的左上角（不再压住右上角的标题／状态文字），尾巴三点朝猫咪脑袋指；
  宠物一说话就自动冒出来（不抢焦点），交互结束后自动收起——用户不必再手动打开。头像颜色＝自动化等级：
  全自动红、半自动蓝、只提示黄（由 LEVEL_COLORS 决定，心情色只留给托盘图标与动画快慢）。
- 宠物自己不新建任何 Tk 变量：Tk 变量若在 worker 线程被 GC 回收，__del__ 会跨线程调 Tcl，轻则报
  main thread is not in main loop，重则与正在 update() 的界面线程互相等待而卡死。
- 所有分发都在既有 150ms 心跳里 pump，不开新线程、不加新轮询。
- 第 22 期：独立小窗与自绘气泡两个功能整个删掉（pet_window.py／pet_toast.py 连同用例一起删）。
  对用户说话只剩一条出口——三虎的云朵框；进度与待确认明细也在这儿展示。
- 第 43 期：模型设置从「换模型」那个硬编码档位下拉升级成模型池（规格《三虎模型设置》）：
  右键「三虎设置 → 模型…」配三虎四个任务维度，「切换模型」列出池里每一条、当前那条打 ✓，
  末项「+ 新增模型…」跳模型管理；改完写盘 ＋ 就地生效，不用重启。
"""
import os
import queue
import datetime
import random
import sys
import time
from pathlib import Path
from tkinter import TclError

import model_pool
import model_router
from app_metadata import APP_NAME
from broadcaster import Broadcaster, PREFIX_PATTERNS
import pet_agent
import pet_cloud
from pet_chat_coordinator import ChatCoordinator
import pet_bus
import pet_llm
import pet_report
import pet_state
import stage_handler_registry
import stage_flow
import stage_parallel
import token_saver
from pet_settings_contract import LEVEL_NOTES
from ui_widgets import ContextMenu, ask_confirmation
from ui_tokens import PET_LAYOUT

PROGRAM = Path(__file__).resolve().parent
SIZE = PET_LAYOUT['avatar_size']  # 显示与命中区域共用的贴片边长
IDLE_MS = 500                    # 闲置 2fps
ACTIVE_MS = 125                  # 忙时 8fps
CANVAS_BG = '#f3f6fa'
SANHU_FUR = '#ff8a3d'             # 与桌面图标一致的虎皮橙：三虎不再因为模式切换失去识别度
SANHU_EAR = '#ff9292'             # 桌面图标同款暖粉耳窝
SANHU_MUZZLE = '#fff2d9'          # 桌面图标同款奶白口鼻
SANHU_INK = '#1a1c2a'             # 厚而清晰的深蓝墨描边
SANHU_STAR = '#22d3ee'            # 桌面图标右上角的青色星光
SANHU_BLUSH = '#ff8d9b'           # Q 版头像的小腮红
# 第 19 期：自动化等级搬到三虎身旁——三个猫爪按钮排成一排，点哪一档就切到哪一档。
PAW_SIZE = PET_LAYOUT['paw_size']                  # 单个猫爪按钮的边长
PAW_GAP = PET_LAYOUT['paw_gap']                    # 爪印之间的间距
PAW_WIDTH = 3 * PAW_SIZE + 2 * PAW_GAP            # 一整排猫爪的宽度
PAW_LEVELS = ('hint', 'semi', 'auto')             # 从左到右：正常／半自动／全自动
SANHU_MODES = ('manual', 'auto')                  # 三虎控制面的两档：手动／全自动

# 自动制作变量由三虎创建、持有和写入；页面只能通过 ``auto_variable`` 取得并读取。
# 编号是流程模板的 process_id，短名是 pet_bus.STAGES 的规范阶段 ID。
AUTO_STAGE_VARIABLES = {
    'storyboard': 'auto_storyboard_var', '01_storyboard_draft': 'auto_storyboard_var',
    'assets': 'auto_asset_var', '02_assets': 'auto_asset_var',
    'keyframe': 'auto_first_frame_var', '05_keyframe': 'auto_first_frame_var',
    '05_first_frame': 'auto_first_frame_var',
    'video': 'auto_video_var', '07_video': 'auto_video_var', '07_video_gen': 'auto_video_var',
    'audio': 'auto_audio_var', '08_audio': 'auto_audio_var', '08_audio_subtitle': 'auto_audio_var',
    # 其余既有自动链保留独立变量，避免把不同行为误合并为一个开关。
    'final': 'auto_final_var', 'auto_final': 'auto_final_var',
    'auto_adopt': 'auto_adopt_var', 'previs': 'auto_previs_var', 'auto_previs': 'auto_previs_var',
    'edit': 'auto_edit_var', 'auto_edit': 'auto_edit_var',
    'delivery': 'auto_handoff_var', 'auto_handoff': 'auto_handoff_var',
    'auto_submit': 'auto_submit_var', 'auto_review': 'auto_review_var',
}
AUTO_VARIABLE_NAMES = tuple(dict.fromkeys(AUTO_STAGE_VARIABLES.values()))


class _BooleanFlag:
    """无 Tk 根时供三虎逻辑测试使用的最小 BooleanVar 接口。"""
    def __init__(self, value=False):
        self.value = bool(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)


def should_auto_run(owner, project, stage_id):
    """页面唯一的自动执行判定入口。"""
    pet = getattr(owner, 'pet', None)
    return bool(pet is not None and pet.should_auto_run(stage_id))
PAW_IDLE = ('#e7edf5', '#a9b6c7')                 # 没选中的爪印：淡灰一只
PAW_HOVER = ('#f4f9ff', '#6f8bab')                # 第 23 期：鼠标停在爪上时提亮一档（可点得可预期）
PAW_GAP_Y = PET_LAYOUT['paw_gap_y']                 # 猫爪排紧贴头像下沿
PAW_ARC = PET_LAYOUT['paw_arc']                     # 三只爪摆成一条向下的弧——
                                                  # 中间那只最低、两边各抬 PAW_ARC 像素（猫爪落地的样子）。
# 切等级之后用圆形气泡说的那句话（用户第 19 期给的原话 ＋ 第 24 期第 4 条要的简单说明）。
# 光说「已切换」不够——用户按完不知道自己刚选了什么，所以每一档都补一句「这一档到底怎么干活」。
LEVEL_SWITCH_NOTES = {
    'hint': '只提醒：我只报进度，不自动制作。',
    'semi': '半自动：免费步骤自动做，付费前先问您。',
    'auto': '全自动：按流程制作；付费或阻塞时会停下。'}
# 第 21 期：等级小字从「贴片左边」挪到「三虎右边」（用户要的「文字移动到三虎右侧，不能遮挡」）。
# 贴片右沿离窗口右边还有 -(PATCH_X) 那么宽，小字就落在这一条空档里：右沿离窗口边 CAPTION_RIGHT，
# 自己最多占 CAPTION_ROOM 宽（三个汉字够用），离猫脸还留着一条缝——标题栏文字按 HEAD_PAD 让开。
CAPTION_RIGHT = PET_LAYOUT['caption_right']
CAPTION_ROOM = PET_LAYOUT['caption_width']
PATCH_X = -(CAPTION_RIGHT + CAPTION_ROOM + PET_LAYOUT['right_gap'])
CAPTION_INK = '#000000'                           # 第 21 期：三档小字一律黑色（用户要的「全部用黑色」）
# PATCH_X 已含右侧状态字的占位；再向左让出头像／爪排宽度和标题间距即可。
HEAD_PAD = -PATCH_X + max(SIZE, PAW_WIDTH) + PET_LAYOUT['header_gap']
# 第 20 期：用户报「3 个猫爪型按钮被遮挡」——原来这排爪子的右沿只比贴片右沿往里 8 像素，
# 而它自己还有 PAW_WIDTH 宽，于是整排压在猫脸上（截图里猫的耳朵被盖住、下巴被标题行裁掉）。
# 现在挪到贴片正下方：右沿与贴片对齐，纵向从贴片底边再往下 PAW_GAP_Y。
PAW_ROW_X = PATCH_X + (PAW_WIDTH - SIZE) // 2       # 猫爪排与头像中心对齐
PAW_Y = PET_LAYOUT['top'] + SIZE + PAW_GAP_Y        # 猫爪排落在贴片正下方
PATCH_ROOM = PAW_Y + PAW_SIZE + PAW_ARC           # 贴片＋猫爪的总高度：标题行必须留够，否则猫脸被裁
CAPTION_Y = PET_LAYOUT['top'] + max(0, (SIZE - PET_LAYOUT['caption_height']) // 2)
# 第 44 期：设置入口做成齿轮，摆在窗口左上角标题（V0.7）旁边。用户要的是「醒目提示」——
# 它不藏在右键菜单里：琥珀色齿身 ＋ 深墨描边，鼠标停上去再亮一档，旁边跟着一句「设置」。
GEAR_SIZE = 22                                    # 齿轮按钮的边长
GEAR_COLOR = ('#f0a03a', '#7a4a0c')               # 齿身／描边
GEAR_HOVER = ('#ffc061', '#a8620f')               # 鼠标停上去时各亮一档
# 第 45 期：原先齿轮旁边还写着一句「设置」，230 像素宽的侧栏装不下（应用名 ＋ V0.7 ＋ 齿轮
# 之后它排在最后，整句被裁掉——用户报的「齿轮旁边的文字被遮挡」）。用户要删掉，所以只留这颗
# 琥珀色齿轮本身（够醒目）；这句话退成无障碍名字，不再画出来。
GEAR_TIP = '设置'
KEEP = 20
# 第 22 期重做形象：用户要的「配色冷酷、线条流畅、造型醒目」。
# 三件事怎么分：造型与线条归 paint()（尖耳、钟形脸、上挑的细长眼、长胡须）；
# 配色归这里——四档心情与三档等级共用同一枚深墨描边（#101c2b 一系），色相一律压冷，
# 冰白（ICE）只留给口鼻与眼里那一点高光。等级色仍是蓝／黄／红（用户第 20 期钉死的语义），
# 只是把三档都往冷里压了一档，配上墨色描边看不出一点甜腻。
ICE = '#eef5fc'                   # 冰白：口鼻底板与眼里那点高光
INK_SOFT = '#3c526d'              # 浅一档的墨色：胡须用它，贴着深墨描边不抢脸
BLUSH = '#8fb6d8'                 # 撒娇时的腮红：冷玫瑰蓝，不是粉
TONGUE = '#c98ba4'                # 舔爪时露出的舌头：压过的冷玫瑰
MOODS = {'idle': ('#7fb0dd', '#101c2b', '#0a1521'),
         'busy': ('#d9a63c', '#2a1e05', '#1b1200'),
         'worry': ('#d4645c', '#2d0d0a', '#1c0603'),
         'paused': ('#c2c8d2', '#3a4048', '#20242a')}
# 自动化等级 → 头像配色（身体色／描边色／高光色）。用户一眼就能从猫的颜色看出现在是哪一档。
# 第 20 期：用户报「自动化级别显示错误」——那排猫爪按第 19 期的新配色填（正常蓝／半自动黄／全自动红），
# 猫身子却还是第 15 期的旧配色（正常黄／半自动蓝／全自动红），同一档两个颜色（蓝爪配黄猫）。
# 现在只留这一份：猫身子、那排猫爪、等级小字共用它；PAW_COLORS 就是它的前两项（填色／描边）。
LEVEL_COLORS = {'hint': ('#6fb3e0', '#123a5e', '#08182a'),
                'semi': ('#e0b13c', '#6b4a10', '#241703'),
                'auto': ('#dd5f57', '#7c231e', '#2a0806')}
PAW_COLORS = {level: colours[:2] for level, colours in LEVEL_COLORS.items()}
# 第 18 期：等级不光靠颜色，标题行里还有一个字样（用户报「正常／半自动／全自动不显示了」）。
# 第 21 期：字样按用户给的说法写——蓝色那只＝「只提醒」（用户原话：蓝爪→蓝猫→只提醒）。
# 三档的顺序与配色由 PAW_LEVELS／LEVEL_COLORS 定，这里只管那三个字写什么。
# 第 23 期：档位名不再各写一份（原来这里与 pet_agent.LEVEL_NAMES 是同一档两个说法）。
LEVEL_CAPTIONS = pet_agent.LEVEL_NAMES
PAUSED_CAPTION = '已暂停'
# 第 18 期：关软件那一眼的两张贴纸——下午之后递日报、周五（含）之后递周报。
BANNER_HOUR = 14                  # 下午两点之后才算「下午以后」
WEEKLY_FROM = 4                   # 周五（datetime.weekday：周一 0、周日 6）起算周报
# 第 36 期第 5／6 条：关软件那一下不再递日报（用户要「删掉关闭前的弹框」），改由三虎自己挑
# 时机；换了阶段也主动问一句。这两件事都按钟点节流，别反复问。
STAGE_ASK_SECONDS = 45.0          # 同一个阶段重复问一句最短隔这么久
REPORT_QUIET_SECONDS = 900.0      # 隔这么久没有新的制作动静＝这一波活干完了，该递日报了
GREET_DELAY_MS = 450              # 开机招呼推迟这么久（用户嫌招呼慢，原 900）：主窗口先映射出来，云才知道往哪落
# 第 68 期任务 11：用户要「打招呼的聊天框关掉之后，再慢慢弹出其他信息」。招呼冒出来之后留
# 一段安静期：这期间自动那几路（进度播报／进度气泡／主动问一句／自动推进／失败提醒）都不出声，
# 各自的节流起算点跟着往后挪——安静期过了按正常节奏慢慢说，不会攒成一大串一起炸出来。
GREET_QUIET_SECONDS = 5.0
ONE_CLICK_TITLE = '开始自动制图'
ONE_CLICK_ASK = ('准备开始自动制图：重试失败项 → 本地补首帧 → 出今日日报。\n'
                 '会产生费用的步骤（云端首帧、视频、配音）仍然只由您在各页面自己按。\n\n现在开始吗？')
# 第 25 期第 3 条：三虎自己看着制作进度，到了该收尾的时候主动问一句「要不要一键自动执行」，
# 并把选择项摆出来。问得比播报稀一点：同一批缺口最短隔 OFFER_SECONDS 才问，缺口一直不变也过
# OFFER_REPEAT 再提一次；用户答「好」就照一键执行那条路走（会花钱的步骤照旧只由他自己按）。
OFFER_TITLE = '要不要一键执行'
OFFER_SECONDS = 300.0                             # 同一批缺口最短隔这么久才问一次
OFFER_REPEAT = 900.0                              # 缺口没变化：也隔这么久重提一次，别一直闷着
OFFER_YES = frozenset(('好', '好的', '好呀', '是', '是的', '要', '可以', '行', '来吧', '开始',
                       '开始吧', '1', '一键执行', '一键收尾', '全部做完', '都做完', '收个尾'))
OFFER_NO = frozenset(('不用', '先不用', '不用了', '不了', '算了', '回头再说', '等会儿', '等会',
                      '先放着', '2'))
AUTOSTART_NAME = '漫剧制作助手·宠物助手'          # 注册表 Run 项的名字
SNOOZE_SECONDS = 900                             # 「稍后再说」默认安静 15 分钟
# 第 60 期第 1 条：用户自己连着按满这么多次、而且都落在 BUSY_WINDOW 这么短的窗口里，就是
# 「人正忙在手上的活上」——这时候三虎再冒话就是打扰，于是自己进免打扰（安静 SNOOZE_SECONDS）。
BUSY_TAPS = 12
BUSY_WINDOW = 45.0

# 第 19 期：进度面板撑下了，改成三虎自己判断时机冒出来的圆形进度气泡（还是同一份快照）。
# 第 49 期第 3 条：用户要「进度面板提示频率降低、不许提示无用内容」——240 秒 → 600 秒
# （十分钟），并且内容跟上一模一样的那一次直接咽下去（见 progress_voice）。
PROGRESS_SECONDS = 600.0                          # 至少隔这么久才自己冒一次进度明细
PROGRESS_MS = 12000                               # 进度圆气泡停留多久
PROGRESS_GAPS = 2                                 # 第 21 期：圆气泡里最多带两条缺口（原来搬整个面板，太大）
CHAT_MUTE_SECONDS = 30.0                          # 单击收起的云朵框：这段时间里自动播报不再把它顶出来
# 第 35 期第 1 条：用户切去别的应用时不再只是「每一路播报各自闭嘴」（第 30 期第 3 条那套），
# 而是三虎自己进入暂停状态——头像置灰、菜单写「已暂停」，回到助手界面再自动恢复。
AWAY_PAUSE_SECONDS = 10.0                        # 离开界面满这么久才暂停：alt-tab 一闪不折腾
# 第 37 期第 6 条：用户要「切回助手界面时不用弹聊天框」——回来只把自动执行接上，一个字都不说。
# 第 18 期：模型档位改成一张登记表——「切换模型」栏按它生成。第 43 期起这张表里的模型来自
# 模型池（模型管理）：池里加一条，子菜单里立刻多一项；这里只剩「自动」这一条出厂项，
# 以及 register_tier() 那个「把外部模型接进这一栏」的接口。
TIER_MODELS = {'auto': ('自动', {'force_tier': ''})}
TIER_CYCLE = tuple(TIER_MODELS)                   # 登记表里的档位顺序（池里的模型另按池的顺序排）
TIER_NAMES = {tier: label for tier, (label, _override) in TIER_MODELS.items()}
# 第 37 期第 1 条：用户要「给三虎记住所有项目」。项目登记表本来就在盘上（程序目录的
# projects.json），三虎以前只看当前这一个；现在把它整本记下来：名字、在制作／已完成、
# 当前阶段与进度都念得出来，问「有哪些项目」也有得答。读盘带一层 TTL 缓存，不能每拍都读。
PROJECT_CACHE_SECONDS = 20.0                      # 项目快照最多缓存这么久
PROJECT_LIMIT = 6                                 # 一句话里最多念几个项目（再多就太长了）
PROJECT_CLOSED = '已完成'
PROJECT_OPEN = '在制作'


def tier_models():
    """登记表的只读快照：现在有哪几档模型，接新模型之后这里自动多一项。"""
    return {tier: label for tier, (label, _override) in TIER_MODELS.items()}


def register_tier(tier, label, override=None):
    """预留接口（第 18 期）：把另一个模型登记成「换模型」栏里的一档。

    tier 是内部代号（客户端配置里 force_tier 用的就是它），label 是菜单上的人话，override 是
    要合并进客户端 config 的键值对（不给就按 force_tier=tier）。重名就改那一行。
    """
    global TIER_CYCLE, TIER_NAMES
    name = str(tier or '').strip()
    if not name:
        return tier_models()
    pairs = {'force_tier': name} if override is None else dict(override)
    TIER_MODELS[name] = (str(label or name), pairs)
    TIER_CYCLE = tuple(TIER_MODELS)
    TIER_NAMES = {key: value[0] for key, value in TIER_MODELS.items()}
    return tier_models()
PANEL_TITLE = '进度面板'                           # 第 68 期任务 4：用户要它就叫「进度面板」，不再挂「三虎」
# 第 44 期照用户附件重排功能栏：面板那一项后来又叫过「三虎面板」（第 68 期任务 4 改回「进度面板」），
# 「三虎设置」改名「设置」，
# 各格收进子菜单（第 59 期第 10 条：子菜单就是齿轮那扇窗的分页表，两边同步；
# 附件里的 SKILL 管理这一轮不做）。
PANEL_MENU_LABEL = '进度面板'                      # 第 68 期任务 4：右键与功能栏都叫这个
DETAIL_MENU_LABEL = '待确认项'                    # 右键入口简短明确，内容在三虎提示框里展开
SETTINGS_LABEL = '设置'
# 第 59 期第 10 条：右键「设置」子菜单的内容与齿轮那扇窗同步——两边只认
# pet_settings_ui.TABS 这一份表，不再各写一份（原来齿轮那边改名「三虎模型配置」
# 之后，右键这里还写着「模型配置…」，用户看到的就是两份对不上）。
def _settings_entries():
    try:
        from pet_settings_contract import TABS
        return tuple(TABS)
    except Exception:
        return (('basic', '基础功能'), ('model', '三虎模型配置'), ('level', '自动化等级'),
                ('token', 'Token 节省'), ('budget', '预算'), ('dev', '开发信息'))
SETTINGS_ENTRIES = _settings_entries()
QUIT_LABEL = '退出程序'
PANEL_HEAD = '当前进度：'                          # 第 36 期第 10 条：面板正文开头那一行
# 第 26 期第 4 条：面板原来是把十几行「名字：值」一股脑倒出来（用户报「文字排版差、难阅读」）。
# 现在按「看什么」分三节，每行一个编号，节标题单独一行——一条一行、不空行，扫一眼就能分段。
PANEL_SECTIONS = (('现在在做什么', ('当前阶段', '进度', '当前状态', '最近提示', '预计剩余')),
                  ('速度与命中', ('阶段停留', '平均单镜耗时', '缓存命中率', 'Flash 占比')),
                  ('配额与设置', ('失败待确认', '当日 Token', '配额', '自动化等级')))
PANEL_DIVIDER = ' · '                             # 编号之后、名字与值之间那个分隔（比「：」好扫）
AUTOSTART_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
CHAT_HINT = '我一说话就冒出云朵框：单击我就能开／关，说一句就行（右键是我能做的事）'
# 第 14 期：播报频率。忙的时候报得勤，闲着也隔一会儿报一次进度；缺口一变化立刻报。
# 第 49 期第 3 条：用户第三回嫌吵——忙时 40 秒 → 2 分钟、闲时 3 分钟 → 10 分钟；缺口真变了
# 仍然是立刻说（那是新消息，不算「无用内容」）。
BROADCAST_BUSY = 120.0           # 有阶段在跑：最多每 2 分钟播报一次
BROADCAST_IDLE = 600.0           # 闲着：最多每 10 分钟播报一次进度
GAP_SECONDS = 30.0               # 未采用分镜／缺首帧这类缺口最多每 30 秒重算一次（不在心跳里读盘）
# 第 57 期第 2 条：同一件事只说一遍。「进度」这一路有两条入口——心跳播报（tick_broadcast）
# 与进度圆气泡（progress_voice）说的是同一句进度线，「缺口」那几句也是两边都带；原来各自
# 按自己的频率说，同一句话能从两条入口各冒一次（用户点名的「重复的弹框」）。说过的记在
# _spoken 里：另一条入口在 SPEAK_GAP_SECONDS 之内不再说第二遍；同一入口自己按频率再说
# 一遍是本来的设计（文字没变时另有 _progress_said 管着），不算重复。
SPEAK_GAP_SECONDS = 900.0
SPOKEN_KEEP = 12                 # _spoken 只留最近这么多笔（这是一份短账，不是日志）
# 自动化等级 → 一句人话解释（切等级时连解释一起播报，用户才知道切完会发生什么）
# 第 23 期：自动推进的节流。比无人值守最短的节流周期（15 秒）还短一点，链路一停就能被推一把，
# 又不至于每一步都每 150ms 问一次宿主。
ADVANCE_SECONDS = 12.0
CLICK_MS = 220                    # 单击贴片：等这么久没有第二下就弹功能下拉栏（双击＝说话）
# 第 29 期第 5 条：用户要「删掉闲聊，只问制作流程；主动问当前页该做的事；聊天框里不用回话，
# 点一下确认就行」。于是每一页配一句问句 ＋ 照着做的那一句话（空着回车发出去的就是它）——
# 原先那两句随口可爱的话（CHATTER_LINES）与五句猜意图的「哈喽~」（CHAT_HELLO_LINES）一并删掉，
# 三虎从此只谈制作流程。页序号与 desktop.PAGES 一一对应（01 剧本准备 … 13 质检与交付）。
# 第 37 期第 5 条：用户要「聊天框里不要说切到第几页了、这是 XX 页，只需询问用户」——问句里
# 只剩一句问，页面名一个字都不提（用户自己知道在哪一页）。问句都短、都像人说的话。
PAGE_ASKS = (
    ('要不要我把剧本这一步按您勾的 SKILL 跑一遍？', '执行选中'),
    ('要不要我把剧本原稿整理成可供分镜使用的结构化正稿？', '执行选中'),
    ('要不要我把这一集转成 JSON 分镜？', '执行选中'),
    ('要不要我用共享参考图生成镜头草图，合成分镜预演？', '执行选中'),
    ('要不要我把缺的资产按勾选的 SKILL 补出来？', '执行选中'),
    ('要不要我把这一集的跨镜约束、锚点与参考图冲突理一遍？', '执行选中'),
    ('要不要我把拍板的那几份分镜采用掉，往后推一步？', '执行选中'),
    ('要不要我把待生成的首帧补出来？', '执行选中'),
    ('要不要我把这一集的镜头跑一遍预演？', '执行选中'),
    ('要不要我把已就绪首帧的镜头交出去生成？', '执行选中'),
    ('要不要我把对白配一遍、字幕导出来？', '执行选中'),
    ('要不要我把已有素材合成一版？', '执行选中'),
    ('要不要我把成片过一遍质检、出一份交付清单？', '执行选中'),
)
# 认不出的页（比如第 13 页参考网站）：不硬凑一件制作上的事，只报一报进度。
FALLBACK_ASK = ('要不要我报一下当前进度？', '进度面板')
CONFIRM_TITLE = '三虎 · 要您点个头'   # 需要用户确认时的通知气泡标题
CONFIRM_NEED = '要您点个头'             # 记录里给「需要确认」补的一句后缀
# 第 17 期：三虎的猫样。右上角那只猫不再是一张定住的脸——随机做点猫的事：
# 爬行（整只轻轻挪＋多两只爪子）／舔爪／打哈欠／摇尾巴／撒娇。独立窗开着时还会沿桌面右上角漫游。
POSES = ('sit', 'walk', 'lick', 'yawn', 'wag', 'nuzzle')
POSE_NAMES = {'sit': '端坐', 'walk': '爬行', 'lick': '舔爪', 'yawn': '打哈欠',
              'wag': '摇尾巴', 'nuzzle': '撒娇'}
POSE_MIN, POSE_MAX = 6, 24        # 一个动作持续 6~24 帧（闲置 2fps ≈ 3~12 秒；忙时换得更快）
def paw_parts(x, y, size=PAW_SIZE):
    """一个猫爪的图元：一个掌垫 ＋ 四个脚趾（都是 ('oval', cx, cy, r)，画布坐标）。

    20 像素见方也得让人看出是猫爪：掌垫大一点摆在下面，四个脚趾呈弧线排在掌垫上方。
    """
    cx = x + size * 0.5
    pad = ('oval', cx, y + size * 0.70, max(2.0, size * 0.30))
    toes = tuple(('oval', cx + (index - 1.5) * size * 0.27, y + size * 0.30, max(1.2, size * 0.09))
                 for index in range(4))
    return (pad,) + toes


def paw_dy(index, arc=PAW_ARC):
    """第 36 期第 9 条：这一只爪往下挪多少像素——三只摆成一条向下的弧。

    中间那只往下挪 arc（最低），两边不动：连起来是一条向下的弧（笑脸那种），
    像猫爪踩在一条弯线上。index 是这一排里的第几只（0／1Ｏ2），
    越界就退回 0（不挪）。
    """
    try:
        index = int(index)
    except (TypeError, ValueError):
        return 0
    if not 0 <= index < len(PAW_LEVELS):
        return 0
    return arc if index == len(PAW_LEVELS) // 2 else 0





def gear_parts(size=GEAR_SIZE, teeth=8):
    """一颗齿轮的图元：齿（多边形点列）＋ 齿身圆 ＋ 中孔（都是画布坐标）。

    22 像素见方也得让人一眼看出「这是齿轮」：八颗方齿绕一圈、齿身比齿根稍小一点，
    中间挖一个孔。与 paw_parts 同一套做法——这里只算形状，画不画、什么颜色由调用方定。
    """
    import math
    centre = size * 0.5
    body = size * 0.30
    outer = size * 0.46
    points = []
    for index in range(teeth * 2):
        angle = math.pi * index / teeth
        radius = outer if index % 2 == 0 else body * 1.05
        points.extend((centre + radius * math.cos(angle), centre + radius * math.sin(angle)))
    return {'teeth': tuple(points), 'body': (centre, centre, body),
            'hole': (centre, centre, max(2.0, body * 0.38))}


class GearButton:
    """左上角那颗齿轮（第 44 期）：点一下开「设置」。

    用户要「醒目提示」，所以它不藏在菜单里——琥珀色齿身 ＋ 深墨描边，鼠标停上去再亮一档。
    第 45 期起不再在旁边写字：那句「设置」在侧栏里会被裁掉，用户要的就是把它删掉（见 GEAR_TIP）。
    画布 pack 进宿主给的那一行（desktop.sidebar_head），与贴片同一套做法：
    只往既有容器里塞一个控件，不动原布局代码。
    """

    def __init__(self, master, command=None, size=GEAR_SIZE, tip=GEAR_TIP, bg=CANVAS_BG):
        import tkinter as tk
        self.command = command
        self.tip_text = tip
        self.canvas = tk.Canvas(master, width=size, height=size, bd=0, highlightthickness=0,
                                bg=bg, cursor='hand2')
        self._hover = False
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<Enter>', self.hover_on)
        self.canvas.bind('<Leave>', self.hover_off)
        self.draw()
        return None

    def draw(self):
        """按当前状态重画一颗齿轮（悬停时换亮一档的颜色）。"""
        shape = gear_parts(int(self.canvas.cget('width')))
        fill, outline = GEAR_HOVER if self._hover else GEAR_COLOR
        self.canvas.delete('gear')
        self.canvas.create_polygon(*shape['teeth'], fill=fill, outline=outline, width=1.4,
                                   tags=('gear', 'gear-teeth'))
        centre_x, centre_y, radius = shape['body']
        self.canvas.create_oval(centre_x - radius, centre_y - radius, centre_x + radius,
                                centre_y + radius, fill=fill, outline=outline, width=1.4,
                                tags=('gear', 'gear-body'))
        hole_x, hole_y, hole = shape['hole']
        self.canvas.create_oval(hole_x - hole, hole_y - hole, hole_x + hole, hole_y + hole,
                                fill=CANVAS_BG, outline=outline, width=1.2, tags=('gear', 'gear-hole'))
        return self.canvas.find_withtag('gear')

    def hover_on(self, event=None):
        self._hover = True
        self.draw()
        return self._hover

    def hover_off(self, event=None):
        self._hover = False
        self.draw()
        return self._hover

    def click(self, event=None):
        """点一下＝开设置；动作坏了只记账，绝不把异常抛回 Tk 的事件循环。"""
        if not callable(self.command):
            return None
        return self.command()

    def place(self, **options):
        """便利：把齿轮与旁边那句「设置」一起摆好（画布与标签用同一套 place 参数）。"""
        self.canvas.place(**options)
        tip = dict(options)
        tip.pop('anchor', None)
        tip['x'] = int(options.get('x', 0)) + int(self.canvas.cget('width')) + 4
        if 'rely' in tip:
            tip['rely'] = 0.5
            tip['anchor'] = 'w'
        try:
            self.tip.place(**tip)
        except TclError:
            # 主窗口销毁后布局补位已无意义；其他错误必须继续暴露。
            pass
        return self.canvas

    def destroy(self):
        for widget in (self.tip, self.canvas):
            try:
                widget.destroy()
            except TclError:
                # 重复销毁属于 Tk 生命周期竞态；其余异常须上抛。
                pass
        return None


def palette(mood='idle', level=None):
    """取这一帧的三种颜色：暂停优先置灰，其余按等级色（头像＝等级），再退回心情色。

    第 18 期：暂停自动执行时三虎整只置灰（用户要的「暂停时头像置灰」）——暂停是一种状态，
    不是某一档等级，所以它压过等级色。
    """
    if str(mood) == 'paused':
        return MOODS['paused']
    if level in LEVEL_COLORS:
        return LEVEL_COLORS[level]
    return MOODS.get(str(mood), MOODS['idle'])


def paint(canvas, step=0, mood='idle', percent=0.0, level=None, pose='sit'):
    """手绘一帧：参考桌面图标的 Q 版三虎（大眼、奶白口鼻、三道额纹）。

    头像与桌面图标使用同一套识别色：虎皮橙、深蓝描边、粉耳、奶白口鼻和青色星光。
    自动化等级仍由 ``accent`` 标记在星光和动作细节中，暂停时整只置灰；这样既不丢失状态语义，
    也不会让三虎在不同页面和桌面图标之间像两个角色。

    第 15 期：给了 level 就按自动化等级上色（全自动红／半自动蓝／只提示黄），mood 仍然管
    动得快慢与托盘图标——两件事各归各的，不再互相串色。
    第 17 期：多了 pose——爬行时整只猫左右轻轻挪、脚下多两只爪子；舔爪／打哈欠／摇尾巴／
    撒娇各有自己的画法，每一段都带 'pose-xxx' 标签（用例按标签认动作，不看像素）。
    眼睛仍只按帧眨眼（不看动作）：动作再怎么换，眨眼节奏不变，用例的帧断言才稳。
    """
    step = int(step)
    blink = step % 4 == 3
    lift = 1 if step % 2 else 0
    state_body, state_outline, accent = palette(mood, level)
    paused = str(mood) == 'paused'
    body = state_body if paused else SANHU_FUR
    outline = state_outline if paused else SANHU_INK
    muzzle = '#e3e6eb' if paused else SANHU_MUZZLE
    ear = '#c7cbd2' if paused else SANHU_EAR
    blush = '#c0a8ac' if paused else SANHU_BLUSH
    pose = str(pose or 'sit')
    ox = 0
    if pose == 'walk':
        ox = (step % 4) - 2             # 左右轻轻挪：看着像在爬
    elif pose == 'nuzzle':
        ox = 2                          # 撒娇：脑袋往一边歪
    oy = -lift
    canvas.delete('all')
    # ① 尖耳与暖粉耳窝：沿用桌面图标轮廓，但缩到 64px 仍留出清晰内耳。
    canvas.create_polygon(11 + ox, 26 + oy, 18 + ox, 4 + oy, 31 + ox, 22 + oy,
                          fill=body, outline=outline, width=2, tags='fur')
    canvas.create_polygon(53 + ox, 26 + oy, 46 + ox, 4 + oy, 33 + ox, 22 + oy,
                          fill=body, outline=outline, width=2, tags='fur')
    canvas.create_polygon(16 + ox, 18 + oy, 19 + ox, 10 + oy, 25 + ox, 20 + oy,
                          fill=ear, outline='', tags='ear')
    canvas.create_polygon(48 + ox, 18 + oy, 45 + ox, 10 + oy, 39 + ox, 20 + oy,
                          fill=ear, outline='', tags='ear')
    # ② 圆润脸与奶白口鼻：桌面图标的简洁记号改成更适合聊天陪伴的 Q 版比例。
    canvas.create_oval(8 + ox, 17 + oy, 56 + ox, 59 + oy,
                       fill=body, outline=outline, width=2, tags='fur')
    canvas.create_oval(18 + ox, 42 + oy, 33 + ox, 56 + oy,
                       fill=muzzle, outline='', tags='muzzle')
    canvas.create_oval(31 + ox, 42 + oy, 46 + ox, 56 + oy,
                       fill=muzzle, outline='', tags='muzzle')
    # ③ 三道额纹：三虎的名字记号，和桌面图标完全一致。
    for y, half in ((23, 5), (27, 7), (31, 5)):
        canvas.create_line(32 - half + ox, y + oy, 32 + half + ox, y + oy,
                           fill=outline, width=2, capstyle='round', tags='stripe')
    # ④ 大圆眼：空闲时两颗亮晶晶的眼睛，眨眼的帧节奏与原实现保持一致。
    if blink:
        canvas.create_line(17 + ox, 38 + oy, 29 + ox, 38 + oy, fill=outline, width=2, tags='eye-line')
        canvas.create_line(35 + ox, 38 + oy, 47 + ox, 38 + oy, fill=outline, width=2, tags='eye-line')
    else:
        for cx in (23, 41):
            canvas.create_oval(cx - 7 + ox, 31 + oy, cx + 7 + ox, 45 + oy,
                               fill=outline, outline='', tags='eye-dot')
            canvas.create_oval(cx - 4 + ox, 33 + oy, cx + 1 + ox, 38 + oy,
                               fill=ICE, outline='', tags='glint')
            canvas.create_oval(cx + 2 + ox, 39 + oy, cx + 5 + ox, 42 + oy,
                               fill='#cfe7ff', outline='', tags='glint')
    # ⑤ 鼻子、笑嘴和腮红：不把动作表情画成黑洞，保持小尺寸里的亲和感。
    canvas.create_polygon(29 + ox, 46 + oy, 35 + ox, 46 + oy, 32 + ox, 50 + oy,
                          fill=outline, outline='', tags='nose')
    canvas.create_arc(26 + ox, 47 + oy, 32 + ox, 54 + oy, start=270, extent=90,
                      style='arc', outline=outline, width=2, tags='mouth')
    canvas.create_arc(32 + ox, 47 + oy, 38 + ox, 54 + oy, start=180, extent=90,
                      style='arc', outline=outline, width=2, tags='mouth')
    for side in (12, 45):
        canvas.create_oval(side + ox, 43 + oy, side + 7 + ox, 48 + oy,
                           fill=blush, outline='', tags='blush')
    # ⑥ 胡须：轻细两根，避免压过大眼。
    for x0, y0, x1, y1 in ((15, 41, 6, 39), (15, 46, 6, 48)):
        canvas.create_line(x0 + ox, y0 + oy, x1 + ox, y1 + oy, fill=INK_SOFT, width=1, tags='whisker')
        canvas.create_line((64 - x0) + ox, y0 + oy, (64 - x1) + ox, y1 + oy,
                           fill=INK_SOFT, width=1, tags='whisker')
    # ⑦ 一颗小星：接住当前自动化等级的色彩，也把桌面图标的识别元素带进聊天页。
    star = (SANHU_STAR if not paused else accent)
    canvas.create_polygon(54 + ox, 8 + oy, 56 + ox, 13 + oy, 61 + ox, 15 + oy,
                          56 + ox, 17 + oy, 54 + ox, 22 + oy, 52 + ox, 17 + oy,
                          48 + ox, 15 + oy, 52 + ox, 13 + oy,
                          fill=star, outline='', tags='sparkle')
    flourish(canvas, pose, step, ox, oy, body, outline, accent, blush)
    scale = SIZE / PET_LAYOUT['source_size']
    canvas.scale('all', 0, 0, scale, scale)
    # Canvas.scale 只缩坐标；描边也须等比收紧，舔爪和摇尾才不会越出命中矩形。
    for item in canvas.find_all():
        canvas.itemconfigure(item, width=max(1.0, float(canvas.itemcget(item, 'width')) * scale))
    return len(canvas.find_all())


def flourish(canvas, pose, step, ox, oy, body, outline, accent, blush):
    """这一帧的猫在做什么：爪子／舌头／张开的嘴／甩起来的尾巴／腮红。

    每个动作各自带一个 'pose-xxx' 标签；端坐（sit）不加东西，就是上面那套基础画法。
    """
    if pose == 'walk':
        for paw in (14, 44):
            canvas.create_oval(paw + ox, 50 + oy, paw + 10 + ox, 58 + oy,
                               fill=body, outline=outline, width=1, tags=('pose-walk', 'paw'))
    elif pose == 'lick':
        canvas.create_line(50 + ox, 44 + oy, 58 + ox, 54 + oy, fill=body, width=6,
                           tags=('pose-lick', 'paw'))
        canvas.create_arc(27 + ox, 43 + oy, 37 + ox, 54 + oy, start=180, extent=180,
                          style='pieslice', fill=TONGUE, outline=outline, tags=('pose-lick', 'tongue'))
    elif pose == 'yawn':
        # 第 24 期第 6 条：原来打哈欠是在脸上张开一张墨色的嘴——64 像素里就是一个黑窟窿
        # （用户原话「像有个黑色大鼻子很丑」）。改成两团腮红：困意靠脸红说，脸不用张开。
        for side in (13, 43):
            canvas.create_oval(side + ox, 37 + oy, side + 8 + ox, 44 + oy, fill=blush,
                               outline='', tags=('pose-yawn', 'blush'))
    elif pose == 'wag':
        sway = 6 if step % 2 else -6
        canvas.create_line(56 + ox, 54 + oy, 63 + ox, 54 + sway + oy, smooth=True,
                           fill=outline, width=3, tags=('pose-wag', 'tail'))
    elif pose == 'nuzzle':
        for side in (14, 42):
            canvas.create_oval(side + ox, 40 + oy, side + 8 + ox, 46 + oy, fill=blush,
                               outline='', tags=('pose-nuzzle', 'blush'))
    return pose


class Cat:
    """三虎的猫样：随机换动作，一段动作持续若干帧。

    第 17 期：右上角那只猫不再是一张定住的脸——过一阵就自己换个动作（爬行／舔爪／打哈欠／
    摇尾巴／撒娇）。接缝设计：
    - rand 可注入（默认 random.random）：用例不必跟真随机较劲，注入固定序列就能复现；
    - 换动作绝不与上一个重复：连着两次一样就等于没换，看着像卡住了；
    - rand 坏掉（抛异常／NaN／负数／大于 1）一律当 0 处理，绝不把界面线程带崩。
    """

    def __init__(self, rand=None, span=(POSE_MIN, POSE_MAX), poses=POSES):
        self.rand = rand or random.random
        self.span = (max(1, int(span[0])), max(1, int(span[1])))
        self.poses = tuple(poses) or POSES
        self.pose = self.poses[0]
        self.until = 0                # 到这一帧就换下一个动作
        self.changes = 0              # 换过几次动作（日志与用例用）

    def roll(self, size):
        """把 rand() 夹成 [0, size-1] 的整数：坏值一律当 0，绝不让它冒到调用方。"""
        size = int(size)
        if size <= 1:
            return 0
        try:
            value = float(self.rand())
        except Exception:
            return 0
        if value != value or value < 0.0:      # NaN 与负数
            return 0
        return max(0, min(size - 1, int(value * size)))

    def pick(self, exclude=None):
        """随机挑一个动作：绝不与 exclude（上一个动作）重复。"""
        pool = [name for name in self.poses if name != exclude] or list(self.poses)
        return pool[self.roll(len(pool))]

    def next(self, frame, force=False):
        """返回这一帧该摆的姿态；到点（或 force=True）就换一个并重新计时。"""
        frame = int(frame)
        if force or frame >= self.until:
            self.pose = self.pick(exclude=self.pose)
            self.changes += 1
            low, high = self.span
            self.until = frame + low + self.roll(high - low + 1)
        return self.pose

    def describe(self):
        """给日志与用例的一眼快照。"""
        return {'pose': self.pose, 'name': POSE_NAMES.get(self.pose, self.pose),
                'until': self.until, 'changes': self.changes, 'span': self.span}


class StageQueue:
    """自动任务队列的薄包装：get_nowait 成功时把 (阶段, 结果) 报给 sink，其余接口原样转发。

    sink 里的异常必须吞掉——这里是 _tick_once 的取件路径，抛出去会让整个 150ms 心跳断掉。
    """

    def __init__(self, stage, sink=None, inner=None):
        self.inner = inner if inner is not None else queue.Queue()
        self.stage = stage
        self.sink = sink
        self.errors = []                  # 心跳不可中断，但失败必须留下可核记录。

    def get_nowait(self):
        item = self.inner.get_nowait()
        if self.sink is not None:
            try:
                self.sink(self.stage, item)
            except Exception as exc:
                # 此处是队列消费的通知支线，不能让 150ms 心跳停摆；
                # 但不再裸吞，调用方可从队列实例读到失败原因。
                self.errors.append(('sink', str(exc)))
        return item

    def put(self, item, *args, **kwargs):
        return self.inner.put(item, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def __len__(self):
        return self.inner.qsize()


def watch_status(desktop, pet):
    """接缝④：在既有状态栏变量外挂一层 set——原文照旧写进变量，宠物顺手记一笔（同一句话只算一次）。

    只包住这一个实例的 set，不碰 tkinter.Variable 类，也不新建任何 Tk 变量：变量仍由界面线程创建与回收，
    宠物只负责记一笔。重复挂载幂等（_petWatched），没有状态栏变量时原样返回 None。
    """
    var = getattr(desktop, 'status', None)
    if var is None or getattr(var, '_petWatched', False):
        return var
    original = var.set

    def set_(value):
        text = '' if value is None else str(value)
        original(text)
        try:
            pet.say(text)
        except TclError:
            # 关窗后宠物气泡不再可用；普通 pet.say 失败不可吞没。
            pass

    var.set = set_
    var._petWatched = True
    return var


def report_done(host, stage, text):
    """接缝⑤：某一步的手工制作收了尾，说给三虎听（第 47 期第 5 条）。

    宿主没接这条线（自检里的假宿主、还没挂宠物的窗口）就静默返回，页面逻辑一个字不受影响。
    真正的播报在 Pet.report_done 里；这里只负责「找得到就报」。报告器本身故障
    是阶段状态链故障，必须由调用者处理，不能假装这一步已经完成。
    """
    report = getattr(host, 'pet_report', None)
    if not callable(report):
        return None
    return report(str(stage), str(text))


def duration(seconds):
    """秒 → mm:ss；信息不足时不编数字。"""
    if seconds is None:
        return '信息不足'
    total = max(0, int(round(float(seconds))))
    return '%d:%02d' % (total // 60, total % 60)


def shot_stats(paths):
    """逐个分镜 JSON 数「镜头数」与「已出首帧数」：返回 (shots, frames)。

    frames 的口径与「待生成首帧」正好相反：只认 shot['frame'] 指向的文件真的在盘上的，
    标了 frame_deleted 的一律不算。首帧文件名带哈希后缀（EP001_SH001_8a7043f5.png），
    只能按 JSON 里记的路径去找，按文件名猜必然数错。
    """
    from storyboard_rows_service import shot_stats as _shot_stats
    return _shot_stats(paths)


def asset_counts(base):
    """资产库：登记的资产数，以及其中已经有图片的个数（与无人值守同一口径）。"""
    from legacy_compat import optional_asset_counts
    return optional_asset_counts(base, pet_bus.read_json)




def config(program=PROGRAM):
    """共享配置文件原样读出：pet_llm.load_config 只认它自己的键，宠物自己的开关要另看一眼。

    文件没有、读坏了都当空表——「没配置」与「配置写错」都必须退化成默认（不开），
    不能把异常丢进界面线程。
    """
    try:
        data = pet_bus.read_json(pet_agent.config_file(program))
    except Exception:                      # 连路径都算不出来（程序目录不可用）也当没配置
        data = {}
    return data if isinstance(data, dict) else {}


def autostart_command(program=PROGRAM):
    """开机自启要执行的命令行：优先同目录的 pythonw.exe（不弹控制台），拿不到就退回当前解释器。

    指的还是外面那个启动器（程序目录的上一级），与手动双击同一条路径，出问题好排查。
    """
    if not sys.executable:
        return ''
    exe = Path(sys.executable)
    quiet = exe.with_name('pythonw.exe')
    if quiet.is_file():
        exe = quiet
    launcher = Path(program).resolve().parent / '启动漫剧制作助手.pyw'
    return '"%s" "%s"' % (exe, launcher)


def startup_api():
    """注册表入口：非 Windows 或没有 winreg 时返回 None，整套开机自启降级为「不可用」。"""
    from platform_tools import windows_registry
    return windows_registry()


_UNSET = object()          # 「没传」与「明确传 None（本机没有 winreg）」必须分开


class Autostart:
    """开机自启：只写当前用户的 Run 项（HKCU），不碰系统级、不要管理员。

    取舍（同步写进维护记录）：没有第三方库做不出真正的托盘图标，第 6 期用「注册表 Run 项」
    ＋「独立窗常驻」两件事凑出常驻效果；关闭时只删自己写的那一项，别人的项一律不动。
    """

    def __init__(self, api=_UNSET, name=AUTOSTART_NAME, key=AUTOSTART_KEY):
        self.api = startup_api() if api is _UNSET else api
        self.name = name
        self.key = key

    @property
    def available(self):
        return self.api is not None

    def get(self):
        """已登记返回命令行，没登记返回空串，读不回来（权限等）返回 None。"""
        if self.api is None:
            return None
        try:
            with self.api.OpenKey(self.api.HKEY_CURRENT_USER, self.key, 0, self.api.KEY_READ) as handle:
                value, _kind = self.api.QueryValueEx(handle, self.name)
                return str(value or '')
        except FileNotFoundError:
            return ''
        except OSError:
            return None

    def set(self, command):
        """把命令行写进 Run 项；写不进去返回 False。"""
        if self.api is None or not command:
            return False
        try:
            with self.api.CreateKeyEx(self.api.HKEY_CURRENT_USER, self.key, 0,
                                      self.api.KEY_SET_VALUE) as handle:
                self.api.SetValueEx(handle, self.name, 0, self.api.REG_SZ, command)
        except OSError:
            return False
        return True

    def clear(self):
        """删掉自己写的项；本来就没有也算成功（幂等）。"""
        if self.api is None:
            return False
        try:
            with self.api.OpenKey(self.api.HKEY_CURRENT_USER, self.key, 0,
                                  self.api.KEY_SET_VALUE) as handle:
                self.api.DeleteValue(handle, self.name)
        except FileNotFoundError:
            return True
        except OSError:
            return False
        return True

    def enabled(self):
        return bool(self.get())

    def toggle(self, program=PROGRAM):
        """开着就关、关着就写当前命令行；返回切换后的状态（不可用的机器恒为 False）。"""
        if self.api is None:
            return False
        if self.enabled():
            self.clear()
            return False
        return bool(self.set(autostart_command(program)) and self.enabled())


def our_process_in_front():
    """前台窗口是不是本进程的窗口：用户切到别的应用上去了就返回 False（第 30 期第 3 条）。

    用户报的是「切到其他应用时三虎还弹聊天框」——判据就取「现在最上面那扇窗是谁的」：
    GetForegroundWindow 拿到句柄，再问这个句柄属于哪个进程；不是本进程就是别的应用在前台。
    认不出来（非 Windows、拿不到句柄、调用出错）一律当 True——宁可多说一句，也不能把播报全吞掉。
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = int(user32.GetForegroundWindow())
        if not hwnd:
            return True
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) == os.getpid()
    except Exception:
        return True


class Pet:
    """贴片宠物：画自己、说人话、把事件喂给父 Agent。界面线程独占，全部方法不抛异常。"""

    def __init__(self, desktop, clock=time.time, front=None):
        self.desktop = desktop
        self.win = desktop.win
        self.clock = clock
        self.errors = []
        self.notice = ''
        self.last_status = ''
        self.frame = 0
        self.attempts = {}
        self.canvas = None
        self.menu = None
        self._timer = None
        self._main_topmost_job = None
        self._project = object()          # 哨兵：第一次访问 core() 一定会重建
        self._core = None
        self._client = None
        self._client_project = object()
        self._flushed = 0
        self._tick_texts = set()
        self.report_path = None
        self.weekly_path = None
        self._autostart = None
        self._announced = ()              # 上一批已经弹过气泡的失败：同一批只弹一次
        self.snooze_until = 0.0           # 「稍后再说」到什么时候为止（时钟可注入，用例不用真等）
        self._busy_taps = []              # 第 60 期第 1 条：用户刚才那几下动作的钟点（判「人正忙」）
        self._menu_labels = {}            # 已经写进菜单的文字，避免每 150ms 白改一遍
        self.menu_index = {}
        self.program = PROGRAM            # 第 43 期：全局配置在哪个目录（用例里可指到临时目录）
        self.broadcaster = Broadcaster(str(self.program / 'logs' / 'sanhu_progress.log'))
        # 第 67 期任务 4：这一次运行的档位。开机那一下定成「只提醒」，之后换项目重建内核
        # （core 会重读盘上的设置）也照它来——不记下来的话，一打开项目就把用户存档里的
        # 旧档位读回来了，「开机一律只提醒」等于没做。
        self.session_level = ''
        # 三虎模式与既有三档自动化等级并存：模式只决定是否统一接管页面自动开关；
        # 等级仍保留 hint／semi／auto 的细粒度审批语义。
        self.mode = 'manual'
        self._auto_variables = {}
        self.probe_transport = None       # 「测试连接」用的传输函数（None＝真发；用例注入假函数）
        self._agent_file = None           # 上一次写盘写到的配置文件（排查时看得见）
        # 第 43 期：「切换模型」的当前档位＝模型池里的一个 id（或「自动」），开局按盘上的设置对表。
        self.tier = str(self.agent_model_tasks().get('default') or model_pool.AUTO)
        self.chat = None                  # 第 14 期云朵框：开着时是云朵对象，收起是 None
        self._cloud = None                # 云朵框实例（只建一次，收起再开保留记录）
        self._broadcast_at = None         # 上一次播报的钟点（频率控制，注入时钟可测）
        self._last_broadcast = ''         # 上一次播报的原文（同一句话不连着说两遍）
        self._menu_open = False           # 第 47 期第 4 条：功能下拉栏正显示着（这期间不冒云朵框）
        self._held_broadcast = ''         # 这期间被压住的那一句话（栏收起后补说）
        self._gap_sig = None              # 上一次算出来的缺口指纹：变了就立刻播报
        self._spoken = {}                 # 第 57 期第 2 条：刚说过的那几件事（key → 钟点）
        self._gap_at = None               # 上一次算缺口的钟点（读盘很贵，按 GAP_SECONDS 节流）
        self._gap_cache = []              # 最近一次算出来的缺口
        self._chat_interaction = ChatCoordinator(
            schedule=lambda delay, callback: self.win.after(delay, callback),
            cancel=self._cancel_chat_click, delay=CLICK_MS,
            visible=lambda: self.cloud_visible(), open_chat=lambda: self.open_chat(),
            close_chat=lambda: self.close_chat(), mute=lambda **kw: self.mute(**kw),
            on_error=lambda name, message: self.errors.append((name, message)))
        self._greet_id = None             # 还没到点的开机招呼（关窗比招呼先到时必须收回来）
        self._quiet_until = None          # 招呼之后的安静期到哪一刻（第 68 期任务 11）
        self.cat = Cat()                  # 第 17 期：三虎的猫样（随机做点猫的事，见 Cat）
        self.caption = None               # 第 18 期：贴片左边那行小字（正常／半自动／全自动）
        self.menu_tier = None             # 「换模型」子菜单：接新模型时按登记表整栏重建
        self.menu_mode = None             # 「模式」子菜单：手动／全自动的唯一界面入口
        self.mode_var = None              # 仅绑定菜单单选状态；自动制作变量仍只归三虎管理
        self.paws = None                  # 第 19 期：贴片左边那排猫爪按钮（自动化等级）
        self.gear = None                  # 第 44 期：窗口左上角那颗齿轮（设置入口）
        self._paws_key = None             # 上一次画的样子（档位 ＋ 悬停在哪只爪）：没变就不白画一遍
        self._paw_hover = None            # 鼠标这会儿停在第几只爪上（None＝没停）
        self._lifted_at = None            # 上一次把贴片抬到最上层的钟点
        self._progress_at = None          # 上一次冒进度圆气泡的钟点（三虎自己判断时机）
        self._progress_stage = None       # 上一次冒进度气泡时的阶段：换阶段就再说一次
        self._progress_said = ''          # 上一条进度气泡的原文（第 49 期第 3 条：一字不差就不再冒）
        self._mute_until = 0.0            # 云朵框被点掉之后，安静到什么时候（别被自动播报顶回来）
        self.asker = None                 # 一键执行前的确认弹窗：None＝系统 messagebox（用例可注入）
        self.recovery_asker = None        # 中断恢复选择器：None＝系统输入框（用例可注入）
        self._recovery_from = None        # 开机恢复选择的 (stage, step)，下一次同阶段执行时消费
        # 第 54 期附件四：自动推进那条链的队长。剧本做完（script.completed）且等级是
        # semi／auto 时武装起来，之后逐阶段往下走；暂停／恢复就是它的 pause／resume。
        self.auto = stage_flow.AUTO
        # 第 63 期任务 3.2：自动推进之前先过阶段间门禁——上游真的做了却没做全就停在这一步，
        # 说一句「缺什么、去哪儿补」；上游压根没开始时照旧往下走（第 47 期起的规矩）。
        self.auto.gate = self.gate_reason
        self._gate_said = ''              # 上一次因门禁停住时说过的那句：同一句不重复念
        self.front = front                # 第 30 期第 3 条：前台判据（None＝不设这道闸，见 attending）
        self._away_since = None           # 第 35 期第 1 条：离开助手界面的钟点（None＝人在界面里）
        self._away_paused = False         # 上面那次离开有没有把自动执行暂停下来（只认自己停的那一次）
        self._banner_key = None           # 关软件那张标签框当天的签名：报过一次就不再弹
        self._advance_at = None           # 上一次把「下一步」提前叫醒的钟点（推进的节流）
        self._last_advance = ''           # 上一次推进说的话：同一句不重复念
        self._notice_step = False         # notice 是不是「清一色的操作步骤」（第 24 期第 5 条）
        self._panel_at = None             # 用户上一次自己打开进度面板的钟点（第 24 期第 10 条）
        self._offer_at = None             # 上一次问「要不要一键执行」的钟点（第 25 期第 3 条）
        self._offer_sig = ()              # 问的时候缺口长什么样：变了才是「进度又往前走了」
        self._offer_open = False          # 那个问题这会儿是不是还挂着（挂着他才认「好」这一句）
        self._stage_page = None           # 第 36 期第 6 条：上一次问过的那一页（换了页才问）
        self._stage_at = None             # 上一次问「这一步要不要我做」的钟点
        self._stage_auto_started = set()  # 已由进页全自动启动过的阶段，切页／刷新不重复派发
        self._work_at = None              # 第 36 期第 5 条：上一次看见制作动静的钟点
        self._report_key = None           # 第 36 期第 5 条：这一天的日报／周报提过没有
        self._projects_rows = None        # 第 37 期第 1 条：全部项目的快照（带 TTL 缓存）
        self._projects_at = 0.0           # 上一次读盘对表的钟点
        self._test_session = None         # P2 测试模式：既有心跳轮询的增量自检子进程
        self._performance_session = None  # P2 优化模式：既有心跳轮询的短基准子进程

    # ── 项目级内核：总线＋状态机＋父 Agent ─────────────────────────────────
    def client(self, project=None):
        """LLM 客户端：同一个项目复用一份；规则未命中才会真的发请求。

        先读配置文件的设置，再把「换模型」按下的档位叠上去：只覆盖 force_tier 一项，
        base_url／密钥来源／错峰窗口这些照旧来自配置文件。
        """
        if self._client is None or self._client_project != project:
            self._client_project = project
            settings = dict(pet_llm.load_config(program=self.program))
            settings.update(self.tier_config())
            self._client = pet_llm.Client(project=project, program=self.program, clock=self.clock,
                                          config=settings)
        return self._client

    def core(self):
        """按当前项目重建内核（换项目时整体换一套，不串台）。"""
        project = Path(self.desktop.root) if getattr(self.desktop, 'root', None) else None
        if self._core is not None and self._project == project:
            return self._core
        self._project = project
        bus = pet_bus.Bus(journal=pet_agent.journal_path(project) if project else None)
        machine = None
        if project is not None:
            machine = pet_state.Machine(project, persist=True).load()
            machine.subscribe(bus)
        # 第 44 期：把 program 递下去——父 Agent 的设置（等级／免打扰／预算／动画）与模型池
        # 落在同一个配置目录里，设置页写下去的那几把键这一份立刻就认。
        agent = pet_agent.Agent(project=project, machine=machine, client=self.client(project),
                                bus=bus, persist=project is not None, program=self.program)
        if self.session_level in pet_agent.LEVELS:
            agent.set_level(self.session_level)      # 第 67 期任务 4：照这一次运行的档来
        # 第 37 期第 1 条：三虎要「记住所有项目」——把这份只读快照供给父 Agent，
        # 它在 context() 里带上（问模型时模型也看得见手上有哪些项目）。
        agent.projects = self.projects_brief
        agent.attach(bus, machine=machine)
        # 第 54 期：把「正在跑哪一步」接到总线上（手动按钮据此写「自动执行中」并置灰），
        # 再把自动推进那条链的起点与收场也挂上——剧本完成就按依赖图往下走，
        # 每一步收场（成或败）都让队长往下挪一格。
        stage_flow.listen(bus)
        bus.subscribe('script.completed',
                      lambda item: self.auto.script_done(self.agent.level))
        bus.subscribe('stage.completed', self._auto_stage_completed)
        bus.subscribe('stage.failed', self._auto_stage_failed)
        # 第 63 期任务 3.3：每一次子 Agent 起手／重试／收场都按统一格式记进
        # <阶段目录>/logs/agent_logs.jsonl；收场时把它手上的并发号全还了，闸门不会漏还卡住。
        bus.subscribe('stage.executing', lambda item: self.log_stage(
            item.get('stage'), 'start', str(item.get('trigger') or '')))
        bus.subscribe('stage.retrying', lambda item: self.log_stage(
            item.get('stage'), 'retry', '第 %s 次，%s 秒后重来' % (item.get('attempt'), item.get('delay'))))
        bus.subscribe('stage.completed', lambda item: self.log_stage(
            item.get('stage'), 'ok', release=True))
        bus.subscribe('stage.failed', lambda item: self.log_stage(
            item.get('stage'), 'failed', str(item.get('error') or ''), release=True))
        bus.subscribe('stage.paused', lambda item: self.log_stage(
            item.get('stage'), 'paused', release=True))
        self._core = (bus, machine, agent)
        self.attempts = {}
        return self._core

    @property
    def bus(self):
        return self.core()[0]

    @property
    def machine(self):
        return self.core()[1]

    @property
    def agent(self):
        return self.core()[2]

    def snapshot(self, at=None):
        """本轮进度快照：动画帧、气泡、面板共用同一份数字（出错也不抛）。"""
        try:
            return self.agent.progress(at=at)
        except Exception as exc:
            self.errors.append(('progress', str(exc)))
            return {}

    def _emit(self, kind, **payload):
        return pet_bus.emit_safe(self.bus, self.errors, kind, **payload)

    def _completion_evidence(self, stage):
        """返回某阶段是否已有可核验的落盘成果及未通过原因。

        自动任务的 ``ok`` 只代表调用没有抛异常：它可能只是提交了远端任务、生成了
        一段提示词，或者页面仍在等待用户采用。三虎只能把可复核的项目产物标成完成。
        没有项目的轻量宿主（旧插件和自检替身）不持久化阶段状态，保留其原有行为。
        """
        import stage_completion_service
        studio = getattr(self.desktop, 'studio', None)
        return stage_completion_service.completion_evidence(
            getattr(self.desktop, 'root', None), stage,
            getattr(studio, 'auto_edit_ready', None))

    def _complete_if_verified(self, stage, text):
        """唯一的自动完成出口；缺少产物时只停止运行态，绝不推进自动链。"""
        import stage_completion_service
        studio = getattr(self.desktop, 'studio', None)
        ok, detail, emitted = stage_completion_service.emit_verified_completion(
            getattr(self.desktop, 'root', None), stage, text, self._emit,
            getattr(studio, 'auto_edit_ready', None))
        if ok:
            return emitted
        self.last_status = '%s（待校验：%s）' % (text, detail)
        return self._emit('stage.paused', stage=stage, text=self.last_status)

    # ── 接缝：自动任务队列 / 状态栏 / 页面按钮 ─────────────────────────────
    def drain(self, stage, item):
        """接缝②：自动任务这一轮的结果 → 阶段事件；失败交给父 Agent 分级。"""
        try:
            ok, value = item[0], item[1]
        except (TypeError, IndexError, KeyError):
            return None
        text = str(value)
        self.last_status = text
        self._tick_texts.add(text)
        if ok:
            self.attempts[stage] = 0
            return self._complete_if_verified(stage, text)
        plan = self.agent.fail(stage, text, attempt=self.attempts.get(stage, 0))
        self.attempts[stage] = plan['next_attempt'] if plan['allow'] else 0
        return plan

    def _auto_stage_completed(self, item):
        """自动链只在成功收场后推进，并预告下一阶段给心跳安全启动。"""
        stage = str((item or {}).get('stage') or '')
        self.auto.done(stage, True)
        if self.mode != 'auto' or not self.auto.armed or self.auto.paused:
            return None
        pending = self.auto.pending()
        if not pending:
            return None
        next_stage = pending[0]
        self._advance_at = None
        name = pet_bus.STAGE_NAMES.get(next_stage, next_stage)
        self.broadcast('【下一阶段】%s - 自动开始' % name)
        return next_stage

    def _auto_stage_failed(self, item):
        """任一阶段失败均阻塞自动链，直到用户修复后手动恢复或重试。"""
        stage = str((item or {}).get('stage') or '')
        error = ' '.join(str((item or {}).get('error') or '').split())
        self.auto.done(stage, False, error)
        name = pet_bus.STAGE_NAMES.get(stage, stage or '当前阶段')
        detail = error or '该阶段未完成，等待用户处理'
        self.broadcast('【阻塞】%s 未完成，自动执行已停止：%s' % (name, detail))
        return None

    def report_done(self, stage, text, at=None):
        """接缝⑤：某一步的手工制作收了尾 → 三虎当场说一句（第 47 期第 5 条）。

        与自动任务那条 StageQueue 通道的区别在那条通道的节拍上：它要等下一次播报窗口
        （忙时 40 秒、闲时 180 秒，见 tick_broadcast），用户盯着页面等成品时这一句必须马上说，
        所以这里走 announce（与「用户按了东西」同一条出口）。

        「稍后再说」期间只记账不冒泡——那是用户自己点名要的安静；失败照旧由失败清单分级处理，
        不走这里。同一句话连着说两次由 broadcast 自己挡掉（_last_broadcast）。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        try:
            import stage_completion_service
            # 自动链先由 script.completed 武装，再消费同一次的 stage.completed。
            # 反过来发会让队长尚未 armed 就吞掉完成事件，停在剧本阶段。
            studio = getattr(self.desktop, 'studio', None)
            verified, detail, _emitted = stage_completion_service.emit_verified_completion(
                getattr(self.desktop, 'root', None), stage, text, self._emit,
                getattr(studio, 'auto_edit_ready', None),
                (lambda: self._emit('script.completed', stage='script', text=text))
                if str(stage or '') == 'script' else None)
            if not verified:
                self.last_status = '%s（待校验：%s）' % (text, detail)
                self._emit('stage.paused', stage=str(stage or ''), text=self.last_status)
                return self.announce(self.last_status, at=at)
        except Exception as exc:
            self.errors.append(('report', str(exc)))
        if self.snoozing():
            self.notice = text
            return text
        return self.announce(text, at=at)

    def say(self, text):
        """接缝④：状态栏原文照旧，宠物只做合并与计数（重复的一句只算一次）。"""
        text = str(text or '').strip()
        if not text or text == self.last_status:
            return None
        self.last_status = text
        if text in self._tick_texts:
            return None                   # 这一轮已经从自动任务队列报过，不再重复记一笔
        self._tick_texts.add(text)
        # step=True：这是「正在做的那一步」的原文，进台账与进度面板，但不进云朵记录（第 24 期第 5 条）
        return self.agent.notifier.add(text=text, step=True)

    def tap(self, label):
        """接缝③：页面按钮成功后上报「用户点了什么」（原按钮逻辑不受影响）。

        第 60 期第 1 条：顺手记一笔「人刚才在按」——连着按太密就自己进免打扰（见 note_work）。
        """
        self.note_work()
        return self._emit('intent.command', text=str(label), source='button')

    # ── 事件分发 ────────────────────────────────────────────────────────────
    def pump(self, limit=200, at=None):
        """把总线上的事件分发掉（状态机与通知聚合各自订阅），再把通知说给气泡。

        第 24 期第 5 条：只有「操作步骤」的那一批汇总（notifier.last_step）不进云朵记录——
        notice 是三虎的口吻，云朵记的是它说的话；操作步骤属于状态栏与进度面板。
        """
        bus, _machine, agent = self.core()
        count = bus.pump(limit)
        flushed = agent.flush(at=at) or agent.catch_up(at=at)
        self._notice_step = bool(flushed) and bool(getattr(agent.notifier, 'last_step', False))
        self.notice = flushed or self.notice
        self._tick_texts.clear()
        self.chat_drain()              # 云朵框的后台回答：在这个既有心跳里贴上，不新增定时器
        self.poll_test_mode(at=at)
        self.poll_performance_mode(at=at)
        self.guard_chat_grab()         # 第 59 期第 8 条：有弹窗抽着指针时，聊天框先自己收起来（那时它点不动）
        self.guard_cloud_away()        # 第 60 期第 4 条：人切去别的应用时，露着的云朵自己收起来
        if not self.modal_grabbed():
            self.say_held()            # 弹窗关了：被它挡住的那一句补说
        self.watch_focus(at=at)        # 第 35 期第 1 条：切出去就暂停、回到界面再恢复
        self.tick_broadcast(at=at)     # 播报：按频率说进度，缺口一变化立刻说（第 14 期）
        if agent.client is not None and agent.client.calls and len(agent.client.calls) != self._flushed:
            self._flushed = len(agent.client.calls)
            try:
                agent.client.flush()
            except Exception as exc:
                self.errors.append(('ledger', str(exc)))
        state = self.snapshot(at=at)
        self.refresh(at=at, state=state)
        self.announce_failures()
        self.progress_voice(state=state, at=at)   # 进度：三虎自己挑时机冒圆气泡（第 19 期）
        self.report_hint(at=at)    # 第 36 期第 5 条：下午／夜里活儿慢下来，把日报周报递上来
        self.offer_oneclick(state=state, at=at)   # 收尾的时机到了就主动问一句（第 25 期第 3 条）
        self.refresh_menu_labels()   # 「稍后再说」的倒计时写在菜单上，跟着心跳走
        self.tune_advance(state=state, at=at)   # 自动推进：把「下一步」提前叫醒（第 23 期）
        return count

    def tune_advance(self, state=None, at=None):
        """自动推进（第 23 期）：等级允许时，把「下一步该做的那一步」提前叫醒一轮。

        Agent.advance() 一直在算「下一步是哪一步」，却从来没人用（只有用例在调）——自动化的
        最后一段路是断的。这里把它接上心跳：不代按任何按钮，只把这一步对应的无人值守轮询的
        due 拉到当前（跑不跑仍然由那一步自己的开关和退避说了算）。

        什么时候不推：只提醒档（advance 自己会返回 None）、忙、暂停、静默、有对话框露着、
        距上次推进不到 ADVANCE_SECONDS。换了一步才说一句，同一阶段不重复念。

        第 44 期（默认档改成半自动之后补的一条）：**开机第一拍只把活叫醒，不冒云**——原来第一次
        推进就会说一句，而默认半自动之后这必然发生在开机那一拍，正好撞上用户第 22 期报过的
        「开机闪一下云朵框」。叫醒照旧（这一步的轮询该跑就跑），只是那一句留到下一次换步再说。
        """
        try:
            now = float(self.clock() if at is None else at)
            if self.quiet(at=at):
                return ''                  # 第 68 期任务 11：招呼刚说完，推进那一步的话也留到安静期之后
            if self._advance_at is not None and (now - self._advance_at) < ADVANCE_SECONDS:
                return ''
            if self.cloud_visible() or self.muted(at=at) or self.snoozing() or self.agent.paused:
                return ''
            state = state if state else self.snapshot(at=at)
            if self.busy(state=state):
                return ''
            stage = self.auto_stage()
            first_beat = self._advance_at is None
            self._advance_at = now             # 到这一拍为止都算推过：没阶段可推也别每 150ms 问一遍
            if not stage:
                return self.gate_note(at=at)   # 第 63 期任务 3.2：被门禁停住就说一句
            # 第 67 期任务 5：自动档下不只把这一步叫醒——能自己派的就派下去、该打开的无人值守
            # 开关替他打开（见 start_stage）；放行不了的那几步照旧只叫醒。
            text = self.start_stage(stage, at=at)
            if first_beat:
                return ''                     # 开机第一拍：只叫醒不念（下一拍这一步仍会被念一次）
            if not text or text == self._last_advance:
                return ''
            self._last_advance = text
            return self.announce(text, at=at)
        except Exception as exc:
            self.errors.append(('advance.tune', str(exc)))
            return ''

    # ── 一键操作 ────────────────────────────────────────────────────────────
    def click(self, intent, at=None):
        """气泡/右键菜单的一键操作：只动宠物自己管得到的，其余记成意图事件。"""
        self.note_work(at=at)              # 第 60 期第 1 条：这一下也是「人在忙」的一笔
        agent = self.agent
        if intent == 'pause':
            agent.pause('您在气泡里按了暂停')
            self.auto.pause()
            self.pause_running_stage()
            self.announce('已暂停自动执行：宠物只报告进度，不再自动推进', at=at)
        elif intent == 'resume':
            agent.resume()
            self.auto.resume()
            self.announce('已继续自动执行：按当前自动化等级推进，会花钱的步骤仍需您确认', at=at)
        elif intent == 'retry':
            self.retry_failures()
        elif intent == 'oneclick':
            return self.one_click(at=at)
        elif intent == 'level':
            # 按一次换一档；子菜单里可以直接点到某一档（set_level），两条路共用同一套实现。
            order = list(pet_agent.LEVELS)
            self.set_paw_level(order[(order.index(agent.level) + 1) % len(order)], at=at)
        elif intent == 'chat':
            return self.open_chat()
        elif intent == 'skip':
            self.skip_failure()
        elif intent == 'model':
            self.switch_model()
        elif intent == 'snooze':
            self.snooze()
            self.notice = '好，安静 %d 分钟：这段时间只记账，出安静期再报一次' % (SNOOZE_SECONDS // 60)
        elif intent == 'details':
            self.show_details()
        self._emit('intent.command', text=str(intent), source='bubble')
        self.refresh(at=at)
        return intent

    def retry_failures(self):
        """失败清单交给链路自己重跑（无人值守链路的下游节流清零），宠物只负责记账。"""
        count = len(self.agent.failures)
        kick = getattr(self.desktop, 'kick_unattended', None)
        if callable(kick):
            try:
                kick('pet')
            except Exception as exc:
                self.errors.append(('kick', str(exc)))
        self.agent.clear_failures()
        self.notice = ('已重试失败项：%d 项已交回链路重跑，无人值守会按原顺序继续' % count if count
                       else '现在没有待确认的项，不用重试')
        return True

    def skip_failure(self, item=None):
        """「跳过这张」：把一条待确认从清单里摘掉——用户显式跳过就是不再等它了。

        摘掉之后清单指纹变化，剩下那些仍然会被气泡提醒一次；清单本来就空就说明一句，
        不做任何别的事（跳过不等于重试，也不动状态机）。
        """
        entry = None
        try:
            entry = self.agent.skip_failure(item)
        except Exception as exc:
            self.errors.append(('skip', str(exc)))
        if entry is None:
            self.notice = '现在没有待确认的项，不用跳过'
            return ''
        stage = str(entry.get('stage') or '')
        category = str(entry.get('category') or '')
        self.notice = '已跳过一条待确认：%s · %s（还剩 %d 项）' % (
            pet_bus.STAGE_NAMES.get(stage, stage or '某阶段'),
            pet_agent.CATEGORY_NAMES.get(category, category or '未分类'), len(self.agent.failures))
        return self.notice

    # ── 对话落地：把「听懂了」变成「真的做了」（第 23 期）───────────────────
    def goto(self, stage, at=None):
        """切到某一页：真的把那一页翻开。

        原来对话里回一句「切到对应页面。」——页面一动不动，用户还得自己找。现在走宿主的
        pet_goto 真翻页；翻不动（没项目／认不出这一步）也老实说一句，不装作做过。
        """
        name = pet_bus.STAGE_NAMES.get(stage, '')
        if not name:
            self.notice = '这句话里没听出要切到哪一步，可以说「打开首帧管理」。'
            return self.notice
        go = getattr(self.desktop, 'pet_goto', None)
        page = ''
        if callable(go):
            try:
                page = str(go(stage) or '')
            except Exception as exc:
                self.errors.append(('goto', str(exc)))
        self.notice = ('已切到「%s」页' % name) if page else ('没能替您翻到「%s」页，自己点一下也行' % name)
        return self.notice

    def stage_states(self):
        """项目里每一步现在是什么状态（读不出来给空表＝一律当没做完）。"""
        try:
            return {stage: (entry or {}).get('state') for stage, entry in self.machine.stages.items()}
        except Exception as exc:
            self.errors.append(('states', str(exc)))
            return {}

    def arm_auto(self):
        """第 67 期任务 5：用户切到自动档之后，不必再做一次剧本——剧本做完了就按现状武装。

        第 54 期起那条链只在「剧本完成」这一条事件上武装；用户在早就做完剧本的项目里切到全自动，
        那一条事件不会再来，自动档于是一直什么都不开始。这里按项目现状补上（见 Auto.arm_from）：
        已经收场的那几步跳过，队长从第一个没做完的阶段接手。
        """
        level = self.agent.level
        if level not in stage_flow.AUTO_LEVELS:
            return False
        states = self.stage_states()
        # 用户可能在切换三虎自动档之前，已经通过「手动制作结构剧本」产出了正稿。
        # 那条手动工作流的历史事件不一定还在状态机里，不能因此把自动链卡在旧的
        # script / script_structure 状态。以真实落盘的正稿为准，并顺手登记到初步
        # 分镜的选择中；后者保证 storyboard_batch 立即有输入可派发，后续自动采用
        # 则会继续把生成的分镜同步给资产、首帧等页面。
        project = getattr(self.desktop, 'root', None)
        ready = self.has_structured_script(project)
        if ready:
            states = dict(states)
            # 旧项目只缺状态记录或仍是初始 pending 时，已有正稿可作为已完成依据；
            # 但本轮若已明确 failed/running/retrying，目录里残留的旧正稿不能掩盖
            # 这次失败，否则自动链会错误跳过结构剧本直接开始分镜。
            for stage in ('script', 'script_structure'):
                if str(states.get(stage) or '') in ('', 'pending'):
                    states[stage] = 'success'
            try:
                from storyboard_selection import sync_structured_script
                sync_structured_script(project)
            except (OSError, ValueError, TypeError) as exc:
                self.errors.append(('structured_script.sync', str(exc)))
                self.broadcast('【警告】结构剧本已存在，但同步分镜输入失败：%s；请稍后重试。' % exc)
        if str(states.get('script') or '') not in stage_flow.DONE_STATES:
            return False
        return self.auto.arm_from(level, states)

    @staticmethod
    def has_structured_script(project):
        """真实的结构剧本是否已落盘（兼容历史状态机没有记录的旧项目）。"""
        try:
            from script_contract import structured_script_path
            structured = structured_script_path(project) if project else None
            return bool(structured and structured.is_file() and structured.stat().st_size > 0)
        except (OSError, TypeError, ValueError):
            return False

    def start_stage(self, stage, at=None):
        """第 67 期任务 5：自动档下「自动开始每个阶段的任务」。

        能免费自己派的（分镜、首帧）走「手动制作XX」那一条准备链；其余各步交给宿主把这一步的
        无人值守开关打开并立刻起跑。半自动档会花钱的那几步只叫醒、等他点一下确认（与 approve
        同一条口径），hint 档一个字都不做。宿主没有这条接缝、或这一步不放行时，退回原来的
        「只叫醒轮询」。
        """
        if self.agent.level not in stage_flow.AUTO_LEVELS:
            # 第 67 期任务 4：只提醒档只看着——连「提前叫醒一轮」都不做，一个阶段都不替他开。
            return ''
        kick = getattr(self.desktop, 'pet_start', None)
        allowed = False
        if callable(kick):
            try:
                allowed = bool(self.agent.approve('stage.run', paid=stage in stage_flow.PAID_STAGES)['run'])
            except Exception as exc:
                self.errors.append(('start', str(exc)))
                allowed = False
        if allowed:
            # 所有阶段都必须经过宿主的 L3 命令入口。此前这里为结构剧本／分镜／首帧
            # 直接调用了三个批处理接缝，既绕过注册器，也使手动与自动拥有两套状态路径。
            # L3 再按阶段选择批处理或无人值守轮询；Pet 只负责授权与观察终态。
            started = ''
            try:
                started = str(kick(stage) or '')
            except Exception as exc:
                self.errors.append(('start', str(exc)))
                # L3 入口抛错也必须给 active 阶段一个终态，不能退回
                # advance_stage 后把“派发失败”伪装成仅仅提前叫醒。
                prefix = {
                    'script_structure': '剧本结构未派发：',
                    'storyboard': '分镜批次未派发：',
                    'keyframe': '首帧批次未派发：',
                }.get(stage, '阶段未派发：')
                started = prefix + str(exc)
            if started:
                # 三个本地批处理接缝会把异常转换成人可读文字。此前这里把那种
                # 非空错误文字误认成「已经启动」，自动链的 active 永远得不到终态事件。
                # 只识别本模块固定前缀，正常宿主返回的任意中文提示仍照旧透传。
                failed_prefix = {
                    'script_structure': '剧本结构未派发：',
                    'storyboard': '分镜批次未派发：',
                    'keyframe': '首帧批次未派发：',
                }.get(stage, '')
                if failed_prefix and started.startswith(failed_prefix):
                    self._emit('stage.failed', stage=stage, error=started)
                return started
        advanced = self.advance_stage(stage, at=at)
        if advanced:
            return advanced
        # 自动队长已经在 next_stage() 中把本阶段置为 active。宿主既没有可派发
        # 的批处理、也没有可提前叫醒的轮询时，继续静默返回会永久显示“自动执行中”。
        # 这不是成功；明确阻塞，让用户手动完成后再恢复自动链。
        if self.auto.armed and self.auto.active == stage:
            error = '当前版本没有「%s」的自动执行入口，请手动完成后再恢复自动流程' % (
                pet_bus.STAGE_NAMES.get(stage, stage))
            self._emit('stage.failed', stage=stage, error=error)
            return error
        return ''

    def auto_stage(self):
        """这一拍该推哪一步（附件四）：自动推进那条链武装了就按它走，否则退回状态机。

        hint（只提醒）档、暂停、链走完都会落到 agent.advance() 上——那一条本来就会返回
        None。第 67 期任务 5：链改由「用户切档」那一下按项目现状武装、切回只提醒时停手
        （见 arm_auto 与 Pet.set_level）；这里不再自己补——补了就等于每拍让链抢在状态机
        前面吃掉一格，「同一阶段连着叫醒几次」的老规矩会当场失效。
        """
        try:
            if self.auto.armed and not self.auto.paused:
                stage = self.auto.next_stage()
                if stage:
                    return stage
                if self.auto.blocked:
                    return None            # 第 63 期任务 3.2：被门禁停住就别去推别的阶段
        except Exception as exc:
            self.errors.append(('auto', str(exc)))
        return self.agent.advance()

    def log_stage(self, stage, status, detail='', release=False):
        """某一步的一个事件按统一格式落进 logs/（第 63 期任务 3.3）。

        只记账：写不进去、还号失败都绝不影响正在跑的那一步。released=True 的几个收场事件
        顺带把这一步手上的并发号还了——不还，闸门会一直当它还在跑。
        """
        try:
            self.agent.log_stage(stage, 'stage', status, detail)
        except Exception as exc:
            self.errors.append(('log', str(exc)))
        if release:
            try:
                self.agent.release_stage(stage)
            except Exception as exc:
                self.errors.append(('release', str(exc)))

    def gate_reason(self, stage):
        """这一步的上游门禁（第 63 期任务 3.2）：挡住了给一句人话，没挡住给空串。

        O24：把「正式自动生产」和「浏览／补录／旧项目兼容」分开——自动链在推（无人值守）时
        用正式生产口径：上游「还没开始」也当前置条件缺失拦住，除非用户显式把那一步标成
        「已跳过」；链没在推时沿用旧的浏览口径，旧项目不会因为严格门禁打不开。
        """
        # 结构剧本是分镜唯一的文件级上游。历史项目可能有成品却未留
        # script_structure.completed 事件；该情况下不要让状态机的旧账阻断
        # 自动派发，后面的阶段仍照常由各自真实产物门禁控制。
        if stage == 'storyboard' and self.has_structured_script(getattr(self.desktop, 'root', None)):
            return ''
        chain = getattr(self, 'auto', None)
        mode = (stage_parallel.PRODUCTION if getattr(chain, 'armed', False)
                else stage_parallel.BROWSE)
        try:
            return str(self.agent.blocked_reason(stage, mode=mode) or '')
        except Exception as exc:
            self.errors.append(('gate', str(exc)))
            return ''

    def parallel_snapshot(self):
        """并发现状（第 63 期任务 3.3）：在跑几个、降速几次、各阶段各几个。"""
        try:
            return self.agent.parallel_snapshot()
        except Exception as exc:
            self.errors.append(('parallel', str(exc)))
            return {'limit': 8, 'running': 0, 'slowed': 0, 'stages': {}, 'tickets': ()}

    def gate_note(self, at=None):
        """被门禁停住时补的一句：同一句只说一次，暂停或忙的时候不打扰用户。"""
        held = getattr(self.auto, 'blocked', None)
        if not held or self.auto.paused or self.agent.paused:
            self._gate_said = ''
            return ''
        reason = str(held[1] or '')
        if not reason or reason == self._gate_said:
            return ''
        self._gate_said = reason
        return self.announce(reason, at=at)

    def pause_running_stage(self):
        """暂停自动：正在跑的那一步按钮恢复「手动制作XX」（附件四第 7 条）。返回那几步。"""
        stages = [stage for stage in stage_flow.OWN_ORDER if stage_flow.running(stage)]
        for stage in stages:
            self._emit('stage.paused', stage=stage)
        return stages

    def advance_stage(self, stage, at=None):
        """让某一步的无人值守轮询提前跑一轮；返回宿主给的那句人话，没有这条路返回空串。

        只有宿主知道那一步有没有轮询、用户在页面上勾没勾开关，所以这里只负责问一句。
        """
        kick = getattr(self.desktop, 'pet_advance', None)
        if not callable(kick) or not stage:
            return ''
        try:
            return str(kick(stage) or '')
        except Exception as exc:
            self.errors.append(('advance', str(exc)))
            return ''

    def generate(self, stage, at=None):
        """「批量生成某一步」：能免费跑的立刻派单，跑不了的说清楚要用户在哪按。

        首帧走本机 ComfyUI 那条免费通道（与「一键执行」同一个入口）；其余几步要么花钱、
        要么得先有素材，一律不代按——最多把用户带到那一页，或者把用户勾过的无人值守开关
        提前叫醒一轮（叫醒之后跑不跑，仍然由那一步自己的开关说了算）。
        """
        name = pet_bus.STAGE_NAMES.get(stage, stage or '这一步')
        if stage == 'keyframe':
            self.notice = self.firstframe_batch() or '现在没有缺首帧的镜头，不用派单'
            return self.notice
        if stage == 'storyboard':
            # 第 62 期任务 2：三虎也能自己把分镜做起来（与「手动制作分镜」同一条准备链）。
            # 没有要做的新分镜时退回老路子——把「自动采用」那一轮提前叫醒。
            text = self.storyboard_batch()
            if text:
                self.notice = text
                return self.notice
            text = self.advance_stage(stage)
            self.notice = text or '分镜这一步现在没有要做的事：先去「初步分镜」页选好剧本。'
            return self.notice
        text = self.advance_stage(stage)
        if text:
            self.notice = text
            return self.notice
        paid = stage in ('assets', 'video', 'audio')
        if paid:
            self.goto(stage)
            self.notice = '「%s」这一步会花钱，三虎不代按：已经带您到那一页，按页面上的按钮就行' % name
            return self.notice
        self.notice = '「%s」这一步还没有能自动跑的路子，可以在页面上手动做' % name
        return self.notice

    def export_delivery(self, at=None):
        """「导出交付」：把用户带到「质检与交付」页——导出按钮在那儿，三虎不代按。"""
        self.goto('delivery')
        self.notice = '交付导出在「质检与交付」页：按「导出」就出清单（这一步三虎不代按）'
        return self.notice

    def run_plan(self, result, at=None):
        """把对话里那句「听懂了」真的落到处（第 23 期）。

        dispatch 在后台线程只出结论（纯读状态机与台账、不碰 Tk）；结论随云朵的队列回到心跳，
        由这里在界面线程办事。没登记的意图一律不动手——宁可什么都不做，也不能替用户按错按钮。
        返回一句「做了什么」的人话；没做就返回空串。
        """
        try:
            plan = (result or {}).get('plan') or {}
            decision = (result or {}).get('decision') or {}
            if not decision.get('run'):
                return ''                     # 没放行：理由已经在对话里说过了
            intent = str(plan.get('intent') or '')
            stage = plan.get('stage')
            if intent == 'goto':
                return self.goto(stage, at=at)
            if intent == 'generate':
                return self.generate(stage, at=at)
            if intent == 'skill':
                return self.run_skill(plan, at=at)
            if intent == 'export':
                return self.export_delivery(at=at)
            if intent in ('progress', 'panel', 'usage'):
                self.show_panel()
                return self.notice
            if intent == 'silence':
                self.click('snooze', at=at)
                return self.notice
            if intent == 'oneclick':
                # 用户在气泡里答过「好」的话（params.confirmed）就不再弹第二次确认窗。
                return self.one_click(at=at, confirm=not bool((plan.get('params') or {}).get('confirmed')))
            if intent in ('retry', 'skip', 'pause', 'resume', 'model', 'details'):
                self.click(intent, at=at)     # 与气泡／菜单共用同一份实现，不再各写一遍
                return self.notice
            if intent == 'level':
                target = (plan.get('params') or {}).get('level')
                if target is None:
                    return ''
                self.set_level(target, at=at)
                return self.notice
            if intent == 'projects':
                # 第 37 期第 1 条：「有哪些项目」「项目都怎么样了」——照着盘上的登记表念一遍。
                self.notice = self.projects_text(at=at)
                return self.notice
            if intent == 'report':
                _data, path = self.daily_report(at=at)
                self.notice = '日报已生成：' + (path.name if path else '（未落盘）')
                return self.notice
            if intent == 'weekly':
                path, _totals = self.weekly_report(at=at)
                self.notice = '周报已生成：' + (path.name if path else '（还没攒够数据）')
                return self.notice
            if intent == 'test':
                return self.run_test_mode(plan.get('params') or {}, at=at)
            if intent == 'performance':
                return self.run_performance_mode(at=at)
            if intent == 'performance_list':
                return self.run_performance_mode(kind='long_list', at=at)
            return ''                         # 没登记的意图不动手
        except Exception as exc:
            self.errors.append(('run_plan', str(exc)))
            # 对话已经承诺执行时，不能只在内部错误列表留下痕迹；否则云朵会显示
            # “听懂了”却没有任何完成或失败反馈。异常详情留在既有错误记录中，界面
            # 仅给出可操作的降级提示，避免把内部路径或凭据片段回显给用户。
            self.notice = '操作未完成，请稍后重试。'
            return self.notice

    def run_skill(self, plan, at=None):
        """「跑 SKILL」这条路上真的动手（第 28 期第 7 条）：读阶段配置 → 编排器跑 → 汇报。

        规格要的四件事都在这里接上：按 project.skillConfig[stage] 挑 SKILL、多个 SKILL 交给
        skill_orchestrator 分层执行、付费的并成一个气泡问一次、结果统一汇报给三虎说出去。
        """
        import skill_panel
        import skill_registry
        import skill_templates
        import stage_config
        params = plan.get('params') or {}
        stage = plan.get('stage')
        project = getattr(self.desktop, 'root', None)
        if project is None:
            self.notice = '还没打开项目——先建一个项目，我才好按 SKILL 动手。'
            self.show_progress(self.notice)
            return self.notice
        registry = skill_registry.default_registry()
        names = [str(item) for item in (params.get('skills') or [])]
        if not names and stage:
            names = [item.name for item in registry.getByStage(stage)]
        if stage:
            chosen = set(stage_config.get(project, stage, registry=registry)['skills'] or [])
            picked = [name for name in names if name in chosen]
            if not picked:
                self.notice = '「%s」这一阶段的 SKILL 都被您取消勾选了——先到阶段配置里勾上再说。' % stage
                self.show_progress(self.notice)
                return self.notice
            names = picked
        if not names:
            self.notice = '我没听出要跑哪几个 SKILL，说具体点？'
            self.show_progress(self.notice)
            return self.notice
        # 与「手动制作XX」走同一份上下文：单次（这句话里点名的模型）＞ 项目 ＞ 全局。
        context = skill_panel.stage_context(self.desktop, stage,
                                           extra={'model': str(params.get('model') or '')})
        orch = skill_panel.build_orchestrator(self.desktop, project)
        # 新项目会持有状态文件，但尚未写入 checkpoint；统一为空字典，恢复分支无需特判。
        checkpoint = ((orch.status.get('checkpoint') or {})
                      if isinstance(orch.status, dict) else {})
        resume_from = 1
        if stage and checkpoint.get('stage') == stage:
            resume_from = self._recovery_from[1] if self._recovery_from and self._recovery_from[0] == stage else 0
            if not resume_from:
                resume_from = orch.recover_from_checkpoint(
                    wait_for_user=self.recovery_choice,
                    broadcast=lambda text: self.broadcast(text, at=at, shape=pet_cloud.SHAPE_CLOUD))
            if resume_from:
                self._recovery_from = None
        # 第 54 期附件二第 6 条：手动与自动共用同一台编排器，只有 trigger 不同。
        # 这一条路是三虎自己动手，所以按「自动」记——正在跑的那一步按钮就写「自动执行中」。
        try:
            template = skill_templates.load_template(stage)
            template_answer = params.get('template_confirmation')
            wait_for_template = (lambda text: template_answer) if template_answer is not None else self.template_choice
            run = orch.run_stage_with_template(
                stage, context, names=names,
                # 「全自动」既可能从三虎模式切换进入，也可能从三虎等级菜单进入；两者都不能
                # 在模板门禁处重新弹窗。半自动仍由 template_choice 等用户确认。
                mode='auto' if (self.should_auto_run(template.process_id or stage)
                                or self.level() == 'auto') else 'manual',
                wait_for_user=wait_for_template,
                broadcast=lambda text: self.broadcast(text, at=at, shape=pet_cloud.SHAPE_CLOUD),
                start_step=resume_from or 1,
            )
        except (OSError, ValueError):
            run = orch.run(names, context, trigger='auto')
        pending = list(run.get('pending') or [])
        if pending:
            run = self.settle_paid(orch, run, pending, context)
        self.notice = str(run.get('text') or '').strip() or '这一批没跑出结果。'
        self.show_progress(self.notice)
        self.refresh(at=at)
        return self.notice

    def template_choice(self, text):
        """手动模板门禁：由用户确认生成类步骤；不可交互时保守跳过。"""
        try:
            from tkinter import simpledialog
            return str(simpledialog.askstring('确认三虎步骤', text, parent=self.win) or '').strip()
        except Exception as exc:
            self.errors.append(('template.ask', str(exc)))
            return ''

    def run_test_mode(self, params, at=None):
        """启动增量自检；真实完成由既有 pump 心跳汇报，绝不阻塞 Tk。"""
        if self._test_session is not None:
            self.notice = '增量自检正在运行，完成后会汇报结果。'
            return self.notice
        project = getattr(self.desktop, 'root', None)
        if project is None:
            self.notice = '还没打开项目，无法写入测试台账。'
            return self.notice
        try:
            self._test_session = stage_handler_registry.start(
                self.desktop, 'pet_test', trigger='manual', text=str(params.get('text') or ''))
            self.notice = '增量自检已启动，完成后汇报成功率与失败用例。'
        except Exception as exc:
            self.errors.append(('test.start', str(exc)))
            self.notice = '增量自检启动失败：' + str(exc)
        return self.notice

    def poll_test_mode(self, at=None):
        """复用 150ms pump 观察测试子进程；不创建额外线程或 Tk 定时器。"""
        if self._test_session is None:
            return ''
        try:
            result = stage_handler_registry.poll_pet_test(
                self._test_session, self.desktop.root, at=at)
            if result is None or result.get('running'):
                return ''
            self._test_session = None
            self.notice = str(result.get('text') or '')
            return self.announce(self.notice, at=at)
        except Exception as exc:
            self.errors.append(('test.poll', str(exc)))
            self._test_session = None
            self.notice = '增量自检失败：' + str(exc)
            return self.announce(self.notice, at=at)

    def run_performance_mode(self, kind='startup', at=None):
        """按用户指令启动短离线基准；只写当前项目的运行报告。"""
        if self._performance_session is not None:
            self.notice = '优化检查正在运行，完成后会汇报结果。'
            return self.notice
        project = getattr(self.desktop, 'root', None)
        if project is None:
            self.notice = '还没打开项目，无法写入优化检查台账。'
            return self.notice
        try:
            self._performance_session = stage_handler_registry.start(
                self.desktop, 'pet_performance', trigger='manual', kind=kind)
            label = '长列表优化检查' if kind == 'long_list' else '优化检查'
            self.notice = label + '已启动，完成后只汇报超过阈值的耗时退化。'
        except Exception as exc:
            self.errors.append(('performance.start', str(exc)))
            self.notice = '优化检查启动失败：' + str(exc)
        return self.notice

    def poll_performance_mode(self, at=None):
        """复用 pump 轮询短基准；不额外创建线程或 Tk 定时器。"""
        if self._performance_session is None:
            return ''
        try:
            result = stage_handler_registry.poll_pet_performance(
                self._performance_session, at=at)
            if result is None:
                return ''
            self._performance_session = None
            self.notice = str(result.get('text') or '')
            return self.announce(self.notice, at=at)
        except Exception as exc:
            self.errors.append(('performance.poll', str(exc)))
            self._performance_session = None
            self.notice = '优化检查失败：' + str(exc)
            return self.announce(self.notice, at=at)

    def recovery_choice(self, text):
        """等待用户从继续、跳过、重做中选一项；不可交互时不擅自恢复。"""
        asker = self.recovery_asker
        if callable(asker):
            try:
                return str(asker(text) or '').strip()
            except Exception as exc:
                self.errors.append(('recovery.ask', str(exc)))
                return ''
        try:
            from tkinter import simpledialog
            return str(simpledialog.askstring('恢复三虎任务', text, parent=self.win) or '').strip()
        except Exception as exc:
            self.errors.append(('recovery.ask', str(exc)))
            return ''

    def recover_project_checkpoint(self):
        """三虎启动时检查当前项目，并把用户选择留给下一次阶段执行。"""
        project = getattr(self.desktop, 'root', None)
        if project is None:
            return False
        try:
            import skill_panel
            orch = skill_panel.build_orchestrator(self.desktop, project)
            stage = (orch.status.get('checkpoint') or {}).get('stage')
            step = orch.recover_from_checkpoint(
                wait_for_user=self.recovery_choice,
                broadcast=lambda text: self.broadcast(text, shape=pet_cloud.SHAPE_CLOUD))
            if stage and step:
                self._recovery_from = (stage, step)
                return step
        except Exception as exc:
            self.errors.append(('recovery.start', str(exc)))
        return False

    def settle_paid(self, orch, run, pending, context):
        """付费 SKILL 合并确认：一个气泡问完，用户点头就接着把这几件做完。"""
        merged = '、'.join(row.get('name') or row['skill'] for row in pending)
        if any(row.get('queued') for row in pending):
            self.confirm('这几个要花钱的活先排着队（现在不打扰您）：' + merged)
            return run
        if not self.confirm_start('确认付费步骤', '这几个要花钱：%s（%s）\n\n现在做吗？'
                                  % (merged, '共 %d 件' % len(pending))):
            orch.confirm_all(False)
            return run
        orch.confirm_all(True)
        again = orch.run([row['skill'] for row in pending], context, trigger='auto')
        run['text'] = str(run.get('text') or '') + '\n' + str(again.get('text') or '')
        run['results'] = list(run.get('results') or []) + list(again.get('results') or [])
        run['failed'] = list(run.get('failed') or []) + list(again.get('failed') or [])
        return run

    def switch_model(self):
        """「切换模型」：在「自动」与池里的模型之间按顺序换一档（下一次调用生效）。

        只换三虎自己用的模型，绝不替用户切生图／视频等会产生费用的引擎——那些开关留在各页面由人来按。
        """
        cycle = [model_pool.AUTO] + list(self.agent_model_records())
        index = (cycle.index(self.tier) + 1) % len(cycle) if self.tier in cycle else 0
        return self.set_tier(cycle[index])

    def tier_config(self):
        """当前档位对应的客户端配置覆盖：池里那一条 ＋ 降级模型那一条（「自动」时是空的）。

        第 43 期起档位就是模型池里的 id：根地址／协议／密钥名／模型名一起换过去——「模型管理 →
        测试连接」说好的那一条，三虎真发请求时用的就是同一份配置。登记表里另接进来的档位
        （register_tier）仍按它自己写的那份覆盖走。
        """
        records = self.agent_model_records()
        if self.tier in records:
            patch = dict(model_pool.patch_for(self.tier, records))
            patch['force_tier'] = ''          # 换过服务商就不该再被上一档的 force_tier 拉着走
        else:
            patch = dict(TIER_MODELS.get(self.tier, TIER_MODELS['auto'])[1])
        patch['fallback'] = model_pool.patch_for(self.agent_model_tasks().get('fallback'), records)
        return patch

    def _apply_tier(self):
        """把档位写进正在用的那份客户端：换档不换会话，失败清单、通知与 Token 台账都不受影响。

        只改 force_tier 一项，其余设置原样保留（直接整份换掉会把配置文件里的设置一起丢掉）。
        """
        core = self._core
        for client in (self._client, getattr(core[2], 'client', None) if core else None):
            if client is None:
                continue
            try:
                client.config = {**(client.config or {}), **self.tier_config()}
            except Exception as exc:
                self.errors.append(('tier', str(exc)))
        return self.tier

    def tier_name(self):
        """当前档位的人话：外部接进来的档位按登记表，其余按池里的显示名（「自动」就是「自动」）。"""
        return TIER_NAMES.get(self.tier) or model_pool.label_of(self.tier, self.agent_model_records())

    def model_label(self):
        """菜单文字直接反映当前档位，不另存一份状态。"""
        return '切换模型（当前：%s）' % self.tier_name()

    def set_tier(self, tier):
        """「切换模型」点了某一条：写盘 ＋ 立刻生效（规格：配置修改后不用重启）。"""
        wanted = str(tier or '').strip()
        records = self.agent_model_records()
        external = wanted in TIER_MODELS and wanted != model_pool.AUTO and wanted not in records
        if wanted != model_pool.AUTO and wanted not in records and not external:
            return self.tier
        if external:                          # 外部接进来的档位：不写进模型池，只当场生效
            self.tier = wanted
            self._apply_tier()
            self._fill_model_menu()
            self.refresh_menu_labels()
            self.notice = '已切换到 %s' % self.tier_name()
            return self.tier
        tasks = dict(self.agent_model_tasks())
        tasks['default'] = wanted
        self.save_agent_models(tasks, notice='已切换到 %s' % model_pool.label_of(wanted, records))
        return self.tier

    def register_model(self, tier, label, override=None):
        """预留接口：把别的模型接进「切换模型」栏（登记完这一栏立刻重建，点得到）。"""
        options = register_tier(tier, label, override)
        self._fill_model_menu()
        self.refresh_menu_labels()
        self.notice = '已接入新模型：%s（「切换模型」栏里可以直接点）' % TIER_NAMES.get(tier, label)
        return options

    # ── 模型池（第 43 期：规格里的「模型管理」＋「三虎设置 → 模型」） ─────────────
    def agent_model_records(self):
        """模型池：界面上的选项与写进客户端的覆盖都从这一份读（模型管理是唯一入口）。"""
        return model_pool.pool(program=self.program)

    def agent_model_tasks(self):
        """三虎四个任务维度各用哪一条（缺项补出厂默认）。"""
        return model_pool.agent_models(program=self.program)

    def resolve_agent_model(self, task='default', context=None):
        """规格里的 resolveAgentModel：这一档实际会用哪条模型（挑不出来时说清为什么）。"""
        return model_router.resolve_agent_model(task, records=self.agent_model_records(),
                                                context=context, program=self.program)

    def apply_agent_models(self):
        """把「三虎设置 → 模型」叠进正在用的客户端，并重建「切换模型」子菜单。

        规格里「配置修改后无需重启」就落在这里：读一次盘上的设置就地换掉客户端配置
        （不换会话：失败清单、通知、Token 台账都不受影响），菜单文字与 ✓ 跟着重排。
        """
        tasks = self.agent_model_tasks()
        self.tier = str(tasks.get('default') or model_pool.AUTO)
        self._apply_tier()
        self._fill_model_menu()
        self.refresh_menu_labels()
        return self.tier

    def save_agent_models(self, tasks, notice=None):
        """写「三虎设置 → 模型」：全局配置落盘 ＋ 就地生效 ＋ 用气泡说一句。"""
        data = model_pool.with_tasks(model_pool.raw(self.program), tasks)
        self._agent_file = model_pool.store(data, self.program)
        self.apply_agent_models()
        self.notice = notice or ('已保存三虎模型设置：默认 %s' % self.tier_name())
        self.speak()
        return self.tier

    def save_pool(self, value, old_id=''):
        """模型管理里加／改一条：写盘 ＋ 重建菜单（池子变了，两处下拉立刻跟着变）。"""
        data = model_pool.raw(self.program)
        key = model_pool.model_id_of(value, old_id)
        if str(old_id or '').strip() and str(old_id).strip() != key:
            data = model_pool.remove(data, old_id)      # 改了模型 ID：旧键让位，不留两条
        data = self._prune_tasks(model_pool.upsert(data, value))
        self._agent_file = model_pool.store(data, self.program)
        self.apply_agent_models()
        self._refresh_model_choices()
        self.notice = '已保存模型「%s」' % (model_pool.record(value, key)['label'] or key)
        self.speak()
        return key

    def delete_pool_model(self, model_id):
        """模型管理里删一条：顺手把四个维度里指向它的那一项退回默认，不留死引用。"""
        data = self._prune_tasks(model_pool.remove(model_pool.raw(self.program), model_id))
        self._agent_file = model_pool.store(data, self.program)
        self.apply_agent_models()
        self._refresh_model_choices()
        self.notice = '已从模型池里删掉「%s」' % str(model_id)
        self.speak()
        return model_id

    def _refresh_model_choices(self):
        """池子变了：把还开着的「阶段配置」下拉框也刷一遍（规格：改完不用重启）。"""
        try:
            import skill_panel
            return skill_panel.refresh_all()
        except Exception as exc:
            self.errors.append(('model.refresh', str(exc)))
            return 0

    def _prune_tasks(self, data):
        """池里没有的那一条不能在四个维度里留着：退回出厂默认（默认那一栏退回「自动」）。"""
        records = model_pool.pool(data)
        tasks = model_pool.agent_models(data)
        changed = False
        for key in model_pool.TASK_KEYS:
            value = str(tasks.get(key) or '')
            if value and value != model_pool.AUTO and value not in records:
                tasks[key] = model_pool.AUTO if key == 'default' else model_pool.TASKS_DEFAULT[key]
                changed = True
        return model_pool.with_tasks(data, tasks) if changed else data

    def open_model_settings(self):
        """「三虎设置 → 模型…」：窗口交给 pet_models_ui，改完由本类落盘并立刻生效。"""
        import pet_models_ui
        return pet_models_ui.open_settings(self)

    def open_model_manager(self):
        """「模型管理…」：模型池＋API 配置的唯一入口（「+ 新增模型…」也走这里）。"""
        import pet_models_ui
        return pet_models_ui.open_manager(self)

    # ── 设置（第 44 期：左上角那颗齿轮 → 基础功能／模型配置／自动化等级／预算） ──────
    def open_settings(self, tab=None):
        """齿轮与右键「设置」都走这里：一扇窗四格；tab 给了就直接落在那一格。

        规格（用户附件第二节 ＋ 本轮要求）：三虎设置改名「设置」，四格＝基础功能、模型配置、
        自动化等级、预算；附件里的 SKILL 管理这一轮不做。
        """
        import pet_settings_ui
        return pet_settings_ui.open_hub(self, tab)

    def build_gear(self, parent=None):
        """左上角那颗齿轮（用户要的「做成齿轮外观的入口…醒目提示」）。

        真 Desktop 放进主窗口根层预留的安全位，既不会被侧栏裁掉，也不遮住标题或正文；
        没有该安全位的宿主（自检里的假桌面）仍嵌入标题行——绝不因为缺个容器就起不来。
        """
        if self.gear is not None:
            return self.gear
        holder = parent if parent is not None else getattr(self.desktop, 'settings_gear_layer', None)
        holder = holder if holder is not None else getattr(self.desktop, 'sidebar_head', None)
        holder = holder if holder is not None else self.win
        try:
            self.gear = GearButton(holder, command=lambda: self.act(self.open_settings))
            if holder is self.win:
                # 主窗口根层不受侧栏、标题行或页面画布的裁剪；它在页面控件之后创建，
                # 因而位于根层子控件的最前。
                x, y = getattr(self.desktop, 'settings_gear_position', (112, 8))
                self.gear.canvas.place(x=x, y=y, anchor='nw')
            else:
                # 无真实 Desktop 的轻量宿主仍嵌入其标题行，方便复用与无界面自检。
                self.gear.canvas.pack(side='right', padx=(0, 2))
        except Exception as exc:
            self.errors.append(('gear', str(exc)))
            self.gear = None
        return self.gear

    def pet_settings(self):
        """「设置 → 基础功能」那一页要的四件事：名字、贴片动画、免打扰窗口、开机自启。"""
        control = self.autostart()
        try:
            opened = bool(control.enabled()) if control.available else False
        except Exception as exc:
            self.errors.append(('autostart', str(exc)))
            opened = False
        return {'name': pet_agent.PET_NAME, 'anim': self.animation_enabled(),
                'dnd': self.dnd_window(), 'autostart': opened, 'ready': bool(control.available)}

    def token_settings(self):
        """「设置 → Token 节省」那八档现在的样子（没存过就是附件那组出厂值）。"""
        try:
            return token_saver.normalize(pet_agent.load_settings(program=self.program).get('token'))
        except Exception as exc:
            self.errors.append(('settings.token', str(exc)))
            return token_saver.normalize()

    def set_token_settings(self, values):
        """把这八档写进全局配置；顺手过一遍钳制（压缩阈值不许高过窗口的 90%），返回落盘那份。"""
        table = token_saver.normalize(values)
        try:
            pet_agent.save_settings({'token': table}, self.program)
        except Exception as exc:
            self.errors.append(('settings.token', str(exc)))
        return table

    def animation_enabled(self):
        """贴片动画开着吗（设置里关掉就停在那一帧）；配置读不出来＝照旧动，不因为读盘失败变木头。"""
        try:
            return bool(self.agent.settings.get('anim', True))
        except Exception as exc:
            self.errors.append(('settings.anim', str(exc)))
            return True

    def set_anim(self, value):
        """贴片动画开关：写进全局配置 ＋ 立刻生效（关掉＝三虎站着不动，省一点 CPU）。"""
        state = bool(value)
        try:
            pet_agent.save_settings({'anim': state}, self.program)
        except Exception as exc:
            self.errors.append(('settings.anim', str(exc)))
        # 立刻生效：正在用的那份 Agent 设置也换过来（不然要等下一次重启才认）。
        try:
            self.agent.settings['anim'] = state
        except Exception as exc:
            self.errors.append(('settings.anim', str(exc)))
        self.notice = '贴片动画已%s' % ('打开' if state else '关掉')
        return state

    def dnd_window(self):
        """免打扰窗口（起止两个整点）：配置里有就用配置的，读不出来退回规格定的 23:00-07:00。"""
        try:
            window = tuple(self.agent.settings.get('dnd') or pet_agent.DND)
        except Exception as exc:
            self.errors.append(('settings.dnd', str(exc)))
            return tuple(pet_agent.DND)
        return window if len(window) == 2 else tuple(pet_agent.DND)

    def set_dnd(self, start, end):
        """免打扰时段：起止各一个 0-23 的整点；写盘 ＋ 立刻作用到这一批通知上。

        首尾对得一样（23 点到 23 点）＝ 一整天都不打扰，显然不是用户想说的，退回 None 让他改。
        """
        try:
            pair = (int(start), int(end))
        except (TypeError, ValueError):
            return None
        if not all(0 <= hour <= 23 for hour in pair) or pair[0] == pair[1]:
            return None
        try:
            pet_agent.save_settings({'dnd': pair}, self.program)
        except Exception as exc:
            self.errors.append(('settings.dnd', str(exc)))
            return None
        try:
            self.agent.settings['dnd'] = pair
            self.agent.notifier.window = pair
        except Exception as exc:
            self.errors.append(('settings.dnd', str(exc)))
        self.notice = '免打扰时段已改成 %02d:00 - %02d:00' % pair
        return pair

    def set_autostart(self, value):
        """开机自启开／关到指定的样子（界面用；开不了就老实报没开，不留假状态）。"""
        control = self.autostart()
        want = bool(value)
        try:
            if not control.available:
                state = False
            elif want:
                state = bool(control.set(autostart_command(PROGRAM)) and control.enabled())
            else:
                control.clear()
                state = False
        except Exception as exc:
            self.errors.append(('autostart', str(exc)))
            state = False
        self.notice = ('开机自启已开启：下次登录会自动启动助手' if state
                       else '开机自启已关闭（或本机不支持）')
        return state

    def budget_limits(self):
        """五类配额现在的样子（进度面板与「设置 → 预算」读的是同一本账）。"""
        try:
            return dict(self.agent.budget.limits)
        except Exception as exc:
            self.errors.append(('budget', str(exc)))
            return dict(pet_agent.DEFAULT_BUDGET)

    def budget_usage(self, at=None):
        """用掉了多少：Token 先跟台账对一次表，其余读计数器。"""
        try:
            self.agent.budget.sync_tokens(getattr(self.agent.client, 'ledger', None), at)
            return self.agent.budget.snapshot()
        except Exception as exc:
            self.errors.append(('budget', str(exc)))
            return {'used': {}, 'limits': {}}

    def save_budget_limits(self, values):
        """「设置 → 预算」保存：五类一起写盘 ＋ 立刻作用到正在用的账本（越线即拦）。

        写盘落在全局配置的 budget_limits；缺项按出厂值补齐——面板那一行「x/y」两边都得有数。
        值不合法（空、零、负数、认不出的类别）一律抛 ValueError，界面把那句话照原样显示出来。
        """
        limits = {}
        for kind, raw in dict(values or {}).items():
            name = pet_agent.normalize_kind(kind)
            text = str(raw).strip()
            if not text:
                continue
            try:
                number = int(float(text))
            except (TypeError, ValueError):
                number = 0
            if number <= 0:
                raise ValueError('%s 要填一个正整数。' % pet_agent.BUDGET_NAMES.get(name, name))
            limits[name] = number
        try:
            pet_agent.save_settings({'budget_limits': limits}, self.program)
        except Exception as exc:
            self.errors.append(('settings.budget', str(exc)))
            raise ValueError('预算没写进配置：%s' % exc)
        merged = dict(pet_agent.DEFAULT_BUDGET)
        merged.update(limits)
        try:
            self.agent.budget.limits = dict(merged)
        except Exception as exc:
            self.errors.append(('budget', str(exc)))
        self.notice = '预算已保存：%s' % '、'.join(
            '%s %d' % (pet_agent.BUDGET_NAMES.get(kind, kind), merged[kind])
            for kind in pet_agent.BUDGET_KINDS if kind in merged)
        return merged

    def quit_app(self):
        """「退出程序」（第 44 期按附件放回功能栏）：先问一句再关，别让误按把活儿关掉。"""
        if not self.confirm_start('退出程序', f'要关掉{APP_NAME}吗？没跑完的活留在原地，下次开机接着来。'):
            self.notice = '已取消退出'
            return False
        close = getattr(self.desktop, 'close', None)
        if not callable(close):
            self.notice = '这扇宿主没有退出通道，请从主窗口右上角关掉程序'
            return False
        self.notice = '正在退出：先把没写完的日志收尾'
        close()
        return True

    def start_level(self):
        """开机那一档（第 67 期任务 4）：一律「只提醒」，用户上一次选的档不沿用。

        第 44 期把用户选的档写进了配置、下一次开机照它来；用户现在要的是「开机就是提示档」，
        所以这里只把这一刻的等级摁回默认那一档——配置里那把键照旧留着（他下次切档时会重写）。
        不冒云、不报错：开机那一下不打扰用户。

        这一档管**整次运行**：换项目会把内核整体重建（core 会重读盘上的设置），所以这里把档位
        记进 session_level，core 建完新 Agent 再照它设一遍——不记的话，一打开项目就把存档里
        那把旧档位读回来，「开机一律只提醒」等于没做。
        """
        self.session_level = pet_agent.DEFAULT_LEVEL
        self.mode = 'manual'
        try:
            self.agent.set_level(self.session_level)
        except Exception as exc:
            self.errors.append(('level', str(exc)))
        self.auto.armed = False
        self.auto.paused = False
        return self.level()

    def auto_variable(self, name):
        """返回三虎唯一创建的自动制作变量；页面不得自行创建或写入。"""
        if name not in AUTO_VARIABLE_NAMES:
            raise ValueError('未知自动制作变量：%s' % name)
        variable = self._auto_variables.get(name)
        if variable is None:
            if self.win is None:
                variable = _BooleanFlag(False)
            else:
                import tkinter as tk
                variable = tk.BooleanVar(master=self.win, value=False)
            self._auto_variables[name] = variable
            setattr(self, name, variable)
            # 兼容页面既有的属性读取；对象归属仍是三虎。
            setattr(self.desktop, name, variable)
        return variable

    def _set_all_auto_actions(self, enabled):
        """把项目中登记的全部自动制作开关统一设为同一个值。

        项目设置仅作持久化兼容；活动变量由三虎创建和写入，页面只读同一对象。
        """
        project = getattr(self.desktop, 'root', None)
        if project is None:
            return ()
        import project_settings
        failures = []
        for key in project_settings.DEFAULTS:
            setter = getattr(project_settings, 'set_' + key, None)
            if not callable(setter):
                failures.append(key)
                continue
            try:
                setter(project, bool(enabled))
            except (OSError, ValueError, KeyError, TypeError):
                failures.append(key)
        for name in AUTO_VARIABLE_NAMES:
            try:
                self.auto_variable(name).set(bool(enabled))
            except (AttributeError, TypeError, RuntimeError):
                failures.append(name)
        return tuple(failures)

    def enable_all_auto_actions(self):
        """全自动模式入口：打开当前项目的全部自动制作开关。"""
        return self._set_all_auto_actions(True)

    def disable_all_auto_actions(self):
        """手动模式入口：关闭当前项目的全部自动制作开关。"""
        return self._set_all_auto_actions(False)

    def set_mode(self, mode, at=None):
        """切换三虎手动／全自动模式，并统一接管页面自动制作开关。"""
        if mode not in SANHU_MODES:
            return None
        # 已有阶段在执行时，重复点“全自动”只是重复确认模式，不能重新 arm_auto()
        # 把 active 清空；否则下面的立即派发会把同一阶段再提交一次。
        keep_active = (mode == 'auto' and self.mode == 'auto' and self.auto.armed
                       and bool(self.auto.active))
        self.mode = mode
        try:
            if self.mode_var is not None:
                self.mode_var.set(mode)
        except TclError:
            # 仅允许窗口销毁竞态静默；变量类型或调用线程错误必须继续暴露。
            pass
        # 复用既有审批与自动推进链：手动＝只提醒，全自动＝全自动等级。
        if not keep_active:
            self.set_level('auto' if mode == 'auto' else 'hint', at=at)
        failed = self.enable_all_auto_actions() if mode == 'auto' else self.disable_all_auto_actions()
        label = '全自动' if mode == 'auto' else '手动'
        self.broadcast('【模式】已切换到%s模式' % label, at=at)
        self.broadcast('【模式】已%s全部自动制作开关' % ('打开' if mode == 'auto' else '关闭'), at=at)
        # 上面两句模式反馈会打开三虎气泡；若只等 tune_advance，气泡可见这一项
        # 门禁又会把刚武装的链路挡住，表现为用户切到全自动却没有任何制作开始。
        # 因此切换成功时立刻派发第一项；之后仍由正常心跳推进后续阶段。
        if mode == 'auto' and not keep_active and self.auto.armed and not self.auto.paused:
            try:
                stage = self.auto_stage()
                if stage:
                    started = self.start_stage(stage, at=at)
                    if started:
                        self.notice = started
            except Exception as exc:
                self.errors.append(('mode.start', str(exc)))
        if failed:
            self.broadcast('【警告】未能同步自动制作开关：' + '、'.join(failed), at=at)
        self.refresh_menu_labels()
        return self.mode

    def set_paw_level(self, level, at=None):
        """猫爪是唯一自动化入口：全自动同步开启，其他两档回到手动控制面。"""
        if level not in PAW_LEVELS:
            return None
        self.set_mode('auto' if level == 'auto' else 'manual', at=at)
        return self.set_level(level, at=at)

    def should_auto_run(self, stage_id):
        """按阶段 ID 读取三虎变量；全自动以外一律不自动执行。"""
        if self.mode != 'auto':
            return False
        try:
            name = AUTO_STAGE_VARIABLES.get(str(stage_id or '').strip())
            return bool(name and self.auto_variable(name).get())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False

    def set_level(self, level, at=None):
        """直接切到某一档自动化等级：切完必须把「现在是哪一档」说出来。

        第 19 期：猫爪按钮与右键菜单都走这里，提醒改用圆形气泡，猫爪的填色与头像颜色都立刻跟着变。
        """
        if level not in pet_agent.LEVELS:
            return None
        self.session_level = level         # 第 67 期任务 4：这一次运行照用户刚选的这一档
        try:
            self.agent.set_level(level)
        except Exception as exc:
            self.errors.append(('level', str(exc)))
            return None
        # 第 44 期：用户选的档写进全局配置——下一次开机照他选的这一档来，不再每次都退回出厂那档。
        try:
            pet_agent.save_settings({'level': level}, self.program)
        except Exception as exc:
            self.errors.append(('settings.level', str(exc)))
        # 第 67 期任务 5：切到半自动／全自动就按项目现状把那条链武装起来——剧本早就做完的
        # 项目里，script.completed 那条事件不会再来，不补这一下自动档会一直什么都不开始。
        if level in stage_flow.AUTO_LEVELS:
            try:
                if self.arm_auto():
                    # 切到自动档是明确的「现在开始」操作，不能被上一轮心跳留下的
                    # 推进节流挡住；下一个 UI 心跳应立即派发当前待办阶段。
                    self._advance_at = None
            except Exception as exc:
                self.errors.append(('level.arm', str(exc)))
        else:
            self.auto.armed = False        # 退回只提醒档：那条链立刻停手，一个阶段都不再开
        self.draw_paws(level)              # 猫爪按钮的填色＝当前档（不等下一帧）
        self.draw()                        # 头像颜色＝等级：这一下要立刻变色，不等下一帧
        text = LEVEL_SWITCH_NOTES.get(level, '已切换自动化等级')
        self.notice = text
        return self.whisper(text, at=at) or self.agent.level
    def details_text(self):
        """待确认详情（纯文本）：一条一段，阶段 · 类目 · 原因 · 建议；没有就说明一句。"""
        try:
            failures = [item for item in self.agent.failures if isinstance(item, dict)]
        except Exception as exc:
            self.errors.append(('details', str(exc)))
            failures = []
        if not failures:
            return '现在没有待确认的项。'
        lines = ['待确认 %d 项：' % len(failures)]
        for index, item in enumerate(failures, 1):
            stage = str(item.get('stage') or '')
            category = str(item.get('category') or '')
            lines.append('%d. %s · %s' % (index, pet_bus.STAGE_NAMES.get(stage, stage or '某阶段'),
                                          pet_agent.CATEGORY_NAMES.get(category, category or '未分类')))
            for prefix, key in (('原因', 'error'), ('建议', 'hint')):
                value = ' '.join(str(item.get(key) or '').split())
                if value:
                    lines.append('   %s：%s' % (prefix, value))
        return '\n'.join(lines)

    def show_details(self):
        """「待确认项」：直接在三虎旁的提示框展示，不创建只读弹窗。"""
        text = self.details_text()
        self.notice = text
        self.progress_bubble(text=text)
        return text

    def tap_safe(self, intent, at=None):
        try:
            return self.click(intent, at=at)
        except Exception as exc:
            self.errors.append(('click', str(exc)))
            return None

    def act(self, action, at=None, speak=True):
        """右键菜单的统一出口：先把事做完，再把结果说给用户听。

        action 是动作 id（走 click，与气泡按钮同一批实现），也可以是菜单里的原方法。
        需要直接展示完整提示框的菜单项可传 speak=False，避免把多行内容再次压成一行播报。
        """
        if callable(action):
            self.note_work(at=at)          # 第 60 期第 1 条：这一路不经过 click，在这儿补记一笔
            try:
                result = action()
            except Exception as exc:
                self.errors.append(('act', str(exc)))
                result = None
        else:
            result = self.tap_safe(action, at=at)
        if not speak or (isinstance(action, str) and action in ('chat',)):
            return result
        self.speak(at=at)
        return result

    def speak(self, at=None):
        """把 self.notice 说给用户听：冒一朵云（第 22 期起只剩这一条出口）。

        菜单项只写 notice 的话，没有任何一处真的说出来就等于没提示——这正是「点了没反应」的来源；
        notice 为空时退回当前进度摘要，动作出错也必须让用户看见一点反应。
        """
        return self.broadcast(self.notice or self.progress_line(at=at), at=at)

    def collect_events(self):
        """菜单项「收集事件」：手动抽一次总线，并把抽到几条说出来。

        第 36 期第 5 条：抽到事件＝这一刻还有制作动静，记下钟点——三虎靠它判「工作强度」，
        隔久了没动静才把日报／周报递上来。
        """
        count = self.pump()
        if count:
            try:
                self._work_at = float(self.clock())
            except (TypeError, ValueError):
                self._work_at = None
            # 第 49 期第 3 条：一个事件都没抽到时就一个字都不写——原来那句「已收集 0 个事件」
            # 什么也没说，却会跟着播报那一路漏进云朵框里，正是用户点名的「无用内容」。
            self.notice = '已收集 %d 个事件' % count
        return count

    def seen_recently(self, key, at=None, mine=None):
        """这件事刚由**另一条入口**说过吗（第 57 期第 2 条）。

        mine 是「我自己是哪条入口」（'broadcast'／'bubble'）：同一句进度由我自己按固定频率
        再说一遍是本来的设计（文字真变了照样要说，见 _progress_said），只有另一条入口刚说过
        的那一次让路——那才是用户看到的「同一句话冒两遍」。

        钟点拿不到（注入的坏时钟）时当作「没说过」：宁可多说一句，也不能把该说的话吞掉。
        """
        if key is None:
            return False
        try:
            now = float(self.clock() if at is None else at)
            last = self._spoken.get(key)
            if last is None:
                return False
            when, who = last
            if mine is not None and who == mine:
                return False
            return (now - float(when)) < SPEAK_GAP_SECONDS
        except (TypeError, ValueError):
            return False

    def mark_spoken(self, key, at=None, mine='pet'):
        """记下「这件事刚说过」：另一条入口在 SPEAK_GAP_SECONDS 之内不再说第二遍。"""
        if key is None:
            return None
        try:
            now = float(self.clock() if at is None else at)
        except (TypeError, ValueError):
            return None
        self._spoken[key] = (now, str(mine or 'pet'))
        while len(self._spoken) > SPOKEN_KEEP:
            self._spoken.pop(next(iter(self._spoken)))
        return now

    def panel_quiet(self, at=None):
        """用户刚自己打开过进度面板吗（第 24 期第 10 条）。

        他自己正在看明细，这时候再弹一个气泡就是打扰——所以从打开那一刻起，按固定频率等着
        的那一次也跳过（见 progress_voice）。拿不到时钟时当作没这道闸。
        """
        if self._panel_at is None:
            return False
        try:
            now = float(self.clock() if at is None else at)
            return (now - float(self._panel_at)) < PROGRESS_SECONDS
        except (TypeError, ValueError):
            return False

    def note_panel(self, at=None):
        """记下「用户自己按开了进度面板」这一笔（第 24 期第 10 条）。"""
        try:
            self._panel_at = float(self.clock() if at is None else at)
        except (TypeError, ValueError):
            self._panel_at = None
        return self._panel_at

    def progress_voice(self, state=None, at=None, force=False):
        """进度圆气泡（第 19 期：原来那块面板改成圆形气泡，什么时候冒由三虎自己判断）。

        第 49 期第 3 条按用户要求收紧两处：
        ① 频率再放一档（PROGRESS_SECONDS 240 → 600 秒）：隔到点了才说；
        ② 这一拍算出来的这一条若与上一条一字不差，就是白说一次——「暂时没有在跑的
           制作任务」这类一样的话反复顶出来，正是用户点名的「无用内容」，直接咽下去。
        用户自己打开着进度面板时一口都不冒：这一次跳过，间隔从他看完起重新算。
        原来这一路还顺手抽一次总线「收事件」：可它本来就长在心跳尾巴上（pump → progress_voice），再抽
        就绕回心跳，一路递归到 RecursionError（第 49 期实测到的）。抽事件归心跳与菜单，这一句只管说话。
        """
        try:
            now = float(self.clock() if at is None else at)
            if self.quiet(at=at):
                return ''                  # 第 68 期任务 11：招呼刚说完，进度气泡先不冒
            if self._menu_open or self.modal_grabbed():
                return ''                      # 第 59 期第 8 条：栏／弹窗抽着指针：这一拍不冒气泡
            if self.cloud_visible() or self.muted(at=at):
                return ''                      # 第 21 期：任何对话框露着就都不再开新的（「只能有一个」）
            if not self.attending():
                return ''                      # 用户在别的应用里：进度气泡也不冒（第 30 期第 3 条）
            if self.panel_quiet(at=now):
                self._progress_at = now        # 用户自己看着明细：跳过这一次，重新计时
                return ''
            state = state if state else self.snapshot(at=at)
            if not force:
                if self._progress_at is None:
                    self._progress_at = now    # 第一次心跳只对表：间隔从这一刻起算
                    self._progress_stage = str((state or {}).get('stage') or '')
                    return ''
                if (now - self._progress_at) < PROGRESS_SECONDS:
                    return ''
            text = self.progress_text(state=state, at=at)
            if text == self._progress_said:
                return ''                      # 与上一条一模一样：没什么新东西可说，不打扰
            # 第 57 期第 2 条：这一句刚由心跳播报说过（两条入口说的是同一件事）就不再从
            # 圆气泡里说第二遍。这一拍不算数：_progress_at 不动，等那一句过了窗口再轮到它。
            if self.seen_recently(('progress', self.progress_line(state=state)), at=now, mine='bubble'):
                return ''
            self._progress_at = now
            self._progress_stage = str((state or {}).get('stage') or '')
            self._progress_said = text
            self.mark_spoken(('progress', self.progress_line(state=state)), at=now, mine='bubble')
            self.mark_spoken(('gaps', tuple(self.gaps(at=at))), at=now, mine='bubble')
            return self.progress_bubble(text=text, state=state, at=at)
        except Exception as exc:
            self.errors.append(('progress.voice', str(exc)))
            return ''

    def offer_text(self, parts):
        """主动问的那一句（含选择项）：一眼看清盘上还差什么、我打算怎么做、怎么回我。"""
        return ('%s：盘上还有 %s。要不要我按「一键执行」把不花钱的这几件一次做完？'
                '（回「好」就开工，「先不用」就先放着；会花钱的步骤仍然只由您按）'
                % (pet_agent.PET_NAME, '；'.join(parts)))

    def offer_parts(self, at=None):
        """这会儿值不值得问一句：盘上的缺口 ＋ 还没确认的失败项，凑成一句句人话。"""
        parts = list(self.gaps(at=at))
        try:
            count = len(self.agent.failures)
        except Exception as exc:
            self.errors.append(('offer.failures', str(exc)))
            count = 0
        if count:
            parts.append('还有 %d 项待确认要收尾' % count)
        return parts

    def offer_oneclick(self, state=None, at=None):
        """按制作进度挑时机问一句「要不要一键自动执行」，并把选择项摆给用户（第 25 期第 3 条）。

        什么时候问：盘上真有缺口（或有待确认的失败项）＋ 没有在跑的阶段 ＋ 不忙不暂停不静默 ＋
        这会儿没有别的对话框露着。问的节流见 OFFER_SECONDS／OFFER_REPEAT，第一拍只对表
        （与播报同一套规矩：开机那一下不许冒东西）。用户答什么由 answer_offer 认。
        返回这次说出口的那句话；没说就返回空串。
        """
        try:
            now = float(self.clock() if at is None else at)
            if self.quiet(at=at):
                return ''                  # 第 68 期任务 11：招呼刚说完，先不问「要不要一键执行」
            parts = self.offer_parts(at=at)
            signature = tuple(parts)
            if self._offer_at is None:
                self._offer_at = now           # 第一拍只对表：间隔从这一刻起算
                self._offer_sig = signature
                return ''
            if not signature:
                self._offer_open = False
                return ''
            if self.cloud_visible() or self.muted(at=at) or self.snoozing() or self.agent.paused:
                return ''
            if not self.attending():
                return ''                      # 用户在别的应用里：不主动问（第 30 期第 3 条）
            state = state if state else self.snapshot(at=at)
            if self.busy(state=state):
                return ''
            waited = now - self._offer_at
            if waited < OFFER_SECONDS:
                return ''
            if signature == self._offer_sig and waited < OFFER_REPEAT:
                return ''
            self._offer_at = now
            self._offer_sig = signature
            self._offer_open = True
            # 第 26 期第 5 条：这是一句「要不要办」的询问，用绿色对话框（长句子也放得下）
            return self.broadcast(self.offer_text(parts), at=at, shape=pet_cloud.SHAPE_CLOUD)
        except Exception as exc:
            self.errors.append(('offer', str(exc)))
            return ''

    def answer_offer(self, text):
        """认下用户对那个问题的回答（第 25 期第 3 条）：还在问就当场给结论。

        只在这个问题挂着的时候认，而且只认几个明确的说法——「好」「1」这种短句在别的场合都是
        没头没尾的，不能一律当成「开工」。认出来了就回一份与 Agent.dispatch 同形状的结论
        （动手照旧交给界面线程的 run_plan）；没认出来返回 None，这句话照常走规则表。
        已经在气泡里点过头了，一键执行就不再弹第二次确认（见 one_click 的 confirm 参数）。
        """
        if not self._offer_open:
            return None
        word = ' '.join(str(text or '').split()).strip(' 。．，,!！?？~')
        if word in OFFER_YES:
            self._offer_open = False
            return {'reply': '好，这就一键执行。',
                    'plan': {'intent': 'oneclick', 'params': {'confirmed': True}},
                    'decision': {'run': True, 'reason': ''}}
        if word in OFFER_NO:
            self._offer_open = False
            self._offer_at = None              # 用户说了先放着：下一次进度一动就见得着再问
            return {'reply': '好，那先不动手；想收尾的时候说一句「一键执行」就行。',
                    'plan': {}, 'decision': {'run': False, 'reason': ''}}
        return None

    def progress_text(self, state=None, at=None, count=0):
        """进度气泡的正文（第 21 期瘦身）：一行进度 ＋ 一行「还要多久」＋ 缺口，一段一行。

        原来把面板上那十行整块搬了进来、段间还空一行，圆里塞不下又挤成一坨（用户报「过大、
        排版乱、没有序号」）。圆气泡是「一眼看个大概」，明细留在状态栏与「查看详情」里。
        """
        state = state if state else self.snapshot(at=at)
        rows = dict(self.rows(state=state, at=at))
        lines = [self.progress_line(state=state)]
        left = str(rows.get('预计剩余') or '')
        if left and left != '信息不足':
            # 第 49 期第 3 条：算不出剩余时间时那一行写的是「信息不足」——它什么也没说，去掉。
            lines.append('预计剩余 ' + left)
        stage = str(rows.get('当前阶段') or '')
        if stage:
            lines.append('当前阶段 ' + stage)      # 第 22 期：明细回到气泡里（整份在进度面板）
        lines += list(self.gaps(at=at))[:PROGRESS_GAPS]
        return '\n'.join(row for row in lines if str(row).strip())

    def progress_bubble(self, text=None, state=None, count=0, at=None):
        """把进度写成圆形气泡冒出来：也是「查看详情」没有窗口时的退路。"""
        text = text if text is not None else self.progress_text(state=state, count=count, at=at)
        text = str(text or '').strip()
        cloud = self.cloud()
        if cloud is None or not text:
            return ''
        try:
            cloud.progress(self._record_output(text))
        except Exception as exc:
            self.errors.append(('progress.bubble', str(exc)))
            return ''
        self.notice = text
        return text

    def one_click(self, at=None, confirm=True):
        """一键执行：把今天该收的尾一次做完——有失败项先重试，缺口交本地引擎补，再出一份当日日报。

        只做三件不花钱的事：重试记账、本地 ComfyUI 补首帧、日报落盘。凡是会产生费用的
        （Seedream 首帧、云端视频、配音），一律留给用户在各页面自己按，这里绝不代按。
        confirm=False 是给「用户已经在气泡里答了好」那条路用的（第 25 期第 3 条）：不再弹第二次。
        返回写进 self.notice 的那句话，出错也照样给一句话。
        """
        if confirm and not self.confirm_start():
            self.notice = '一键执行已取消：您按了「否」，这次什么都没做'
            self.show_progress(self.notice)
            self.refresh(at=at)
            return self.notice
        steps = []
        self.show_progress('一键执行中：重试失败项 → 本地补首帧 → 日报（进度就写在这里）')
        try:
            if self.agent.failures:
                self.retry_failures()
                steps.append('已重试失败项')
        except Exception as exc:
            self.errors.append(('one_click.retry', str(exc)))
        try:
            batch = self.firstframe_batch()
            if batch:
                steps.append(batch)
        except Exception as exc:
            self.errors.append(('one_click.firstframe', str(exc)))
        try:
            _data, path = self.daily_report(at=at)
            steps.append('日报已生成 ' + (path.name if path else '（未落盘）'))
        except Exception as exc:
            self.errors.append(('one_click.report', str(exc)))
        try:
            counts = self.counts()
            missing = int(counts['shots']) - int(counts['frames'])
            if missing > 0:
                steps.append('首帧还差 %d 个镜头' % missing)
        except Exception as exc:
            self.errors.append(('one_click.counts', str(exc)))
        self.notice = '一键执行：' + ('；'.join(steps) if steps else '没有可以自动收尾的事')
        self.show_progress(self.notice)
        self.refresh(at=at)
        return self.notice

    def storyboard_batch(self):
        """分镜缺口接进自动链路（第 62 期任务 2）：把「手动制作分镜」那条准备链交给宿主真的跑一遍。

        与 firstframe_batch 同一套：真正的派发在宿主（Desktop.pet_storyboard_batch）里做——
        那里才知道当前勾了哪些剧本／分镜、有没有正在跑的 Agent。宠物只负责把这件事说出来。
        宿主要么返回一句中文结果，要么返回空串（没有要做的分镜）。
        """
        dispatch = getattr(self.desktop, 'pet_storyboard_batch', None)
        if not callable(dispatch):
            return ''
        try:
            # 宿主需要知道这是自动链的派发：没有输入、或所有输入均已采用时，
            # 它才能给 active 的 storyboard 一个确定的终态事件。保留无参数
            # 接缝兼容，避免旧版宿主／自检替身被这次参数扩展打断。
            try:return str(dispatch(trigger='auto') or '')
            except TypeError:return str(dispatch() or '')
        except Exception as exc:
            self.errors.append(('storyboard', str(exc)))
            return '分镜批次未派发：' + str(exc)

    def script_structure_batch(self):
        """把剧本结构阶段交给宿主执行，避免自动链停在没有轮询的确定性步骤。"""
        dispatch = getattr(self.desktop, 'pet_script_structure_batch', None)
        if not callable(dispatch):
            return ''
        try:
            return str(dispatch() or '')
        except Exception as exc:
            self.errors.append(('script_structure', str(exc)))
            return '剧本结构未派发：' + str(exc)

    def firstframe_batch(self, trigger='manual'):
        """首帧缺口接进自动链路：本地 ComfyUI 就绪时，按分镜顺序补一批缺首帧的镜头。

        真正的派发在宿主（Desktop.pet_frame_batch）里做——那里才知道当前分镜、批次忙不忙、
        本地引擎配没配好。宠物只负责「把缺口这件事说出来」，一个按钮都不替用户按；
        宿主要么返回一句中文结果，要么返回空串（没有缺口／没有项目）。
        """
        dispatch = getattr(self.desktop, 'pet_frame_batch', None)
        if not callable(dispatch):
            return ''
        try:
            # 自动链已经先把 keyframe 标成 active。将触发来源传给宿主，才能把
            # 「无分镜／没有缺口／暂时无法派发」收成明确阶段事件；无参数接缝仍兼容。
            try:return str(dispatch(trigger=trigger) or '')
            except TypeError:return str(dispatch() or '')
        except Exception as exc:
            self.errors.append(('firstframe', str(exc)))
            return '首帧批次未派发：' + str(exc)


    # ── 文字：气泡与面板 ────────────────────────────────────────────────────
    def text(self, state=None, at=None):
        """气泡文字：进度摘要 + 最近通知 + 状态栏原文 + 待确认条数（都来自状态机与台账）。"""
        agent = self.agent
        state = state if state else self.snapshot(at=at)
        if not state:
            return '进度暂时读不出来'
        lines = [state['summary']]
        if self.notice:
            lines.append(self.notice)
        if self.last_status and self.last_status != state['summary']:
            lines.append(self.last_status)
        failures = agent.failures
        if failures:
            shown = '、'.join(str(item['stage']) + '（' + str(item['category']) + '）' for item in failures[:3])
            lines.append('待确认 ' + str(len(failures)) + ' 项：' + shown)
        lines.append(CHAT_HINT)          # 对话窗是第 13 期的交互入口，气泡里得让人看得见
        return '\n'.join(lines)

    def rows(self, state=None, at=None):
        """进度面板的每一行：数字全部来自状态机与台账，不编。"""
        agent = self.agent
        state = state if state else self.snapshot(at=at)
        snap = agent.budget.snapshot()
        used, limits = snap['used'], snap['limits']
        name = pet_agent.LEVEL_NAMES.get(state['level'], state['level'])
        return [('当前阶段', state['stage_name'] or '已完成'),
                ('进度', '%.1f%%' % state['percent']),
                # 第 22 期：用户要的「提示详细进度信息」——状态栏那句话与最近一条提示也摆进来，
                # 面板一打开就知道「现在在做什么、上一次三虎说了什么」。
                ('当前状态', str(self.last_status or '空闲')),
                ('最近提示', str(self.notice or '暂无')),
                ('预计剩余', duration(state['eta_seconds'])),
                ('阶段停留', self.dwell_text()),
                ('平均单镜耗时', self.per_unit_text()),
                ('失败待确认', str(len(agent.failures))),
                ('缓存命中率', '%.0f%%' % (100 * state['hit_rate'])),
                ('Flash 占比', '%.0f%%' % (100 * state['flash_share'])),
                ('当日 Token', '%d / %d' % (state['tokens_today'], limits.get('tokens', 0))),
                ('配额', '生图 %d/%d · 首帧 %d/%d · 视频 %d/%d · 配音 %d/%d'
                 % (used.get('image', 0), limits.get('image', 0), used.get('firstframe', 0),
                    limits.get('firstframe', 0), used.get('video', 0), limits.get('video', 0),
                    used.get('voice', 0), limits.get('voice', 0))),
                ('自动化等级', name + ('（已暂停）' if state['paused'] else ''))]

    def timings(self):
        """阶段停留、产出单位与平均单位耗时：全部来自状态机，没有产出单位的阶段不编。"""
        try:
            machine = self.machine
            if machine is None:
                return {}
            return {'stages': machine.dwell(),
                    'units': {stage: machine.units_of(stage) for stage in pet_bus.STAGES},
                    'rates': machine.per_unit_all()}
        except Exception as exc:
            self.errors.append(('timings', str(exc)))
            return {}

    def dwell_text(self):
        """面板一行：停留最久的那个阶段；还没有停留数据就写「信息不足」。"""
        try:
            rows = self.machine.slowest(1) if self.machine is not None else []
        except Exception as exc:
            self.errors.append(('dwell', str(exc)))
            rows = []
        if not rows:
            return '信息不足'
        stage, seconds = rows[0]
        return '%s %s' % (pet_bus.STAGE_NAMES.get(stage, stage), duration(seconds))

    def per_unit_text(self):
        """面板一行：平均每个产出单位的耗时；没有产出单位就写「信息不足」。"""
        try:
            rates = self.machine.per_unit_all() if self.machine is not None else {}
        except Exception as exc:
            self.errors.append(('per_unit', str(exc)))
            rates = {}
        if not rates:
            return '信息不足'
        stage = 'keyframe' if rates.get('keyframe') else sorted(rates, key=pet_bus.STAGES.index)[0]
        return '%s %s%s' % (pet_bus.STAGE_NAMES.get(stage, stage), duration(rates[stage]),
                            pet_report.RATE_UNITS.get(stage, '/单位'))

    # ── 日报、周报与独立窗（第 6 期） ───────────────────────────────────────
    def stages(self):
        """阶段状态表：日报要的「每个阶段什么状态」；读不出来就给空表，不编数字。"""
        try:
            return dict(getattr(self.machine, 'stages', None) or {})
        except Exception as exc:
            self.errors.append(('stages', str(exc)))
            return {}

    def token_budget(self):
        """当日 Token 配额：取预算五类里的 tokens 一项；读不出来写 0。"""
        try:
            return int(self.agent.budget.snapshot().get('limits', {}).get('tokens', 0) or 0)
        except Exception:
            return 0

    def counts(self):
        """日报的真实计数：剧本／分镜／镜头／首帧／资产都从盘上数，读不出来的项写 0，绝不编。"""
        result = {key: 0 for key in pet_report.COUNT_KEYS}
        project = self.agent.project
        if project is None:
            return result
        try:
            from stage_execution_service import storyboard_catalog as catalog
            result['scripts'] = len(catalog(project, 'script'))
            entries = catalog(project, 'storyboard')
            result['storyboards'] = len(entries)
            result['shots'], result['frames'] = shot_stats([entry['path'] for entry in entries])
        except Exception as exc:
            self.errors.append(('counts.storyboard', str(exc)))
        try:
            import storyboard_selection
            result['adopted'] = len(storyboard_selection.adopted(project))
        except Exception as exc:
            self.errors.append(('counts.adopted', str(exc)))
        try:
            result['assets'], result['ready_assets'] = asset_counts(self.desktop.asset_base())
        except Exception as exc:
            self.errors.append(('counts.assets', str(exc)))
        return result

    # ── 播报与缺口（第 14 期：说得更勤，也把「还没做的那一步」说出来） ──────
    def gaps(self, at=None, force=False):
        """盘上的缺口：还没采用的分镜 JSON、还没生成首帧的镜头。

        读盘很贵（要解析每一份分镜 JSON），所以结果按 GAP_SECONDS 缓存，心跳里只读缓存。
        """
        now = float(self.clock() if at is None else at)
        if force or self._gap_at is None or (now - self._gap_at) >= GAP_SECONDS:
            self._gap_at = now
            try:
                self._gap_cache = self._gap_parts(self.counts())
            except Exception as exc:
                self.errors.append(('gaps', str(exc)))
                self._gap_cache = []
        return list(self._gap_cache)

    def _gap_parts(self, counts):
        """缺口 → 一句句人话（带上该点哪里），没有缺口就是空表。"""
        counts = counts or {}
        parts = []
        try:
            waiting = int(counts.get('storyboards', 0)) - int(counts.get('adopted', 0))
            if waiting > 0:
                parts.append('%d 份分镜 JSON 还没采用（%s → 手动采用分镜）' % (waiting, pet_bus.stage_label('storyboard')))
            missing = int(counts.get('shots', 0)) - int(counts.get('frames', 0))
            if missing > 0:
                parts.append('首帧还差 %d 个镜头（%s → 手动制作首帧）' % (missing, pet_bus.stage_label('keyframe')))
        except (TypeError, ValueError) as exc:
            self.errors.append(('gaps.parts', str(exc)))
        return parts

    def busy(self, state=None):
        """现在有没有阶段真的在跑：状态机说 running／retrying 才算。

        快照里的 stage 是「下一步做什么」，闲着也永远有值（第一个没完成的阶段），
        拿它当忙闲判据会让宠物一直按忙时的频率播报——第 14 期踩过这个坑。
        """
        try:
            stage = (state or self.snapshot() or {}).get("stage")
            states = self.machine.stages if self.machine is not None else {}
            return str((states.get(stage) or {}).get("state") or "") in ("running", "retrying")
        except Exception as exc:
            self.errors.append(("busy", str(exc)))
            return False

    def progress_line(self, state=None, at=None):
        """一句进度：忙时报阶段与百分比，闲时明说「没有在跑的任务」。"""
        state = state if state else self.snapshot(at=at)
        state = state or {}
        name = str(state.get('stage_name') or state.get('stage') or '').strip()
        try:
            percent = float(state.get('percent') or 0.0)
        except (TypeError, ValueError):
            percent = 0.0
        if not name:
            return '暂时没有在跑的制作任务'
        return '%s %.0f%%' % (name, percent)

    def tick_broadcast(self, at=None):
        """心跳里的播报：忙时 40 秒、闲时 180 秒说一次；缺口一变化立刻说。返回这次说的话。"""
        try:
            if self.cloud_visible(sticker_only=True) or self.muted(at=at):
                return ''                  # 贴纸正露着或用户刚点掉云朵：这一次不说
            if not self.attending():
                return ''                  # 用户切到别的应用上去了：这一拍不冒泡（第 30 期第 3 条）
            now = float(self.clock() if at is None else at)
            if self.quiet(at=at):
                return ''                  # 第 68 期任务 11：招呼刚说完，进度播报先留到安静期之后再慢慢说
            # 第 22 期：第一次心跳只对表（连缺口指纹一起记下）——原来第一次就把「缺口刚出现」
            # 当成急事播报出去，开机那一下云朵框会短暂冒一下（用户报的就是这个）。
            if self._broadcast_at is None:
                self._broadcast_at = now
                self._gap_sig = tuple(self.gaps(at=at))
                return ''
            parts = self.gaps(at=at)
            signature = tuple(parts)
            fresh = signature != self._gap_sig
            self._gap_sig = signature
            state = self.snapshot(at=at) or {}
            span = BROADCAST_BUSY if self.busy(state=state) else BROADCAST_IDLE
            due = (now - self._broadcast_at) >= span
            urgent = bool(parts) and fresh
            if not (urgent or due):
                return ''
            line = self.progress_line(state=state)
            # 第 57 期第 2 条：这一句（或这几条缺口）刚由进度圆气泡说过就不再从播报里
            # 重复一遍；急事（缺口真变了）照旧立刻说——那是新消息，不算重复。
            if not urgent and (self.seen_recently(('progress', line), at=now, mine='broadcast')
                              or self.seen_recently(('gaps', signature), at=now, mine='broadcast')):
                return ''
            self._broadcast_at = now
            news = list(parts)
            if not news:
                # 第 24 期第 5 条：状态栏那一句（＝用户／链路正在做的那一步）不再搬进云朵记录；
                # 三虎的播报（notice）里若也是清一色的操作步骤，同样不进记录。
                news = [line, '' if self._notice_step else str(self.notice or '')]
            self.mark_spoken(('progress', line), at=now, mine='broadcast')
            self.mark_spoken(('gaps', signature), at=now, mine='broadcast')
            return self.broadcast('；'.join(piece for piece in news if piece), at=at)
        except Exception as exc:
            self.errors.append(('broadcast.tick', str(exc)))
            return ''
    def inputs(self):
        """日报／周报的入参：进度、台账、失败项、通知、配额、阶段状态、真实计数。"""
        try:
            agent = self.agent
            return {'progress': self.snapshot(), 'ledger': getattr(agent.client, 'ledger', None),
                    'failures': list(agent.failures), 'notices': agent.notifier.snapshot(),
                    'budget': self.token_budget(), 'stages': self.stages(), 'counts': self.counts(),
                    'timings': self.timings()}
        except Exception as exc:
            self.errors.append(('inputs', str(exc)))
            return {}

    def report(self, at=None):
        """日报数据（只算不落盘）：命中率、Flash 占比、Token 全来自台账；出错返回 None。"""
        try:
            return pet_report.gather(project=self.agent.project, at=at, **self.inputs())
        except Exception as exc:
            self.errors.append(('report', str(exc)))
            return None

    def daily_report(self, at=None):
        """生成今日日报并落盘（同日重跑覆盖同一份）；返回（数据，路径），出错返回（None，None）。"""
        try:
            project = self.agent.project
            if project is None:
                return None, None
            data, path = pet_report.daily(project, at=at, **self.inputs())
            self.report_path = path
            self.notice = '今日日报已生成：' + (path.name if path else '（未落盘）')
            return data, path
        except Exception as exc:
            self.errors.append(('daily_report', str(exc)))
            return None, None

    def weekly_report(self, at=None):
        """生成本周周报（读日报汇总重算命中率）；返回（路径，汇总），出错返回（None，None）。"""
        try:
            project = self.agent.project
            if project is None:
                return None, None
            path, totals = pet_report.write_weekly(project, at=at)
            self.weekly_path = path
            self.notice = '本周周报已生成：' + (path.name if path else '（未落盘）')
            return path, totals
        except Exception as exc:
            self.errors.append(('weekly_report', str(exc)))
            return None, None

    # ── 云朵框（第 14 期：贴片旁边的思考框，既播报也能对话） ────────────────
    def cloud(self):
        """云朵框实例：只建一次（记录留得住），建不出来返回 None，绝不抛。"""
        if self._cloud is None:
            try:
                self._cloud = pet_cloud.Cloud(self, self.win)
            except Exception as exc:
                self.errors.append(('cloud', str(exc)))
                self._cloud = None
        return self._cloud

    def window_visible(self):
        """主窗口现在看得见吗：常驻／最小化时看不见，云朵框也就无处可显。"""
        try:
            # Windows 上图标化窗口的 winfo_viewable() 仍可能为真；若只看它，
            # 点击三虎时不会走 show_main()，主界面便会一直留在任务栏。
            state = str(self.win.state()).lower()
            return state not in ('iconic', 'withdrawn') and bool(self.win.winfo_viewable())
        except Exception:
            return False

    def attending(self):
        """用户这会儿在看着我们吗（第 30 期第 3 条）：切去别的应用时，自动播报一律不冒。

        只拦「三虎自己冒出来」的那几路（心跳播报、进度气泡、主动询问、失败提醒），用户自己
        点出来的对话框一条都不拦——那些本来就是他当下要的。front 可注入：None＝不设这道闸
        （自检与假宿主走这条路），真机上由 attach(front=our_process_in_front) 挂上来。
        """
        front = self.front
        if front is None:
            return True
        try:
            return bool(front())
        except Exception as exc:
            self.errors.append(('front', str(exc)))
            return True

    def watch_focus(self, at=None):
        """用户人在不在助手界面（第 35 期第 1 条）：切出去就把自动执行暂停，回来再接着跑。

        第 30 期第 3 条的做法是「切到别的应用就不弹框」——每一路自动播报（心跳、进度气泡、
        主动询问、失败提醒）各自闭嘴。可三虎看起来还在跑，只是什么都不说，用户看不出它已经
        停了。现在把这件事集中在这里判一次：离开助手界面满 AWAY_PAUSE_SECONDS 就把自动执行
        真的暂停下来（头像置灰、菜单写「已暂停」，与手按暂停长得一模一样），回到助手界面再
        自动恢复并说一句。原来那几道 attending 闸门照旧留着——暂停期间还得靠它们管住播报。

        手动按的暂停不会被这里替我恢复：只有「因为我离开而暂停」的那一次才算数（回来时若
        发现已经不在暂停态，说明用户自己按过「继续」，那就一个字都不说）。判据仍是
        attending()：没有注入判据的假宿主与自检一律当作「人在界面里」，这里什么都不做。
        返回人在不在界面里。
        """
        try:
            here = self.attending()
            now = float(self.clock() if at is None else at)
            if not here:
                if self._away_since is None:
                    self._away_since = now
                if not self.agent.paused and (now - self._away_since) >= AWAY_PAUSE_SECONDS:
                    self.agent.pause('您切去了别的应用：三虎先暂停，回到助手界面再继续')
                    self._away_paused = True
                    self.refresh_menu_labels()
                return False
            self._away_since = None
            if not self._away_paused:
                return True
            self._away_paused = False
            if not self.agent.paused:
                return True                    # 用户自己按过「继续」：不替他说话
            self.agent.resume()
            self.refresh_menu_labels()
            # 第 37 期第 6 条：用户切回助手界面时不再弹一句（原来这里 announce 一句「已回到
            # 助手界面」）——回来只把自动执行接上，安静地接着跑。
            return True
        except Exception as exc:
            self.errors.append(('focus', str(exc)))
            return True

    def _prefix_output(self, text):
        """为每条三虎对外消息补上任务 2.2 规定的播报前缀。"""
        text = ' '.join(str(text or '').split())
        if any(pattern.match(text) for pattern in PREFIX_PATTERNS):
            return text
        if '门禁' in text:
            return '【门禁】' + text
        if any(word in text for word in ('阻塞', '中断', '无法继续', '已停下等您处理')):
            return '【阻塞】' + text
        if any(word in text for word in ('警告', '失败', '暂缓', '缺', '错误')):
            return '【警告】' + text
        if any(word in text for word in ('已完成', '完成：', '制作完成', '已生成')):
            return '【完成】' + text
        if any(word in text for word in ('恢复', '已继续', '接着')):
            return '【恢复】' + text
        if any(word in text for word in ('下一阶段', '下一步')):
            return '【下一阶段】' + text
        if '模式' in text or '自动化等级' in text:
            return '【模式】' + text
        try:
            stage = str((self.snapshot() or {}).get('stage') or '')
            return Broadcaster.stage(pet_bus.STAGES.index(stage) + 1, text)
        except (ValueError, TypeError, AttributeError) as exc:
            self.errors.append(('broadcast.prefix', str(exc)))
            return Broadcaster.step(1, 1, text)

    def _record_output(self, text):
        """把已加前缀的三虎输出写进统一进度日志，不让日志故障影响界面。"""
        message = self._prefix_output(text)
        try:
            return self.broadcaster.broadcast(message)
        except (OSError, ValueError) as exc:
            self.errors.append(('broadcast.log', str(exc)))
            return message

    def broadcast(self, text, at=None, hold=None, shape=None):
        """播报一句：云朵框优先（第 19 期起没有托盘这一路），同一句话不连着说两遍。

        不管走哪条路这句话都会留在云朵记录里——菜单项点完「没提示」，来源就是只写
        self.notice 而没有任何一处真的把它说出来。

        shape 给形状（第 26 期第 5 条）：问用户「要不要做这件事」时传绿色对话框
        （pet_cloud.SHAPE_CLOUD），不传就沿用当前形状。
        """
        text = ' '.join(str(text or '').split())
        if not text or text == self._last_broadcast:
            return ''
        if self.speech_blocked(text):
            return ''
        self._last_broadcast = text
        message = self._record_output(text)
        cloud = self.cloud()
        if cloud is not None:
            try:
                if not self.attending():
                    # 第 49 期第 1 条：用户人在别的应用里（多半是把助手最小化去忙别的）——这句话
                    # 只记进云朵记录，不把框顶出来。原来照顶：那一刻贴片量出来的坐标是假的，框
                    # 于是落到屏幕另一头（用户报的「从右边跳到左边」），而他人根本不在这软件上。
                    # 等他自己打开三虎，这一句还在记录里。
                    cloud.append(message)
                else:
                    # 摆哪、抢不抢焦点、多久后收，全交给云朵框自己；hold 不传就「按这句话要读多久」
                    cloud.broadcast(message, hold=hold, shape=shape)
            except Exception as exc:
                self.errors.append(('cloud', str(exc)))
        return message
    def announce(self, text, at=None, shape=None):
        """用户按了东西：写进 notice 并立刻播报（同一句不会连着说两遍）。"""
        self.notice = ' '.join(str(text or '').split())
        self._notice_step = False         # 这一句是三虎自己的话，不是状态栏那一步（第 24 期第 5 条）
        return self.broadcast(self.notice, at=at, shape=shape)

    def reset_cloud(self):
        """清掉聊天记录（第 18 期：每次重开软件都从干净的一条开始，不带上次的对话）。"""
        cloud = self.cloud()
        if cloud is None:
            return []
        try:
            return cloud.reset()
        except Exception as exc:
            self.errors.append(('reset_cloud', str(exc)))
            return []

    def quiet(self, at=None):
        """招呼等待期间及说完的这一小段里，自动消息先不出声。

        用户原话：「启动软件->三虎打招呼的聊天框关闭后，再慢慢弹出其他信息」。安静期里那几路
        自动播报都闭嘴，各自的节流起算点跟着往后挪（安静期一过接着按正常节奏说，不会攒成一大串
        挤在一起）；这段里新冒出来的缺口也顺手记成「已对表」，不当急事顶出来。返回 True ＝ 还在
        安静期里。用户自己按出来的话（换档位、一键执行）不走这道闸，照常说。
        """
        if self._greet_id is None and not self._quiet_until:
            return False
        now = float(self.clock() if at is None else at)
        if self._greet_id is not None or now < self._quiet_until:
            self._broadcast_at = now
            self._progress_at = now
            self._offer_at = now
            self._advance_at = now
            self._gap_sig = tuple(self.gaps(at=at))
            return True
        self._quiet_until = None
        self._gap_sig = tuple(self.gaps(at=at))   # 安静期结束：当下这一批缺口算「对过表」
        return False
    def schedule_greet(self, delay_ms=GREET_DELAY_MS):
        """挂一次开机招呼（第 18 期）：到点还没关窗就冒云朵框。"""
        self.cancel_greet()
        try:
            self._greet_id = self.win.after(delay_ms, self.greet)
        except Exception as exc:
            self.errors.append(('greet', str(exc)))
            self._greet_id = None
        return self._greet_id

    def cancel_greet(self):
        """把还没到点的开机招呼收回来：关窗比招呼先到，留着就是一句 invalid command name。"""
        job, self._greet_id = self._greet_id, None
        if job is None:
            return None
        try:
            self.win.after_cancel(job)
        except TclError:
            # after job 已随窗口销毁。
            pass
        return job

    def greet(self, at=None):
        """开机招呼：云朵框说一句「哈喽~」（第 18 期；第 25 期起用云朵框）。

        主窗口还没露出来（常驻／最小化启动）就先不冒——云朵要贴着贴片摆，窗口没映射时贴片没有
        真实的屏幕坐标，冒出来就是一朵落在屏幕角落的野云。
        """
        scheduled = self._greet_id is not None
        self._greet_id = None             # 到点了：这一笔定时器就算用掉了
        if not self.window_visible() or not self.attending():
            if scheduled:
                self.schedule_greet()     # 启动招呼等窗口回到前台，不让报表抢先
            return ''
        cloud = self.cloud()
        if cloud is None:
            return ''
        try:
            # 开机只留一条问候：使用说明不能与正式招呼同时留在记录里。
            # 后续仍经 broadcast 统一加前缀、写日志和显示。
            cloud.lines = []
            cloud._scroll = 0
            self._last_broadcast = ''
            message = self._record_output(pet_cloud.GREETING)
            self._last_broadcast = pet_cloud.GREETING
            cloud.append(message)
            cloud.show(pinned=False,
                       hold=pet_cloud.GREETING_MS,
                       focus=False, shape=pet_cloud.SHAPE_PUFF)
        except Exception as exc:
            self.errors.append(('greet', str(exc)))
            return ''
        # 第 68 期任务 11：招呼真的冒出来了才开始数安静期——招呼的云才收，别的话别一起挤上来。
        now = float(self.clock() if at is None else at)
        self._quiet_until = now + GREET_QUIET_SECONDS
        self.notice = message
        return self.notice

    def whisper(self, text, at=None):
        """随口一句：圆形气泡浮出来，说完自己淡下去（第 18 期：做动作时才说）。

        第 60 期第 4 条：人切去别的应用时这一句也压着——这朵气泡是无边框置顶窗，冒出来就是
        压在别人的界面上。它本来就是「顺手夸一句」，不是要留话的那种，压掉不丢信息。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        if not self.attending():
            return ''
        cloud = self.cloud()
        if cloud is None:
            return ''
        try:
            text = self._record_output(text)
            cloud.whisper(text)
        except Exception as exc:
            self.errors.append(('whisper', str(exc)))
            return ''
        return text

    def banner(self, text, hold=None, at=None):
        """关软件前的日报／周报：清新标签框渐入（第 18 期）。"""
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        if self.speech_blocked(text):
            return ''                      # 第 59 期第 8 条：栏／弹窗抽着指针时这张便签也先压着
        if not self.attending():
            return ''                      # 第 60 期第 4 条：人在别的应用里，这张便签也先不递
        cloud = self.cloud()
        if cloud is None:
            return ''
        try:
            text = self._record_output(text)
            cloud.banner(text, hold=pet_cloud.BANNER_MS if hold is None else hold)
        except Exception as exc:
            self.errors.append(('banner', str(exc)))
            return ''
        return text

    def report_hint_text(self, weekly=False, path=None):
        """提示去看报表的那一句：数字来自台账（取不到就只说一句，不编数），末尾带上文件名。

        第 36 期第 5 条：这句话不再出现在「关软件那一眼」，所以原来那句「明天见」的告别话
        一并去掉——它现在是干活途中递上来的一张便签，只说「报表在哪」。
        """
        try:
            counts = self.counts()
            shots, frames = int(counts['shots']), int(counts['frames'])
        except Exception:
            shots = frames = None
        head = '本周周报已备好' if weekly else '今日日报已备好'
        name = '（文件：%s）' % path.name if path is not None else ''
        if shots is None:
            return '%s：%s%s（随时能在「生成今日日报」里看全文）' % (pet_agent.PET_NAME, head, name)
        return '%s：%s——%d 个镜头、%d 张首帧入账%s' % (pet_agent.PET_NAME, head, shots, frames, name)

    def report_hint(self, at=None):
        """第 36 期第 5 条：下午／夜里活儿慢下来了，三虎主动把日报／周报递到用户眼前。

        原来这件事挂在「关软件」那一下——点关闭弹一张标签框、真关还要等它渐入；用户要的是
        「删掉关闭前的弹框，改由三虎看工作强度自己提」。判据三条：下午两点之后、距上一次看见
        制作动静满 REPORT_QUIET_SECONDS（这一波活干完了）、这一份日报／本周周报还没提过。提的时候顺手
        把报表生成好，标签框里带上文件名——用户要的「提示他去看生成好的文件」。
        """
        try:
            now = float(self.clock() if at is None else at)
        except Exception as exc:
            self.errors.append(('report_hint', str(exc)))
            return ''
        try:
            moment = datetime.datetime.fromtimestamp(now)
        except Exception as exc:
            self.errors.append(('report_hint', str(exc)))
            return ''
        if self.quiet(at=now):
            return ''                                  # 启动问候及其安静期优先
        if moment.hour < BANNER_HOUR:
            return ''                                  # 上午不递：一天才开头，报表也没什么可写
        weekly = moment.weekday() >= WEEKLY_FROM
        project = self.agent.project
        if project is None:
            return ''
        kind = 'weekly' if weekly else 'daily'
        day = moment.date().isoformat()
        period = pet_report.week_key(day) if weekly else day
        key = (str(project), kind, period)
        if key == self._report_key:
            return ''                                  # 这一份已经递过
        if self._work_at is not None and (now - float(self._work_at)) < REPORT_QUIET_SECONDS:
            return ''                                  # 手上还有动静：不在这时候拿报表打断
        if self.cloud_visible() or self.muted(at=at) or not self.attending():
            return ''                                  # 有框露着／静音／人不在界面里：都不提
        if self.busy(state=self.snapshot(at=at)):
            return ''                                  # 正跑着活儿：等它跑完再递
        try:
            if pet_report.reminder_seen(project, kind, period):
                self._report_key = key
                return ''
        except Exception as exc:
            self.errors.append(('report_hint.reminder', str(exc)))
            return ''
        path = None
        try:
            if weekly:
                path, _totals = self.weekly_report(at=at)
            else:
                _data, path = self.daily_report(at=at)
        except Exception as exc:
            self.errors.append(('report_hint.report', str(exc)))
        if path is None:
            return ''
        text = self.report_hint_text(weekly=weekly, path=path)
        said = self.banner(text) if text else ''
        if said:
            self._report_key = key
            try:
                pet_report.mark_reminder_seen(project, kind, period)
            except Exception as exc:
                self.errors.append(('report_hint.reminder', str(exc)))
        return said

    def confirm_start(self, title=ONE_CLICK_TITLE, text=ONE_CLICK_ASK):
        """一键执行前的确认弹窗（第 18 期）：要自动制图，先问一句，别一按就跑起来。

        asker 可注入；默认经统一确认窗口，自检可换成假函数而不弹真窗。
        无界面或弹窗失败一律不放行，避免在未获确认时启动自动制作。
        """
        asker, parent = self.asker, None
        if asker is None:
            try:
                return bool(ask_confirmation(self.win, title, text, dangerous=True))
            except Exception as exc:
                self.errors.append(('ask', str(exc)))
                return False
        try:
            if parent is None:
                return bool(asker(title, text))
            return bool(asker(title, text, parent=parent))
        except Exception as exc:
            self.errors.append(('ask', str(exc)))
            return True

    def confirm(self, text, title=CONFIRM_TITLE):
        """三虎判断某件事要用户点头时说一句（第 16 期）。

        第 22 期：自绘气泡删了，要用户点头的事统一走云朵框——先写进记录，再当场播报出来；
        安静时段（「稍后再说」）只记账不说话。title 参数留着不删，旧调用点不用改。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        cloud = self.cloud()
        if cloud is not None:
            try:
                cloud.append(self._record_output('%s：%s（%s）' % (pet_agent.PET_NAME, text, CONFIRM_NEED)))
            except Exception as exc:
                self.errors.append(('confirm.cloud', str(exc)))
        if self.snoozing():
            return text
        # 第 26 期第 5 条：问用户「要不要办这件事」统一用绿色对话框——一眼就和播报分得开
        self.announce(text, shape=pet_cloud.SHAPE_CLOUD)
        return text

    def show_progress(self, text):
        """把「正在做什么」写到主界面状态栏：一键执行这类活儿跑在页面之外，用户找不到进度。

        状态栏拿不到才退回云朵框（self.notice），总之不许一点动静都没有。
        """
        text = ' '.join(str(text or '').split())
        if not text:
            return ''
        status = getattr(self.desktop, 'status', None)
        if status is not None:
            try:
                status.set(text)
                return text
            except Exception as exc:
                self.errors.append(('progress', str(exc)))
        self.notice = text
        return text

    def chat_task(self, index=None):
        """当前这一页该做的那件事（第 29 期第 5 条）：问句 ＋ 确认按钮要发出去的那一句话。

        用户要的是「主动问对应页面的对应操作，聊天框里不用回话，点一下确认就行」——所以问什么、
        按下去做什么，都在这里一次定好，对话框那边的按钮只负责把 command 发出来。
        页序号读不出来（假宿主、没建过页）就当第 01 页，绝不因为读不到页面而说不出话。
        """
        page = getattr(self.desktop, 'page_index', 0) if index is None else index
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 0
        if 0 <= page < len(PAGE_ASKS):
            return PAGE_ASKS[page]
        return FALLBACK_ASK

    # ── 记住所有项目（第 37 期第 1 条） ──────────────────────────────────────
    def projects_registry(self):
        """项目登记表（只读）：宿主手里的那份优先，拿不到就读程序目录的 projects.json。"""
        info = getattr(getattr(self.desktop, 'projects', None), 'info', None)
        if isinstance(info, dict) and isinstance(info.get('projects'), list):
            return info
        import json
        path = PROGRAM / 'projects.json'
        if not path.is_file():
            return {}
        try:
            with path.open(encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception as exc:
            self.errors.append(('projects.read', str(exc)))
            return {}
        return data if isinstance(data, dict) else {}

    def project_progress(self, path):
        """一个项目走到哪了：读它的阶段状态文件，读不出来就不编（返回空表）。"""
        try:
            state = pet_state.Machine(path, persist=False).load().progress()
        except Exception as exc:
            self.errors.append(('projects.progress', str(exc)))
            return {}
        return {'stage': str(state.get('stage_name') or ''), 'percent': float(state.get('percent') or 0.0)}

    def projects_snapshot(self, at=None, force=False):
        """所有项目的只读快照（第 37 期第 1 条）：当前项目排最前，其余按名字。

        每次读盘都是一小段 JSON，但播报可能每几秒问一次，所以带一层 TTL 缓存
        （PROJECT_CACHE_SECONDS）；force=True 时立刻重读（用户刚建过项目就走这条）。
        """
        try:
            now = float(self.clock() if at is None else at)
        except Exception:
            now = 0.0
        if not force and self._projects_rows is not None and (now - self._projects_at) < PROJECT_CACHE_SECONDS:
            return [dict(row) for row in self._projects_rows]
        registry = self.projects_registry()
        active = str(registry.get('active') or '')
        rows = []
        for item in registry.get('projects') or []:
            if not isinstance(item, dict):
                continue
            path = str(item.get('path') or '')
            if not path:
                continue
            row = {'name': str(item.get('name') or Path(path).name), 'path': path,
                   'status': PROJECT_CLOSED if item.get('status') == 'completed' else PROJECT_OPEN,
                   'active': bool(active and Path(path) == Path(active))}
            row.update(self.project_progress(path))
            rows.append(row)
        rows.sort(key=lambda row: (not row['active'], row['name']))
        self._projects_rows, self._projects_at = rows, now
        return [dict(row) for row in rows]

    def projects_text(self, at=None, force=False):
        """把手上这些项目说成一句人话：「某某（在制作 · 剧本准备 20%）」。"""
        rows = self.projects_snapshot(at=at, force=force)
        if not rows:
            return '还没建过项目——建一个我就记住它，往后随时问我。'
        parts = []
        for row in rows[:PROJECT_LIMIT]:
            where = row.get('stage') or ('全部做完' if row['status'] == PROJECT_CLOSED else '刚起步')
            head = row['name'] + ('（当前）' if row['active'] else '')
            parts.append('%s：%s · %s' % (head, row['status'], where))
        tail = '' if len(rows) <= PROJECT_LIMIT else '；还有 %d 个没念' % (len(rows) - PROJECT_LIMIT)
        return '手上 %d 个项目。%s%s' % (len(rows), '；'.join(parts), tail)

    def projects_brief(self):
        """给模型的短快照：一行一个项目，顺序固定（sort_keys 那边才不会被打破）。"""
        try:
            rows = self.projects_snapshot()
        except Exception as exc:
            self.errors.append(('projects.brief', str(exc)))
            return []
        return ['%s|%s|%s%s' % (row['name'], row['status'], row.get('stage') or '未开工',
                                '' if not row['active'] else '|当前') for row in rows]

    def is_page_ask(self, line):
        """这一句是不是三虎在问「要不要做这一页的事」（换页时旧的那一句要让位）。

        第 37 期第 6 条「及时清理」落到实处的一条判据：只认自己问出去的那几句（PAGE_ASKS ＋
        兜底那一句），用户自己说的话、别的播报一个字都不动。
        """
        body = str(line or '')
        # 进页半自动会把当前进度与问句合并为同一条，换页时仍要识别并清理末行问句。
        if '\n' in body:
            body = body.rsplit('\n', 1)[-1]
        prefix = pet_agent.PET_NAME + '：'
        if not body.startswith(prefix):
            return False
        question = body[len(prefix):]
        return any(question == ask for ask, _command in PAGE_ASKS + (FALLBACK_ASK,))

    def page_name(self, page=None):
        """这一页叫什么（「08  首帧管理」这种）：从宿主的页表里读，读不到就退回序号。

        第 36 期第 6 条起名字以宿主的页表为准（desktop.PAGES），拿不到也不编。第 37 期第 5 条
        之后换页那句问句不再报页码，这里留着给别的入口（菜单、用例）用同一份口径。
        """
        try:
            index = int(getattr(self.desktop, 'page_index', 0) if page is None else page)
        except (TypeError, ValueError):
            return ''
        pages = list(getattr(self.desktop, 'PAGES', None) or [])
        if 0 <= index < len(pages):
            return ' '.join(str(pages[index]).split())
        return '第 %d 页' % (index + 1)

    def page_stage(self, index):
        """页序号 → 制作阶段：页表与 pet_bus.STAGES 一一对应。"""
        try:
            index = int(index)
        except (TypeError, ValueError):
            return ''
        stages = list(getattr(pet_bus, 'STAGES', ()) or ())
        return stages[index] if 0 <= index < len(stages) else ''

    def stage_failures(self, stage):
        """这一阶段上还等着用户点头的那些项（条数直接来自台账，不编）。"""
        try:
            return [item for item in self.agent.failures
                    if isinstance(item, dict) and str(item.get('stage') or '') == str(stage)]
        except Exception as exc:
            self.errors.append(('stage.failures', str(exc)))
            return []

    def stage_needs_user(self, index, at=None):
        """第 45 期：换到这一页，用户到底需不需要三虎开口——判据只有「有没有非他不可的事」。

        用户报的是「用户一换页三虎就弹对话框」，要改成「三虎自己判断」：纯粹翻页看看，一个字都
        不说；只有这一阶段真压着「失败待确认」（等他点个头才能接着往下走）时才开口。暂停期间也
        不打扰——那会儿三虎本来就不动手，问了也做不成。额度用光的提醒走预算播报那条路，
        不在这里重复一遍。
        """
        if getattr(self.agent, 'paused', False):
            return False
        stage = self.page_stage(index)
        return bool(stage) and bool(self.stage_failures(stage))

    def stage_entry_status(self, index):
        """进入制作页时的一句状态：只报当前阶段与进度，不创建新的助手窗口。"""
        stage = self.page_stage(index)
        name = pet_bus.STAGE_NAMES.get(stage, '当前阶段')
        try:
            raw_state = str(self.stage_states().get(stage) or 'pending')
            state = {
                'pending': '未开始', 'running': '进行中', 'success': '已完成',
                'failed': '待处理', 'blocked': '已阻塞', 'skipped': '已跳过',
            }.get(raw_state, raw_state)
        except Exception:
            state = '状态待读取'
        return '【阶段 %d/%d】%s：当前进度 %s' % (int(index) + 1, len(pet_bus.STAGES), name, state)

    def enter_stage(self, page=None, at=None):
        """统一进页规则：提示档报进度，半自动征询，全自动按已选 SKILL 执行。"""
        try:
            index = int(getattr(self.desktop, 'page_index', 0) if page is None else page)
        except (TypeError, ValueError):
            return ''
        stage = self.page_stage(index)
        if not stage:
            return ''
        status = self.stage_entry_status(index)
        level = self.level()
        if level == 'hint' or getattr(self.agent, 'paused', False):
            return self.broadcast(status, at=at)
        if level == 'semi':
            # 进度与确认合在同一朵云，避免状态云把确认云顶掉。
            return self.note_stage(index, at=at, force_prompt=True, intro=status)
        if level != 'auto':
            return self.broadcast(status, at=at)
        marker = (str(getattr(self.desktop, 'root', '') or ''), stage)
        self.broadcast(status, at=at)
        if marker in self._stage_auto_started:
            return status
        self._stage_auto_started.add(marker)
        # 分镜／结构／首帧各有文件级完成条件，不能把通用 SKILL 的“已派发”当成
        # 阶段完成。它们必须走与页面手动按钮相同的专用入口：由产物轮询、采用或
        # 本地校验发出 completed，才允许自动链进入下一阶段。
        if stage in ('script_structure', 'storyboard', 'keyframe'):
            result = self.start_stage(stage, at=at)
        else:
            # 其余阶段沿用既有模板／SKILL 编排器；不会打开或并发创建新的 Agent 窗口。
            result = self.run_skill({'stage': stage, 'params': {'skills': [], 'template_confirmation': '确认'}}, at=at)
        # 全自动可以代为产出剧本，但剧本内容仍由用户确认后再进入分镜。
        if stage == 'script' and result:
            self.confirm('确认剧本信息后，可继续制作分镜。')
        return result or status

    def script_downloaded(self, path=None, at=None):
        """已下载的真实剧本可完成阶段；模型首次回复仍不触发弹窗。"""
        try:
            from pathlib import Path
            saved = Path(path) if path else None
            source = saved if saved and saved.is_file() and saved.stat().st_size else None
        except (OSError, TypeError, ValueError):
            source = None
        if source is not None:
            # 同一轮先让自动队长武装，再结束 script；否则 completed 会被未武装的
            # 自动队长吞掉，保存成功仍无法进入结构剧本阶段。
            verified, detail = self._completion_evidence('script')
            if verified:
                self._emit('script.completed', stage='script', source=str(source))
                self._complete_if_verified('script', '剧本文档已下载')
            else:
                self._emit('stage.paused', stage='script',
                           text='剧本文档已下载（待校验：%s）' % detail)
        self.broadcast('【完成】剧本文档已下载', at=at)
        return self.confirm('【下一阶段】剧本已下载。现在制作分镜吗？')

    def note_stage(self, page=None, at=None, force_prompt=False, intro=''):
        """第 36 期第 6 条：用户换到别的阶段，三虎看一眼「这一步要不要我自动做」。

        旧的普通换页入口仍只给一句问句；进页协调器传入 intro 时会把「当前进度」与问句合并，
        既不另开窗口，也不会让状态提示把用户确认顶掉。
        对话框正开着的时候不另冒一朵：新的问句接着排进同一个框里（顺手清一清旧话），
        框里于是永远只有当前这一页的事。回车要做的那件事照旧 propose 给回复框。

        第 45 期：换页本身不再等于「该说话了」——先问 stage_needs_user（有没有非等用户点头的
        事），没有就安静地记下这一页。同一页重复问要隔 STAGE_ASK_SECONDS；暂停／静音／人不在
        界面里都不问——这时候再冒一个框只会更吵。返回问出去的那句话（没问返回空串）。
        """
        try:
            index = int(getattr(self.desktop, 'page_index', 0) if page is None else page)
        except (TypeError, ValueError):
            return ''
        try:
            now = float(self.clock() if at is None else at)
        except Exception as exc:
            self.errors.append(('stage.clock', str(exc)))
            return ''
        first_entry = self._stage_page is None
        if first_entry:
            self._stage_page, self._stage_at = index, now
            if not force_prompt:
                return ''                              # 旧入口：开机落在哪一页不算「换阶段」
        if index == self._stage_page and self._stage_at is not None \
                and (now - float(self._stage_at)) < STAGE_ASK_SECONDS \
                and not (force_prompt and first_entry):
            return ''                                  # 刚问过这一页：不重复问
        self._stage_page, self._stage_at = index, now
        try:
            if self.muted(at=at) or not self.attending():
                return ''
            if not force_prompt and not self.stage_needs_user(index, at=at):
                return ''                  # 第 45 期：没什么非等用户点头的事，这句就咽下去
            ask, command = self.chat_task(index)
            line = ('%s\n%s：%s' % (str(intro).strip(), pet_agent.PET_NAME, ask)) if intro else '%s：%s' % (pet_agent.PET_NAME, ask)
            chat = self.chat
            if chat is not None and getattr(chat, 'visible', False) and getattr(chat, 'pinned', False):
                # 对话框开着：这一页的问句接着排进去，框里跟着换页更新（不另冒一朵、不打断用户）。
                if command and hasattr(chat, 'propose'):
                    try:
                        chat.propose(command)
                    except Exception as exc:
                        self.errors.append(('stage.propose', str(exc)))
                if chat.lines and self.is_page_ask(chat.lines[-1]):
                    # 上一页问过的那一句让位：框里永远只有「当前这一页要不要做」，
                    # 换十页也不会攒成十句问句（第 37 期第 6 条）。
                    chat.pop()
                chat.append(line)
                chat.trim()                # 再顺手收一收：只留最近几段
                return line
            if self.cloud_visible():
                return ''                  # 已经有别的贴纸露着：不叠一个
            cloud = self.cloud()
            if cloud is not None and command and hasattr(cloud, 'propose'):
                try:
                    cloud.propose(command)
                except Exception as exc:
                    self.errors.append(('stage.propose', str(exc)))
            return self.broadcast(line, at=at, shape=pet_cloud.SHAPE_CLOUD)
        except Exception as exc:
            self.errors.append(('stage.ask', str(exc)))
            return ''

    def chat_hello(self):
        """开对话框时三虎主动问的那一句（第 24 期第 1 条；第 29 期第 5 条改成问当前页的流程）。

        问句与「按下确认要做的那件事」一起从 chat_task 取；取到就顺手递给云朵框（propose），
        按钮上于是写着「确认」。返回说出口的那句话——一句提问不该把「打开对话框」弄坏。
        """
        ask, command = self.chat_task()
        cloud = self.cloud()
        if cloud is not None and hasattr(cloud, 'propose'):
            try:
                cloud.propose(command)
            except Exception as exc:
                self.errors.append(('chat.propose', str(exc)))
        return '%s：%s' % (pet_agent.PET_NAME, ask)

    def open_chat(self):
        """打开云朵框（对话形态）：主窗口收起时先把它叫回来，否则云朵没地方冒。"""
        if not self.window_visible():
            self.show_main()
        cloud = self.cloud()
        if cloud is None:
            return None
        try:
            widget = cloud.show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        except Exception as exc:
            self.errors.append(('chat', str(exc)))
            widget = None
        if widget is None:
            # 画不出来也要说一声：点了「和宠物说话」却毫无动静，正是用户说的「没反应」。
            self.errors.append(('chat', '云朵框没建起来'))
            self.notice = '云朵框没建起来，主界面照常用（右键菜单里还有别的入口）'
            self.speak()
            return None
        self.chat = cloud
        try:
            cloud.append(self._record_output(self.chat_hello()))      # 第 24 期第 1 条：一打开，三虎先问这一页该做的事
        except Exception as exc:
            self.errors.append(('chat.hello', str(exc)))
        self.notice = '云朵框已打开：三虎问的是这一页该做的事，点「确认」它就去办'
        return widget

    def close_chat(self, event=None):
        """收起云朵框（主窗口销毁或从菜单收起）：子组件冒泡上来的 <Destroy> 一律不认领。"""
        if event is not None and getattr(event, 'widget', None) is not self.win:
            return None
        cloud, self.chat = self._cloud, None
        if cloud is not None:
            try:
                cloud.close()
            except Exception as exc:
                self.errors.append(('chat.close', str(exc)))
        return self.chat

    def toggle_chat(self):
        """贴片双击／右键菜单入口：开着就收、关着就开；两个方向都不抛。"""
        return self._chat_interaction.toggle(self.chat is not None)

    def speech_blocked(self, text=''):
        """这会儿不能冒云？不能就把这句话压住，返回 True。

        第 47 期第 4 条：功能下拉栏（tk_popup 的嵌套事件循环带 grab）正显示着时冒一朵云会把栏
        顶掉，用户点的就不是自己想点的那一项了。第 59 期第 8 条：有弹窗（阶段配置、设置…）抽着
        指针时同样不能冒——那时候云朵框挡路又点不动。两种情形后果一样：压住，等 say_held
        在下一个心跳补说。
        """
        if self._menu_open or self.modal_grabbed():
            self._held_broadcast = text
            return True
        return False

    def modal_grabbed(self):
        """这会儿是不是有别的窗口抓着指针（Tk 的本地 grab）。

        第 59 期第 8 条：本地抓取会把整个应用的指针事件都送进抓着的那一屋窗——三虎的
        聊天框这时候连右上角那颗「关闭」都点不动（用户报的就是这个）。判据只看「抓取
        还在不在」：自己的主窗（以及从不自己抓取的云朵框）不算。
        """
        try:
            holder = self.win.grab_current()
        except Exception:
            return False
        return bool(holder) and holder is not self.win

    def guard_chat_grab(self):
        """第 59 期第 8 条：有弹窗抽着指针时，三虎的聊天框自己先收起来。

        与其留一朵关不掉的框（点哪都落到那屎弹窗上），不如先收起；要说的那一句话
        已经在记录里，弹窗一关心跳再把它补说。返回 True ＝这一拍真的收了一朵。
        """
        return self._chat_interaction.guard(self.modal_grabbed())

    def guard_cloud_away(self):
        """第 60 期第 4 条：用户在别的应用里时，露着的那朵云自己收起来。

        对话框只能在漫剧助手上面。这朵云是无边框置顶窗（pet_cloud 里 overrideredirect ＋
        -topmost），用户 alt-tab 去了别的应用，它还压在人家界面上，看着就是「三虎穿过去了」。
        收起来不丢话：要说的那句已经记进云朵记录，回来打开三虎照旧看得见。返回 True ＝这一拍
        真的收了一朵。
        """
        return self._chat_interaction.guard(not self.attending())

    def chat_drain(self):
        """心跳里把云朵框的后台回答贴上记录；没有云朵框就是空操作。"""
        cloud = self._cloud
        if cloud is None:
            return 0
        try:
            return cloud.drain()
        except Exception as exc:
            self.errors.append(('chat.drain', str(exc)))
            return 0

    def hide_to_pet(self):
        """常驻模式第 22 期跟着独立窗一起删了：桌面.py 仍在问，这里一律答「不收」。

        desktop.pet_hides_instead_of_quitting() 拿 False 就走原来的关闭流程——关主窗口就是关程序，
        与用户要的「删掉独立小窗」一致。留着这个空壳是为了不再改桌面那条接缝。
        """
        return False

    def show_main(self):
        """把主窗口放回来，并把 Windows 的任务栏最小化状态彻底解除。"""
        hidden = True
        try:
            state = str(self.win.state()).lower()
            hidden = state in ('iconic', 'withdrawn') or not bool(self.win.winfo_viewable())
            # Windows/Tk 对任务栏图标化的恢复并不稳定：部分宿主必须先映射，
            # 再显式 normal；只做其中一步会留下一个看似可见、实际仍在任务栏的根窗口。
            self.win.deiconify()
            self.win.state('normal')
            self.win.update_idletasks()
            self.win.lift()
            # lift 在被别的顶层窗口遮挡时可能无效；短暂置顶仅用于交还焦点，
            # 空闲后立刻恢复，避免主界面长期压住其他应用。
            try:
                self.win.attributes('-topmost', True)
                # Use a bound method, not a throw-away lambda: Tk can dispatch
                # this idle task after a close and otherwise reports an invalid
                # Tcl command name to stderr.
                self._main_topmost_job = self.win.after_idle(self._release_main_topmost)
            except TclError:
                # 重复销毁是 Tk 生命周期竞态。
                pass
            try:
                self.win.focus_force()
            except Exception as exc:
                self.errors.append(('show_main.focus', str(exc)))
        except Exception as exc:
            self.errors.append(('show_main', str(exc)))
            return False
        self.notice = '主窗口已显示' if hidden else '主窗口本来就在屏幕上'
        return True

    def _release_main_topmost(self):
        """Release show_main's one-shot topmost flag if the root still exists."""
        self._main_topmost_job = None
        try:
            self.win.attributes('-topmost', False)
        except TclError:
            # The root may be destroyed between after_idle() and this callback.
            pass


    # ── 开机自启（只写当前用户的 Run 项） ───────────────────────────────────
    def autostart(self):
        """注册表封装按需建一个（拿不到 winreg 的机器上就是「不可用」，不是错误）。"""
        if self._autostart is None:
            self._autostart = Autostart()
        return self._autostart

    def autostart_label(self):
        """菜单文字直接反映注册表里的现状，不另存一份状态。"""
        control = self.autostart()
        if not control.available:
            return '开机自启（本机不支持）'
        value = control.get()
        if value is None:
            return '开机自启（读不到）'
        return '开机自启（已开启）' if value else '开机自启（未开启）'

    def toggle_autostart(self):
        """切换开机自启并把菜单文字改成最新状态；返回切换后的状态。"""
        try:
            state = self.autostart().toggle(PROGRAM)
        except Exception as exc:
            self.errors.append(('autostart', str(exc)))
            state = False
        self.notice = ('开机自启已开启：下次登录会自动启动助手' if state
                       else '开机自启已关闭（或本机不支持）')
        self.refresh_menu_labels()
        return state

    def autostart_default(self):
        """开机自启默认开着（第 19 期）：注册表里还没这一项就补上；本机不支持就当没这回事。"""
        control = self.autostart()
        if not control.available:
            return False
        try:
            if control.enabled():
                return True
            return bool(control.set(autostart_command(PROGRAM)) and control.enabled())
        except Exception as exc:
            self.errors.append(('autostart.default', str(exc)))
            return False

    def refresh_menu_labels(self):
        """菜单文字跟着状态走（模型档位、「暂停 / 播放」与静默倒计时；不用 Tk 变量）。

        心跳每 150ms 调一次，所以先跟上一份文字比对：没变就不碰菜单（改文字会重排菜单）。
        """
        # 第 22 期：这三条都在一级栏上（静默那条原来在子菜单里，改文字不用整栏重建了）。
        for name, label in (('model', self.model_label()), ('mode', self.mode_label()),
                            ('pause', self.pause_label()), ('snooze', self.snooze_label())):
            if self._menu_labels.get(name) == label:
                continue
            index = self.menu_index.get(name)
            if index is None or self.menu is None:
                continue
            try:
                self.menu.configure_entry(index, label=label)
            except Exception as exc:
                self.errors.append(('menu', str(exc)))
            else:
                self._menu_labels[name] = label
        return self.menu_index.get('pause')

    # ── 稍后再说（静默一段时间） ─────────────────────────────────────────────
    def snooze_left(self):
        """还剩多少秒不播报；时钟可注入，用例不必真等 15 分钟。"""
        try:
            return max(0.0, float(self.snooze_until) - float(self.clock()))
        except (TypeError, ValueError):
            return 0.0

    def snoozing(self):
        return self.snooze_left() > 0

    def snooze_label(self):
        """菜单文字直接反映还剩多久恢复，不另存一份状态。

        第 44 期：这一项按用户附件叫「免打扰」（原来是「稍后再说」）——同一件事的两种说法里，
        用户附件给的说法更直白：这一段时间别打扰我。
        """
        left = self.snooze_left()
        if left > 0:
            return '免打扰中：还有 %d 分钟恢复播报' % max(1, int((left + 59) // 60))
        return '免打扰（安静 %d 分钟）' % (SNOOZE_SECONDS // 60)
    def snooze(self, seconds=None):
        """「稍后再说」（第 22 期回到一级功能栏，紧挨在「暂停」下面）：安静一段时间不说话。

        到点之后同一批失败会**再提醒一次**——所以这里连同 already-announced 指纹与「同一句话
        不连着说两遍」那枚指纹一起清掉；只清前者的话，那句一模一样的提醒会被播报的判重吃掉，
        用户永远等不到第二次。
        """
        span = SNOOZE_SECONDS if seconds is None else max(0.0, float(seconds))
        self.snooze_until = float(self.clock()) + span
        self._announced = ()
        self._last_broadcast = ''
        self._busy_taps = []              # 第 60 期第 1 条：这一轮数满了，下一轮重新攒
        self.refresh_menu_labels()
        return self.snooze_left()
    def unsnooze(self):
        """立刻恢复播报；同一批失败下一轮心跳就会重新说一次（判重指纹同上一起清）。"""
        self.snooze_until = 0.0
        self._announced = ()
        self._last_broadcast = ''
        self._busy_taps = []              # 第 60 期第 1 条：刚恢复就别拿旧账立刻又把自己按静
        self.refresh_menu_labels()
        return self.snooze_left()

    def note_work(self, at=None):
        """第 60 期第 1 条：用户正忙着按个不停时，三虎自己进免打扰。

        每一下用户动作（页面按钮、气泡按钮、右键菜单）都在这儿记一笔；BUSY_WINDOW 秒里攒满
        BUSY_TAPS 下就说明人正忙在手上的活上——这时候再冒话就是打扰。于是照手按「免打扰」那
        条路安静 SNOOZE_SECONDS，并且把「先安静多久」这一句当场说出去（安静前最后一句）。
        已经在免打扰里、或者时钟读不出来时什么都不做：安静期间用户照样按个不停，那不算新的一轮。
        返回 True ＝这一拍真的进了免打扰。
        """
        if self.snoozing():
            return False
        try:
            now = float(self.clock() if at is None else at)
        except (TypeError, ValueError):
            return False
        self._busy_taps = [item for item in self._busy_taps if (now - item) <= BUSY_WINDOW]
        self._busy_taps.append(now)
        if len(self._busy_taps) < BUSY_TAPS:
            return False
        self.snooze()                      # 连同 _busy_taps 一起清掉
        self.announce('您在忙：三虎先安静 %d 分钟，过后再把待确认的项报给您' % (SNOOZE_SECONDS // 60),
                      at=at)
        return True

    def toggle_snooze(self):
        """菜单入口：安静着就恢复，否则安静一段时间；两个方向都不抛，也都留一句提示。"""
        if self.snoozing():
            self.unsnooze()
            self.notice = '已恢复播报：下一轮心跳就把待确认的项重新报一次'
        else:
            self.snooze()
            self.notice = '已安静 %d 分钟：这段时间失败项只记账，出安静期再报一次' % (SNOOZE_SECONDS // 60)
        return self.snooze_left()

    # ── 播报 ────────────────────────────────────────────────────────────────
    def announce_failures(self):
        """失败有新变化时播报一条：同一批失败只说一次，失败清零之后再出现算新的一批。

        第 22 期：自绘气泡与系统托盘都删了，通知只剩云朵框这一条出口（只报告、不处置——
        要重试请走「一键执行」或功能栏里的「重试失败项」）。
        """
        if self.quiet():
            return ''                          # 第 68 期任务 11：安静期里失败提醒也缓一缓，过了再说
        if self.snoozing():
            return ''                          # 「稍后再说」期间不打扰；到点后同一批会再提醒一次
        if not self.attending():
            return ''                          # 用户在别的应用里：失败提醒先记着，不弹（第 30 期第 3 条）
        try:
            failures = [item for item in self.agent.failures if isinstance(item, dict)]
        except Exception as exc:
            self.errors.append(('announce', str(exc)))
            return ''
        stamp = tuple(sorted('%s|%s' % (item.get('stage', ''), item.get('category', ''))
                             for item in failures))
        if not stamp:
            self._announced = ()
            return ''
        if stamp == self._announced:
            return ''
        self._announced = stamp
        first = failures[0]
        stage = str(first.get('stage') or '')
        # 第 71 期任务 1：原来气泡一律念那条模板 hint（「没见过的错误：停下等您确认」），
        # 真正的原因——异常原文——反而被盖掉了，用户看到的就是一句「没见过的错误」，
        # 不知道该修什么。现在不管认得出认不出类目，先把原因原文摆出来，建议跟在后面作补充。
        reason = ' '.join(str(first.get('error') or '').split())
        hint = ' '.join(str(first.get('hint') or '').split())
        pieces = []
        for piece in (reason, hint):
            if piece and piece not in pieces:
                pieces.append(piece)
        text = '%s：%s' % (pet_bus.STAGE_NAMES.get(stage, stage or '某阶段'),
                          '；'.join(pieces) or '原因未知')
        extra = len(failures) - 1
        if extra > 0:
            text += '（另有 %d 项待确认）' % extra
        self.announce(text)
        return text
    # ── 心情与动画 ──────────────────────────────────────────────────────────
    def mood(self, state=None):
        try:
            agent = self.agent
            if agent.paused:
                return 'paused'
            if agent.failures:
                return 'worry'
            state = state if state else self.snapshot()
            return 'busy' if state.get('stage') is not None else 'idle'
        except Exception:
            return 'idle'

    def interval(self, state=None):
        return ACTIVE_MS if self.mood(state) == 'busy' else IDLE_MS

    def caption_text(self):
        """三虎右边那行小字：哪一档自动化等级；暂停时写「已暂停」（第 18 期）。

        第 23 期：有卡住的活儿就带上「· 待确认 N」——不打开任何窗口，一眼就知道有没有事
        等着自己处理（数字来自父 Agent 的失败清单，不编）。
        """
        pending = 0
        try:
            if self.agent.paused:
                return PAUSED_CAPTION
            pending = len([item for item in self.agent.failures if isinstance(item, dict)])
        except Exception:
            pending = 0
        text = LEVEL_CAPTIONS.get(self.level(), LEVEL_CAPTIONS['hint'])
        # 第 23 期补：这行小字是从右沿往左长的（anchor='ne'），加长必须往下一行走。
        # 「只提醒 · 待确认 2」横着写实测压住猫的左脸（贴片特写截屏），所以第二行另起。
        return '%s\n待确认 %d' % (text, pending) if pending else text

    def show_caption(self):
        """把等级字样写到三虎右边（写不进去就少一行字，不影响别的）。"""
        if self.caption is None:
            return None
        value = self.caption_text()
        try:
            self.caption.configure(text=value)
            # 第 21／22 期：四档小字一律黑色（用户要的「文字全部用黑色」「已暂停也显示黑色」）——
            # 哪一档已经由猫身子和那排猫爪说清楚了，字再上色反而看不清（浅色字压在浅色底上）。
            colour = CAPTION_INK
            if colour:
                self.caption.configure(foreground=colour)
            self.caption.lift()
        except Exception as exc:
            self.errors.append(('caption', str(exc)))
            return None
        return value

    def level(self, state=None):
        """当前自动化等级：快照里有就用快照的，取不到退回父 Agent 自己记的那一档。"""
        try:
            value = (state if state is not None else self.snapshot()).get('level')
        except Exception:
            value = None
        if value in pet_agent.LEVELS:
            return value
        try:
            return self.agent.level
        except Exception:
            return pet_agent.DEFAULT_LEVEL

    def draw(self, index=None, state=None):
        """手绘一帧（共用 paint()，方案 B 的独立窗也用它，不另画一份）。

        第 15 期：颜色跟着自动化等级走——切等级那一下要立刻变，所以 click('level') 里会手画一帧。
        """
        if self.canvas is None:
            return 0
        state = state if state else self.snapshot()
        try:
            percent = state['percent']
        except Exception:
            percent = 0.0
        self.show_caption()                # 等级字样：切等级／暂停都要立刻反映，不等下一帧
        return paint(self.canvas, step=(self.frame if index is None else int(index)),
                     mood=self.mood(state), percent=percent, level=self.level(state),
                     pose=self.cat.pose)

    def step(self):
        """动画帧推进：忙时 8fps、闲置 2fps（一帧只采一次进度）。

        第 17 期：顺手推一下猫样——到点就换个动作（爬行／舔爪／打哈欠／摇尾巴／撒娇）。
        第 44 期：设置里把「贴片动画」关掉就停在那一帧（帧号与猫样都不动），照旧重画——
        进度、等级、暂停这些还会跟着变，只是猫不再换动作（关掉是为了省一点 CPU）。
        """
        state = self.snapshot()
        if self.animation_enabled():
            self.frame += 1
            self.cat.next(self.frame)
        self.draw(state=state)
        self._schedule(state)
        return self.frame

    def _schedule(self, state=None):
        if getattr(self.desktop, 'shutting_down', False):
            return None
        # 一次只准有一个在排队：build() 之后再手动 step()（自测里到处在用）会叠出第二个定时器，
        # 动画双倍频，关窗时也只取消得掉最后一个——剩下那个到期就报 invalid command name "…step"。
        self._cancel_animation_timer()
        try:
            self._timer = self.win.after(self.interval(state), self.step)
        except Exception as exc:
            self.errors.append(('after', str(exc)))
            self._timer = None
        return self._timer

    def _cancel_animation_timer(self):
        """动画重排只撤销旧帧，不影响聊天、单击和主窗恢复回调。"""
        if self._timer:
            try:
                self.win.after_cancel(self._timer)
            except TclError:
                # 计时器随窗口销毁。
                pass
            self._timer = None

    def stop(self, event=None):
        if event is not None and getattr(event, 'widget', None) is not self.win:
            return None
        self.cancel_click()                # 待唤出的下拉栏一并撤掉：窗口没了，它到点就是一句报错
        # 云朵的位置重试挂在主窗口 after 队列；主窗退出不会自然调用 Cloud.close()。
        # 先收云朵，才能撤销 ``_place_window`` 的挂起重试。
        cloud = getattr(self, '_cloud', None)
        closer = getattr(cloud, 'close', None)
        if callable(closer):
            closer()
        else:
            cancel = getattr(cloud, 'cancel_deferred_render', None)
            if callable(cancel):
                cancel()
        self._cancel_animation_timer()
        if self._main_topmost_job:
            try:
                self.win.after_cancel(self._main_topmost_job)
            except TclError:
                # The root already owns no Tcl timer during teardown.
                pass
            self._main_topmost_job = None
        return self._timer

    # ── 界面搭建 ────────────────────────────────────────────────────────────
    def build(self):
        """把贴片、猫爪、等级小字与右键菜单建出来（全部 place 在既有容器里，不动原布局代码）。"""
        self._build_canvas()
        self._build_paws()
        self._build_menu()
        self.build_gear()
        self._bind()
        self.draw()
        self.lift_patch()
        self._schedule()
        return self
    def _build_canvas(self):
        import tkinter as tk
        parent = (getattr(self.desktop, 'pet_layer', None)
                  or getattr(self.desktop, 'title_row', None) or self.win)
        self.canvas = tk.Canvas(parent, width=SIZE, height=SIZE, bd=0, highlightthickness=0, bg=CANVAS_BG)
        # 第 18 期：贴片往左挪一个身位（用户要的「位置向左移动一倍距离」）——原来贴着窗口右边，
        # 猫的脸和耳朵被窗口控件压住；让出这一格，脸才是完整的。
        self.canvas.place(relx=1.0, rely=0.0, anchor='ne', x=PATCH_X, y=PET_LAYOUT['top'])
        # 第 20 期：标题行本来只有约 40 像素高，64 像素的猫脸会被它裁掉下半张（用户报「头像被遮挡一半」）。
        self._reserve_room(parent)
        # 第 16 期：单击＝收起云朵框＋唤出功能下拉栏（用户要的是「点一下就能唤出」）；
        # 双击仍然是云朵框（要说话就双击我）。
        self.canvas.bind('<Button-1>', self.pet_click)
        self.canvas.bind('<Double-Button-1>', self.double_click)
        self.canvas.bind('<Button-3>', self.popup)
        for name in ('header_status', 'header_model'):
            widget = getattr(self.desktop, name, None)
            if widget is None:
                continue
            try:
                widget.configure(padding=(0, 0, HEAD_PAD, 0))
                widget.bind('<Configure>',
                            lambda event, w=widget: w.configure(wraplength=max(120, event.width - HEAD_PAD)),
                            add='+')
            except Exception as exc:
                self.errors.append((name, str(exc)))
        # 第 18 期：贴片左边一行小字，说明现在是哪一档（正常／半自动／全自动，暂停时写「已暂停」）。
        # 用户报「模式不显示了」——它原来只体现在猫的颜色上，不写字就看不出来。
        try:
            from tkinter import ttk
            # 第 23 期：宽度钉死在 CAPTION_ROOM 上——anchor='ne' 是从右沿往左长的，
            # 不钉宽度的话「待确认 N」那一行会把小字撑到猫脸上（实测过）。
            self.caption = ttk.Label(parent, text='', style='Muted.TLabel',
                                     wraplength=CAPTION_ROOM, justify='right', anchor='e')
            # 第 21 期：小字落在三虎右边那条空档里（anchor='ne' ＋ 往内收 CAPTION_RIGHT）。
            self.caption.place(relx=1.0, rely=0.0, anchor='ne', x=-CAPTION_RIGHT,
                               y=CAPTION_Y, width=CAPTION_ROOM)
            self.show_caption()
        except Exception as exc:
            self.errors.append(('caption', str(exc)))
            self.caption = None
        return self.canvas



    def _reserve_room(self, parent, needed=True):
        """给贴片＋猫爪在标题行里留够高度（第 20 期用户报「三虎的头像被遮挡一半」）。

        贴片挂在标题行里，而标题行的高度原本是它自己那几个标签撑出来的（实测约 40 像素）。
        猫脸加下面那排猫爪一共要 PATCH_ROOM 像素，不留够就会被标题行裁掉下半张脸。
        独立窗开着时贴片收起，这里再把高度还给标题行（pack_propagate 打开＝回到标签的自然高度）。
        """
        if parent is None:
            return None
        # 主窗口提供的承载层由主窗口按项目列表顶边管理，避免贴片反向撑高标题区。
        if parent is getattr(self.desktop, 'pet_layer', None):
            return parent
        try:
            if needed:
                parent.pack_propagate(False)
                parent.configure(height=PATCH_ROOM)
            else:
                parent.pack_propagate(True)
                parent.configure(height=0)
        except Exception as exc:
            self.errors.append(('room', str(exc)))
        return parent

    def _build_paws(self):
        """三虎下方那排猫爪（第 19 期）：自动化等级外置，点哪一爪就切到哪一档。"""
        import tkinter as tk
        parent = (getattr(self.desktop, 'pet_layer', None)
                  or getattr(self.desktop, 'title_row', None) or self.win)
        self.paws = tk.Canvas(parent, width=PAW_WIDTH, height=PAW_SIZE + PAW_ARC, bd=0,
                              highlightthickness=0, bg=CANVAS_BG)
        self.paws.place(relx=1.0, rely=0.0, anchor='ne', x=PAW_ROW_X, y=PAW_Y)
        self.paws.bind('<Button-1>', self.paw_click)
        self.paws.bind('<Button-3>', self.popup)
        # 第 23 期：鼠标扫过哪只爪就把哪只提亮——三档点哪一档，扫一眼就知道。
        self.paws.bind('<Motion>', self.paw_hover)
        self.paws.bind('<Leave>', self.paw_leave)
        self.draw_paws()
        return self.paws

    def draw_paws(self, level=None, force=False):
        """按当前等级重画那排猫爪：选中的填等级色、鼠标停着的那只提亮，其余淡灰。

        档位与悬停位置都没变就不白画一遍（心跳每 150ms 会调一次）。
        """
        canvas = self.paws
        if canvas is None:
            return None
        try:
            level = self.level() if level is None else level
            key = (level, self._paw_hover)
            if not force and key == self._paws_key and canvas.find_withtag('paw'):
                return canvas
            self._paws_key = key
            canvas.delete('paw')
            for index, name in enumerate(PAW_LEVELS):
                if name == level:
                    fill, edge = PAW_COLORS.get(name, PAW_IDLE)
                elif index == self._paw_hover:
                    fill, edge = PAW_HOVER
                else:
                    fill, edge = PAW_IDLE
                for part in paw_parts(index * (PAW_SIZE + PAW_GAP), paw_dy(index)):
                    _kind, cx, cy, radius = part
                    canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                       fill=fill, outline=edge, width=2, tags=('paw', 'paw-' + name))
        except Exception as exc:
            self.errors.append(('paws', str(exc)))
        return canvas

    def paw_at(self, x):
        """横坐标落在第几只爪上（不在任何一只上返回 None）。"""
        try:
            index = int(x) // (PAW_SIZE + PAW_GAP)
        except (TypeError, ValueError):
            return None
        return index if 0 <= index < len(PAW_LEVELS) else None

    def paw_hover(self, event=None):
        """鼠标扫过那排爪：停在谁身上就把谁提亮，扫出去了就恢复。"""
        index = self.paw_at(getattr(event, 'x', None))
        if index == self._paw_hover:
            return index
        self._paw_hover = index
        self.draw_paws()
        return index

    def paw_leave(self, event=None):
        """鼠标离开那排爪：恢复成没停的样子。"""
        if self._paw_hover is None:
            return None
        self._paw_hover = None
        self.draw_paws()
        return self._paw_hover

    def paw_click(self, event=None):
        """点某个猫爪＝切到那一档（一次点到位，不用一轮一轮按）。"""
        index = self.paw_at(getattr(event, 'x', None))
        if index is None:
            return None
        return self.set_paw_level(PAW_LEVELS[index])

    def lift_patch(self):
        """三虎永远在最上层（第 19 期）：贴片、猫爪、等级小字各抬一次，别被内容框压住。"""
        for widget in (self.canvas, self.paws, self.caption):
            if widget is None:
                continue
            try:
                # 不能用 widget.lift()：Canvas 把 lift 覆写成了 tag_raise（抬手画布里的图元），
                # 无参调用只会报 wrong # args。直接走 Tcl 的 raise <窗口路径> 才是把窗口抬上去。
                widget.tk.call('raise', widget._w)
            except Exception as exc:
                self.errors.append(('lift', str(exc)))
        return self.canvas

    def _build_menu(self):
        """三虎的功能下拉栏（第 22 期／第 44 期）：越靠上越常按；等级仍由三虎身旁那排猫爪管。

        第 22 期按用户要求重排：① 独立小窗、② 自绘气泡两条彻底从功能栏拿掉；
        「暂停自动执行」改名「暂停」、「稍后再说」放回一级栏紧挨在它下面；
        「进度面板」回到功能栏（第 19 期被圆气泡顶替过），点开就是那十几行明细——
        第 24 期第 10 条：用户自己点开的这段时间里，三虎不再弹进度气泡。

        第 44 期照用户附件再对一遍：面板那一项叫「打开三虎面板」；「三虎设置」改名「设置」，
        下面四格＝基础功能／模型配置／自动化等级／预算（附件里的 SKILL 管理这一轮不做）；
        「稍后再说」改名「免打扰」；附件要的「退出」放回最后一行（按下去会先问一句）。

        第 59 期第 10 条：右键「设置」子菜单与齿轮那扇窗的分页同步（见 SETTINGS_ENTRIES）——名字一模一样。
        第 50 期第 3 条：用户报「三虎头像右键界面列表有点乱」——原来只有两条分隔线，
        十一项连成一大片。现在按用途分五块，块间用分隔线拉开：
        ① 和三虎说话（提问、一键收尾）；② 进度与待确认（面板、重试、详情、跳过）；
        ③ 设置与模型（设置、切换模型）；④ 运行状态（暂停／继续、免打扰）；⑤ 退出程序（单独一块，
        省得手一拖就点到）。块内次序照旧是「越靠上越常按」，所以只加线、不动顺序。

        第 60 期第 2 条：光有分隔线还是看不出「这一块是干什么的」——中间那三块各加一行灰色
        小标题（见 _add_section），用户扫一眼就知道该去哪一块找。头尾两块一眼就懂，不加。
        """
        import tkinter as tk
        self.menu = ContextMenu(self.win)
        # ① 和三虎说话：提问、一键收尾。
        self.menu.command('向三虎提问', lambda: self.act('chat'))
        self._add_menu('一键执行（重试＋补首帧＋日报）', lambda: self.act('oneclick'))
        self.menu.separator()
        # ② 进度与待确认的事：面板、重试、详情、跳过。
        self._add_section('进度与待确认')
        self._add_menu(PANEL_MENU_LABEL, lambda: self.act(self.show_panel, speak=False), name='panel')
        self._add_menu('重试失败项', lambda: self.act('retry'))
        self._add_menu(DETAIL_MENU_LABEL, lambda: self.act(self.show_details, speak=False))
        self._add_menu('跳过这张', lambda: self.act('skip'))
        self.menu.separator()
        # ③ 设置与模型：两子菜单。
        self._add_section('设置与模型')
        self._build_settings_menu()
        self._build_model_menu()
        self.menu.separator()
        # ④ 运行状态：自动化入口只保留猫爪，右键不再重复提供手动／全自动。
        self._add_section('运行状态')
        self._add_menu(self.pause_label(), lambda: self.act(self.pause_action), name='pause')
        self._add_menu(self.snooze_label(), lambda: self.act(self.toggle_snooze), name='snooze')
        self.menu.separator()
        # ⑤ 退出程序：单独一块（点错了真会关掉）。
        self._add_menu(QUIT_LABEL, lambda: self.act(self.quit_app), name='quit')
        return self.menu

    def pause_action(self):
        """「暂停 / 继续」按下去做什么：现在是哪一头就翻到另一头。"""
        return self.act('resume' if self.agent.paused else 'pause')

    def panel_text(self):
        """面板正文：按节分块、逐行编号（第 26 期第 4 条）。

        原来一行一条「名字：值」连着十几条，看不出哪些是「现在在做什么」、哪些是配额——
        用户报的就是「文字排版差、难阅读」。这里照 PANEL_SECTIONS 分三节，节名单独一行，
        每行「编号. 名字 · 值」；没列进分节表的新行也不会丢，统一落到最后一节。
        """
        rows = list(self.rows())
        known = {name for _title, names in PANEL_SECTIONS for name in names}
        blocks = [PANEL_HEAD]        # 第 36 期第 10 条：用户要的抬头「当前进度：」
        index = 0
        for title, names in PANEL_SECTIONS:
            picked = [(name, value) for name, value in rows if name in names]
            if not picked:
                continue
            lines = []
            for name, value in picked:
                index += 1
                lines.append('%d.%s%s%s%s' % (index, pet_cloud.NUMBER_GAP, name, PANEL_DIVIDER, value))
            blocks.append('【%s】\n%s' % (title, '\n'.join(lines)))
        rest = [(name, value) for name, value in rows if name not in known]
        if rest:
            lines = []
            for name, value in rest:
                index += 1
                lines.append('%d.%s%s%s%s' % (index, pet_cloud.NUMBER_GAP, name, PANEL_DIVIDER, value))
            blocks.append('【其它】\n%s' % '\n'.join(lines))
        return '\n'.join(blocks)

    def show_panel(self):
        """「进度面板」：在三虎旁的提示框展示分节后的完整进度，不创建弹窗。"""
        text = self.panel_text()
        self.notice = text
        self.note_panel()                      # 这次已主动查看完整进度，自动播报先让路
        self.progress_bubble(text=text)
        return text

    def pause_label(self):
        """菜单文字直接反映现在是哪一头（第 22 期：用户要的名字就是「暂停」）。"""
        return '继续' if self.agent.paused else '暂停'

    def mode_label(self):
        """控制面板入口文字始终反映三虎当前模式。"""
        return '模式：' + ('全自动' if self.mode == 'auto' else '手动')

    def _build_model_menu(self):
        """「切换模型」子菜单（第 43 期）：自动 ＋ 池里每一条（当前那条前面打 ✓）＋ 新增模型…。

        第 18 期起整栏重建一次就跟着变；第 43 期起条目来自模型池（模型管理），不再硬编码档位。
        """
        import tkinter as tk
        sub = self.menu.submenu()
        self.menu_tier = sub
        self._fill_model_menu()
        self._add_cascade(self.model_label(), sub, name='model')
        return sub

    def _fill_model_menu(self):
        """按模型池重排「切换模型」（模型管理里加／删了一条之后调它一次就跟着变）。"""
        sub = self.menu_tier
        if sub is None:
            return None
        sub.clear()
        records = self.agent_model_records()
        entries = [(model_pool.AUTO, model_pool.AUTO_LABEL)]
        entries.extend((model_id, item['label']) for model_id, item in records.items())
        entries.extend((tier, label) for tier, label in tier_models().items()
                       if tier != model_pool.AUTO and tier not in records)
        for model_id, label in entries:
            mark = '✓ ' if model_id == self.tier else ''
            sub.command(mark + label, lambda value=model_id: self.act(lambda: self.set_tier(value)))
        sub.separator()
        sub.command('+ 新增模型…', lambda: self.act(self.open_model_manager))
        return sub

    def _build_settings_menu(self):
        """「设置」子菜单（第 44 期）：基础功能／三虎模型配置／自动化等级／预算／开发信息，
        每一格开的就是齿轮那扇窗的同一页（第 59 期第 10 条：两边同步，名字也一模一样）。

        附件里还有一格「SKILL 管理」——用户这一轮说不用做，所以这里不摆，也不留空占位。
        """
        import tkinter as tk
        sub = self.menu.submenu()
        self.menu_settings = sub
        for tab, label in SETTINGS_ENTRIES:
            sub.command(label, lambda key=tab: self.act(lambda: self.open_settings(key)))
        self._add_cascade(SETTINGS_LABEL, sub, name='settings')
        return sub

    def _add_section(self, title):
        """右键栏的分块小标题：灰色的、点不动，只用来告诉用户「这一块是干什么的」。

        第 60 期第 2 条。它不记序号——事后改文字（refresh_menu_labels）只认 model／pause／snooze
        那几项，标题永远不动，也就不会被算错。
        """
        self.menu.disabled('【%s】' % title)
        return title

    def _add_cascade(self, label, menu, name=None):
        """加一个子菜单并记下它的序号（序号用来事后改文字，不用 Tk 变量）。"""
        index = self.menu.index('end')
        self.menu.cascade(label, menu)
        index = 0 if index is None else index + 1
        if name:
            self.menu_index[name] = index
        return index

    def _add_menu(self, label, command, name=None):
        """加一个菜单项并记下它的序号（序号用来事后改文字，不用 Tk 变量）。"""
        index = self.menu.index('end')
        self.menu.command(label, command)
        index = 0 if index is None else index + 1
        if name:
            self.menu_index[name] = index
        return index

    def _bind(self):
        try:
            self.win.bind('<Destroy>', self.stop, add='+')
            # stop 清理退出资源；close_chat 另负责清空聊天引用，保持绑定顺序。
            # 自绘气泡也跟着主窗口走：主窗口没了，气泡留在屏幕上就是没人管的孤儿窗。
            # 云朵框同理：主窗口没了，浮层与它的定时器都要跟着停。
            self.win.bind('<Destroy>', self.close_chat, add='+')
        except Exception as exc:
            self.errors.append(('bind', str(exc)))
    def pet_click(self, event=None):
        """左键点三虎＝开／关云朵框（第 19 期：单击直接切换，不再借道下拉栏）。

        为什么还等 CLICK_MS：第二下（双击）该由 double_click 接管，单击才真的切一次；
        下拉栏改成只跟右键，不再跟弹出的菜单抢那一下点击（“再点一下关不掉”就是这么来的）。
        """
        return self._chat_interaction.request_single()

    def cloud_visible(self, sticker_only=False):
        """云朵框这会儿是不是真露着（含云朵框／圆／标签这些贴纸形态）。

        第 23 期：把原来那个「现在露着的是不是贴纸」并进来——两处问的其实是同一件事，
        分开写迟早走偏。sticker_only=True 只认贴纸（云朵对话框不算）：播报要能接着往
        对话里写，而「随口一句」不该把用户正在看的对话窗换掉。
        """
        cloud = self._cloud
        if cloud is None or not cloud.visible:
            return False
        return (cloud.shape != pet_cloud.SHAPE_CLOUD) if sticker_only else True

    def flip_chat(self, at=None):
        """单击的落点：云朵框开着就收起（并且安静一会儿），关着就打开。"""
        return self._chat_interaction.flip(at=at)

    def mute(self, seconds=CHAT_MUTE_SECONDS, at=None):
        """安静一会儿：这段时间里自动播报与进度气泡不再往外顶（用户刚把云点掉）。"""
        try:
            now = float(self.clock() if at is None else at)
            self._mute_until = max(self._mute_until, now + max(0.0, float(seconds)))
        except (TypeError, ValueError) as exc:
            self.errors.append(('mute', str(exc)))
        return self._mute_until

    def muted(self, at=None):
        """现在是不是在「刚点掉云朵框」的安静期里。"""
        try:
            return float(self.clock() if at is None else at) < float(self._mute_until)
        except (TypeError, ValueError):
            return False
    def cancel_click(self):
        """双击与退出共用协调 module 的待单击取消入口。"""
        return self._chat_interaction.cancel_pending()

    @property
    def _click_at(self):
        """保留既有观察口径，待点击只由协调 module 写入。"""
        return self._chat_interaction.pending

    def _cancel_chat_click(self, job):
        """Tk 调度 adapter：只吞掉已经销毁的 Tcl 任务。"""
        try:
            self.win.after_cancel(job)
        except TclError:
            # 延迟任务已被 Tk 清理。
            pass

    def double_click(self, event=None):
        """双击贴片＝直接和三虎说话（云朵框以对话形态打开）。"""
        return self._chat_interaction.request_double()
    def popup_at(self, x=None, y=None):
        """把功能下拉栏弹在鼠标处；拿不到鼠标坐标（键盘／程序触发）就落在贴片下沿。"""
        if self.menu is None:
            return None
        if x is None or y is None:
            try:
                x = self.canvas.winfo_rootx()
                y = self.canvas.winfo_rooty() + self.canvas.winfo_height()
            except Exception:
                x = y = 0
        # 第 47 期第 4 条：下拉栏显示期间三虎不弹聊天框／云朵框（见 broadcast 里那道闸）；
        # 栏里那几项自己开的界面（比如「向三虎提问」）照旧，不受这道闸影响。
        self._menu_open = True
        try:
            self.menu.popup_at(int(x), int(y))
        finally:
            self._menu_open = False
            self.say_held()
        return self.menu
    def say_held(self):
        """下拉栏／弹窗收起之后，把压住的那一句补上（没有就空操作）。

        云已经露着（栏里刚点开的对话／贴纸，或者刚被弹窗赶走、正在淡出）就先留着：
        用户正看着的那一朵不该被顶掉。第 59 期第 8 条：原来这里把压住的话直接丢了（那句话其实
        连记录都没进）；现在只是再等一下，下一次心跳等云收了再补说。
        """
        text = self._held_broadcast
        if not text or self.cloud_visible():
            return ''
        self._held_broadcast = ''
        return self.broadcast(text)

    def popup(self, event=None):
        """右键贴片：同一张下拉栏（左键单击也走它）。"""
        return self.popup_at(getattr(event, 'x_root', None), getattr(event, 'y_root', None))









    def refresh(self, at=None, state=None):
        """重绘等级小字与猫爪，并把贴片抬到最上层（动画帧由定时器自己推进）。"""
        state = state if state else self.snapshot(at=at)
        try:
            self.show_caption()
            self.draw_paws()
            now = float(self.clock() if at is None else at)
            if self._lifted_at is None or (now - self._lifted_at) >= 1.0:
                self._lifted_at = now
                self.lift_patch()
        except Exception as exc:
            self.errors.append(('refresh', str(exc)))
        return self
def attach(desktop, clock=time.time, autostart=None, front=None):
    """接缝总入口：Desktop.__init__ 里调用一次，返回并挂上宠物控制器。

    第 22 期：独立小窗（pet_window）与自绘气泡（pet_toast）两个功能按用户要求整个删除，
    参数里的 window／toast 也跟着去掉——不再有「传了也没用」的空挡。
    autostart：None＝按默认（开机自启默认开着，注册表里没有就补上）、False＝一个字节都不动注册表。
    第 19 期撞掉了系统托盘，参数里不再有 tray。
    """
    pet = Pet(desktop, clock=clock, front=front)
    desktop.pet = pet
    try:
        pet.build()
    except Exception as exc:
        pet.errors.append(('build', str(exc)))
    if autostart is not False:
        pet.autostart_default()
    pet.refresh_menu_labels()
    return pet
def start(desktop, delay_ms=GREET_DELAY_MS):
    """开机那一下（第 18 期）：清掉上一次的对话，再让三虎用云朵框打个招呼。

    退回主循环之后再招呼——Desktop.__init__ 里主窗口还没映射出来，云朵框拿不到贴片的坐标。
    返回挂上的定时器；没有宠物就什么也不做。
    """
    pet = getattr(desktop, 'pet', None)
    if pet is None:
        return None
    try:
        pet.start_level()              # 第 67 期任务 4：开机一律回到「只提醒」档
    except Exception as exc:
        pet.errors.append(('start.level', str(exc)))
    try:
        pet.reset_cloud()
    except Exception as exc:
        pet.errors.append(('start', str(exc)))
        return None
    try:
        pet.recover_project_checkpoint()
    except Exception as exc:
        pet.errors.append(('start.recovery', str(exc)))
    return pet.schedule_greet(delay_ms)


def tap(desktop, label, fn):
    """接缝③：按钮的薄封装——原逻辑照旧先跑，成功后再上报「用户点了什么」。"""
    result = fn()
    pet = getattr(desktop, 'pet', None)
    if pet is not None:
        try:
            pet.tap(label)
        except Exception as exc:
            pet.errors.append(('tap', str(exc)))
    return result


def pump(desktop, limit=200, at=None):
    """接缝①：_tick_once 末尾调用——把事件搬进状态机与宠物（同一个 150ms 心跳，无新线程）。"""
    pet = getattr(desktop, 'pet', None)
    if pet is None:
        return 0
    try:
        return pet.pump(limit=limit, at=at)
    except Exception as exc:
        pet.errors.append(('pump', str(exc)))
        return 0
