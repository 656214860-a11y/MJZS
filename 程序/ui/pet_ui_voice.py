"""三虎的播报、对话、报告与项目概览。

从 ``pet_ui.Pet`` 原样迁出（R1506）：方法体未改，``self`` 语义不变，``Pet`` 通过继承
``PetVoiceMixin`` 获得；用到的模块级名字来自 ``pet_ui_support``。
"""
import datetime
import re
import pet_agent
import contract.pet_bus as pet_bus
import ui.pet_cloud as pet_cloud
import ui.pet_report as pet_report
import infra.pet_state as pet_state
from infra.broadcaster import Broadcaster, PREFIX_PATTERNS
from pathlib import Path
from tkinter import TclError
from ui.pet_ui_support import AWAY_PAUSE_SECONDS, BANNER_HOUR, BROADCAST_BUSY, BROADCAST_IDLE, CAPTION_INK, CHAT_HINT, FALLBACK_ASK, GAP_SECONDS, GREET_DELAY_MS, GREET_QUIET_SECONDS, GREET_SETTLE_POLLS, LEVEL_CAPTIONS, OFFER_BACKOFF_MAX, OFFER_MAX_CHARS, OFFER_NO, OFFER_REPEAT, OFFER_SECONDS, OFFER_YES, PAGE_ASKS, PAUSED_CAPTION, PROGRESS_GAPS, PROGRESS_SECONDS, PROJECT_CACHE_SECONDS, PROJECT_CLOSED, PROJECT_LIMIT, PROJECT_OPEN, REPORT_QUIET_SECONDS, SPEAK_GAP_SECONDS, SPOKEN_KEEP, WEEKLY_FROM, asset_counts, duration, shot_stats



def offer_verdict(word):
    """「要不要一键执行」的回答：True 开工、False 先放着、None 不是在答这个问题。

    整句命中词表最准；再认「不用了谢谢」「好啊做吧」这种以答词起头的说法，否定先认。
    """
    if word in OFFER_YES:
        return True
    if word in OFFER_NO:
        return False
    if any(word.startswith(no) for no in OFFER_NO if len(no) > 1):
        return False
    if any(word.startswith(yes) for yes in OFFER_YES if len(yes) > 1):
        return True
    if len(word) <= 4 and word[:1] in '好行':
        return True                    # 「好啊做吧」「行吧」；「是什么」这类问句不算点头
    return None


def offer_sentence(parts):
    """主动问的那一句：只说头一件缺口和一共几件，导航与花钱说明留给「查看详情」。

    原来把每条缺口连同「阶段 → 手动xxx」全拼进来，再跟两段括号，用户嫌长、不合时宜。
    """
    heads = [re.sub(r'（[^（）]*→[^（）]*）', '', str(part)).strip() for part in parts]
    head = heads[0] if heads else ''
    more = '等 %d 件事' % len(heads) if len(heads) > 1 else ''
    text = '%s：还差 %s%s，要我一键执行免费的部分吗？回「好」开工／「先不用」。' % (
        pet_agent.PET_NAME, head, more)
    if len(text) > OFFER_MAX_CHARS:
        text = text[:OFFER_MAX_CHARS - 1] + '…'
    return text


def offer_reply(verdict):
    """认出回答后的结论：与 Agent.dispatch 同形状，动手照旧交给界面线程的 run_plan。

    已经在气泡里点过头了，一键执行就不再弹第二次确认（见 one_click 的 confirm 参数）。
    """
    if verdict:
        return {'reply': '好，这就一键执行。',
                'plan': {'intent': 'oneclick', 'params': {'confirmed': True}},
                'decision': {'run': True, 'reason': ''}}
    return {'reply': '好，那先不动手；想收尾的时候说一句「一键执行」就行。',
            'plan': {}, 'decision': {'run': False, 'reason': ''}}


def offer_backoff(signature, last_signature, still_open, backoff, declined):
    """这次要问时更新追问节奏，返回 (backoff, declined)。"""
    if signature == last_signature and still_open:
        # 上回问了没人理：下一次再隔久一点，最多拉到 OFFER_BACKOFF_MAX 倍
        return min(OFFER_BACKOFF_MAX, backoff * 2), declined
    if signature != last_signature:
        return 1, None
    return backoff, declined


class PetVoiceMixin:
    """Pet 的播报与对话方法集（见模块说明）。"""
    def say(self, text):
        """接缝④：状态栏原文照旧，宠物只做合并与计数（重复的一句只算一次）。"""
        text = str(text or '').strip()
        if not text or not self.bstate.remember_status(text):
            return None
        if text in self._tick_texts:
            return None                   # 这一轮已经从自动任务队列报过，不再重复记一笔
        self._tick_texts.add(text)
        # step=True：这是「正在做的那一步」的原文，进台账与进度面板，但不进云朵记录（第 24 期第 5 条）
        return self.agent.notifier.add(text=text, step=True)
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
            if not self.can_pop():
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
        return offer_sentence(parts)
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
            if self.offer.at is None:
                self.offer.at = now           # 第一拍只对表：间隔从这一刻起算
                self.offer.sig = signature
                return ''
            if not signature:
                self.offer.open = False
                return ''
            if self.cloud_visible() or self.muted(at=at) or self.snoozing() or self.agent.paused:
                return ''
            if not self.can_pop():
                return ''                      # 用户在别的应用里：不主动问（第 30 期第 3 条）
            state = state if state else self.snapshot(at=at)
            if self.busy(state=state):
                return ''
            waited = now - self.offer.at
            if waited < OFFER_SECONDS:
                return ''
            if signature == self.offer.declined:
                return ''                      # 用户刚说过「先不用」：这批缺口不再追问
            if signature == self.offer.sig and waited < OFFER_REPEAT * self.offer.backoff:
                return ''
            self.offer.backoff, self.offer.declined = offer_backoff(signature, self.offer.sig, self.offer.open, self.offer.backoff, self.offer.declined)
            self.offer.at = now
            self.offer.sig = signature
            self.offer.open = True
            # 第 26 期第 5 条：这是一句「要不要办」的询问，用绿色对话框（长句子也放得下）
            text = self.offer_text(parts)
            self.agent.pending_offer = text
            return self.broadcast(text, at=at, shape=pet_cloud.SHAPE_CLOUD)
        except Exception as exc:
            self.errors.append(('offer', str(exc)))
            return ''
    def answer_offer(self, text):
        """认下用户对那个问题的回答（第 25 期第 3 条）：还在问就当场给结论。

        只在这个问题挂着的时候认，而且只认几个明确的说法——「好」「1」这种短句在别的场合都是
        没头没尾的，不能一律当成「开工」。结论形状见 offer_reply；没认出来返回 None，照常走规则表。
        """
        if not self.offer.open:
            return None
        word = ' '.join(str(text or '').split()).strip(' 。．，,!！?？~')
        verdict = offer_verdict(word)
        if verdict is None:
            return None
        self.agent.pending_offer = ''
        if verdict:
            self.offer.open = False
            return offer_reply(True)
        self.offer.open = False
        # 用户说了先放着：同一批缺口今天不再问（原来清空 _offer_at，反倒更快再问一遍）
        self.offer.declined = tuple(self.offer.sig or ())
        return offer_reply(False)
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
            import orchestrator.storyboard_selection as storyboard_selection
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
            if not self.can_pop():
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
        if not text or self.bstate.is_repeat(text):
            return ''
        if self.speech_blocked(text):
            return ''
        self.bstate.spoke(text)
        message = self._record_output(text)
        cloud = self.cloud()
        if cloud is not None:
            try:
                if not self.can_pop():
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
            self.offer.at = now
            self.bstate.mark_advance(now)
            # 安静期不需要新盘点；结束时再按实际缺口对表，避免首屏心跳递归读盘。
            self._gap_sig = tuple(self._gap_cache)
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
        if not self.window_visible() or not self.can_pop() or (scheduled and _startup_page_busy(self)):
            if scheduled:
                self.schedule_greet()     # 启动招呼等窗口回到前台、启动页建完，不让报表抢先
            return ''
        cloud = self.cloud()
        if cloud is None:
            return ''
        try:
            # 开机只留一条问候：使用说明不能与正式招呼同时留在记录里。
            # 后续仍经 broadcast 统一加前缀、写日志和显示。
            cloud.lines = []
            cloud._scroll = 0
            self.bstate.last_broadcast = ''
            message = self._record_output(pet_cloud.GREETING)
            self.bstate.spoke(pet_cloud.GREETING)
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
        if not self.can_pop():
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
        if not self.can_pop():
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
        if self.cloud_visible() or self.muted(at=at) or not self.can_pop():
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
        """项目登记表（只读）：只认宿主注入的那一份，拿不到就报缺，不自行开文件。"""
        info = getattr(getattr(self.desktop, 'projects', None), 'info', None)
        if isinstance(info, dict) and isinstance(info.get('projects'), list):
            return info
        self.errors.append(('projects.read', '宿主未提供项目登记表'))
        return {}
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
        cloud = None if self.login_locked() else self.cloud()      # R2051：登录闸挡着不开对话框
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
            if not getattr(cloud, 'choice', ''):
                cloud.append(self._record_output(self.chat_hello()))      # 第 24 期第 1 条：一打开，三虎先问这一页该做的事
        except Exception as exc:
            self.errors.append(('chat.hello', str(exc)))
        self.notice = '云朵框已打开：三虎问的是这一页该做的事，在回复框按回车它就去办'
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
        if self._menu_open or self.modal_grabbed() or self.login_locked():
            self.bstate.hold(text)
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
        if not self.can_pop():
            return ''                          # 用户在别的应用里：失败提醒先记着，不弹（第 30 期第 3 条）
        try:
            failures = [item for item in self.agent.failures if isinstance(item, dict)]
        except Exception as exc:
            self.errors.append(('announce', str(exc)))
            return ''
        stamp = tuple(sorted('%s|%s' % (item.get('stage', ''), item.get('category', ''))
                             for item in failures))
        if not self.bstate.new_failure_batch(stamp):
            return ''
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
    def caption_text(self):
        """三虎图像下方那行小字：哪一档自动化等级；暂停时写「已暂停」（第 18 期）。

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
        # 第 R2933 期补：这行小字宽度钉死在 DOCK_CAPTION_ROOM 上，「待确认 N」另起一行，
        # 两行换行时猫爪列底边跟着小字底边走（pet_ui_view._align_paws）。
        return '%s\n待确认 %d' % (text, pending) if pending else text
    def show_caption(self):
        """把等级字样写到三虎图像下方（写不进去就少一行字，不影响别的）。"""
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


def _startup_page_busy(pet):
    """启动页还在后台建（版面计算会占住主线程 1～3 秒）时先别冒：云朵的重绘会把它整笔吞进
    揭开后的第一秒。上限 GREET_SETTLE_POLLS 拍，页面迟迟不就绪也不能让招呼永远不来。"""
    if getattr(pet.win, '_desktop_startup_settled', True):
        return False
    waited = getattr(pet, '_greet_settle_waits', 0)
    if waited >= GREET_SETTLE_POLLS:
        return False
    pet._greet_settle_waits = waited + 1
    return True
