"""首帧／视频／配音／剪辑／交付与连贯性／动态分镜页。

从 ``desktop.Desktop`` 原样迁出（R1505）：方法体未改，``self`` 语义不变，``Desktop`` 通过继承
``MediaPagesMixin`` 获得。测试按 ``desktop.<名字>`` 打补丁的名字（confirm／open_path 等）经
``Desktop`` 注入的 ``MediaPageServices`` 在调用时取 ``desktop`` 的当前值，补丁照常生效（R1983 J2）。
"""
import pet_state
import json
import threading
import contract.pet_bus as pet_bus
import tkinter as tk
import ui_plugin_registry
from agent.core import read
from app import App
import orchestrator.media_page_controller as media_logic
import video_progress
from local_video import skip_summary
from pathlib import Path
from contract.platform_tools import launch_windows_app, open_target, tcp_listener
from domain.project_naming import dated_path
from responsive_ui import FlowBar, MIN_COL, auto_columns, fit_row_height, refresh_request_width, remember_columns
from contract.storyboard_paths import media_root
from tkinter import ttk
from ui_tokens import CHAR_WIDTH, COLORS, SPACING, TABLE_HEADER_FONT, TABLE_ROW_FONT, TEXT_DESC
from ui_widgets import Card, DataTable, DescriptionBlock, PrimaryButton, SecondaryButton, ask_string
from dataclasses import dataclass
from typing import Callable
from desktop_page_support import ASSET_ROW_LABEL, STAGE_ACTION_WIDTH, _prefs

PAGE = pet_state.PAGE_OF
VIDEO_PROMPT_FLOW = 'video_prompt'  # workflow_settings.FLOWS 里的键；原写 'final' 会抛“未知的工作流入口”


@dataclass(frozen=True)
class MediaPageServices:
    """配音／后期／交付页用到的宿主服务；``Desktop`` 注入，页面不读全局宿主。"""
    open_path: Callable
    file_dialog: Callable
    confirm: Callable
    open_studio: Callable
    comfy_executable: Callable
    find_editor_shortcut: Callable


def _configure_table_style(tree):
    """清单表的表头与行字体取自 ui_tokens，避免每张表各写一套。"""
    style = tree.cget('style') or 'Treeview'
    current = ttk.Style(tree)
    current.configure(style, font=TABLE_ROW_FONT)
    current.configure(style + '.Heading', font=TABLE_HEADER_FONT,
                      foreground=COLORS['text_primary'])
    fit_row_height(tree, 0, style=style)


class MediaPagesMixin:
    """Desktop 的制作后段页面方法集（见模块说明）。"""
    def edit_ready(self):
        """整集「已验收」就绪判定：返回 (验收状态签名, 成片指纹)。

        验收状态没变就不重新校验整集成片（否则每轮把所有成片重读一遍）；签名与指纹放在一处算，
        自动粗剪和自动整理交接包共用同一次校验，避免同一批验收结果被哈希两遍。
        """
        studio=self.studio
        # 签名必须带上分镜文件（见 media_page_controller.edit_ready_signature）。
        signature=media_logic.edit_ready_signature(studio)
        if signature!=getattr(self,'edit_ready_signature',None):
            self.edit_ready_signature=signature
            self.edit_ready_digest,_waiting=studio.auto_edit_ready()
        return signature,getattr(self,'edit_ready_digest',None)
    def keyframe_signature(self,source,pending):
        """「这一批缺首帧的镜头」的指纹：带上每镜还缺几张参考图。

        资产补齐后清单会变，于是自动补首帧能再跑一轮（否则参考图缺失的镜头跑过一遍就再也不会重试）；
        无人值守与「一键执行」共用同一份指纹，两条路派发出来的批次不会互相再触发一次。
        """
        from asset_batch_state_service import ready_asset_ids
        from asset_context import references
        from domain.keyframe_batch import batch_signature
        return batch_signature(source,pending,ready_asset_ids(self.asset_base()),references)
    def keyframe_settings(self):
        """「首帧制作」窗口保存的本地 ComfyUI 设置里还缺哪几项；空列表表示已就绪。"""
        from keyframe_comfy import missing_settings, saved_settings
        values={key:value for key,value in saved_settings().items() if key not in ('shot_ids','shot_id')}
        return missing_settings(values)
    def keyframe_batch_state(self,check_settings=False):
        """「现在能不能补首帧」的唯一判据：返回 (source, pending, reason, warn)。

        reason 为空串＝可以立刻派发；否则是不能派发的原因。warn=True 表示这个原因值得写进状态栏
        并记住这一批（本地引擎没配好、整批镜头缺参考资产），warn=False 只是这一轮先让路
        （有别的批次在跑、定稿在等），安静等下一轮就行。
        check_settings 只在「用户按了按钮」时打开：无人值守那条路由 auto_batch 自己报设置缺失，
        提前检查会让自检依赖本机有没有配过 ComfyUI。
        """
        if self.root is None or self.studio is None:
            return None,[],'',True
        try:source=self.current_frame_json()
        except ValueError:
            return None,[],'',True
        if source is None or not Path(source).is_file():
            return None,[],'',True
        from keyframe_comfy import pending_shots
        pending=pending_shots(read(source).get('shots'),media_root(source))
        if not pending:
            return source,[],'',True
        reason,warn=media_logic.keyframe_batch_verdict(
            pending,lambda:self.auto.keyframe_busy or self.worker or self.final_holding(),
            self.keyframe_settings,lambda:self.batch_blockers(source,pending),skip_summary,check_settings)
        return source,pending,reason,warn
    def start_keyframe_batch(self,label,check_settings=False,unless_signature=None):
        """补首帧的唯一派发实现：无人值守的定时轮询与宠物「一键执行」都走这里。

        返回 (是否派发, 一句中文结果, 清单指纹)；没有缺口时是 False／''／None——
        「没有缺口」与「有缺口但补不了」必须分开，前者不该打扰任何人。
        unless_signature 是「这一批已经处理过」的指纹：命中就只回指纹、不派发，让无人值守
        能先判重再动手（批次还在跑的时候，同一批镜头不会再被重复下单）。用户按下的按钮不传它。
        """
        source,pending,reason,warn=self.keyframe_batch_state(check_settings=check_settings)
        if source is None or not pending:return False,'',None
        signature=self.keyframe_signature(source,pending)
        if signature==unless_signature:return False,'',signature
        if reason:return False,'首帧未补：'+reason,signature if warn else None
        self.auto.keyframe_blocked=None
        self.auto.keyframe_busy=True
        self.auto.keyframe_ticket+=1
        ticket=self.auto.keyframe_tasks.submit(self.auto.keyframe_ticket,project=getattr(self,'root',None))
        self.status.set(label+'：准备用本地 ComfyUI 按分镜顺序补 '+str(len(pending))+' 镜首帧…')
        def worker():
            from keyframe_comfy import auto_batch
            try:self.auto.keyframe_queue.put((ticket,True,self.auto.keyframe_tasks.run(ticket,lambda:auto_batch(source,lambda text:self.auto_keyframe_log(ticket,text))),signature))
            except Exception as exc:self.auto.keyframe_queue.put((ticket,False,label+'未完成：'+str(exc),signature))
        threading.Thread(target=worker,daemon=True).start()
        return True,'已按分镜顺序派发 '+str(len(pending))+' 镜首帧（本地 ComfyUI 免费后端，未运行会自动启动）',signature
    def pet_frame_batch(self, trigger='manual'):
        """宠物「一键执行」的首帧缺口：本地 ComfyUI 就绪时按分镜顺序补一批缺首帧的镜头。

        不读「无人值守自动补首帧」开关——用户按下的按钮就是他的显式意思；也不会去碰付费的
        Seedream 通道，花钱的一律等人自己按。派发与无人值守共用同一份实现（见 start_keyframe_batch）。
        返回一句中文结果；手动入口在没项目、没缺口时仍返回空串。自动入口已经把
        keyframe 标为 active，必须把同样的前置条件转为明确阶段终态，不能静默卡住。
        """
        sent,message,_signature=self.start_keyframe_batch('一键执行',check_settings=True)
        if trigger != 'auto' or sent:
            return message
        return self._finish_unsent_auto_keyframe(message)
    def _finish_unsent_auto_keyframe(self,message):
        """把首帧自动入口未派发的结果转为明确的三虎阶段终态。"""
        pet=getattr(self,'pet',None)
        if message:
            error=message
            if pet is not None:
                pet._emit('stage.failed',stage='keyframe',error=error)
            return error
        source,pending,_reason,_warn=self.keyframe_batch_state(check_settings=True)
        if source is not None and not pending:
            text='首帧已齐全，无需制作'
            if pet is not None:
                pet._complete_if_verified('keyframe', text)
            return text
        error='未找到可用分镜，无法制作首帧'
        if pet is not None:
            pet._emit('stage.failed',stage='keyframe',error=error)
        return error
    def auto_keyframe_log(self,ticket,text):
        # 工作线程回调：只入队，由主循环写状态栏，线程里不碰 Tk。
        self.auto.keyframe_messages.put((ticket,str(text)))
    def auto_video_log(self,ticket,text):
        # 工作线程回调：只入队，由主循环写状态栏，线程里不碰 Tk。
        self.auto.video_messages.put((ticket,str(text)))
    def continuity_ledger_data(self):
        """现场算一份连贯性台账：读当前分镜 JSON ＋ 这一集的资产清单（第 61 期 v0.8 任务 7）。"""
        return media_logic.build_ledger(lambda:read(self.current_frame_json()),self.asset_requirements)
    def continuity_folder(self):
        """这一阶段落盘的地方（03_continuity/output）。"""
        return media_logic.continuity_folder(self.root)
    def write_continuity_ledger(self,ledger=None):
        """把台账落到 03_continuity（第 62 期任务 11：这一步成了独立的一页，清单由「手动生成」写）。"""
        from continuity_ledger import write
        return write(self.root,self.continuity_ledger_data() if ledger is None else ledger)
    def generate_continuity_ledger(self,ledger=None):
        """生成连贯性清单：手动按钮与三虎自动链共用的唯一实现（落盘＋同步问题登记＋播报）。"""
        ledger=self.continuity_ledger_data() if ledger is None else ledger
        summary=ledger.get('summary') or {}
        if not summary.get('shots'):
            raise ValueError('当前没有可用的分镜镜头，请先在「初步分镜」采用一份分镜再生成连贯性清单。')
        self.write_continuity_ledger(ledger)
        self.sync_continuity_issues(ledger)
        text=media_logic.summary_text(summary)
        self.pet_report('continuity','连贯性清单已生成：'+text+'。')
        self.status.set('连贯性清单已生成并落盘：'+text)
        if getattr(self,'page_index',None)==PAGE['continuity']:self.show(PAGE['continuity'])
        return text
    def pet_continuity_ledger(self):
        """三虎自动链的连贯性清单入口（经 stage_handler_registry.start 的回调）；没有分镜时返回空串。"""
        try:return '已自动生成「连贯性清单」：'+self.generate_continuity_ledger()
        except ValueError:return ''
    def continuity_page(self):
        """06 连贯性清单（第 62 期任务 11）。

        第 61 期 v0.8 它只是资产管理页底部的一个折叠区；用户要它成为独立的一步（左侧列表
        「05 资产管理」之下、「07 分镜定稿」之上），显示方式照首帧管理页那一套：上面一行按钮，
        下面按组各一张表。表里的数字全部来自同一次台账计算，页面上写的批次、镜头与结论不会
        各说各话（第 62 期任务 11 的「信息要准确」）。
        """
        from stage_execution_service import run_stage_confirmation_gate
        ledger=self.continuity_ledger_data()
        summary=ledger.get('summary') or {}
        passed=bool(summary.get('ok'))
        def line():
            return media_logic.summary_text(summary)
        def make():
            self.generate_continuity_ledger(ledger)
        bar=FlowBar(self.content);bar.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        ttk.Label(bar,text='清单',width=ASSET_ROW_LABEL).pack(side='left')
        _make=PrimaryButton(bar,text='手动生成连贯性清单',style='Primary.TButton',width=STAGE_ACTION_WIDTH,command=lambda:self.safe(make))
        _make.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs'])
        ui_plugin_registry.module('stage_flow').follow(_make,'continuity')     # 三虎在跑这一步就写「自动执行中」并置灰
        # R2942：「阶段配置」按钮＋模型下拉框删除。
        SecondaryButton(bar,text='清单目录',style='Asset.TButton',
                   command=lambda:self.safe(lambda:self.media_page_services.open_path(self.continuity_folder()))).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        head=ttk.Frame(self.content);head.pack(fill='x',pady=(SPACING['xs'],SPACING['none']))
        ttk.Label(head,text=line(),foreground=COLORS['success_text'] if passed else COLORS['warning_text']).pack(side='left')
        file=self.continuity_folder()/'continuity_ledger.json'
        DescriptionBlock(head,text=('已落盘：'+file.name) if file.is_file() else '还没生成，按左边的按钮生成').pack(
            side='left',padx=(SPACING['sm'],SPACING['none']))
        def table_of(title,columns,rows,height,detail=''):
            """一张小表：抬头 ＋ 表头 ＋ 若干行（这一页的清单就是这几张表）。

            第 64 期任务 6：最后一列（「冻结锚点」「说明」）跟着窗口一起收放——原来固定
            620／700 像素，界面一窄就被挤没、界面一宽又留一大片白。detail 写某一列时，
            点这一列的格子弹一扇只读窗把整段字显示全（表格格子放不下长说明）。
            """
            frame=Card(self.content)
            frame.pack(fill='both',expand=True,pady=(SPACING['xs'],SPACING['none']))
            ttk.Label(frame,text=title).pack(anchor='w')
            compact=[(key,label,MIN_COL) for key,label,width in columns]
            table=DataTable(frame,columns=compact,show='headings',height=height,
                            selectmode='browse',empty_text='暂无'+title)
            tree=table.tree
            _configure_table_style(tree)
            last=columns[-1][0]
            for key,label,width in columns:
                tree.heading(key,text=label)
                tree.column(key,width=MIN_COL,minwidth=MIN_COL,stretch=key==last)
            remember_columns(tree,[(key,width) for key,label,width in columns])
            auto_columns(tree)
            refresh_request_width(tree)
            for row in rows:tree.insert('','end',values=row)
            table.pack(fill='both',expand=True)
            if detail:
                def open_detail(event,tree=tree,column_name=detail,heading=title):
                    row=tree.identify_row(event.y);column=tree.identify_column(event.x)
                    if not row or not column:return
                    if tree.column(column,'id')!=column_name:return
                    text=str(tree.set(row,column_name) or '')
                    if not text:return
                    from prompt_window import show as show_text
                    show_text(self.win,heading+' · 说明',text,status=self.status,
                              receipt='说明已复制',button='复制说明',scrollbar=True)
                tree.bind('<Button-1>',open_detail,add='+')
            return tree
        batches=media_logic.batch_rows(ledger)
        table_of('批次与冻结锚点',
                 [('batch','批次',120),('shots','镜头',200),('seconds','秒数',70),
                  ('anchors','冻结锚点（逐字复用，机器不许改写）',620)],
                 batches,min(8,max(2,len(batches))))
        checks=media_logic.check_rows(ledger)
        table_of('跨批次与三元组校验',
                 [('kind','项目',110),('id','编号',150),('result','结论',100),('detail','说明',700)],
                 checks,min(8,max(2,len(checks))),detail='detail')
        issue_rows=self.continuity_issue_rows(ledger)
        if issue_rows:
            table_of('问题闭环',
                     [('id','编号',130),('kind','类型',110),('severity','严重度',60),
                      ('state','状态',80),('where','涉及镜头/资产',170),('evidence','证据',560)],
                     media_logic.issue_table_rows(issue_rows),min(8,max(2,len(issue_rows))),detail='evidence')
        problems=list(summary.get('problems') or [])
        foot=Card(self.content);foot.pack(fill='x',pady=(SPACING['xs'],SPACING['none']))
        ttk.Label(foot,text='待办与裁决').pack(anchor='w')
        if problems:
            for text in problems[:8]:ttk.Label(foot,text='· '+text,wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w')
        else:
            ttk.Label(foot,text='没有待办：批次、锚点与三元组都对得上。',foreground=COLORS['success_text']).pack(anchor='w')
        asks=run_stage_confirmation_gate(self.root, 'G-08', ledger=ledger).get('ask') or ()
        if asks:
            ttk.Label(foot,text='参考图优先级（每条选一个，问过就不再问）：',
                      foreground=COLORS['warning_text']).pack(anchor='w',pady=(SPACING['xs'],SPACING['none']))
        for item in asks:
            box=ttk.Frame(foot);box.pack(fill='x',anchor='w',pady=SPACING['xs'])
            text=' ／ '.join('候选%d %s'%(index+1,value)
                            for index,value in enumerate(item['candidates']))
            ttk.Label(box,text=item['title']+'：'+text,wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w')
            DescriptionBlock(box,text='理由：'+str(item.get('reason') or '')).pack(anchor='w')
            choice=item['candidates'][item.get('recommended',0)]
            PrimaryButton(box,text='采用推荐',
                       command=lambda key=item['key'],value=choice,digest=item.get('digest',''):self.safe(
                           lambda:self.pick_gate(key,value,
                               lambda:self.show(PAGE['continuity']),digest))).pack(anchor='w')
        for row in media_logic.open_issues(issue_rows):
            box=ttk.Frame(foot);box.pack(fill='x',anchor='w',pady=SPACING['xs'])
            ttk.Label(box,text='%s %s：%s'%(row.get('severity') or '',row.get('id') or '',
                                          row.get('detail') or ''),wraplength=TEXT_DESC['wraplength'],justify='left').pack(anchor='w')
            SecondaryButton(box,text='忽略（写明理由）',
                            command=lambda iid=row.get('id'):self.safe(lambda:self.ignore_continuity_issue(iid))).pack(anchor='w')
    def continuity_issue_rows(self,ledger):
        """问题闭环视图：登记表与本次台账合并后的行（只读，不落盘）。"""
        from stage_execution_service import continuity_issue_report
        try:return list(continuity_issue_report(self.root,ledger))
        except (ValueError,OSError,TypeError,AttributeError,KeyError):return []
    def sync_continuity_issues(self,ledger=None):
        """把本次问题并进 03_continuity/output/continuity_issues.json（跟「手动生成」同一次做）。"""
        from stage_execution_service import sync_continuity_issues
        try:return list(sync_continuity_issues(self.root,ledger))
        except (ValueError,OSError,TypeError,AttributeError,KeyError) as exc:
            self.status.set('问题闭环台账没写成：'+str(exc));return []
    def ignore_continuity_issue(self,iid):
        """忽略一条问题：必须先写理由（记下当时那一版证据），再刷新页面。"""
        reason=ask_string(self.win,'忽略这条问题','忽略这条问题的理由：')
        if reason is None:return
        reason=str(reason).strip()
        if not reason:
            self.status.set('没写理由，这条问题不忽略。');return
        from stage_execution_service import decide_continuity_issue
        decide_continuity_issue(self.root,iid,'ignored',reason)
        self.status.set('已忽略 '+str(iid)+'（理由与作用版本已记录）。')
        self.show(PAGE['continuity'])
    def comfy_listening(self,timeout=0.3):
        """本地 ComfyUI 端口上是否已有实例在听：只做 TCP 连接，不发 HTTP 请求。

        旧实现同步发一次 /system_stats 并等满 3 秒：ComfyUI 刚被拉起（端口已开、还没开始
        应答）或端口被防火墙丢包时，点「开始生成」「启动并检测」整机界面就僵住约 3 秒，
        表现出来正是「点了就卡死」。启动只关心「有没有实例在跑」，连得上就说明有；
        真正就绪与否由工作线程里的 wait_comfy 去等，不该占用界面线程。
        """
        return tcp_listener(self.settings.get('comfy_url','http://127.0.0.1:8188'), timeout=timeout)
    def launch_comfy(self,silent=False):
        # 先看端口再看桌面程序：ComfyUI 已经在跑时根本不需要程序路径，
        # 也就不该因为没配 exe 而弹出选择框拦住正在生成的用户。
        #
        # 第 62 期任务 8：silent=True 是「制作链路自动拉起」这一路——「手动制作资产」「手动
        # 制作首帧」点下去自己开始跑，这时再弹一个「选择 ComfyUI 桌面程序」会把用户从正在
        # 做的事里拽出来（用户报的就是这个）。静默这一路找不到程序就写一句人话收手，
        # 用户回头在「桌面打开 ComfyUI」那颗按钮里选一次，之后就一直静默了。
        if self.comfy_listening():
            self.status.set('ComfyUI 已在运行，无需重复启动。')
            return True
        exe=self.media_page_services.comfy_executable(self.settings)
        if exe is None:
            if silent:
                self.status.set('没找到 ComfyUI 桌面程序，本次不启动；请点“桌面打开 ComfyUI”选一次程序。')
                return False
            selected=self.media_page_services.file_dialog(self.win).open_file(title='选择 ComfyUI 桌面版程序',filetypes=[('程序','*.exe')])
            if not selected:return
            exe=Path(selected)
            from stage_execution_service import publish_desktop_preferences
            result=publish_desktop_preferences(self.settings_file,self.settings,{'comfy_exe':str(exe)})
            if not result.ok:raise ValueError(result.reason)
            self.settings=result.data
        from native_apps import open_comfy
        open_comfy({**self.settings,'comfy_exe':str(exe)})
        self.status.set('已打开本地 ComfyUI；可在桌面窗口查看工作流和调整参数。')
        return True
    def open_comfy_browser(self):
        url=self.settings.get('comfy_url','http://127.0.0.1:8188')
        open_target(url)
        self.status.set('已在浏览器打开 ComfyUI：'+url+'（若未就绪请稍后刷新，或先点“桌面打开 ComfyUI”启动服务）')
    def align_studio(self):
        """工作集跟随当前选择的分镜：切换分镜或自动采用新分镜后，后续流程不能还按旧分镜执行。

        只改内存里的工作集（不重写 config 的工作集指针），正在跑任务时不动，避免切换途中打断批次；
        新分镜暂时不合规（时长、编号、提示词等）时保留原工作集，并在状态栏写明原因。
        """
        if self.root is None:return False
        if self.worker or self.cloud_monitor_busy or any(getattr(v,'busy',False) or getattr(v,'optimizer_busy',False) for v in self.video_sessions.values()):return False
        try:source=self.current_frame_json()
        except ValueError as exc:
            self.status.set('工作集未切换：'+str(exc));return False
        if source is None:return False
        if self.studio is not None and Path(self.studio.episode_path).resolve()==Path(source).resolve():return True
        try:studio=self.media_page_services.open_studio(self.root,episode_file=source)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            self.status.set('工作集未切换：'+str(exc));return False
        self.studio=studio
        return True
    # 第 50 期第 1 条：原来那颗「选择镜头 JSON」删掉——首帧页看的永远是「当前分镜」，
    # 也就是初步分镜页采用的那一份（自动认领见 current_frame_json），不用在这儿再挑一遍。
    def focus_missing_frame(self,source,sid):
        from storyboard_selection import focus
        focus(self.root,source)
        self.pending_frame_selection=sid
        self.show(PAGE['keyframe'])
        self.status.set(sid+' 尚无首帧，已定位到首帧管理页；请用「手动制作首帧」生成，或用「导入 / 替换选中首帧」导入图片。')
    def adopt_frame_jsons(self,paths):
        from stage_execution_service import adopt_asset_storyboards
        return adopt_asset_storyboards(self.root,paths)
    def remove_frame_jsons(self,paths):
        from stage_execution_service import remove_asset_storyboards
        return remove_asset_storyboards(self.root,paths)
    def remember_frame_json(self,path):
        return self.adopt_frame_jsons([path])
    def current_frame_json(self):
        from storyboard_selection import current_source
        episode_dir = getattr(getattr(self, 'studio', None), 'episode_dir', None)
        return current_source(
            self.root,
            legacy_sources=self.settings.get('frame_json_by_project', {}).items(),
            fallbacks=(episode_dir / 'episode.json',) if episode_dir else (),
            remember=self.remember_frame_json,
        )
    def frame_checks_apply(self,source,ids):
        """「首帧制作」弹窗提交后回写勾选：页面、下拉框与弹窗共用同一份状态，刷新即同步。"""
        # 第 68 期任务 12：「全部分镜」把几份分镜的行合成一屏，勾选表也合成一张（storyboard 里按行
        # 编号记）；这一页记着那张表的钥匙，弹窗回写就先认它。
        key=media_logic.frame_checks_key(getattr(self,'_frame_checks_merged',False),
                                         getattr(self,'_frame_checks_key',None),source)
        state=self.frame_checks.get(key)
        return state.keep(ids) if state is not None else []
    def delete_keyframe(self,shot,episode=None,base=None,source=None,ask=True,rebuild=True):
        """删除一镜的首帧（移入回收站）。

        第 46 期第 9 条：ask／rebuild 两个接缝给「批量删除首帧」用——批量时确认框只弹一次、
        循环里不重建页面，逐个删除（右键／按钮）照旧走默认值。
        """
        episode=episode or self.studio.episode;base=Path(base or self.studio.episode_dir).resolve()
        path=(base/shot['frame']).resolve()
        if not path.is_file():raise ValueError('首帧已不存在，请刷新列表')
        if ask and not self.media_page_services.confirm(self.win, '删除首帧', f'删除 {shot["id"]} 的首帧图片？\n{path}\n图片进首帧回收目录，可恢复；视频和记录保留。', dangerous=True):return False
        if not path.is_relative_to(base/'frames'):raise ValueError('仅允许删除所选JSON目录下frames中的首帧')
        if any(s['id']!=shot['id'] and (base/s['frame']).resolve()==path for s in episode['shots']):raise ValueError('其他镜头也在使用此图片，请先替换它们的首帧')
        from stage_execution_service import delete_stage_keyframe
        result=delete_stage_keyframe(base,source or base/'episode.json',episode,shot)
        if not result.ok:raise ValueError(result.reason)
        if rebuild:self.show(PAGE['keyframe']);self.status.set('首帧已删除并从列表移除')
        return True
    def restore_keyframe(self,shot,episode,base,source):
        sid=shot['id']
        if not self.media_page_services.confirm(self.win, '恢复首帧', f'将恢复 {sid} 的最近回收首帧。'):return
        from stage_execution_service import restore_stage_keyframe
        result=restore_stage_keyframe(base,source,episode,shot)
        if not result.ok:raise ValueError(result.reason)
        self.show(PAGE['keyframe']);self.status.set(sid+' 首帧已恢复')
    def animatic_page(self):
        from stage_execution_service import (animatic_reference_paths, import_animatic_references,
                                             import_animatic_audio, run_animatic, confirm_animatic, animatic_video,
                                             generate_animatic_reference)
        from ui_widgets import DescriptionBlock, PrimaryButton, SecondaryButton, ProgressLabel, LineInput, HintLabel
        from ui_tokens import SPACING
        project = self.root
        selected = {'source': None, 'audio': None}
        comfy_settings = {'url': self.settings.get('comfy_url', 'http://127.0.0.1:8188')}
        DescriptionBlock(self.content, text='先准备共享参考图，再用本地 ComfyUI 生成镜头草图并合成预演。正式资产仍在线上生成。').pack(fill='x')
        detail = ProgressLabel(self.content, text='请选择本项目分镜初稿和临时音频')
        detail.pack(fill='x')

        def choose(kind):
            paths = self.file_dialog.open_files(parent=self.win,
                title='选择分镜初稿' if kind == 'source' else '选择临时音频',
                filetypes=[('分镜 JSON', '*.json')] if kind == 'source' else [('临时音频', '*.wav *.mp3 *.m4a *.aac')])
            if paths:
                if kind == 'audio':
                    def imported(result):
                        if not result.ok:
                            self.status.set(result.reason); return
                        selected[kind] = result.data
                        detail.configure(text='已导入临时音频：' + Path(result.data).name)
                    self.async_(lambda: import_animatic_audio(project, paths[0]), imported)
                else:
                    selected[kind] = paths[0]
                    detail.configure(text='已选择：' + Path(paths[0]).name)

        def references():
            paths = self.file_dialog.open_files(parent=self.win, title='导入共享参考图',
                filetypes=[('参考图', '*.png *.jpg *.jpeg *.webp')])
            if paths:
                self.async_(lambda: import_animatic_references(project, paths),
                            lambda result: self.status.set('已准备 %d 张共享参考图' % len(result)))

        def generate():
            source, audio = selected['source'], selected['audio']
            text = tts_text.get().strip()
            if self.worker:
                self.status.set('请等待当前任务完成'); return
            if not source or (not audio and not text):
                self.status.set('请选择分镜初稿，并导入音频或填写临时 TTS 文本'); return
            for value in checked.values():
                value.set(False)
            self.async_(lambda: run_animatic(project, source, animatic_reference_paths(project), audio,
                                            settings={**comfy_settings, 'tts_text': text}),
                        lambda _result: self.status.set('分镜预演已生成；请观看后确认节奏、时长与对白同步'),
                        label='正在生成分镜预演…')

        for text, command in [('导入共享参考图', references), ('选择分镜初稿', lambda: choose('source')),
                              ('选择临时音频', lambda: choose('audio'))]:
            SecondaryButton(self.content, text=text, command=command).pack(anchor='w', pady=SPACING['xs'])
        reference_prompt = LineInput(self.content, placeholder='参考图描述（角色或场景草图）')
        reference_prompt.pack(fill='x', pady=SPACING['xs'])
        reference_model = LineInput(self.content, placeholder='本地已安装模型名称（含扩展名）')
        reference_model.pack(fill='x', pady=SPACING['xs'])
        def make_reference():
            prompt, model = reference_prompt.get().strip(), reference_model.get().strip()
            if self.worker:
                self.status.set('请等待当前任务完成'); return
            self.async_(lambda: generate_animatic_reference(project, prompt, model, comfy_settings),
                        lambda result: self.status.set('已生成共享参考草图' if result.ok else result.reason),
                        label='正在生成共享参考草图…')
        SecondaryButton(self.content, text='本地生成参考草图', command=make_reference).pack(anchor='w', pady=SPACING['xs'])
        HintLabel(self.content, text='临时 TTS（已导入音频优先）').pack(anchor='w')
        tts_text = LineInput(self.content, placeholder='未导入音频时使用的临时对白')
        tts_text.pack(fill='x', pady=SPACING['xs'])
        PrimaryButton(self.content, text='生成分镜预演', command=generate).pack(anchor='w', pady=SPACING['sm'])
        def preview():
            self.async_(lambda: animatic_video(project), lambda path: open_target(path))
        SecondaryButton(self.content, text='观看预演视频', command=preview).pack(anchor='w', pady=SPACING['xs'])
        checked = {key: tk.BooleanVar(value=False) for key in ('rhythm', 'duration', 'dialogue_sync')}
        for key, label in [('rhythm', '已确认节奏'), ('duration', '已确认时长'), ('dialogue_sync', '已确认对白同步')]:
            ttk.Checkbutton(self.content, text=label, variable=checked[key]).pack(anchor='w')

        def confirm():
            values = {key: value.get() for key, value in checked.items()}
            def confirmed(_result):
                self.status.set('分镜预演已确认，可以进入资产管理')
                if self.root == project:
                    self.pet_report('animatic', '节奏、时长与对白同步均已确认')
            self.async_(lambda: confirm_animatic(project, **values),
                        confirmed)
        SecondaryButton(self.content, text='确认预演（SG-B）', command=confirm).pack(anchor='w', pady=SPACING['sm'])
    def previs(self):
        ui_plugin_registry.module('local_previs').show(self)
    def refresh_video_workspace(self):
        current=self.video
        if current is None:return
        if current.busy:
            current.write('后台任务处理中，保留当前界面；完成后自动更新。');return
        source=self.current_frame_json().resolve()
        if current.studio.episode_path.resolve()!=source:
            self.show(PAGE['video'],video_mode=self.video_mode);return
        current.studio.episode=read(current.studio.episode_path)
        current.refresh();current.update_progress();current.next_poll=0
        current.write('镜头与首帧已刷新，当前提示词草稿保留。')
    def set_video_workspace(self,folder=None,navigate=True):
        path=self.root/'ui_settings.json'
        prefs=_prefs(path)
        media_logic.apply_video_workspace(self.root,prefs,folder)
        if folder is not None:folder=Path(folder).resolve()
        from stage_execution_service import publish_cloud_video_workspace_preference
        publish_cloud_video_workspace_preference(path,prefs)
        if navigate:self.show(PAGE['video'],video_mode='cloud' if folder is not None else 'local')
    def video_home(self):
        """07 步还没选生成方式时的落地页（第 26 期第 3 条）。

        未选方式前不需要分镜，所以这一页不摆「选择分镜」；改成先确认「分镜几份、首帧够不够、
        两种方式各用哪个模型、要不要无人值守补视频」这些本来要进了工作台才知道的事——
        进去之后就不用再翻回来问，两个入口也改成主色按钮，一眼能看见。
        """
        from video_navigation import confirm_rows,local_model
        self.title.set_text(pet_bus.stage_label('video')+' · 选择生成方式')
        # 第 48 期第 2 条：这一屏不再挂「阶段配置」；R2942 起页面级阶段配置按钮与
        # 标题旁入口全部删除，模型/技能走共享输入框。
        # 第 38 期第 2 条：「线上走」和「API（按秒计费）」之间那个空格是整句唯一的断点，
        # 窗口一窄就把这两个词劈成两行；改成不换行空格粘住，并自己在这里断句，两种方式各占一行。
        lead=ttk.Label(self.content,text='本地走本机 ComfyUI（免费，用显卡），线上走\u00a0API（按秒计费）。\n两种都用同一份分镜与首帧；先确认下面几项，选定方式后再挑镜头。',
                       wraplength=TEXT_DESC['wraplength'],justify='left',style='Muted.TLabel')
        lead.pack(anchor='w',pady=(SPACING['xs'],SPACING['sm']))
        # 折行交给 _fit_content_now：它按内容框的实际宽度重排所有带 wraplength 的标签。
        # 自己再绑一个 <Configure> 会和它打架——标签按被压窄后的宽度折行，越折越窄。
        facts=Card(self.content);facts.pack(fill='x',pady=(SPACING['none'],SPACING['md']))
        ttk.Label(facts,text='开工前先确认').grid(row=0,column=0,columnspan=2,sticky='w')
        for row,(label,value) in enumerate(confirm_rows(self)):
            ttk.Label(facts,text=label,width=CHAR_WIDTH['lg']).grid(row=row+1,column=0,sticky='nw',pady=SPACING['xs'])
            ttk.Label(facts,text=value,wraplength=TEXT_DESC['wraplength'],justify='left',style='Muted.TLabel').grid(row=row+1,column=1,sticky='w',pady=SPACING['xs'])
        local=Card(self.content);local.pack(fill='x',pady=(SPACING['none'],SPACING['md']))
        ttk.Label(local,text='本地生成').pack(anchor='w')
        ttk.Label(local,text='用本机 ComfyUI 与已安装的视频模型出片，不花云端额度；缺视频的镜头可以交给无人值守自动补。',
                  wraplength=TEXT_DESC['wraplength'],justify='left',style='Muted.TLabel').pack(anchor='w')
        self.pet.auto_variable('auto_video_var')
        auto=self.auto_video_var
        state=tk.StringVar()
        def say_state():
            state.set('已开启：缺视频的镜头按顺序自动提交并取回（免费通道）' if auto.get()
                      else '未开启：进去后仍可逐个镜头手动生成')
        say_state()
        ttk.Label(local,textvariable=state,style='Muted.TLabel').pack(anchor='w',pady=(SPACING['xs'],SPACING['none']))
        PrimaryButton(local,text='进入本地生成',
                   command=lambda:self.safe(lambda:self.show(PAGE['video'],video_mode='local'))).pack(anchor='w',pady=(SPACING['md'],SPACING['none']))
        cloud=Card(self.content);cloud.pack(fill='x')
        ttk.Label(cloud,text='线上生成').pack(anchor='w')
        ttk.Label(cloud,text='用万相 / Seedance API 出片，按秒计费；读取已采用分镜的镜头与首帧，提交前会先问一次。',
                  wraplength=TEXT_DESC['wraplength'],justify='left',style='Muted.TLabel').pack(anchor='w')
        entry=FlowBar(cloud);entry.pack(fill='x',pady=(SPACING['md'],SPACING['none']))
        PrimaryButton(entry,text='进入线上生成',
                   command=lambda:self.safe(lambda:self.show(PAGE['video'],video_mode='cloud'))).pack(side='left')
        ttk.Label(entry,text='（线上接口在「阶段配置」→「接口」里配）',
                  style='Muted.TLabel').pack(side='left',padx=(SPACING['sm'],SPACING['none']))
    def videos(self):
        mode=getattr(self,'video_mode',None)
        if mode is None:
            self.video_home()
            return
        self.title.set_text(pet_bus.stage_label('video')+' · '+('线上生成' if mode=='cloud' else '本地生成'))
        from video_navigation import show_back
        show_back(self)
        top=ttk.Frame(self.content);top.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        heading=ttk.Frame(top);heading.pack(side='left',fill='both',expand=True)
        def header_note(text):
            label=DescriptionBlock(heading,text=text);label.pack(anchor='w',fill='x',pady=SPACING['xs'])
            label.bind('<Configure>',lambda e,w=label:w.configure(wraplength=max(SPACING['2xl']*5,e.width)))
        prefs_path=self.root/'ui_settings.json'
        prefs=read(prefs_path) if prefs_path.is_file() else {}
        video_root=media_logic.resolve_video_root(self.root,mode,prefs)
        is_cloud=video_root!=self.root
        if is_cloud and read(video_root/'config.json').get('cloud_provider')=='openai':
            header_note('原视频服务商已移除，请重新选择服务商。历史文件仍保存在项目目录。')
            self.button(self.content,'配置线上视频 API',lambda:ui_plugin_registry.module('cloud_video').settings_window(self))
            return
        if mode=='cloud' and not is_cloud:
            header_note('首次使用线上生成，请先配置服务商、模型和API Key。保存后在此页面显示镜头工作台。')
            self.button(self.content,'配置线上视频 API',lambda:ui_plugin_registry.module('cloud_video').settings_window(self))
            return
        if is_cloud:
            video_root=ui_plugin_registry.module('cloud_video').align_source(self,video_root)
            self.header_model.configure(text='当前模型：'+read(video_root/'config.json')['model'])
        from shared_video_controls import build
        build(self,heading,is_cloud)
        def prepare_video_prompt(sid):
            from agent.shot_assets import prompt_direct,prompt_task
            final_source=self.current_frame_json()
            final_episode=read(final_source)
            final_shot=next((s for s in final_episode.get('shots',[]) if s.get('id')==sid),None)
            if final_shot is None:raise ValueError('当前分镜定稿没有此镜头，请先选择正确的镜头 JSON')
            prompt=prompt_task(final_source,final_shot,self.video.studio.cfg,output_source=self.video.studio.episode_path)
            draft=self.video.prompt.get('1.0','end').strip()
            if draft:
                prompt+='\n当前编辑框中的提示词（作为待修订素材，结合以上镜头和资产检查）：\n'+json.dumps(draft,ensure_ascii=False)
            self.open_direct_flow_agent(VIDEO_PROMPT_FLOW,'提示词渲染阶段',prompt,prompt_direct(final_source,final_shot,self.video.studio.cfg,self.video.studio.episode_path,draft))
        source=self.current_frame_json()
        session_key=(str(video_root.resolve()),str(source.resolve()))
        cached=self.video_sessions.get(session_key)
        if cached:
            self.video=cached;cached.window.pack(fill='both',expand=True);cached.footer.pack(side='bottom',fill='x',pady=SPACING['xs'])
            if not cached.busy:
                cached.studio.cfg=read(video_root/'config.json')
                cached.studio.episode=read(cached.studio.episode_path)
                cached.refresh();cached.update_progress();cached.next_poll=0
            if is_cloud:self.header_status.configure(textvariable=cached.status)
            # R2942：「阶段配置」按钮＋模型下拉框已删除，工作台不再暴露独立入口。
            return
        panel=ttk.Frame(self.content);panel.pack(fill='both',expand=True)
        from stage_models import manual_command
        # R2942：视频工作台的「阶段配置」按钮＋模型下拉框删除（模型/技能走共享输入框）。
        self.video=App(panel,video_root,settings_callback=(lambda:ui_plugin_registry.module('cloud_video').settings_window(self)) if is_cloud else None,prompt_callback=prepare_video_prompt,episode_file=None if is_cloud else source,missing_frame_callback=lambda sid,source=source:self.focus_missing_frame(source,sid),report_callback=self.pet_report,manual_command_factory=manual_command)
        # 视频页自己的文字框重排也听主窗口合并器：拖动时并进松手后的补做。
        self.video.resize_scheduler=self.resize_scheduler
        if is_cloud:self.header_status.configure(textvariable=self.video.status)
        self.video_sessions[session_key]=self.video
        self.stage_button=getattr(self.video,'stage_button',None)
        # The shared workspace owns script/project actions.
        self.video.writing_setup=lambda:self.show(PAGE['script']);self.video.import_json=self.import_json
    def open_tts_settings(self):
        from tts_settings import show
        show(self.win)
    def generate_tts(self):
        import domain.tts_api as tts_api
        entries,estimated=self.dialogue_entries();assets=self.dialogue_assets()
        if not entries:raise ValueError('当前分镜没有对白，无法生成配音')
        script=tts_api.build_script(entries,assets)
        if len(script)>4000:raise ValueError('整集对白超过 4000 字，请改用“逐句配音（分句）”生成')
        # 整段配音一次就是一次付费请求：台词与音色都没变、文件还在时直接沿用，双击或重复点击
        # 不会再扣一次费；改台词、改模型或改音色会得到新指纹，才重新合成。
        settings=tts_api.read_settings()
        signature=tts_api.script_signature(script, settings)
        from stage_execution_service import reusable_tts_full_track
        previous=reusable_tts_full_track(self.root,signature)
        if previous:
            self.status.set('配音台词与音色都没变，沿用已有配音：'+str(previous)+'（未重复扣费）');return
        def work():
            raw=tts_api.synthesize(script, settings=settings, project=self.root, request_id='tts-full:' + signature)
            from stage_execution_service import publish_tts_full_track
            p=publish_tts_full_track(self.root,signature,raw)
            note='配音已生成：'+str(p)
            if estimated:note+='（时间轴为草稿均分，建议在剪映中听校）'
            return note
        self.async_(work)
    def generate_tts_per_line(self):
        import domain.tts_api as tts_api
        episode=self.current_episode()
        entries,estimated=self.dialogue_entries(episode);assets=self.dialogue_assets()
        if not entries:raise ValueError('当前分镜没有对白，无法生成配音')
        tts_settings=tts_api.read_settings()
        lines=tts_api.build_lines(entries,assets,tts_settings.get('voices'),tts_settings.get('speeds'),settings=tts_settings)
        from contract.project_stages import audio
        folder=audio(self.root)/'配音分句'
        # 同一项目可有多集：把集标识纳入批次指纹，两集同名台词／音色不会共用缓存目录。
        token=(episode.get('episode_id') or episode.get('id')) if isinstance(episode,dict) else None
        out=tts_api.resume_folder(folder,lines,token);resumed=out is not None
        out=out or dated_path(folder,'配音批次')
        # 付费闸口：逐句配音按句计费，点一次会发出「待合成句数」个请求。先在点按钮时把要花多少、
        # 有多少句沿用已生成文件摊开确认，取消时一句都不提交（沿用判定与批次内部同一口径）。
        quote=tts_api.batch_cost_preview(self.root,lines,out,tts_settings)
        pending=quote['pending']
        if not pending:
            self.status.set('逐句配音：'+('都已有成品，无需重复合成。' if not quote['unknown'] else '')+quote['text']);return
        tip=quote['text']
        if not self.media_page_services.confirm(self.win, '逐句配音（付费）', tip+'\n\n继续提交？', dangerous=True):
            self.status.set('已取消逐句配音：未提交任何句子，也没有产生费用');return
        def work():
            from stage_execution_service import run_tts_lines
            ok,reused,failed=run_tts_lines(lines,out,episode=token,project=self.root)
            note=f'逐句配音完成：成功 {ok}/{len(lines)}，失败 {failed}'
            if reused:note+=f'（沿用已生成 {reused} 句，未重复扣费）'
            if resumed:note+='；已接续上次未完成的批次'
            return note+f'；目录 {out}'
        self.async_(work)
    def open_audio_skill(self):
        from orchestrator.workflow_tasks import audio_prompt
        source=self.current_frame_json()
        self.open_flow_agent('audio','配音制作',audio_prompt(self.root,source))
    def audio(self):
        from domain.stage_workspace_service import ensure_audio_workspace
        result=ensure_audio_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        audio_dir,subtitle_dir=result.data
        self.note('可导入配音或音乐；按剧本对白时间导出整集SRT。字幕时间需在剪映中听校。')
        # 对白读不出来时不要静默禁用按钮：把原因写在页面上，用户才知道该改哪里。
        has_dialogue,dialogue_reason=media_logic.dialogue_availability(self.dialogue_entries)
        if dialogue_reason:
            self.note(dialogue_reason)
            # 状态栏会在换页后被覆盖；在当前页面也保留原因，避免用户只看到灰按钮。
            ttk.Label(self.content,text=dialogue_reason,style='Muted.TLabel').pack(
                anchor='w',pady=(SPACING['none'],SPACING['xs']))
        production=FlowBar(self.content);production.pack(
            fill='x',pady=(SPACING['none'],SPACING['sm']))
        ttk.Label(production,text='配音制作').pack(
            side='left',padx=(SPACING['none'],SPACING['sm']))

        def audio_button(parent,text,command,primary=False):
            """保留既有事件封装，仅将本页按钮接入设计系统。"""
            button=self.button(parent,text,command)
            button.configure(style='Tokens.Primary.TButton' if primary else 'Tokens.Secondary.TButton')
            if isinstance(parent,FlowBar):
                button.pack_configure(padx=(SPACING['none'],SPACING['sm']),pady=SPACING['xs'])
            else:
                button.pack_configure(pady=SPACING['xs'])
            return button

        from stage_models import manual_command as _manual_audio
        _audio_button=audio_button(production,'手动制作配音',
                                   _manual_audio(self,'audio',self.open_audio_skill,self.win),primary=True)
        ui_plugin_registry.module('stage_flow').follow(_audio_button,'audio')
        # R2942：「阶段配置」按钮＋模型下拉框删除。
        dialogue_buttons=[]
        dialogue_buttons.append(audio_button(production,'生成配音（TTS）',self.generate_tts))
        dialogue_buttons.append(audio_button(production,'逐句配音（分句）',self.generate_tts_per_line))
        audio_button(production,'配音设置',self.open_tts_settings)
        audio_button(self.content,'导入配音 / 音乐',self.import_audio)
        audio_button(self.content,'校验并确认本阶段成果',lambda:self.confirm_stage_media('audio'))
        dialogue_buttons.append(audio_button(self.content,'导出对白字幕 SRT',lambda:self.media_page_services.open_path(self.subtitles())))
        dialogue_buttons.append(audio_button(self.content,'导出对白脚本 TXT',lambda:self.media_page_services.open_path(self.dialogue_script())))
        for button in dialogue_buttons:button.configure(state='normal' if has_dialogue else 'disabled')
        audio_button(self.content,'打开音频目录',lambda:self.media_page_services.open_path(audio_dir))
        audio_button(self.content,'打开字幕目录',lambda:self.media_page_services.open_path(subtitle_dir))
        audio_button(self.content,'打开 ElevenLabs（浏览器）',lambda:self.safe(lambda:open_target('https://elevenlabs.io/app')))
    def import_audio(self):
        from domain.stage_workspace_service import ensure_audio_workspace
        result=ensure_audio_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        folder,_=result.data
        p=self.media_page_services.file_dialog(self.win).open_file(initialdir=folder,filetypes=[('音频','*.wav *.mp3 *.m4a *.aac')])
        if not p:return
        from stage_execution_service import import_stage_audio
        project=self.root
        def work():
            result=import_stage_audio(project,p)
            if not result.ok:raise ValueError(result.reason)
            return result.data
        self.async_(work,lambda dest:self.status.set('音频已导入：'+str(dest)))
    def subtitle_rows(self):
        """按剧本对白时间算出 SRT 行；没有对白时抛 ValueError。只读文件、不碰界面，可在工作线程里用。"""
        from domain.subtitle_timing import srt_rows
        rows,estimated=srt_rows(self.current_episode())
        if not rows:raise ValueError('当前分镜没有对白，无法导出字幕')
        return rows,estimated
    def subtitles(self):
        from stage_execution_service import export_stage_srt
        result=export_stage_srt(self.root,self.current_episode())
        if not result.ok:raise ValueError(result.reason)
        p,report=result.data
        # 字幕轴来自校准报告：按实际配音校准了就说清楚，仍是估算的就把未校准句数列出来。
        self.status.set(media_logic.subtitle_status(report))
        return p
    def stage_action_bar(self,stage,manual_text):
        """后期／交付页顶部一行：「手动制作…」按钮（R2942：阶段配置按钮已删）。"""
        from stage_models import manual_command
        bar=FlowBar(self.content);bar.pack(fill='x',pady=(SPACING['xs'],SPACING['xs']))
        manual=PrimaryButton(bar,text=manual_text,width=STAGE_ACTION_WIDTH,
                             command=lambda:self.safe(manual_command(self,stage,
                                 lambda:ui_plugin_registry.module('stage_exec').show(self,stage),self.win)))
        manual.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs'])
        ui_plugin_registry.module('stage_flow').follow(manual,stage)
    def editing(self):
        from orchestrator.editing_page_controller import EditingPageController
        from domain.stage_workspace_service import ensure_editing_workspace
        controller = EditingPageController(self.root, self.studio)
        result=ensure_editing_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        edit_dir,=result.data
        self.stage_action_bar('edit','手动制作剪辑')
        self.note('自动粗剪只拼装已验收的镜头：未验收的镜头会被跳过并列在状态栏，不再因为个别镜头卡住整集。本页可设置基础转场与背景音乐，并按平台导出成片副本；精细剪辑、对白音量和字幕烧录仍交给剪映，交接包保留镜头顺序。素材交接包只给有序视频与字幕，不是剪映草稿，可用「校验交接包」离线核对。本次输出规格：%s（等比缩放＋居中留边，不裁切）。'%controller.output_spec_text())
        edit_buttons=[]
        def edit_button(text,command,primary=False):
            """保留共享事件封装，只让后期页采用统一的视觉组件样式。"""
            button=self.button(self.content,text,command)
            button.configure(style='Tokens.Primary.TButton' if primary else 'Tokens.Secondary.TButton')
            button.pack_configure(pady=SPACING['xs'])
            return button
        def assemble_all():return controller.assemble()
        def assembled(path):
            message=controller.assembled_message(path)
            if message:self.status.set(message)
        edit_buttons.append(edit_button('自动粗剪整集（跳过未验收镜头）',lambda:self.async_(assemble_all,assembled),primary=True))
        import project_settings
        self.pet.auto_variable('auto_edit_var')
        self.pet.auto_variable('auto_handoff_var')
        edit_buttons.append(edit_button('整理剪映素材交接包',lambda:self.async_(self.handoff,self.media_page_services.open_path)))
        has_downloaded=controller.has_downloaded_video()
        for button in edit_buttons:button.configure(state='normal' if has_downloaded else 'disabled')
        if not has_downloaded:self.note('还没有已下载的镜头视频，自动粗剪与交接包暂不可用；请先在'+pet_bus.stage_step('video')+'生成并下载视频。')
        transition_button=edit_button('转场：'+controller.transition_label()+'（点击切换）',lambda:None)
        def switch_transition():
            transition_button.configure(text='转场：'+controller.next_transition()+'（点击切换）')
        transition_button.configure(command=lambda:self.safe(switch_transition))
        music_button=edit_button('背景音乐：'+controller.music_label(),lambda:None)
        def pick_music():
            chosen=self.media_page_services.file_dialog(self.win).open_file(title='选择背景音乐',filetypes=[('音频','*.wav *.mp3 *.m4a *.aac *.flac')])
            if not chosen:return
            controller.set_music(chosen)
            music_button.configure(text='背景音乐：'+controller.music_label())
        def clear_music():
            controller.set_music('')
            music_button.configure(text='背景音乐：'+controller.music_label())
        music_button.configure(command=lambda:self.safe(pick_music))
        edit_button('清除背景音乐',lambda:self.safe(clear_music))
        from domain.edit_export import PLATFORMS
        for platform_key,platform in PLATFORMS.items():
            edit_button('导出%s版（%dx%d）'%(platform['label'],platform['width'],platform['height']),
                        lambda key=platform_key:self.account_blocked('delivery') or self.async_(lambda:controller.export_platform(key),
                                                            lambda path:self.status.set('平台版本已导出：'+str(path))))
        edit_button('启动剪映',self.launch_editor)
        edit_button('打开后期目录',lambda:self.media_page_services.open_path(edit_dir))
        edit_button('校验交接包',self.verify_handoff)
        edit_button('校验并确认本阶段成果',lambda:self.confirm_stage_media('edit'))
        f=edit_dir/'剪辑优化清单.md'
        from file_cache import read_text
        box=self.text(read_text(f,encoding='utf-8') if f.exists() else '□ 删除多余停顿\n□ 检查对白口型\n□ 校对字幕\n□ 统一人声与环境音量\n□ 检查角色、镜头衔接\n□ 检查片头片尾和导出比例',8)
        from stage_execution_service import save_stage_editing_checklist
        edit_button('保存剪辑优化清单',lambda:save_stage_editing_checklist(self.root,box.get('1.0','end-1c')),primary=True)
    def find_editor(self):
        from orchestrator.media_page_controller import editor_candidates;saved=self.settings.get('jianying','')
        for executable in editor_candidates(saved):
            if executable.is_file():
                if str(executable)!=saved:
                    from stage_execution_service import publish_desktop_preferences
                    result=publish_desktop_preferences(self.settings_file,self.settings,{'jianying':str(executable)})
                    if not result.ok:raise ValueError(result.reason)
                    self.settings=result.data
                return executable
        return None
    def find_editor_shortcut(self):
        """在后台查找开始菜单中的剪映快捷方式（实现搬到 L0 platform_tools，入口不变）。"""
        return self.media_page_services.find_editor_shortcut()
    def launch_editor(self):
        executable=self.find_editor()
        if executable is not None:
            launch_windows_app(executable, '剪映专业版')
            return
        def open_shortcut(shortcut):
            def finish():
                if shortcut is not None:
                    self.media_page_services.open_path(shortcut)
                    return
                raise ValueError('未自动找到剪映专业版。请先安装剪映，然后重新点击“启动剪映”。')
            self.safe(finish)
        self.async_(self.find_editor_shortcut,open_shortcut,
                    label='正在在开始菜单中查找剪映专业版…')
    def handoff(self,auto=False):
        # 选版规则见 media_page_controller.handoff_rows（engine.adopted_edit_version 是唯一口径）。
        rows=media_logic.handoff_rows(self.root,self.studio)
        subtitle=None
        if len(rows)==len(self.studio.episode['shots']):
            try:
                if auto:
                    texts,_estimated=self.subtitle_rows()
                    subtitle='\n'.join(texts).encode('utf-8-sig')
                else:
                    subtitle=self.subtitles()
            except ValueError:pass  # 无对白时不附字幕，交接包仍可用
        from stage_execution_service import publish_stage_handoff_bundle
        return publish_stage_handoff_bundle(self.root, self.studio.episode['shots'], rows,
                                            subtitle, auto)
    def verify_handoff(self):
        """离线校验一个已解包的交接包：选目录、照清单核对文件，如实报缺项与被改文件。"""
        folder=self.media_page_services.file_dialog(self.win).directory(title='选择已解包的交接包目录')
        if not folder:return
        def work():
            from stage_execution_service import verify_handoff_bundle
            return verify_handoff_bundle(folder)
        def done(report):
            label=report.get('label') or '素材交接包'
            if report.get('ok'):
                missing=report.get('missing') or []
                text='交接包校验通过：%s，共 %d 个文件'%(label,report.get('count',0))
                if missing:text+='；清单声明缺 '+'、'.join(str(item) for item in missing)+' 镜（素材交接包允许缺镜）'
                self.status.set(text)
                return
            self.status.set('交接包校验未通过：'+'；'.join(report.get('problems') or ['未知问题']))
        self.async_(work,done)
    def delivery(self):
        from domain.stage_workspace_service import ensure_delivery_workspace
        result=ensure_delivery_workspace(self.root)
        if not result.ok:raise ValueError(result.reason)
        delivery_dir,export_dir=result.data
        self.stage_action_bar('delivery','手动制作交付')
        self.note('查看本地任务和技术质检状态，再由您确认画面、对白和剧情。这里不会查询云端任务。')
        def delivery_button(text,command,primary=False):
            """保留共享事件封装，只让交付页采用统一的视觉组件样式。"""
            button=self.button(self.content,text,command)
            button.configure(style='Tokens.Primary.TButton' if primary else 'Tokens.Secondary.TButton')
            button.pack_configure(pady=SPACING['xs'])
            return button
        lines=media_logic.delivery_lines(self.root,self.studio,video_progress.LABELS,video_progress.status_next)
        box=self.text('\n'.join(lines),12);box.configure(state='disabled')
        from stage_completion_service import commercial_status
        self.note(commercial_status(self.root)[1])
        delivery_button('导入剪映最终成片',self.final_import,primary=True)
        delivery_button('校验并确认本阶段成果',lambda:self.confirm_stage_media('delivery'))
        delivery_button('生成商用待填资料',lambda:self.safe(lambda:self.commercial_delivery_review(create=True)))
        delivery_button('核验商用交付资料',lambda:self.safe(self.commercial_delivery_review))
        delivery_button('选择采用版本…',lambda:self.safe(self.open_version_picker))
        delivery_button('打开交付目录',lambda:self.media_page_services.open_path(delivery_dir))
        delivery_button('打开自动剪辑与QC报告目录',lambda:self.open_folder(export_dir))
