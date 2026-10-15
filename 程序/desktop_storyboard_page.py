"""首帧管理页（阶段 keyframe）的页面构建（方法名为 ``Desktop.storyboard``，侧栏第 07 项）。

从 ``desktop.Desktop`` 原样迁出（R1504 拆分步骤 3，一页一轮）：方法体未改，``self`` 语义不变，
``Desktop`` 通过继承 ``StoryboardPageMixin`` 获得。测试按 ``desktop.<名字>`` 打补丁的名字（confirm／open_path 等）
经 ``desktop_page_support`` 的转发函数在调用时取 ``desktop`` 的当前值，补丁照常生效。
"""
import pet_state
import asset_thumbs
import frame_checks
import tkinter as tk
import ui_plugin_registry
from agent.core import read
from pathlib import Path
from responsive_ui import CheckboxColumn, FlowBar, bind_row_toggle, configure_check_column, fit_columns_by_content, fit_row_height
from storyboard_paths import media_root
from tkinter import ttk
from ui_tokens import COLORS, SPACING
from ui_widgets import DataTable, SelectBox
from desktop_page_support import ASSET_ROW_HEIGHT, FileDialog, THUMB_SIZE, confirm, open_path

PAGE = pet_state.PAGE_OF


class StoryboardPageMixin:
    """Desktop 的首帧管理页构建（见模块说明）。"""
    def storyboard(self):
        from keyframe_import import resume,watch_list
        from keyframe_batch import frame_prompt
        from keyframe_page_controller import KeyframePageController
        resume(self)
        source=self.current_frame_json()
        episode=read(source);base=media_root(source)
        # 第 68 期任务 12：用户报「全部分镜显示不全」。这一页原来只读当前那一份分镜；现在「选择分镜」
        # 选到「全部分镜」时，把已采用的每一份的镜头一起列出来，每一镜各自认自己那一份的目录与文件。
        # 只有一份（用户选了「只这一份」，或本来就只采用了一份）时，下面与从前一字不差。
        def load_rows():
            from storyboard_rows_service import frame_rows
            return frame_rows(self.root, source, episode, base, self.asset_scope(), self.note)
        rows=load_rows()
        page_controller=KeyframePageController(source,episode,base,rows)
        row_ctx=page_controller.row_context
        def use_rows():
            """刷新后将每个表格行重新归属到它的分镜来源。"""
            page_controller.replace_rows(rows)
        def home(shot):return page_controller.home(shot)
        def iid_of(shot):return page_controller.iid_of(shot)
        from writing import validate_episode
        validate_episode(episode,base)
        # 勾选表按行编号记账：只有一份时键就是那一份的路径（与从前同一个键），多份时合成一张。
        self._frame_checks_key=page_controller.checks_key
        self._frame_checks_merged=page_controller.merged
        if not hasattr(self,'frame_checks'):self.frame_checks={}
        checked=self.frame_checks.get(self._frame_checks_key)
        if checked is None:checked=self.frame_checks[self._frame_checks_key]=frame_checks.FrameChecks()
        def frame(shot,required=True):return page_controller.frame_path(shot,required)
        def exists(shot):return page_controller.frame_exists(shot)
        if hasattr(self,'header_status'):
            # 「全部分镜」不是一份文件：这一栏写清这一屏列的是哪几份（第 68 期任务 12）。
            total=len({str(item.resolve()) for _i,_s,item,_b,_e in rows})
            label=('全部 %d 份已采用分镜'%total) if total>1 else source.relative_to(self.root).as_posix()
            self.header_status.configure(text='当前 JSON：'+label)
            self.header_model.configure(text='镜头编号保留；点表头勾选框切换全部，单击镜头行勾选单个。')
        # 底部两行先贴底占位、内容框最后占满剩余高度，主界面缩放时按钮与下拉框始终可见。
        table_box=ttk.Frame(self.content)
        target_row=FlowBar(self.content)
        # 选中镜头一行紧贴镜头内容框下方：左侧是下拉框，右侧依次是刷新、查看与文件维护按钮。
        ttk.Label(target_row,text='选中镜头').pack(
            side='left', padx=(SPACING['none'], SPACING['sm'])
        )
        available_shots={iid:shot for iid,shot,_item,_bse,_one in rows}
        target=SelectBox(target_row,values=list(available_shots));target.pack(
            side='left', padx=(SPACING['none'], SPACING['sm'])
        )
        if available_shots:target.current(0)
        # 第 53 期第 5 条：「图片文件」那一列要盖一层首帧缩略图（Tk 的 value 格只写得了文字），
        # 行高得跟着放大——这一张表单给一个样式，别的内容框照旧 34。
        table_shell=DataTable(table_box, columns=[
            ('id', '镜头', 155), ('title', '内容', 175), ('duration', '秒数', 60),
            ('status', '首帧状态', 120), ('file', '图片文件(点击查看)', 180),
            ('prompt', '首帧图片提示词(点击查看)', 480),
        ], show='tree headings', height=9, selectmode='browse', style='Frame.Treeview',
            auto_hide_scrollbars=True)
        table=table_shell.tree
        fit_row_height(table,THUMB_SIZE,style='Frame.Treeview')   # 第 58 期第 2 条：同上
        table_shell.grid(row=0,column=0,sticky='nsew')
        table_box.columnconfigure(0,weight=1);table_box.rowconfigure(0,weight=1)
        configure_check_column(table)
        for key,title,width in [('id','镜头',155),('title','内容',175),('duration','秒数',60),('status','首帧状态',120),('file','图片文件(点击查看)',180),('prompt','首帧图片提示词(点击查看)',480)]:
            table.heading(key,text=title);table.column(key,width=width,minwidth=50)
        table.tag_configure(
            'completed', background=COLORS['border_default'], foreground=COLORS['success']
        )
        from responsive_ui import auto_height
        auto_height(table, table_box, row_height=ASSET_ROW_HEIGHT)   # 行高了，按 80 算，别再按 34
        def fit_frame_columns():
            fit_columns_by_content(table, {'prompt': lambda w: min(540,max(360,w))})
        def selected():
            if not table.selection():raise ValueError('请先在镜头内容框中选择一行')
            return shot_row(table.selection()[0])
        box=CheckboxColumn(table,self.win._tick_images,lambda sid:checked.get(sid,False),lambda sid,v:checked.__setitem__(sid,v))
        def update_header_check():
            box.refresh_header()
        def toggle_frame(sid):
            box.toggle(sid);selection_changed()
        def toggle_all_frames():
            box.toggle_all();selection_changed()
        table.heading('#0',command=toggle_all_frames)
        def toggle_focus_check(event):
            sid=table.focus()
            if not sid or not table.exists(sid):
                rows=table.selection()
                sid=rows[0] if rows else None
            if sid:
                if table.selection()!=(sid,):table.selection_set(sid)
                toggle_frame(sid)
            return 'break'
        table.bind('<space>',toggle_focus_check,add='+')
        def selection_changed(event=None):
            valid=bool(table.selection())
            available=valid and exists(selected()) and not selected().get('frame_deleted')
            # 第 46 期第 9 条：删除按钮改成批量——它认的是勾选行，所以按勾选数决定能不能按。
            # 第 47 期第 1 条：「批量删除首帧」按统一口径亮起来——勾选优先，高亮那一行也算
            # （只有一个镜头高亮时按钮不再是灰的，点下去删的就是它，提示里会写明）。
            delete.configure(state='normal' if (page_checked() or table.selection()) else 'disabled')
            replace_button.configure(state='normal' if valid else 'disabled')
            if valid:target.set(table.selection()[0])
            update_header_check()
        def refresh():
            nonlocal rows,episode,base
            rows=load_rows()
            use_rows()
            for _i,_s,item,bse,one in rows:
                if item.resolve()==source.resolve():episode,base=one,bse;break
            previous=table.selection()
            # 重建行以前记住内容框的滚动位置：刷新或无人值守轮询重建后，内容不应跳回顶部。
            offset=0.0;top=''
            try:offset=table.yview()[0];top=table.identify_row(1)
            except tk.TclError:pass
            table.delete(*table.get_children())
            # 建行以前先按最新首帧状态对齐勾选：首帧刚就位的镜头自动取消勾选，缺首帧的新镜头默认勾选，
            # 用户手动改过的待生成镜头保持不动——无人值守轮询刷新因此不会悄悄改掉用户的批次。
            states={iid:(exists(shot) and not shot.get('frame_deleted'),bool(shot.get('frame_deleted'))) for iid,shot,_i,_b,_e in rows}
            available=sum(1 for present,_ in states.values() if present)
            checked.sync([(iid,*states[iid]) for iid in states])
            for iid,shot,_i,_b,_e in rows:
                present=states[iid][0]
                state='已导入' if present else ('待重新生成' if states[iid][1] else '待生成 / 待导入')
                # 第 54 期第 3 条：这一格盖得上缩略图就只留图——那句「图与字叠着多余」的活
                # 第 55 期第 3 条起由盖图那一层自己做（盖上收走、撤掉写回），这里照旧写文件名与「—」：
                # 原来为了判「这一格还写不写字」在这儿逐镜解一遍缩略图（几十上百镜就是几十上百张），白解。
                file_text=Path(shot['frame']).name if present else '—'
                table.insert('','end',iid=iid,text='',image=self.win._tick_images[int(checked[iid])],values=(shot['id'],shot['title'],shot['duration'],state,file_text,frame_prompt(shot).replace('\n',' ') or '待补齐首帧提示词'),tags=('completed',) if present else ())
            available_shots.clear();available_shots.update({row[0]:row[1] for row in rows})
            target.set_values(list(available_shots))
            fit_frame_columns()
            # 第 53 期第 5 条：行重建之后格子全挪了位，缩略图那一层跟着重排一次。
            images=getattr(table,'cell_images',None)
            if images is not None:images.refresh()
            if previous and table.exists(previous[0]):table.selection_set(previous[0])
            if top and table.exists(top):table.yview_moveto(offset);table.see(top)
            selection_changed()
            # 这句话按「当下有几镜已就位」说，不按「这一次对齐新取消了几镜」——
            # 原来拿的是 sync 的增量，三虎心跳重拍本页时第二次对齐就没增量了，
            # 状态栏会被改回不带这一句的版本（第 71 期发现的偶发）。
            note=f'；其中 {available} 镜首帧已就位，已自动取消勾选' if available else ''
            self.status.set(f'现有首帧 {available} 张；待补图 {len(episode["shots"])-available} 镜'+note)
        table.grid(row=0,column=0,sticky='nsew')
        actions=FlowBar(self.content);actions.pack(
            side='bottom', fill='x', pady=SPACING['sm']
        )
        target_row.pack(
            side='bottom', fill='x', pady=(SPACING['sm'], SPACING['none'])
        )
        table_box.pack(fill='both',expand=True)
        def page_checked():
            ids=checked.checked([iid for iid,_s,_i,_b,_e in rows])
            return ids or None
        def work_targets():
            """第 47 期第 1 条：删除／制作这一类动作的目标——勾选优先，高亮兜底。

            返回 (ids, 来源)；来源为 'shown' 时说明这一行是按高亮算的（文案里由 work_hint 补一句）。
            """
            from responsive_ui import work_rows
            return work_rows(table,lambda sid: checked.get(sid,False))
        def work_hint(ids,how):
            from responsive_ui import work_hint as hint
            return hint(ids,how)
        # 第二行：最高频的生成与查看，选中镜头后即可用；首帧制作用主色按钮突出。
        # 第 47 期第 3 条：点「手动制作首帧」先问一句模型配没配（没配就问要不要现在去「阶段配置」）。
        def pick_batch():
            """「手动制作首帧」要提交的那一批：勾选的镜头，按所属分镜分堆。

            第 68 期任务 12：「全部分镜」把几份分镜合成一屏，而首帧制作是一次一份的事——所以一次
            只提交一堆（当前选中的那一堆），其余几堆说清楚让用户切过去再做，不闷声丢掉。
            """
            item,ids,rest=page_controller.pick_batch(page_checked(),table.selection())
            if not ids:return item,None
            if rest:
                self.note('「手动制作首帧」一次做一份分镜：先做 %s 那一份的 %d 镜，另有 %d 镜请切到它们那一份再生成。'
                          %(item.stem,len(ids),rest))
            return item,ids
        def make_frames():
            item,ids=pick_batch()
            return ui_plugin_registry.module('keyframe_comfy').show(self,item,ids)
        def restore_selected():
            shot=selected();item,bse,one=home(shot)
            return self.restore_keyframe(shot,one,bse,item)
        from stage_models import manual_command
        make_button=self.button(actions,'手动制作首帧',manual_command(self,'keyframe',make_frames,self.win))
        make_button.configure(style='Tokens.Primary.TButton')
        make_button.pack_configure(
            padx=(SPACING['none'], SPACING['sm']), pady=SPACING['xs']
        )
        ui_plugin_registry.module('stage_flow').follow(make_button,'keyframe')
        # 第 32 期第 6 条：这一页的阶段配置就挂在「手动制作首帧」右边。
        self.stage_button=ui_plugin_registry.module('skill_panel').stage_button(actions,self,PAGE['keyframe']);self.stage_button.pack(
            side='left', padx=(SPACING['sm'], SPACING['none'])
        )

        def secondary_action(text, action):
            """Keep the shared safe callback while applying this page's token button contract."""
            button=self.button(target_row,text,action)
            button.configure(style='Tokens.Secondary.TButton')
            button.pack_configure(
                padx=(SPACING['none'], SPACING['sm']), pady=SPACING['xs']
            )
            return button

        self.pet.auto_variable('auto_first_frame_var')
        def prompt_details():
            from prompt_window import show as show_prompt_window
            shot=selected();prompt=frame_prompt(shot)
            if not prompt:self.status.set(shot['id']+' 还没有首帧图片提示词，请先补齐后再复制')
            show_prompt_window(self.win,shot['id']+' · 首帧图片提示词',prompt,status=self.status,
                               receipt=shot['id']+' 首帧图片提示词已复制，可直接粘贴到生图或对话工具',
                               empty_text='此镜头尚未填写首帧图片提示词。',
                               empty_hint='没有可复制的首帧图片提示词，请先补齐后再复制')
        def view_frame_image(sid):
            shot=next(s for s in episode['shots'] if s['id']==sid)
            if exists(shot) and not shot.get('frame_deleted'):
                path=(base/shot['frame']).resolve()
                if path.is_file():
                    open_path(path);return
            self.status.set(sid+' 尚未导入首帧图片，可先导入或生成。')
        def open_cell(sid,col):
            table.selection_set(sid);table.focus(sid);selection_changed()
            if col=='#0':toggle_frame(sid)
            elif col=='#5':view_frame_image(sid)
            elif col=='#6':prompt_details()
        # 第 50 期第 1 条：「选择镜头 JSON」按钮按用户要求删除（上一步已经改掉文案）。
        def choose_target(event=None):
            if table.exists(target.get()):table.selection_set(target.get());table.see(target.get());selection_changed()
        target.bind('<<ComboboxSelected>>',choose_target)
        def replace(shot=None):
            shot=shot or selected();path=FileDialog(self.win).open_file(initialdir=base/'frames',filetypes=[('PNG','*.png')])
            if not path:return
            raw=Path(path).read_bytes()
            from stage_execution_service import replace_stage_keyframe
            result=replace_stage_keyframe(base,source,episode,shot,raw)
            if not result.ok:raise ValueError(result.reason)
            if source.resolve()==(self.studio.episode_dir/'episode.json').resolve():self.studio.episode=episode
            refresh();table.selection_set(iid_of(shot));selection_changed()
            self.status.set('首帧已保存为 '+shot['id']+'.png，镜头JSON已同步')
        # 选中镜头右侧：刷新与查看在前，文件维护三键在后（下行内容框改动本地图片，低频且需谨慎）。
        secondary_action('刷新首帧列表',refresh)
        secondary_action('查看首帧提示词',prompt_details)
        secondary_action('查看镜头资产',lambda:self.notifier.info(ui_plugin_registry.module('agent.shot_assets').summary(home(selected())[0],selected()).replace('；','\n'), title='镜头资产', modal=True))
        replace_button=secondary_action('导入 / 替换选中首帧',replace)
        # 第 46 期第 9 条：这颗按钮改名「批量删除首帧」——它删的是勾选那一批（高亮不算数），
        # 只想删一镜时用内容框上的右键菜单「删除」（目标就是右键那一行）。
        delete=secondary_action('批量删除首帧',lambda:delete_checked_frames())
        secondary_action('恢复删除的首帧',lambda:restore_selected())
        def shot_row(sid):
            row=row_ctx.get(sid)
            if row is None:raise ValueError('镜头已被其他操作移除，请刷新首帧列表')
            return row[0]
        def delete_one(sid):
            """逐个删除：目标就是右键（或下拉框）点中的那一镜。"""
            shot=shot_row(sid);item,bse,one=home(shot)
            self.delete_keyframe(shot,one,bse,item)
        def delete_checked_frames():
            """批量删除：勾选的那些镜头；一个都没勾就按高亮那一行算（第 47 期第 1 条）。

            已删除与没有首帧的镜头自动跳过。
            """
            wanted,how=work_targets()
            shots=[shot for iid,shot,_i,_b,_e in rows
                   if iid in set(wanted) and exists(shot) and not shot.get('frame_deleted')]
            if not shots:raise ValueError('先在镜头内容框里勾选要删除首帧的镜头')
            listed='、'.join(shot['id'] for shot in shots[:12])+('…' if len(shots)>12 else '')
            if not confirm(self.win,'批量删除首帧',
                    f'删除勾选的 {len(shots)} 镜首帧？\n{listed}\n\n图片将移入首帧回收目录，可恢复；'
                    '镜头记录、已生成视频与未勾选的镜头不受影响。'+work_hint(wanted,how),
                    dangerous=True):
                return []
            done=[]
            for shot in shots:
                item,bse,one=home(shot)
                try:
                    if self.delete_keyframe(shot,one,bse,item,ask=False,rebuild=False):done.append(shot['id'])
                except (OSError,ValueError,KeyError) as exc:
                    self.note(shot['id']+' 首帧未删除：'+str(exc))
            refresh()
            self.status.set('已删除 %d 镜首帧（移入回收站，可恢复）：%s'%(len(done),'、'.join(done)))
            return done
        table.bind('<<TreeviewSelect>>',selection_changed)
        from cell_hover import CellHover
        link_cols=('#0','#5','#6')
        # 第 46 期第 1 条：右键＝查看（这一格）／删除（这一镜的首帧）。
        # 第 55 期第 2 条：#5（图片文件）那一列盖着缩略图，不再走高亮——打勾选框那一格照旧带图。
        table.cell_hover=CellHover(table,link_cols,lambda sid,col:self.safe(lambda:open_cell(sid,col)),cell_image=lambda sid,col:(self.win._tick_images[int(checked.get(sid,False))] if col=='#0' else None),checked=lambda sid:checked.get(sid,False),toggle=toggle_frame,delete=lambda sid:self.safe(lambda:delete_one(sid)))
        bind_row_toggle(table,toggle_frame,link_cols)
        # 第 53 期第 5 条：「图片文件」那一列盖一层首帧缩略图——已导入、Tk 读得出来的才盖；
        # 还没导入／图不在／格式 Tk 不认（jpg 等）就不盖，那一格退回原来写的文件名。
        # 盖住的那一格鼠标落到这层图上，照旧转给 CellHover（单击仍是打开图片，一条没改）。
        from cell_hover import CellImages,ZOOM_SIZE
        def frame_thumb(sid,column):
            try:
                shot=shot_row(sid)
                if shot.get('frame_deleted') or not exists(shot):return None
                image=asset_thumbs.thumbnail(self.win,frame(shot,False),THUMB_SIZE)
            except (ValueError,OSError):
                return None
            return None if image is None else (image,'')
        def frame_row_background(sid):
            try:
                return COLORS['border_default'] if exists(shot_row(sid)) else COLORS['background_card']
            except (ValueError,OSError):
                return COLORS['background_card']
        def frame_zoom(sid,column):
            """鼠标停在缩略图上：另解一张大图（第 57 期第 5 条）——把 72 像素的小图拉大只会糊。"""
            try:
                shot=shot_row(sid)
                if shot.get('frame_deleted') or not exists(shot):return None
                return asset_thumbs.thumbnail(self.win,frame(shot,False),ZOOM_SIZE)
            except (ValueError,OSError):
                return None
        table.cell_images=CellImages(table,('#5',),frame_thumb,hover=table.cell_hover,
                                     background=frame_row_background,zoom=frame_zoom)
        # 第 55 期第 1 条：视图一变就重排已经收进盖图那一层（watch_view），这儿不必再交代一遍。
        refresh()
        requested=getattr(self,'pending_frame_selection',None)
        if requested and table.exists(requested):
            table.selection_set(requested);table.focus(requested);table.see(requested);selection_changed()
        self.pending_frame_selection=None
        # 第 68 期任务 12：一屏里有几份分镜就盯几份（只有一份时与从前一样，就一个）。
        for _watched in sorted({str(item.resolve()) for _i,_s,item,_b,_e in rows}):
            watch_list(table_box,Path(_watched),refresh)
