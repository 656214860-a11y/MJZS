"""三虎桥接（从 desktop.Desktop 原样迁出，SPLITD 结构治理轮）。

方法体未改、self 语义不变；Desktop 通过继承 PetBridgeMixin 获得。PET_STAGE_POLL 与
UNATTENDED_SWITCH 的唯一定义在 desktop_auto_state（R2230 J15），desktop.py 仍按原名转发，
保持 ``from desktop import PET_STAGE_POLL`` 等既有入口不变。
"""
import time

from ui.desktop_auto_flows import UNATTENDED_BACKOFF_FLOOR
from orchestrator.desktop_auto_state import (
    PET_STAGE_POLL, UNATTENDED_SWITCH, UNATTENDED_SWITCH_SETTERS, flow_get, flow_set,
)
from ui.desktop_page_registry import PAGES
from contract.pet_bus import STAGES, stage_name
from contract.storyboard_paths import media_root
import orchestrator.stage_handler_registry as stage_handler_registry
from ui.pet_ui_stages import stage_run_action, skip_unchecked


class PetBridgeMixin:
    def pet_show_text(self,title,text,receipt=''):
        """宠物「查看详情」的只读文本：复用全程序唯一的只读文本窗口（prompt_window），不另造一个。"""
        from ui.prompt_window import show
        return show(self.win,title,text,status=self.status,receipt=receipt,button='复制详情')
    def pet_goto(self,stage):
        """宠物说「切到某一页」时真的把那页翻开（第 23 期）。

        页序号只认 pet_state.PAGE_OF 那一份（阶段枚举与页面一一对应）；没有项目、认不出这一步、
        页面翻不动都返回空串——聊天里先听到一句「切到「剪辑」这一步」然后什么也没发生，比不说还糟。
        返回真正翻过去的那一页标题。
        """
        import infra.pet_state as pet_state
        index=pet_state.PAGE_OF.get(stage)
        if index is None or self.root is None:return ''
        try:
            self.show(index)
        except Exception as exc:
            self.status.set('切页失败，已忽略：'+str(exc));return ''
        return PAGES[index]
    def pet_advance(self,stage):
        """宠物「自动推进」的接缝（第 23 期）：把这一步对应的无人值守轮询提前叫醒一轮。

        只把 due 拉到当前（下一次心跳就会轮到它），不碰任何开关、不代按任何按钮：
        那一步该不该跑、要怎么跑，仍然由它自己的轮询与用户在页面上勾的开关说了算。
        没项目、这一步没有轮询、正在退避（due 比正常节流周期还远）都原样不动，返回空串。
        """
        name=PET_STAGE_POLL.get(stage)
        if name is None or self.root is None:return ''
        if flow_get(self,name,'_busy',False):return ''
        now=time.monotonic()
        if flow_get(self,name,'_due',0)>now+UNATTENDED_BACKOFF_FLOOR:return ''
        flow_set(self,name,'_due',0)
        return '已把「'+stage_name(stage)+'」这一步提前叫醒一轮'
    def pet_start(self,stage):
        """第 67 期任务 5：三虎在自动档要「自动开始每个阶段的任务」。

        先把这一步的无人值守开关替他打开（用户不必自己回页面上勾），再把它提前叫醒一轮——
        开关一开，这一步的轮询从此每一轮都会接着做，直到做完（中途断了也照旧自己接着做）。
        剧本结构虽没有常驻轮询，但有一条与手动按钮相同的确定性模板执行链，单独派发；
        连贯性清单是本地规则计算，直接走与手动按钮同一个实现；其余没有无人值守的步骤（剧本、配音）老实给空串，让宠物自己说「没有能自动跑的路子」。
        """
        if stage not in (*STAGES, 'pet_performance', 'pet_test'):
            raise ValueError(f'未知阶段指令：{stage!r}')
        return stage_handler_registry.start(
            self, stage, trigger='auto', fallback=self._start_unattended_stage, skip_action=skip_unchecked,
            run_action=stage_run_action)
    def _start_unattended_stage(self,stage,trigger):
        """尚未拆出的无人值守阶段由 L3 启动适配器回调到此处。"""
        return stage_run_action(self, stage, trigger, unattended=True)

    def _execute_unattended_stage(self, stage, trigger):
        """执行 L4 启动动作。直接派发的阶段由既有批次或清单处理器收场。"""
        if self.root is None:
            return ''
        if stage == 'script_structure':
            return self.pet_script_structure_batch(trigger=trigger)
        if stage == 'continuity':
            return self.pet_continuity_ledger()
        if stage == 'keyframe':
            return self.pet_frame_batch(trigger=trigger)
        name = PET_STAGE_POLL.get(stage)
        if name is None:
            return ''
        try:
            UNATTENDED_SWITCH_SETTERS[name](self.root, True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return '阶段未派发：' + str(exc)
        title = stage_name(stage)
        awakened = self.pet_advance(stage)
        if awakened:
            return f'已自动开始「{title}」：无人值守已打开，跑完自己往下走'
        return f'「{title}」这一步已经在跑，等它收尾'

    def pet_storyboard_batch(self, trigger='manual'):
        """第 62 期任务 2：三虎要「自动制作分镜」时走这一条——与「手动制作分镜」同一份实现。

        没有可做的输入（没勾剧本、或勾中的都做好了）返回空串，让宠物自己说「没有要做的事」；
        真的派了就返回一句人话。派发本身是异步的（work 在后台线程里算），失败那句会走
        「操作未完成」的既有出口，不在这里另造一套。S03 手动发送仍复用此入口。
        """
        return stage_handler_registry.start(
            self, 'storyboard', trigger=trigger, skip_action=skip_unchecked,
            run_action=stage_run_action)

    def start_storyboard_send(self, project, request_text, named, model_snapshot):
        """S03 手动发送的 L4 适配器：保留统一注册器门禁，只替换呈现动作。"""
        context = {'project': project, 'request_text': request_text, 'named': named,
                   'model_snapshot': model_snapshot, 'started': []}
        previous = getattr(self, '_storyboard_send_context', None)
        self._storyboard_send_context = context
        try:
            result = self.pet_storyboard_batch(trigger='manual')
        finally:
            self._storyboard_send_context = previous
        if not context['started'] and isinstance(result, str) and result.strip():
            self.status.set(result)
        return bool(context['started'])

    def batch_blockers(self,source,pending):
        """用引擎自己的逐镜检查（batch_frames.shot_inputs）列出无法生成的镜头与原因。

        与批次内部判定的口径完全一致：只有真正能出图的镜头才值得启动一次批次。
        """
        from batch_frames_tool.batch_frames import load_assets,shot_inputs
        assets=load_assets(source);result=[]
        for shot in pending:
            try:shot_inputs(shot,media_root(source),assets)
            except ValueError as exc:result.append((shot['id'],str(exc)))
        return result
    def busy_reason(self):
        """当前拦着退出的那件事（没有就返回空串）。

        第 47 期第 7 条从 close 里拆出来：关窗要先知道「在等什么」，才问得出那句「要强制关闭吗」。
        """
        if getattr(self,'previs_jobs',{}).get('busy'):return '白模预演正在制作'
        if self.worker:return '有一步 Agent 任务或批量任务正在执行'
        if self.cloud_monitor_busy:return '正在查询线上任务'
        if any(v.busy or getattr(v,'optimizer_busy',False) for v in self.video_sessions.values()):
            return '视频提交、下载或提示词优化正在跑'
        return ''
    def pet_report(self,stage,text,ok=True):
        """第 47 期第 5 条：某一步的制作收了尾，说给三虎听——各页共用这一条出口。

        成了当场播报（pet.report_done）；没成仍走原来那条「待确认清单」（pet.drain），
        由三虎按自动化等级决定重试还是问用户。宠物不在（自检里的宿主）就什么都不做。
        """
        pet=getattr(self,'pet',None)
        if pet is None:return None
        # 宠物报告是阶段状态链的一部分；真实报告器故障必须让调用者看见，
        # 不能把完成／失败事件吞成“页面看似正常”。没有宠物的假宿主仍是无操作。
        if ok:return pet.report_done(str(stage),str(text))
        return pet.drain(str(stage),(False,str(text),None))
    def pet_at_stage(self,index,*,automatic=False):
        """进入制作页交给三虎统一协调：提示进度、半自动征询或全自动按 SKILL 执行。

        宠物不在、问不出来都不影响翻页——它只是搭一句话，不参与页面本身。
        """
        pet=getattr(self,'pet',None)
        if pet is None:return ''
        try:
            # 启动自动进页不得抢先打开聊天框；用户主动切页不受静默限制。
            if automatic and pet.quiet():return ''
            return pet.enter_stage(index)
        except Exception:return ''
    def pet_stage_wanted(self,index):
        """R1948：换页先记一笔用户动作（云朵停留按操作疏密伸缩），再问三虎这一页有没有待办；
        没有就连进页播报的定时器都不挂。"""
        pet=getattr(self,'pet',None)
        if pet is None:return False
        try:
            pet.note_activity()
            return bool(pet.stage_has_todo(index))
        except Exception:return False
    def pet_hides_instead_of_quitting(self):
        """常驻模式（配置里明确开）：关主窗口＝收进宠物窗，不退出。

        只有独立窗真的起来了才拦这一步：收不起来还硬拦，用户就再也关不掉程序了。
        """
        if getattr(self,'_forcing_quit',False):return False
        pet=getattr(self,'pet',None)
        if pet is None:return False
        try:return bool(pet.hide_to_pet())
        except Exception:return False
