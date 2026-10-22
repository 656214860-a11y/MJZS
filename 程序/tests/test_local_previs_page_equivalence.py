"""local_previs.show 改写成 _LocalPrevisWindow：HEAD 旧实现原样内嵌，替换到同一个真 Desktop 的白模预演页上，
做通用探测（安全按钮、镜头列表选中／全选／取消）后再点“强制停止制作”，对照每步控件树与状态栏。"""
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import local_previs as module
import pet_state
from catalog_page_test_support import show_catalog_page_ready
from page_diff_support import _clean, button_by_text, poke, pump, safe_call, snapshot
from skip_reasons import PLATFORM_TKINTER
from test_script_structure_page_equivalence import _open_app
from window_diff_support import legacy

LEGACY = 'def show(desktop):\n    project=Path(desktop.root);source=desktop.current_frame_json()\n    shots=read_json(source).get(\'shots\',[])\n    state=getattr(desktop,\'previs_jobs\',None)\n    if state is None:state={\'busy\':False,\'status\':{},\'selected\':set()};desktop.previs_jobs=state\n    if not state.get(\'busy\'):\n        # 旧项目的白模成果还在旧目录：打开本页时一次性迁入项目身份目录（可重复、不覆盖、\n        # 中途失败原样搬回）。项目已有身份或有任务在跑时不动任何文件。\n        try:\n            from stage_execution_service import migrate_white_model_directories\n            moved=migrate_white_model_directories(project).get(\'moved\')\n            if moved:state[\'summary\']=\'已把 %d 个旧白模目录迁入项目身份目录，原成果未覆盖\'%len(moved)\n        except Exception as exc:state[\'summary\']=\'白模目录迁移未执行：\'+str(exc)\n    body=ttk.Frame(desktop.content);body.pack(fill=\'both\',expand=True)\n    decisions=previs_entries(project,source)\n    DescriptionBlock(body,text=\'简单／固定动作：无需白模；中等动作：线上简单制作；复杂动作：Agent 自动制作。\',wraplength=920).pack(anchor=\'w\')\n    DescriptionBlock(body,text=\'优先读取分镜的复杂度标注；未标注时自动判断。选中镜头可手动调整。\').pack(\n        anchor=\'w\', pady=SPACING[\'xs\']\n    )\n    # O26：成果目录与 Blender 分开，且成果目录来自可配置的用户数据目录；这里给一行只读检查结果，\n    # 「白模环境检查」按需跑一次完整检查（版本＋写权限），打开页面的每次刷新只做轻量判断。\n    env_line=tk.StringVar(value=\'\')\n    def refresh_environment():\n        try:env_line.set(wm.environment_summary())\n        except Exception:env_line.set(\'白模环境检查暂不可用\')\n    def check_environment():\n        notify(desktop.win,wm.diagnose_text(),title=\'白模环境检查\')\n    env_row=ttk.Frame(body);env_row.pack(fill=\'x\',pady=SPACING[\'xs\'])\n    SecondaryButton(env_row,text=\'白模环境检查\',command=lambda:desktop.safe(check_environment)).pack(side=\'left\')\n    ProgressLabel(env_row,textvariable=env_line,wraplength=780).pack(side=\'left\',padx=SPACING[\'sm\'])\n    refresh_environment()\n    tablebox=ttk.Frame(body);tablebox.pack(fill=\'both\',expand=True,pady=SPACING[\'sm\'])\n    # 第 47 期第 5 条：用户点名删掉「制作进度」那一栏——进度条整列撤掉，状态那一栏照旧说事。\n    table_shell=DataTable(tablebox,columns=[\n        (\'id\',\'镜头\',165),(\'title\',\'内容\',150),(\'duration\',\'秒数\',50),\n        (\'complexity\',\'动作复杂度\',120),(\'route\',\'制作方式\',130),(\'status\',\'状态\',140),\n    ],show=\'tree headings\',height=8,selectmode=\'browse\',empty_text=\'暂无镜头\')\n    tree=table_shell.tree\n    icons=desktop.win._tick_images[:2]\n    configure_check_column(tree)\n    for col,title,width in [(\'id\',\'镜头\',165),(\'title\',\'内容\',150),(\'duration\',\'秒数\',50),(\'complexity\',\'动作复杂度\',120),(\'route\',\'制作方式\',130),(\'status\',\'状态\',140)]:\n        tree.heading(col,text=title);tree.column(col,width=width,stretch=col in (\'title\',\'status\'))\n    auto_columns(tree)\n    tree.tag_configure(\'completed\',background=COLORS[\'border_default\'],foreground=COLORS[\'success\'])\n    table_shell.grid(row=0,column=0,sticky=\'nsew\')\n    tablebox.columnconfigure(0,weight=1);tablebox.rowconfigure(0,weight=1)\n    auto_height(tree, tablebox)\n    def key(sid):return str(project)+\'|\'+sid\n    def needs_previs(sid):\n        """这一镜要不要白模：判断结果不是「简单／固定动作」就要；已经有可用成品的不用再勾。"""\n        level=(decisions.get(sid) or {}).get(\'level\')\n        if level in (None,\'simple\'):return False\n        try:\n            record=wm.read_record(white_model_shot_directory(project,sid,source=source))\n        except Exception:\n            return True\n        preview=record.get(\'preview\')\n        return not (preview and Path(preview).is_file())\n    # 第 42 期第 1 条：进这一页默认把「需要白模的镜头」勾上（用户要的「默认选中需要白模的镜头栏」）。\n    # 一份分镜只默认勾一次——用户自己取消过就不再替他勾回来，所以签名要记下来（state 跟着 Desktop 走）。\n    signature=str(project)+\'|\'+str(source)\n    defaulted=state.setdefault(\'defaulted\',set())\n    if signature not in defaulted:\n        defaulted.add(signature)\n        pending=[shot[\'id\'] for shot in shots if needs_previs(shot[\'id\'])]\n        state[\'selected\'].update(key(sid) for sid in pending)\n        if pending and not state.get(\'busy\'):\n            state[\'summary\']=\'已默认勾选 %d 个需要白模的镜头，可直接「手动制作白模」或自行调整\'%len(pending)\n    for shot in shots:\n        sid=shot[\'id\'];tree.insert(\'\',\'end\',iid=sid,text=\'\',image=icons[int(key(sid) in state[\'selected\'])],values=(sid,shot.get(\'title\',\'\'),shot.get(\'duration\',5),\'\'))\n    box=CheckboxColumn(tree, icons, lambda sid: key(sid) in state[\'selected\'], lambda sid,v: (state[\'selected\'].add(key(sid)) if v else state[\'selected\'].discard(key(sid))))\n    def update_header_check():\n        box.refresh_header()\n    def toggle(sid):\n        box.toggle(sid)\n    from shot_selection import bind_shot_checks\n    bind_shot_checks(tree,toggle)\n    # 第 53 期第 2 条：镜头内容框的格子加悬停高亮。高亮层是盖在格子上的 Label，鼠标因此落不到\n    # 树上——单击／右键照原样重发给树（打勾选还是上面 bind_shot_checks 那一套），一条不改。\n    from cell_hover import CellHover\n    def forward_to_tree(event):\n        tree.event_generate(\'<Button-%d>\'%int(event.num),\n                            x=event.x_root-tree.winfo_rootx(),\n                            y=event.y_root-tree.winfo_rooty())\n        return \'break\'\n    tree.cell_hover=CellHover(tree,(\'#1\',\'#2\',\'#3\',\'#4\',\'#5\',\'#6\'),lambda row,col:None,\n                              hover_only=True,forward=forward_to_tree)\n    tree.heading(\'#0\',command=lambda:box.toggle_all())\n    status=tk.StringVar(value=\'就绪\');ProgressLabel(body,textvariable=status).pack(anchor=\'w\')\n    level_row=ttk.Frame(body);level_row.pack(fill=\'x\',pady=SPACING[\'xs\'])\n    ttk.Label(level_row,text=\'选中镜头的复杂度\').pack(side=\'left\')\n    choices={\'自动判断\':\'auto\',**{name:key for key,name in previs_routing.LEVELS.items()}}\n    chosen_level=tk.StringVar(value=\'自动判断\')\n    level_box=SelectBox(level_row,values=list(choices),textvariable=chosen_level);level_box.pack(\n        side=\'left\', padx=SPACING[\'sm\']\n    )\n    reason=tk.StringVar(value=\'点击一个镜头查看判断依据\')\n    ProgressLabel(level_row,textvariable=reason,wraplength=610).pack(side=\'left\')\n    def adjust_targets():\n        """第 47 期第 1 条：调复杂度认的目标与「手动制作白模」逐条对齐——勾选优先，高亮兜底。"""\n        return work_rows(tree,lambda sid: key(sid) in state[\'selected\'])\n    def show_decision(event=None):\n        rows,_source=adjust_targets()\n        if not rows:return\n        row=decisions[rows[0]];chosen_level.set(next(name for name,value in choices.items() if value==row[\'override\']));reason.set(row[\'reason\'])\n    def change_level(event=None):\n        nonlocal decisions\n        try:\n            if state.get(\'busy\'):raise ValueError(\'请等待本批次结束后调整复杂度\')\n            rows,how=adjust_targets()\n            if not rows:raise ValueError(\'请先点击一个镜头\')\n            # 勾选了几行就一起改：原来只改高亮那一行，勾了 3 镜却只动 1 镜，页面上看不出区别。\n            from stage_execution_service import save_stage_previs_override\n            for sid in rows:save_stage_previs_override(project,source,sid,choices[chosen_level.get()])\n            decisions=previs_entries(project,source)\n            if len(rows)>1:reason.set(\'已把 %d 个镜头设为「%s」%s\'%(len(rows),chosen_level.get(),work_hint(rows,how)))\n            show_decision();refresh()\n        except Exception as exc:notify(desktop.win, str(exc), level=\'error\', title=\'动作复杂度\', status=desktop.status)\n    tree.bind(\'<<TreeviewSelect>>\',show_decision);level_box.bind(\'<<ComboboxSelected>>\',change_level)\n    def start():\n        if state[\'busy\']:notify(desktop.win, \'已有本地任务运行中，请等待完成\', title=\'白模预演\', status=desktop.status);return\n        # 第 47 期第 1 条：勾选优先；一个都没勾时，把高亮那一行当作选中的那一个（顺手补上勾选，\n        # 页面上的小勾立刻看得见）。原来这里只认勾选，用户点了一行看着是选中的，却被告知「请先勾选」。\n        ids,how=adjust_targets()\n        if not ids:notify(desktop.win, \'请先勾选要制作的镜头\', title=\'白模预演\', status=desktop.status);return\n        if how==\'shown\':\n            state[\'selected\'].add(key(ids[0]))\n            state[\'summary\']=\'没有勾选行，按高亮的那一行 %s 派发（已替您勾上）\'%ids[0]\n            box.refresh_row(ids[0])\n        try:\n            # 第 47 期第 2 条：手动派发就在浏览器里开一页制作监视页（HTTP），不弹桌面 Blender。\n            # 路由模块只负责分流；页面在需要复杂镜头时延迟取得自动制作执行器，\n            # 避免 ``previs_routing <-> previs_automation`` 的服务层循环依赖。\n            agent_start=ui_plugin_registry.module(\'previs_automation\').start\n            from stage_execution_service import dispatch_stage_previs\n            groups=dispatch_stage_previs(project,source,ids,state,monitor=True,start_complex=agent_start)\n            if groups[\'medium\']:online_window(desktop,source,groups[\'medium\'])\n            refresh()\n        except Exception as exc:notify(desktop.win, str(exc), level=\'error\', title=\'白模预演\', status=desktop.status)\n    # 主动作行：开始制作 → 强制停止 → 无人值守 → 线上白模。\n    buttons=FlowBar(body);buttons.pack(fill=\'x\',pady=SPACING[\'sm\'])\n    # 第 29 期第 1 条：原先这一行左头挂着阶段配置面板（模型＋SKILL）＋「调用设置」＋「Skill说明」，\n    # 与标题栏那颗「阶段配置」重复，一并删掉——模型、SKILL、调用设置、SKILL 说明都在面板里。\n    # 第 32 期第 1 条：这颗按钮改名「手动制作白模」（与其它阶段页的「手动XX」一个写法）。\n    # 第 47 期第 3 条：点「手动制作白模」先问一句模型配没配（没配就问要不要现在去「阶段配置」）。\n    from stage_models import manual_command\n    start_button=PrimaryButton(buttons,text=\'手动制作白模\',width=16,\n                               command=manual_command(desktop,\'previs\',start,desktop.win))\n    start_button.pack(side=\'left\',padx=(SPACING[\'none\'],SPACING[\'xs\']),pady=SPACING[\'xs\']);ui_plugin_registry.module(\'stage_flow\').follow(start_button,\'previs\')\n    # 第 32 期第 6 条：这一页的阶段配置就挂在「手动制作白模」右边。\n    desktop.stage_button=ui_plugin_registry.module(\'skill_panel\').stage_button(buttons,desktop,desktop.page_of(\'previs\'));desktop.stage_button.pack(\n        side=\'left\',padx=(SPACING[\'sm\'],SPACING[\'xs\']),pady=SPACING[\'xs\']\n    )\n    import project_settings\n    previs_engine=engine_name(project)\n    def stop():\n        """强制关闭制作进程：结束正在跑的引擎（连同子进程），并让工作线程停掉后续镜头。\n\n        taskkill 放后台线程：界面线程不等待，按下去立刻有反馈；进度与结果只写共享 state，\n        由本页 750 毫秒一次的刷新显示，线程里不碰 Tk。\n        """\n        if not state.get(\'busy\'):\n            notify(desktop.win, \'当前没有正在制作的白模任务，无需停止\', title=\'白模预演\', status=desktop.status);return\n        state[\'summary\']=\'正在强制停止制作进程…\'\n        def work():\n            try:\n                from ui_plugin_registry import module\n                module(\'previs_automation\').force_stop(project,state)\n            except Exception as exc:state[\'summary\']=\'强制停止未完成：\'+str(exc)\n        import threading\n        threading.Thread(target=work,daemon=True).start()\n    SecondaryButton(buttons,text=\'强制停止制作\',command=stop).pack(side=\'left\',padx=SPACING[\'xs\'])\n    desktop.pet.auto_variable(\'auto_previs_var\')\n    def current():\n        # 第 47 期第 1 条：查看／定位这一类是高亮优先——高亮那一行才算「我正在看的这一行」；\n        # 一行都没高亮时才退回第一个勾选行（原来没高亮就直接报错）。\n        row=view_row(tree,lambda sid: key(sid) in state[\'selected\'])\n        if not row:raise ValueError(\'请先点击一个镜头行\')\n        return row\n    def online_selected():\n        rows,how=adjust_targets()\n        ids=[sid for sid in rows if decisions[sid][\'level\']==\'medium\']\n        if not ids:raise ValueError(\'请先勾选待制作的中等复杂度镜头\'+work_hint(rows,how))\n        online_window(desktop,source,ids)\n    online_button=SecondaryButton(buttons,text=\'线上白模入口\',command=lambda:desktop.safe(online_selected));online_button.pack(\n        side=\'left\',padx=SPACING[\'xs\']\n    )\n    # 第 29 期第 1 条：「调用设置」「Skill说明」这两颗按钮与标题栏「阶段配置」重复，删掉；\n    # 编排模型与 SKILL 在面板里挑，SKILL 说明也在面板里直接看（prompt_with_settings 仍旧照用）。\n    # 查看行：成品与目录，全部只读或打开文件，不派发任务。\n    views=FlowBar(body);views.pack(fill=\'x\',pady=SPACING[\'xs\'])\n    def open_file(field):\n        try:\n            sid=current();record=wm.read_record(white_model_shot_directory(project,sid,source=source));path=Path(record.get(field,\'\'))\n            if not path.is_file():raise ValueError(\'请先创建相应工程或视频\')\n            if field==\'project_file\':\n                from native_apps import open_blender\n                open_blender(path)\n            else:open_path(path)\n        except Exception as exc:notify(desktop.win, str(exc), level=\'error\', title=\'白模预演\', status=desktop.status)\n    SecondaryButton(views,text=\'播放视频\',command=lambda:open_file(\'preview\')).pack(side=\'left\',padx=SPACING[\'xs\'])\n    SecondaryButton(views,text=\'打开工程调整\',command=lambda:open_file(\'project_file\')).pack(side=\'left\',padx=SPACING[\'xs\'])\n    def open_current_directory():\n        try:\n            folder=white_model_shot_directory(project,current(),source=source)\n            folder.mkdir(parents=True,exist_ok=True)\n            open_path(folder)\n        except Exception as exc:\n            notify(desktop.win, str(exc), level=\'error\', title=\'当前白模目录\', status=desktop.status)\n    SecondaryButton(views,text=\'当前白模目录\',command=open_current_directory).pack(side=\'left\',padx=SPACING[\'xs\'])\n    def logs():\n        folder=previs_records_directory(project,state);open_path(folder);desktop.status.set(\'已打开制作记录：\'+str(folder))\n    SecondaryButton(views,text=\'制作记录\',command=lambda:desktop.safe(logs)).pack(side=\'left\',padx=SPACING[\'xs\'])\n    SecondaryButton(views,text=\'进入视频生成\',command=lambda:desktop.show_stage(\'video\')).pack(side=\'left\',padx=SPACING[\'xs\'])\n    def record_status(sid):\n        current_state=state[\'status\'].get(key(sid))\n        if current_state and state.get(\'busy\'):return current_state\n        try:\n            record=wm.read_record(white_model_shot_directory(project,sid,source=source))\n            if record.get(\'preview\') and Path(record[\'preview\']).is_file():\n                return \'已就绪\' if previs_ready(project,sid,source) else \'预演已过期，请重新校验\'\n            if record.get(\'project_file\') and Path(record[\'project_file\']).is_file():return \'工程已生成，待导出视频\'\n            level=decisions[sid][\'level\']\n            if level==\'simple\':return \'无需白模，直接生成视频\'\n            if level==\'medium\':return \'待线上制作／导入\'\n            if current_state and (current_state.startswith(\'失败\') or current_state==\'已停止\'):return current_state\n            return \'待制作\'\n        except (OSError,ValueError):return \'记录异常，请检查\'\n    def refresh():\n        if not body.winfo_exists():return\n        for shot in shots:\n            sid=shot[\'id\'];status_text=record_status(sid);tree.item(sid,image=icons[int(key(sid) in state[\'selected\'])],tags=(\'completed\',) if status_text==\'已就绪\' else ());tree.set(sid,\'status\',status_text)\n            tree.set(sid,\'complexity\',previs_routing.LEVELS[decisions[sid][\'level\']]);tree.set(sid,\'route\',decisions[sid][\'route\'])\n        update_header_check()\n        level_box.state([\'disabled\'] if state.get(\'busy\') else [\'!disabled\'])\n        # 第 47 期第 1 条：两颗制作按钮的可用状态跟 start／online_selected 用同一个口径\n        # （勾选优先、高亮兜底），否则会出现「按钮是灰的但点了也能做」或者反过来的错配。\n        target_rows,_target_source=adjust_targets()\n        selected_any=bool(target_rows)\n        start_button.state([\'disabled\'] if state.get(\'busy\') or not selected_any else [\'!disabled\'])\n        medium_selected=any(decisions[sid][\'level\']==\'medium\' for sid in target_rows)\n        online_button.state([\'disabled\'] if state.get(\'busy\') or not medium_selected else [\'!disabled\'])\n        line=state.get(\'summary\',\'请选择要制作的镜头\')\n        if state.get(\'monitor\'):line+=\'\u3000·\u3000监视页：\'+str(state[\'monitor\'][0])\n        status.set(line)\n        previous=getattr(body,\'_previs_refresh\',None)\n        if previous:body.after_cancel(previous)\n        body._previs_refresh=body.after(750,refresh)\n    def disposed(event):\n        if event.widget is body and getattr(body,\'_previs_refresh\',None):body.after_cancel(body._previs_refresh)\n    body.bind(\'<Destroy>\',disposed,add=\'+\')\n    refresh()\n'

EXTRA = ()


def _labels(widget):
    out = [widget] if widget.winfo_class() == 'TLabel' else []
    for child in widget.winfo_children():
        out.extend(_labels(child))
    return out


class LocalPrevisPageEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            tkinter.Tk().destroy()
            cls.tk = tkinter
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)

    def _session(self, impl, summary='', probe=None):
        td = Path(tempfile.gettempdir()) / ('drama_previs_diff_%d' % os.getpid())
        shutil.rmtree(td, ignore_errors=True)
        td.mkdir(parents=True)
        try:
            win, desktop = _open_app(self.tk, td)
            roots = sorted({str(td), td.as_posix(), str(td.resolve()), td.resolve().as_posix()}, key=len, reverse=True)
            steps = []
            try:
                # HEAD 旧实现的环境说明变量只被一次性调用的闭包引用，show 返回后即被回收、标签变空；
                # 新实现挂在 self 上会一直显示。为让其余控件树可比，这里把说明文字统一置空，
                # 修复本身由 test_environment_line_survives 单独断言。
                with mock.patch.object(module, 'show', impl),                         mock.patch.object(module.wm, 'environment_summary', return_value=summary):
                    show_catalog_page_ready(desktop, pet_state.PAGE_OF['previs'])
                    pump(win, 1.0)   # 换行宽度随 <Configure> 分几轮收敛，等布局稳定再拍
                    if probe is not None:
                        import gc; gc.collect(); pump(win, 0.1)
                        probe.extend(str(w.cget('text')) for w in _labels(desktop.content))
                        return []
                    poke(desktop, 'previs#1', steps, roots)
                    for text in EXTRA:
                        button = button_by_text(desktop.content, text)
                        if button is None:
                            steps.append((text, 'missing'))
                            continue
                        outcome = safe_call(button.invoke)
                        pump(win, 0.1)
                        steps.append((text, outcome, snapshot(desktop.content, roots), _clean(desktop.status.get(), roots)))
                    desktop.go_page(pet_state.PAGE_OF['assets'])
                    pump(win, 0.1)
                    show_catalog_page_ready(desktop, pet_state.PAGE_OF['previs'])
                    pump(win, 1.0)
                    poke(desktop, 'previs#2', steps, roots)
            finally:
                desktop.cancel_timers()
                win.destroy()
            # Tk 变量名（PY_VAR<n>）随进程里已建的变量数递增，与实现无关，统一抹掉。
            # 旧实现那个被回收的变量在快照里没有 var 项、新实现是空串 var 项，同样抹掉空 var 项。
            return [re.sub(r", \('var', ''\)", '', re.sub(r'PY_VAR\d+', 'PY_VAR', repr(step))) for step in steps]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_matches_legacy(self):
        old = legacy(module, LEGACY, 'show')
        self._session(old)   # 预热：进程里第一次建窗的布局与之后不同
        expected = self._session(old)
        actual = self._session(module.show)
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertEqual(a, b, a[:60])
        self.assertGreater(max(step.count("('TFrame'") for step in expected), 5)   # 对照不能是空对空：页面真的建出了一棵控件树

    def test_environment_line_survives(self):
        seen = []
        self._session(module.show, summary='环境说明样例', probe=seen)
        self.assertIn('环境说明样例', seen)

if __name__ == '__main__':
    unittest.main()
