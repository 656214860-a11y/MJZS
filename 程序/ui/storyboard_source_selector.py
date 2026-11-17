# -*- coding: utf-8 -*-
"""下游页面共用的「选择分镜」下拉框（L4 界面）。

从 storyboard_selection 拆出（R2311，J 路线 #20）：采用清单与偏好的读写留在 L3 的
storyboard_selection，Tk 控件只在这里。
"""
import infra.app_logging as app_logging
from pathlib import Path
from agent.core import save
from orchestrator.storyboard_selection import adopted, focus, writable_prefs
from ui_tokens import SPACING


def source_selector(app,index,*,select_box):
    """Downstream pages share one focus control while keeping every adopted file."""
    import tkinter as tk
    from tkinter import ttk
    sources=adopted(app.root)
    if not sources:return
    from domain.storyboard_source_service import source_options
    labels,sources,current_index=source_options(sources,app.asset_scope(),app.current_frame_json())
    row=ttk.Frame(app.content);row.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
    # 第 64 期任务 5：「全部分镜」这一项原来只有资产管理页有，用户要它同步到其他页面的
    # 「选择分镜」下拉框——各页本来就是同一份范围偏好（asset_scope：全部分镜 ／ 只这一份），
    # 列出来的项也该一模一样。只有一份采用清单时这一项没有意义，就照旧不列。
    broad=len(sources)>1
    def display_index():
        """下拉框该显示的那一条：「全部分镜」不是一个文件，只能按范围偏好判断。"""
        return source_options(adopted(app.root),app.asset_scope(),app.current_frame_json())[2]
    line=ttk.Frame(row);line.pack(fill='x',pady=SPACING['xs'])
    ttk.Label(line,text='选择分镜').pack(side='left',padx=(SPACING['none'],SPACING['sm']))
    combo=select_box(line,values=labels,width=1)
    combo.pack(side='left',fill='x',expand=True)
    combo.current(current_index)
    def guard_wheel(event):
        # 「选择分镜」只读下拉框绝不被滚轮改选：控件自身的绑定先于 TCombobox 类绑定执行，
        # 这里直接把滚轮转给页面滚动并中断后续绑定，即使页面滚轮标签万一没补上也不会换文件。
        scroll=getattr(app,'scroll_page',None)
        if scroll is not None:scroll(event)
        return 'break'
    combo.bind('<MouseWheel>',guard_wheel)
    def collapse():
        """重建页面前先收起 Tk 自建的下拉弹窗：弹窗与页面同时变化，看起来就是「换文件内容抖动」。"""
        try:app.win.tk.call('ttk::combobox::Unpost',str(combo))
        except tk.TclError:pass
    def choose(event=None):
        selected=combo.current()
        if selected<0:return
        def apply():
            video=getattr(app,'video',None)
            if video and (getattr(video,'busy',False) or getattr(video,'optimizer_busy',False)):
                raise ValueError('请等待当前镜头操作完成后再切换集数')
            target=sources[selected]
            # 重复选中同一项（例如下拉列表里点回原来那条）不再重建整页，避免内容抖动。
            if broad and target is None:
                if app.asset_scope()!='current':return
            # 范围偏好还是「全部分镜」时，点回当前这一份也要把它切回「只这一份」，
            # 否则下拉框会立刻弹回「全部分镜」，看着像点了没反应。
            elif (target is not None and app.asset_scope()=='current'
                  and app.current_frame_json()==Path(target).resolve()):return
            if broad:
                data=writable_prefs(app.root);data['asset_scope']='current' if target else 'adopted'
                save(Path(app.root)/'ui_settings.json',data)
            if target is not None:focus(app.root,target)
            # 先明确收起下拉弹窗，等本控件的事件处理结束后再重建页面：切换途中的重建会让页面抖动。
            collapse()
            app.win.after_idle(lambda:app.safe(lambda:app.show(index)))
        def resync():
            """切换没生效时把下拉框显示拉回真实文件。

            后台任务占用时 safe 只提示不切换，下拉框却已经停在新文件名上：显示与页面内容
            不一致，下一次重建又跳回原文件，表现出来就是「换文件时内容抖动」。
            """
            try:
                if not combo.winfo_exists():return
                target=display_index()
                if combo.current()!=target:combo.current(target)
            except Exception:app_logging.swallowed()
        app.safe(apply)
        app.win.after_idle(resync)
    combo.bind('<<ComboboxSelected>>',choose)
