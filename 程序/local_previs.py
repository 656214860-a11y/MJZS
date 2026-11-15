"""Local preset previs, no model/API calls. Jobs outlive page navigation."""
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import white_model_service as wm
from file_cache import read_json
from previs_batch_service import prepare_batch
import previs_routing
from stage_execution_service import previs_entries, previs_ready, previs_records_directory, white_model_shot_directory, record_previs_evidence
import ui_plugin_registry
from contract.platform_tools import open_path
from responsive_ui import (FlowBar, auto_height, auto_columns, configure_check_column, CheckboxColumn,
                           work_rows, work_hint, view_row)
from ui_tokens import CHAR_WIDTH, TEXT_ROWS, WRAPLENGTH, COLORS, SPACING
from ui_widgets import SelectBox, BaseDialog, Card, DataTable, DescriptionBlock, PrimaryButton, ProgressLabel, SecondaryButton, TextArea, notify

def engine_name(project):
    """当前白模引擎名：读得出来就写进口径，读不出来退回空串。

    这里必须容错：白模页处处要用这个名字，为一句提示把整页挡在 ImportError 上不值——用户看到的会是
    「cannot import name model_name」，而正确做法是页面照常打开、只是名字暂时显示为空。
    写成模块级函数（不是页面里的闭包）是为了让自检能直接喂一个坏掉的 workflow_settings 进来。
    """
    from legacy_compat import optional_workflow_model_name
    return optional_workflow_model_name(project, 'previs')


def online_window(desktop, source, ids):
    """中等复杂度镜头的线上白模操作窗口（Tk 视图职责）。"""
    import white_model as wm
    from agent.core import read
    ep = read(source)
    shots = {shot['id']: shot for shot in ep['shots']
             if shot['id'] in ids and not previs_ready(desktop.root, shot['id'])}
    if not shots:
        raise ValueError('没有勾选待制作的中等复杂度镜头；已就绪镜头不重复制作')
    win = BaseDialog(desktop.win, '线上白模 · 中等动作', geometry='740x480',
                     modal=False, chrome=False)
    body = Card(win, padding=SPACING['lg']); body.pack(fill='both', expand=True)
    DescriptionBlock(body, text='按分镜简化制作 → 导出预演视频 → 导入对应镜头', wraplength=WRAPLENGTH['lg']).pack(anchor='w')
    selected = tk.StringVar(value=next(iter(shots)))
    combo = SelectBox(body, textvariable=selected, values=list(shots)); combo.pack(
        fill='x', pady=SPACING['sm']
    )
    text = TextArea(body, wrap='word', height=TEXT_ROWS['2xl']); text.pack(fill='both', expand=True)
    def update(event=None):
        shot = shots[selected.get()]
        task = f"{ep.get('episode_id', '')} / {shot['id']} · {shot.get('title', '')} · {shot.get('duration', 0)}秒\n"
        task += '仅用简化几何体验证动作、站位、持物和镜头；不用精细材质。\n'
        task += '\n'.join(f'{label}：{shot.get(key, "")}' for label, key in
                           [('起点', 'action_start'), ('动作', 'action'), ('终点', 'action_end'), ('机位', 'camera'), ('连续性', 'continuity')])
        if not shot.get('action'):
            task += '\n分镜提示词：' + str(shot.get('video_prompt', ''))
        text.delete('1.0', 'end'); text.insert('1.0', task)
    combo.bind('<<ComboboxSelected>>', update); update()
    def open_online():
        if previs_ready(desktop.root, selected.get()):
            desktop.status.set(selected.get() + ' 白模已就绪，本次跳过'); return
        from prompt_window import copy_text
        reason = copy_text(desktop.win, text.get('1.0', 'end-1c'))
        wm.webbrowser.open(wm.TOOLS[0][1])
        desktop.status.set(selected.get() + (('白模制作说明已复制；在线上工作台制作后导入。') if not reason
                           else ('白模制作说明复制失败：' + reason + '；请手动选中复制；线上工作台已打开。')))
    def import_result():
        try:
            sid = selected.get(); target = wm.import_media(wm.shot_directory(desktop.root, sid, source), sid, win)
            if target:
                record_previs_evidence(desktop.root, sid, source)
                desktop.status.set(sid + ' 白模已导入：' + str(target))
        except Exception as exc:
            notify(win, str(exc), level='error', title='导入白模', status=desktop.status)
    row = ttk.Frame(body); row.pack(fill='x', pady=SPACING['sm'])
    PrimaryButton(row, text='打开线上白模并复制说明', command=open_online).pack(side='left')
    SecondaryButton(row, text='导入该镜头白模', command=import_result).pack(
        side='left', padx=SPACING['sm']
    )
    SecondaryButton(row, text='关闭', command=win.destroy).pack(side='right')
    return win


def show(desktop):
    return _LocalPrevisWindow(desktop).build()


class _LocalPrevisWindow:
    """白模预演页：环境检查、镜头复杂度列表与制作／停止／查看入口。"""
    def __init__(self, desktop):
        self.desktop = desktop

    def build(self):
        self.project=Path(self.desktop.root);self.source=self.desktop.current_frame_json()
        self.shots=read_json(self.source).get('shots',[])
        self.state=getattr(self.desktop,'previs_jobs',None)
        if self.state is None:self.state={'busy':False,'status':{},'selected':set()};self.desktop.previs_jobs=self.state
        if not self.state.get('busy'):
            # 旧项目的白模成果还在旧目录：打开本页时一次性迁入项目身份目录（可重复、不覆盖、
            # 中途失败原样搬回）。项目已有身份或有任务在跑时不动任何文件。
            try:
                from stage_execution_service import migrate_white_model_directories
                moved=migrate_white_model_directories(self.project).get('moved')
                if moved:self.state['summary']='已把 %d 个旧白模目录迁入项目身份目录，原成果未覆盖'%len(moved)
            except Exception as exc:self.state['summary']='白模目录迁移未执行：'+str(exc)
        self.body=ttk.Frame(self.desktop.content);self.body.pack(fill='both',expand=True)
        self.decisions=previs_entries(self.project,self.source)
        DescriptionBlock(self.body,text='简单／固定动作：无需白模；中等动作：线上简单制作；复杂动作：Agent 自动制作。',wraplength=WRAPLENGTH['3xl']).pack(anchor='w')
        DescriptionBlock(self.body,text='优先读取分镜的复杂度标注；未标注时自动判断。选中镜头可手动调整。').pack(
            anchor='w', pady=SPACING['xs']
        )
        # O26：成果目录与 Blender 分开，且成果目录来自可配置的用户数据目录；这里给一行只读检查结果，
        # 「白模环境检查」按需跑一次完整检查（版本＋写权限），打开页面的每次刷新只做轻量判断。
        self.env_line=tk.StringVar(value='')
        env_row=ttk.Frame(self.body);env_row.pack(fill='x',pady=SPACING['xs'])
        SecondaryButton(env_row,text='白模环境检查',command=lambda:self.desktop.safe(self.check_environment)).pack(side='left')
        ProgressLabel(env_row,textvariable=self.env_line,wraplength=WRAPLENGTH['xl']).pack(side='left',padx=SPACING['sm'])
        self.refresh_environment()
        tablebox=ttk.Frame(self.body);tablebox.pack(fill='both',expand=True,pady=SPACING['sm'])
        # 第 47 期第 5 条：用户点名删掉「制作进度」那一栏——进度条整列撤掉，状态那一栏照旧说事。
        table_shell=DataTable(tablebox,columns=[
            ('id','镜头',165),('title','内容',150),('duration','秒数',50),
            ('complexity','动作复杂度',120),('route','制作方式',130),('status','状态',140),
        ],show='tree headings',height=TEXT_ROWS['lg'],selectmode='browse',empty_text='暂无镜头')
        self.tree=table_shell.tree
        self.icons=self.desktop.win._tick_images[:2]
        configure_check_column(self.tree)
        for col,title,width in [('id','镜头',165),('title','内容',150),('duration','秒数',50),('complexity','动作复杂度',120),('route','制作方式',130),('status','状态',140)]:
            self.tree.heading(col,text=title);self.tree.column(col,width=width,stretch=col in ('title','status'))
        auto_columns(self.tree)
        self.tree.tag_configure('completed',background=COLORS['row_completed'],foreground=COLORS['success'])
        table_shell.grid(row=0,column=0,sticky='nsew')
        tablebox.columnconfigure(0,weight=1);tablebox.rowconfigure(0,weight=1)
        auto_height(self.tree, tablebox)
        # 第 42 期第 1 条：进这一页默认把「需要白模的镜头」勾上（用户要的「默认选中需要白模的镜头栏」）。
        # 一份分镜只默认勾一次——用户自己取消过就不再替他勾回来，所以签名要记下来（state 跟着 Desktop 走）。
        signature=str(self.project)+'|'+str(self.source)
        defaulted=self.state.setdefault('defaulted',set())
        if signature not in defaulted:
            defaulted.add(signature)
            pending=[shot['id'] for shot in self.shots if self.needs_previs(shot['id'])]
            self.state['selected'].update(self.key(sid) for sid in pending)
            if pending and not self.state.get('busy'):
                self.state['summary']='已默认勾选 %d 个需要白模的镜头，可直接「手动制作白模」或自行调整'%len(pending)
        for shot in self.shots:
            sid=shot['id'];self.tree.insert('','end',iid=sid,text='',image=self.icons[int(self.key(sid) in self.state['selected'])],values=(sid,shot.get('title',''),shot.get('duration',5),''))
        self.box=CheckboxColumn(self.tree, self.icons, lambda sid: self.key(sid) in self.state['selected'], lambda sid,v: (self.state['selected'].add(self.key(sid)) if v else self.state['selected'].discard(self.key(sid))))
        from contract.shot_selection import bind_shot_checks
        bind_shot_checks(self.tree,self.toggle)
        # 第 53 期第 2 条：镜头内容框的格子加悬停高亮。高亮层是盖在格子上的 Label，鼠标因此落不到
        # 树上——单击／右键照原样重发给树（打勾选还是上面 bind_shot_checks 那一套），一条不改。
        from cell_hover import CellHover
        self.tree.cell_hover=CellHover(self.tree,('#1','#2','#3','#4','#5','#6'),lambda row,col:None,
                                  hover_only=True,forward=self.forward_to_tree)
        self.tree.heading('#0',command=lambda:self.box.toggle_all())
        self.status=tk.StringVar(value='就绪');ProgressLabel(self.body,textvariable=self.status).pack(anchor='w')
        level_row=ttk.Frame(self.body);level_row.pack(fill='x',pady=SPACING['xs'])
        ttk.Label(level_row,text='选中镜头的复杂度').pack(side='left')
        self.choices={'自动判断':'auto',**{name:key for key,name in previs_routing.LEVELS.items()}}
        self.chosen_level=tk.StringVar(value='自动判断')
        self.level_box=SelectBox(level_row,values=list(self.choices),textvariable=self.chosen_level);self.level_box.pack(
            side='left', padx=SPACING['sm']
        )
        self.reason=tk.StringVar(value='点击一个镜头查看判断依据')
        ProgressLabel(level_row,textvariable=self.reason,wraplength=WRAPLENGTH['md']).pack(side='left')
        self.tree.bind('<<TreeviewSelect>>',self.show_decision);self.level_box.bind('<<ComboboxSelected>>',self.change_level)
        # 主动作行：开始制作 → 强制停止 → 无人值守 → 线上白模。
        buttons=FlowBar(self.body);buttons.pack(fill='x',pady=SPACING['sm'])
        # 第 29 期第 1 条：原先这一行左头挂着阶段配置面板（模型＋SKILL）＋「调用设置」＋「Skill说明」，
        # 与标题栏那颗「阶段配置」重复，一并删掉——模型、SKILL、调用设置、SKILL 说明都在面板里。
        # 第 32 期第 1 条：这颗按钮改名「手动制作白模」（与其它阶段页的「手动XX」一个写法）。
        # 第 47 期第 3 条：点「手动制作白模」先问一句模型配没配（没配就问要不要现在去「阶段配置」）。
        from stage_models import manual_command
        self.start_button=PrimaryButton(buttons,text='手动制作白模',width=CHAR_WIDTH['3xl'],
                                   command=manual_command(self.desktop,'previs',self.start,self.desktop.win))
        self.start_button.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs']);ui_plugin_registry.module('stage_flow').follow(self.start_button,'previs')
        # 第 32 期第 6 条：这一页的阶段配置就挂在「手动制作白模」右边。
        self.desktop.stage_button=ui_plugin_registry.module('skill_panel').stage_button(buttons,self.desktop,self.desktop.page_of('previs'));self.desktop.stage_button.pack(
            side='left',padx=(SPACING['sm'],SPACING['xs']),pady=SPACING['xs']
        )
        import project_settings
        previs_engine=engine_name(self.project)
        SecondaryButton(buttons,text='强制停止制作',command=self.stop).pack(side='left',padx=SPACING['xs'])
        self.desktop.pet.auto_variable('auto_previs_var')
        self.online_button=SecondaryButton(buttons,text='线上白模入口',command=lambda:self.desktop.safe(self.online_selected));self.online_button.pack(
            side='left',padx=SPACING['xs']
        )
        # 第 29 期第 1 条：「调用设置」「Skill说明」这两颗按钮与标题栏「阶段配置」重复，删掉；
        # 编排模型与 SKILL 在面板里挑，SKILL 说明也在面板里直接看（prompt_with_settings 仍旧照用）。
        # 查看行：成品与目录，全部只读或打开文件，不派发任务。
        views=FlowBar(self.body);views.pack(fill='x',pady=SPACING['xs'])
        SecondaryButton(views,text='播放视频',command=lambda:self.open_file('preview')).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(views,text='打开工程调整',command=lambda:self.open_file('project_file')).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(views,text='当前白模目录',command=self.open_current_directory).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(views,text='制作记录',command=lambda:self.desktop.safe(self.logs)).pack(side='left',padx=SPACING['xs'])
        SecondaryButton(views,text='进入视频生成',command=lambda:self.desktop.show_stage('video')).pack(side='left',padx=SPACING['xs'])
        self.body.bind('<Destroy>',self.disposed,add='+')
        self.refresh()

    def refresh_environment(self):
        try:self.env_line.set(wm.environment_summary())
        except Exception:self.env_line.set('白模环境检查暂不可用')

    def check_environment(self):
        notify(self.desktop.win,wm.diagnose_text(),title='白模环境检查')

    def key(self, sid):return str(self.project)+'|'+sid

    def needs_previs(self, sid):
        """这一镜要不要白模：判断结果不是「简单／固定动作」就要；已经有可用成品的不用再勾。"""
        level=(self.decisions.get(sid) or {}).get('level')
        if level in (None,'simple'):return False
        try:
            record=wm.read_record(white_model_shot_directory(self.project,sid,source=self.source))
        except Exception:
            return True
        preview=record.get('preview')
        return not (preview and Path(preview).is_file())

    def update_header_check(self):
        self.box.refresh_header()

    def toggle(self, sid):
        self.box.toggle(sid)

    def forward_to_tree(self, event):
        self.tree.event_generate('<Button-%d>'%int(event.num),
                            x=event.x_root-self.tree.winfo_rootx(),
                            y=event.y_root-self.tree.winfo_rooty())
        return 'break'

    def adjust_targets(self):
        """第 47 期第 1 条：调复杂度认的目标与「手动制作白模」逐条对齐——勾选优先，高亮兜底。"""
        return work_rows(self.tree,lambda sid: self.key(sid) in self.state['selected'])

    def show_decision(self, event=None):
        rows,_source=self.adjust_targets()
        if not rows:return
        row=self.decisions[rows[0]];self.chosen_level.set(next(name for name,value in self.choices.items() if value==row['override']));self.reason.set(row['reason'])

    def change_level(self, event=None):
        try:
            if self.state.get('busy'):raise ValueError('请等待本批次结束后调整复杂度')
            rows,how=self.adjust_targets()
            if not rows:raise ValueError('请先点击一个镜头')
            # 勾选了几行就一起改：原来只改高亮那一行，勾了 3 镜却只动 1 镜，页面上看不出区别。
            from stage_execution_service import save_stage_previs_override
            for sid in rows:save_stage_previs_override(self.project,self.source,sid,self.choices[self.chosen_level.get()])
            self.decisions=previs_entries(self.project,self.source)
            if len(rows)>1:self.reason.set('已把 %d 个镜头设为「%s」%s'%(len(rows),self.chosen_level.get(),work_hint(rows,how)))
            self.show_decision();self.refresh()
        except Exception as exc:notify(self.desktop.win, str(exc), level='error', title='动作复杂度', status=self.desktop.status)

    def start(self):
        if self.state['busy']:notify(self.desktop.win, '已有本地任务运行中，请等待完成', title='白模预演', status=self.desktop.status);return
        # 第 47 期第 1 条：勾选优先；一个都没勾时，把高亮那一行当作选中的那一个（顺手补上勾选，
        # 页面上的小勾立刻看得见）。原来这里只认勾选，用户点了一行看着是选中的，却被告知「请先勾选」。
        ids,how=self.adjust_targets()
        if not ids:notify(self.desktop.win, '请先勾选要制作的镜头', title='白模预演', status=self.desktop.status);return
        if how=='shown':
            self.state['selected'].add(self.key(ids[0]))
            self.state['summary']='没有勾选行，按高亮的那一行 %s 派发（已替您勾上）'%ids[0]
            self.box.refresh_row(ids[0])
        try:
            # 第 47 期第 2 条：手动派发就在浏览器里开一页制作监视页（HTTP），不弹桌面 Blender。
            # 路由模块只负责分流；页面在需要复杂镜头时延迟取得自动制作执行器，
            # 避免 ``previs_routing <-> previs_automation`` 的服务层循环依赖。
            agent_start=ui_plugin_registry.module('previs_automation').start
            from stage_execution_service import dispatch_stage_previs
            groups=dispatch_stage_previs(self.project,self.source,ids,self.state,monitor=True,start_complex=agent_start)
            if groups['medium']:online_window(self.desktop,self.source,groups['medium'])
            self.refresh()
        except Exception as exc:notify(self.desktop.win, str(exc), level='error', title='白模预演', status=self.desktop.status)

    def stop(self):
        """强制关闭制作进程：结束正在跑的引擎（连同子进程），并让工作线程停掉后续镜头。

        taskkill 放后台线程：界面线程不等待，按下去立刻有反馈；进度与结果只写共享 state，
        由本页 750 毫秒一次的刷新显示，线程里不碰 Tk。
        """
        if not self.state.get('busy'):
            notify(self.desktop.win, '当前没有正在制作的白模任务，无需停止', title='白模预演', status=self.desktop.status);return
        self.state['summary']='正在强制停止制作进程…'
        def work():
            try:
                from ui_plugin_registry import module
                module('previs_automation').force_stop(self.project,self.state)
            except Exception as exc:self.state['summary']='强制停止未完成：'+str(exc)
        import threading
        threading.Thread(target=work,daemon=True).start()

    def current(self):
        # 第 47 期第 1 条：查看／定位这一类是高亮优先——高亮那一行才算「我正在看的这一行」；
        # 一行都没高亮时才退回第一个勾选行（原来没高亮就直接报错）。
        row=view_row(self.tree,lambda sid: self.key(sid) in self.state['selected'])
        if not row:raise ValueError('请先点击一个镜头行')
        return row

    def online_selected(self):
        rows,how=self.adjust_targets()
        ids=[sid for sid in rows if self.decisions[sid]['level']=='medium']
        if not ids:raise ValueError('请先勾选待制作的中等复杂度镜头'+work_hint(rows,how))
        online_window(self.desktop,self.source,ids)

    def open_file(self, field):
        try:
            sid=self.current();record=wm.read_record(white_model_shot_directory(self.project,sid,source=self.source));path=Path(record.get(field,''))
            if not path.is_file():raise ValueError('请先创建相应工程或视频')
            if field=='project_file':
                from native_apps import open_blender
                open_blender(path)
            else:open_path(path)
        except Exception as exc:notify(self.desktop.win, str(exc), level='error', title='白模预演', status=self.desktop.status)

    def open_current_directory(self):
        try:
            folder=white_model_shot_directory(self.project,self.current(),source=self.source)
            folder.mkdir(parents=True,exist_ok=True)
            open_path(folder)
        except Exception as exc:
            notify(self.desktop.win, str(exc), level='error', title='当前白模目录', status=self.desktop.status)

    def logs(self):
        folder=previs_records_directory(self.project,self.state);open_path(folder);self.desktop.status.set('已打开制作记录：'+str(folder))

    def record_status(self, sid):
        current_state=self.state['status'].get(self.key(sid))
        if current_state and self.state.get('busy'):return current_state
        try:
            record=wm.read_record(white_model_shot_directory(self.project,sid,source=self.source))
            if record.get('preview') and Path(record['preview']).is_file():
                return '已就绪' if previs_ready(self.project,sid,self.source) else '预演已过期，请重新校验'
            if record.get('project_file') and Path(record['project_file']).is_file():return '工程已生成，待导出视频'
            level=self.decisions[sid]['level']
            if level=='simple':return '无需白模，直接生成视频'
            if level=='medium':return '待线上制作／导入'
            if current_state and (current_state.startswith('失败') or current_state=='已停止'):return current_state
            return '待制作'
        except (OSError,ValueError):return '记录异常，请检查'

    def refresh(self):
        if not self.body.winfo_exists():return
        for shot in self.shots:
            sid=shot['id'];status_text=self.record_status(sid);self.tree.item(sid,image=self.icons[int(self.key(sid) in self.state['selected'])],tags=('completed',) if status_text=='已就绪' else ());self.tree.set(sid,'status',status_text)
            self.tree.set(sid,'complexity',previs_routing.LEVELS[self.decisions[sid]['level']]);self.tree.set(sid,'route',self.decisions[sid]['route'])
        self.update_header_check()
        self.level_box.state(['disabled'] if self.state.get('busy') else ['!disabled'])
        # 第 47 期第 1 条：两颗制作按钮的可用状态跟 start／online_selected 用同一个口径
        # （勾选优先、高亮兜底），否则会出现「按钮是灰的但点了也能做」或者反过来的错配。
        target_rows,_target_source=self.adjust_targets()
        selected_any=bool(target_rows)
        self.start_button.state(['disabled'] if self.state.get('busy') or not selected_any else ['!disabled'])
        medium_selected=any(self.decisions[sid]['level']=='medium' for sid in target_rows)
        self.online_button.state(['disabled'] if self.state.get('busy') or not medium_selected else ['!disabled'])
        line=self.state.get('summary','请选择要制作的镜头')
        if self.state.get('monitor'):line+='　·　监视页：'+str(self.state['monitor'][0])
        self.status.set(line)
        previous=getattr(self.body,'_previs_refresh',None)
        if previous:self.body.after_cancel(previous)
        self.body._previs_refresh=self.body.after(750,self.refresh)

    def disposed(self, event):
        if event.widget is self.body and getattr(self.body,'_previs_refresh',None):self.body.after_cancel(self.body._previs_refresh)
