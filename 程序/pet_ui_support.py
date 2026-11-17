"""三虎窗口（``pet_ui.Pet``）各 Mixin 共用的常量、辅助函数与小类（L4）。

从 ``pet_ui`` 模块级原样迁出（R1506）：被迁出的 Pet 方法用到的模块级名字都在这里，``pet_ui`` 重新导入，旧的 ``pet_ui.<名字>`` 引用不变。本模块不导入 ``pet_ui``，没有导入环。
"""
from ui_tokens import PET_PALETTE
import sys
import pet_agent
import contract.pet_bus as pet_bus
from pathlib import Path
from tkinter import TclError
from ui_tokens import BUTTON_BORDER_WIDTH, COLORS, CONTROL_HIT_MIN, PET_LAYOUT, SPACING

PROGRAM = Path(__file__).resolve().parent
SIZE = PET_LAYOUT['avatar_size']  # 显示与命中区域共用的贴片边长
IDLE_MS = 500                    # 闲置 2fps
ACTIVE_MS = 125                  # 忙时 8fps
CANVAS_BG = COLORS['background_primary']
SANHU_FUR = PET_PALETTE['fur']             # 与桌面图标一致的虎皮橙：三虎不再因为模式切换失去识别度
SANHU_EAR = PET_PALETTE['ear']             # 桌面图标同款暖粉耳窝
SANHU_MUZZLE = PET_PALETTE['muzzle']          # 桌面图标同款奶白口鼻
SANHU_INK = PET_PALETTE['ink']             # 厚而清晰的深蓝墨描边
SANHU_STAR = PET_PALETTE['star']            # 桌面图标右上角的青色星光
SANHU_BLUSH = PET_PALETTE['blush']           # Q 版头像的小腮红
# 第 19 期：自动化等级搬到三虎身旁——三个猫爪按钮，点哪一档就切到哪一档。
# 第 60+ 期：猫爪从三虎下方挪到三虎右侧竖向排列（用户要求），原 16px 图形与命中区不变。
PAW_SIZE = PET_LAYOUT['paw_size']                  # 单个猫爪按钮的边长
PAW_GAP = PET_LAYOUT['paw_gap']                    # 爪印之间的间距（旧横排用；竖排取消缝隙）
PAW_ARC = PET_LAYOUT['paw_arc']                    # 弧形下坠量：本期用户要「间距保持一致」，取 0＝等距直排
PAW_STEP = PAW_SIZE                                # 竖向相邻猫爪的间距：等距直排，列高与头像同高
PAW_COL_WIDTH = PAW_SIZE                           # 竖向猫爪列的宽度
PAW_COL_HEIGHT = 2 * PAW_STEP + PAW_SIZE + PAW_ARC  # 竖向排开后的画布高度（弧形为 0 时正好三格）
PAW_HIT_SIZE = CONTROL_HIT_MIN                     # 每只猫爪的键盘／鼠标命中区
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
PAW_IDLE = (PET_PALETTE['paw_idle_fill'], PET_PALETTE['paw_idle_line'])                 # 没选中的爪印：淡灰一只
PAW_HOVER = (PET_PALETTE['paw_hover_fill'], PET_PALETTE['paw_hover_line'])                # 第 23 期：鼠标停在爪上时提亮一档（可点得可预期）
PAW_GAP_Y = PET_LAYOUT['paw_gap_y']                 # 猫爪排紧贴头像下沿
# 切等级之后用圆形气泡说的那句话（用户第 19 期给的原话 ＋ 第 24 期第 4 条要的简单说明）。
# 光说「已切换」不够——用户按完不知道自己刚选了什么，所以每一档都补一句「这一档到底怎么干活」。
LEVEL_SWITCH_NOTES = {
    'hint': '只提醒：我只报进度，不自动制作。',
    'semi': '半自动：免费步骤自动做，付费前先问您。',
    'auto': '全自动：按流程制作；付费或阻塞时会停下。'}
# 第 R2933 期：三虎簇从标题行右上角搬进侧栏左下角固定底栏（齿轮之下）。
# 第 R2946 期：簇整体收成正方形——左列＝头像（上）＋等级小字（下，间距收紧）；
# 右列＝猫爪竖排，对「头像＋小字」整组垂直居中；簇区边长取「内容宽／高」较大者，
# 小字一行／两行换行时由 pet_ui_view._align_paws 随动重算，dock 高＝正方形边长。
DOCK_PAD_X = SPACING['xs'] // 2      # 头像／小字左边距（相对 pet_dock 内左列）
DOCK_PAD_TOP = SPACING['xs']          # 簇顶边距
DOCK_PAD_BOTTOM = SPACING['xs']       # 簇底边距（dock 高度合成用）
DOCK_CAPTION_GAP = SPACING['xs'] // 2  # 小字与头像间距：比原 caption_gap(sm=8) 收紧
DOCK_CAPTION_ROOM = 56                # 小字宽度：「待确认 NN」尽量一行放下（两行换行由正方形逻辑兜底）
DOCK_PAW_GAP = SPACING['sm']          # 左列（头像＋小字）与猫爪列之间的间距
DOCK_PAW_RIGHT = SPACING['sm']        # 猫爪列视觉右沿离 pet_dock 右边；命中区右沿收在 dock 内不压正文
PATCH_X = DOCK_PAD_X                  # 头像 place 的 x（anchor='nw'；运行时由 _cluster_layout 细算）
CAPTION_INK = PET_PALETTE['caption_ink']                           # 第 21 期：三档小字一律黑色（既有用例与用户要求都钉死这一色）
CAPTION_Y = DOCK_PAD_TOP + SIZE + DOCK_CAPTION_GAP
# 猫爪列不再有固定顶边：对「头像＋小字」整组垂直居中（_paw_col_top 实测小字高度）。
PAW_COL_X = -DOCK_PAW_RIGHT           # 猫爪列 place 的 x（anchor='ne'）：视觉右沿离 dock 右边 DOCK_PAW_RIGHT
# 命中区比猫爪列每侧宽出一截：承接区右沿比列右沿再出头同样的量，整列命中区右沿贴 dock 右沿。
PAW_HIT_X = PAW_COL_X - PAW_COL_WIDTH // 2 + PAW_HIT_SIZE // 2
# 簇内容总宽＝左内边距＋左列宽（头像与小字取大）＋爪列间距＋爪列宽＋右边距；
# dock 宽恒为侧栏内宽，正方形边长 side=max(本值, 内容高+边距)。
DOCK_CLUSTER_W = (DOCK_PAD_X + max(SIZE, DOCK_CAPTION_ROOM) + DOCK_PAW_GAP
                  + PAW_COL_WIDTH + DOCK_PAW_RIGHT)
# pet_dock 保留高度初值取正方形边长；运行时 pet.patch_room 跟着内容实高走。
DOCK_ROOM = DOCK_CLUSTER_W
# 第 44 期：设置入口做成齿轮；第 R2933 期改用 Fluent settings 图标（assets/nav/settings.png），
# 与侧栏导航同一套字形；PNG 缺失时退回原手绘齿轮。命中区仍是 CONTROL_HIT_MIN 的 36px。
GEAR_SIZE = 22                                    # 齿轮图形的边长
GEAR_HIT_SIZE = CONTROL_HIT_MIN                    # 齿轮按钮的命中边长
GEAR_COLOR = (COLORS['primary'], COLORS['primary_pressed'])          # 兜底手绘齿轮的齿身／描边
GEAR_HOVER = (COLORS['primary_hover'], COLORS['primary_pressed'])    # 兜底手绘齿轮的悬停加深
GEAR_TIP = '设置'
# 第 22 期重做形象：用户要的「配色冷酷、线条流畅、造型醒目」。
# 三件事怎么分：造型与线条归 paint()（尖耳、钟形脸、上挑的细长眼、长胡须）；
# 配色归这里——四档心情与三档等级共用同一枚深墨描边（#101c2b 一系），色相一律压冷，
# 冰白（ICE）只留给口鼻与眼里那一点高光。等级色仍是蓝／黄／红（用户第 20 期钉死的语义），
# 只是把三档都往冷里压了一档，配上墨色描边看不出一点甜腻。
ICE = PET_PALETTE['ice']                   # 冰白：口鼻底板与眼里那点高光
INK_SOFT = PET_PALETTE['ink_soft']              # 浅一档的墨色：胡须用它，贴着深墨描边不抢脸
TONGUE = PET_PALETTE['tongue']                # 舔爪时露出的舌头：压过的冷玫瑰
MOODS = {'idle': (PET_PALETTE['mood_idle'], PET_PALETTE['mood_idle_line'], PET_PALETTE['mood_idle_deep']),
         'busy': (PET_PALETTE['mood_busy'], PET_PALETTE['mood_busy_line'], PET_PALETTE['mood_busy_deep']),
         'worry': (PET_PALETTE['mood_worry'], PET_PALETTE['mood_worry_line'], PET_PALETTE['mood_worry_deep']),
         'paused': (PET_PALETTE['mood_paused'], PET_PALETTE['mood_paused_line'], PET_PALETTE['mood_paused_deep'])}
# 自动化等级 → 头像配色（身体色／描边色／高光色）。用户一眼就能从猫的颜色看出现在是哪一档。
# 第 20 期：用户报「自动化级别显示错误」——那排猫爪按第 19 期的新配色填（正常蓝／半自动黄／全自动红），
# 猫身子却还是第 15 期的旧配色（正常黄／半自动蓝／全自动红），同一档两个颜色（蓝爪配黄猫）。
# 现在只留这一份：猫身子、那排猫爪、等级小字共用它；PAW_COLORS 就是它的前两项（填色／描边）。
LEVEL_COLORS = {'hint': (PET_PALETTE['level_hint'], PET_PALETTE['level_hint_line'], PET_PALETTE['level_hint_deep']),
                'semi': (PET_PALETTE['level_semi'], PET_PALETTE['level_semi_line'], PET_PALETTE['level_semi_deep']),
                'auto': (PET_PALETTE['level_auto'], PET_PALETTE['level_auto_line'], PET_PALETTE['level_auto_deep'])}
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
STAGE_TODO_STATES = ('failed', 'blocked')   # R1948：进页时算「待办」的阶段状态（其余状态换页不开口）
REPORT_QUIET_SECONDS = 900.0      # 隔这么久没有新的制作动静＝这一波活干完了，该递日报了
GREET_SETTLE_POLLS = 40           # 等启动页建完最多再等这么多拍（每拍 GREET_DELAY_MS），约 18 秒
GREET_DELAY_MS = 450              # 开机招呼推迟这么久（用户嫌招呼慢，原 900）：主窗口先映射出来，云才知道往哪落
# 第 68 期任务 11：用户要「打招呼的聊天框关掉之后，再慢慢弹出其他信息」。招呼冒出来之后留
# 一段安静期：这期间自动那几路（进度播报／进度气泡／主动问一句／自动推进／失败提醒）都不出声，
# 各自的节流起算点跟着往后挪——安静期过了按正常节奏慢慢说，不会攒成一大串一起炸出来。
GREET_QUIET_SECONDS = 5.0
ONE_CLICK_TITLE = '开始自动制图'
ONE_CLICK_ASK = ('准备开始自动制图：重试失败项 → 本地补首帧 → 出今日日报。\n'
                 '会产生费用的步骤（云端首帧、视频、配音）仍然只由您在各页面自己按。\n\n现在开始吗？')
OFFER_SECONDS = 300.0                             # 同一批缺口最短隔这么久才问一次
OFFER_REPEAT = 900.0                              # 缺口没变化：也隔这么久重提一次，别一直闷着
OFFER_MAX_CHARS = 60                              # 主动问的那一句最多这么长：一眼读完
OFFER_BACKOFF_MAX = 8                             # 问了没人理就翻倍再问，最多拉到 OFFER_REPEAT 的这么多倍（2 小时）
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
PROGRESS_GAPS = 2                                 # 第 21 期：圆气泡里最多带两条缺口（原来搬整个面板，太大）
CHAT_MUTE_SECONDS = 30.0                          # 单击收起的云朵框：这段时间里自动播报不再把它顶出来
# 第 35 期第 1 条：用户切去别的应用时不再只是「每一路播报各自闭嘴」（第 30 期第 3 条那套），
# 而是三虎自己进入暂停状态——头像置灰、菜单写「已暂停」，回到助手界面再自动恢复。
AWAY_PAUSE_SECONDS = 10.0                        # 离开界面满这么久才暂停：alt-tab 一闪不折腾
# 第 37 期第 1 条：用户要「给三虎记住所有项目」。项目登记表本来就在盘上（程序目录的
# projects.json），三虎以前只看当前这一个；现在把它整本记下来：名字、在制作／已完成、
# 当前阶段与进度都念得出来，问「有哪些项目」也有得答。读盘带一层 TTL 缓存，不能每拍都读。
PROJECT_CACHE_SECONDS = 20.0                      # 项目快照最多缓存这么久
PROJECT_LIMIT = 6                                 # 一句话里最多念几个项目（再多就太长了）
PROJECT_CLOSED = '已完成'
PROJECT_OPEN = '在制作'
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
        from contract.pet_settings_contract import TABS
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
    """设置齿轮按钮（第 44 期；第 R2933 期搬进 sidebar_dock；第 R2946 期真桌面改走图标轨）。

    用户要「醒目提示」，所以它不藏在菜单里——Fluent settings 图标（PNG 缺失退回
    手绘齿轮），鼠标停上去垫一层浅灰底衬。第 45 期起不再在旁边写字（见 GEAR_TIP）。
    真 Desktop 有 ``settings_rail_button`` 时 build_gear 不再建它；无该控件的宿主
    仍把画布 pack 进 settings_gear_layer／pet_dock 等既有承载层。
    """

    def __init__(self, master, command=None, size=GEAR_SIZE, tip=GEAR_TIP, bg=CANVAS_BG):
        import tkinter as tk
        self.command = command
        self.tip_text = tip
        self.visual_size = int(size)
        self.hit_size = max(self.visual_size, GEAR_HIT_SIZE)
        self._offset = (self.hit_size - self.visual_size) // 2
        self.canvas = tk.Canvas(master, width=self.hit_size, height=self.hit_size, bd=0,
                                highlightthickness=0, bg=bg, cursor='hand2', takefocus=1)
        self._hover = False
        self._focused = False
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<Enter>', self.hover_on)
        self.canvas.bind('<Leave>', self.hover_off)
        self.canvas.bind('<FocusIn>', self.focus_on)
        self.canvas.bind('<FocusOut>', self.focus_off)
        self.canvas.bind('<Return>', self.click)
        self.canvas.bind('<Key-space>', self.click)
        self.draw()
        # 齿轮只有图形没有字：悬停／键盘聚焦时用统一 Tooltip 说出「设置」（原来 tip_text 存了却没人显示）
        self.tooltip = None
        if self.tip_text:
            from ui_widgets import Tooltip
            self.tooltip = Tooltip(self.canvas, self.tip_text)
        return None

    def _gear_image(self):
        """Fluent settings 图标（assets/nav/settings.png），与侧栏导航同一套字形；缺资源返回 None。"""
        try:
            from ui_icons import IconLoader
            return IconLoader.nav_icon(self.canvas, 'settings')
        except Exception:
            return None

    def draw(self):
        """按当前状态重画齿轮与键盘焦点环；图形尺寸不变，画布只多出命中留白。"""
        offset = self._offset
        self.canvas.delete('gear')
        self.canvas.delete('gear-focus')
        if self._focused:
            inset = BUTTON_BORDER_WIDTH
            self.canvas.create_rectangle(
                inset, inset, self.hit_size - inset, self.hit_size - inset,
                outline=COLORS['focus'], width=BUTTON_BORDER_WIDTH * 2, tags=('gear-focus',))
        if self._hover:
            # 悬停底衬：与导航钮的浅灰悬停胶囊同族（PNG 是单色字形，改不了墨色，只能垫底色）。
            self.canvas.create_oval(2, 2, self.hit_size - 2, self.hit_size - 2,
                                    fill=COLORS['surface_hover'], outline='', tags=('gear',))
        image = self._gear_image()
        if image is not None:
            self.canvas.create_image(self.hit_size // 2, self.hit_size // 2,
                                     image=image, tags=('gear', 'gear-icon'))
            return self.canvas.find_withtag('gear')
        # 兜底：PNG 缺失时退回原手绘齿轮（gear-teeth／gear-body／gear-hole 三件套）。
        shape = gear_parts(self.visual_size)
        points = tuple(value + offset for value in shape['teeth'])
        fill, outline = GEAR_HOVER if self._hover else GEAR_COLOR
        self.canvas.create_polygon(*points, fill=fill, outline=outline, width=1.4,
                                   tags=('gear', 'gear-teeth'))
        centre_x, centre_y, radius = shape['body']
        centre_x += offset
        centre_y += offset
        self.canvas.create_oval(centre_x - radius, centre_y - radius, centre_x + radius,
                                centre_y + radius, fill=fill, outline=outline, width=1.4,
                                tags=('gear', 'gear-body'))
        hole_x, hole_y, hole = shape['hole']
        hole_x += offset
        hole_y += offset
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

    def focus_on(self, event=None):
        self._focused = True
        self.draw()
        return self._focused

    def focus_off(self, event=None):
        self._focused = False
        self.draw()
        return self._focused

    def click(self, event=None):
        """点击、Enter 与空格都走同一个回调。"""
        try:
            self.canvas.focus_set()
        except TclError:
            pass
        if not callable(self.command):
            return None
        return self.command()

    def place(self, **options):
        """便利：把齿轮画布摆好（R2933 起不再有旁边的文字标签，tip 已删）。"""
        self.canvas.place(**options)
        return self.canvas

    def destroy(self):
        tip = getattr(self, 'tooltip', None)
        if tip is not None:
            try:
                tip.hide()          # Tooltip 不是控件：收浮层，不 destroy
            except TclError:
                # 销毁竞态：根窗已走后 after_cancel／destroy 会抛 TclError；其余异常须上抛。
                pass
        try:
            self.canvas.destroy()
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
    muzzle = PET_PALETTE['paused_muzzle'] if paused else SANHU_MUZZLE
    ear = PET_PALETTE['paused_ear'] if paused else SANHU_EAR
    blush = PET_PALETTE['paused_blush'] if paused else SANHU_BLUSH
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
                               fill=PET_PALETTE['glint'], outline='', tags='glint')
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
        return pose
    if pose == 'lick':
        canvas.create_line(50 + ox, 44 + oy, 58 + ox, 54 + oy, fill=body, width=6,
                           tags=('pose-lick', 'paw'))
        canvas.create_arc(27 + ox, 43 + oy, 37 + ox, 54 + oy, start=180, extent=180,
                          style='pieslice', fill=TONGUE, outline=outline, tags=('pose-lick', 'tongue'))
        return pose
    if pose == 'yawn':
        # 第 24 期第 6 条：原来打哈欠是在脸上张开一张墨色的嘴——64 像素里就是一个黑窟窿
        # （用户原话「像有个黑色大鼻子很丑」）。改成两团腮红：困意靠脸红说，脸不用张开。
        for side in (13, 43):
            canvas.create_oval(side + ox, 37 + oy, side + 8 + ox, 44 + oy, fill=blush,
                               outline='', tags=('pose-yawn', 'blush'))
        return pose
    if pose == 'wag':
        sway = 6 if step % 2 else -6
        canvas.create_line(56 + ox, 54 + oy, 63 + ox, 54 + sway + oy, smooth=True,
                           fill=outline, width=3, tags=('pose-wag', 'tail'))
        return pose
    if pose == 'nuzzle':
        for side in (14, 42):
            canvas.create_oval(side + ox, 40 + oy, side + 8 + ox, 46 + oy, fill=blush,
                               outline='', tags=('pose-nuzzle', 'blush'))
    return pose
def accepts_keyword(func, name):
    """func 能不能按关键字收 name：先看签名，再只调一次。

    不用「带上调、遇 TypeError 再不带重调」：那会把实现内部抛出的 TypeError 当成签名不符，
    同一件事再做一遍。签名读不出来时按能收处理。"""
    import inspect
    try:
        parameters = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return True
    return any(item.kind is item.VAR_KEYWORD
               or (item.name == name and item.kind in (item.POSITIONAL_OR_KEYWORD, item.KEYWORD_ONLY))
               for item in parameters)
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
    from domain.storyboard_rows_service import shot_stats as _shot_stats
    return _shot_stats(paths)
def asset_counts(base):
    """资产库：登记的资产数，以及其中已经有图片的个数（与无人值守同一口径）。"""
    from orchestrator.legacy_compat import optional_asset_counts
    return optional_asset_counts(base, pet_bus.read_json)
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
    from contract.platform_tools import windows_registry
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
