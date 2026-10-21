"""desktop_asset_pages.AssetPagesMixin.assets（资产管理页）由闭包改写成类：旧方法原样内嵌，用同一份脚本驱动两个真 Desktop，逐步对照整棵控件树。"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_asset_pages as module
import pet_state
from page_diff_support import freeze_times, poke, pump, snapshot
from catalog_page_test_support import show_catalog_page_ready
from skip_reasons import PLATFORM_TKINTER

LEGACY_ASSETS = r'''def _legacy_assets(self,kind):
    from asset_context import ensure_browser_directory
    from stage_path_service import LEGACY_NUMBERED
    base=self.asset_base()
    folder=ensure_browser_directory(base,kind,create=base != Path(self.root)/LEGACY_NUMBERED['assets'])
    registry=self.asset_requirements()
    try:source=self.current_frame_json();episode=read(source)
    except ValueError:source=None;episode={}
    controller=self.asset_page_controller(registry)
    count=len(controller.rows())
    record=self.asset_base()/'assets/资产清单/来源.json'
    current_ids=read(record).get('asset_ids',[]) if record.is_file() else []
    used=sum(controller.matches(aid) for aid in current_ids)
    label={'scenes':'场景','characters':'角色','props':'道具','all':'全部资产'}[kind]
    scope_label={'all':'全部资产','adopted':'已采用分镜','current':'选择分镜'}[self.asset_scope()]
    used_label='本集' if self.asset_scope()=='current' else '已采用分镜'
    from storyboard_selection import summary
    self.note(f'{label} {count} 项 · {scope_label}')
    from asset_reference_prompts import display_prompt,show_prompt
    from asset_reference_images import role_summary
    table_box=ttk.Frame(self.content);table_box.pack(fill='both',expand=True,pady=SPACING['xs']);table_box.columnconfigure(0,weight=1);table_box.rowconfigure(0,weight=1)
    # 第 52 期第 3 条：「导入图片」那一列要放缩略图（value 格只能写文字，图另盖一层），
    # 行高得跟着放大——单给这张表一个样式，别的内容框照旧 34。
    # 第 53 期第 3 条：「名称」那一列不再摆图（用户判它与「导入图片」重复），只留文字；
    # 行高与样式照旧——「导入图片」那一列还要放。
    asset_columns=[('id','资产编号',130),('name','名称',230),('status','资产图片',96),
                   ('references','参考图（类目）',190),('note','外观要求',230),
                   ('prompt','资产提示词',360)]
    # 第 55 期第 6 条：「参考图」这一栏改成「参考图（类目）」：格子里写的不再只是张数，
    # 而是「几张 · 按类目各几张」——角色／场景／道具各有自己的类目（见 ROLE_GROUPS）。
    # 第 57 期第 6 条：这一栏改名「资产图片」（原来叫「导入图片」，与它上面那一行按钮同名）。
    compact=[(key,label,MIN_COL) for key,label,width in asset_columns]
    table_shell=DataTable(table_box,columns=compact,show='tree headings',height=7,
                          style='Asset.Treeview',empty_text='暂无资产',
                          auto_hide_scrollbars=True)
    table=table_shell.tree
    _configure_table_style(table,'Asset.Treeview',THUMB_SIZE);configure_check_column(table)
    for col,title,width in asset_columns:
        table.heading(col,text=title);table.column(col,width=MIN_COL,minwidth=MIN_COL,stretch=col in ('note','prompt'))
    remember_columns(table,[(col,width) for col,title,width in asset_columns]);auto_columns(table)
    refresh_request_width(table)
    table.tag_configure('completed',background=COLORS['border_default'],foreground=COLORS['success'])
    table_shell.grid(row=0,column=0,sticky='nsew')
    from responsive_ui import auto_height
    auto_height(table, table_box, row_height=ASSET_ROW_HEIGHT)      # 行高了，按 80 算，别再按 34
    self.asset_table=table          # 第 46 期第 2 条：两行按钮要问「选中／勾选了哪几行」
    self.asset_registry=registry
    checked=controller.checks
    # 第 54 期第 3 条：「导入图片」那一列盖得上缩略图就只留图，格子里的「已导入」不再显示
    # （图与字叠着用户判是多此一举）；还没导入／图解不开的照旧写原来的状态文字。
    asset_dir=self.asset_base()
    def asset_thumb(aid,size=THUMB_SIZE):
        """这一项资产已经导入的那张图的小图（路径不安全或没导入就是 None）。

        第 57 期第 5 条：多了 size 一档——鼠标停上去要放大时另解一张大图，不是把小图拉大
        （Tk 只认整数倍抽点，小图放大必然糊）。
        """
        asset=registry.get(aid) or {}
        if asset.get('status')!='已导入' or not asset.get('image'):return None
        root=asset_dir.resolve();path=(root/asset['image']).resolve()
        if path!=root and root not in path.parents:return None
        return asset_thumbs.thumbnail(self.win,path,size)
    # 第 72 期（Round 3）：分段建行。原来一口气把整份清单 insert 完，几千项的时候打开
    # 这一拍界面完全不动；现在先建够第一屏＋余量的那些（ASSET_FIRST_ROWS），剩下的按帧
    # 补（ASSET_ROWS_PER_FRAME）。界面立刻可用、列表随后长齐；中途换页或重建时令牌一过期，
    # 上一串没跑完的分片自己作废，不会往新表里插旧行。
    wanted=controller.rows()
    controller.initialize_checks()

    def insert_row(aid,asset):
        prompt=display_prompt(asset)
        # 第 55 期第 3 条：这一格要不要写字交给盖图那一层（盖上收走、撤掉写回）。
        # 原来这里为了判「有没有缩略图」把整个资产库的图都解了一遍——100 项资产就是
        # 100 张图，其中绝大多数根本不在可视区，打开这一页就卡在这儿。
        table.insert('','end',iid=aid,text='',image=self.win._tick_images[int(checked[aid])],values=(aid,asset.get('name',aid),asset['status'],role_summary(asset),asset.get('description',asset.get('reference_region','')),prompt.replace('\n',' ') if prompt else '待第1／2步补齐提示词'),tags=('completed',) if asset.get('status')=='已导入' else ())

    asset_rows_token=self.asset_rows_token=getattr(self,'asset_rows_token',0)+1
    for aid,asset in wanted[:ASSET_FIRST_ROWS]:
        insert_row(aid,asset)
    def checked_ids():
        return controller.checked_ids()
    def update_header_check():
        refresh_check_heading(table, self.win._tick_images, lambda aid: checked.get(aid,False))
    def refresh_buttons():
        self.asset_checked_count=len(checked_ids())
        self.asset_has_pending=controller.has_pending()
        self.update_asset_buttons()
        update_header_check()
    box=CheckboxColumn(table,self.win._tick_images,lambda aid:checked.get(aid,False),lambda aid,v:checked.__setitem__(aid,v),refresh_buttons)
    def toggle_asset(aid):
        box.toggle(aid)
    def toggle_all_assets():
        box.toggle_all()
    table.heading('#0',command=toggle_all_assets)
    bind_space_toggle(table,toggle_asset)
    def preview():
        if not table.selection():raise ValueError('先在资产表中选择一项')
        asset=registry[table.selection()[0]]
        if asset['status']!='已导入':raise ValueError('该资产尚未导入图片，请先导入')
        p=(self.asset_base()/asset['image']).resolve()
        if not p.is_relative_to(self.asset_base()):raise ValueError('资产路径越界')
        open_path(p)
    def selected():return table.selection()[0] if table.selection() else None
    def detail(aid,field):
        asset=registry[aid]
        text={'name':asset.get('name',aid),'note':asset.get('description',asset.get('reference_region',''))}.get(field,'')
        win=BaseDialog(self.win,aid+' · '+('名称' if field=='name' else '外观要求'),geometry='650x340',modal=False,chrome=False)
        box=TextArea(win,wrap='word',height=10,padx=SPACING['md'],pady=SPACING['md']);box.pack(fill='both',expand=True,padx=SPACING['md'],pady=SPACING['md'])
        box.insert('1.0',text or '暂无内容');box.configure(state='disabled');bind_show_all(box)
        if field=='name':SecondaryButton(win,text='修改名称',command=lambda:(win.destroy(),self.safe(lambda:self.rename_asset(aid)))).pack(anchor='e',padx=SPACING['md'],pady=(SPACING['none'],SPACING['md']))
        # 第 64 期任务 13（附件任务 4.1）：正典板不再嵌在主页面这个弹窗里，搬进了资产详情页。
        PrimaryButton(win,text='打开资产详情页',
                      command=lambda:(win.destroy(),self.safe(lambda:self.open_asset_detail(aid)))).pack(anchor='e',padx=SPACING['md'],pady=(SPACING['none'],SPACING['md']))
    def open_cell(aid,col):
        table.selection_set(aid);table.focus(aid)
        if col=='#0':
            toggle_asset(aid);return
        if col=='#1':
            # 第 64 期任务 13：「资产编号」那一格就是进详情的入口（主页面不再嵌正典板）。
            # 走 after_idle：点这一格的是内容框自己的事件处理，等它结束再整页重建。
            self.win.after_idle(lambda:self.safe(lambda:self.open_asset_detail(aid)))
        elif col=='#2':
            def save_name(name):
                self.rename_asset(aid,name,refresh=False)
                registry[aid]['name']=name;table.set(aid,'name',name)
            table.cell_hover.edit_name(aid,registry[aid].get('name',aid),save_name,self.status.set,'#2')
        elif col=='#3':
            if registry[aid]['status']=='已导入':preview()
        elif col=='#4':self.view_reference_images(aid)
        elif col=='#5':detail(aid,'note')
        elif col=='#6':show_prompt(self,aid,registry[aid])
    from cell_hover import CellHover,CellImages
    import cell_hover
    link_cols=('#0','#1','#2','#3','#4','#5','#6')
    # 第 46 期第 1／9 条：同一张表上，「查看」认点中的那一格（仍先补勾选再打开，规矩没变），
    # 「删除」只认右键那一行——高亮不再兼作删除目标，逐个删与批量删从此不会互相误伤。
    # 第 57 期第 3 条：「删除」还要认「右键落在哪一列」——「参考图」那一格删的是这一项的
    # 参考图（原来一律删资产图片，用户在参考图上右键就把导入的图删了）。
    table.cell_hover=CellHover(table,link_cols,lambda aid,col:self.safe(lambda:open_cell(aid,col)),cell_image=lambda aid,col:(self.win._tick_images[int(checked.get(aid,False))] if col=='#0' else None),checked=lambda aid:checked.get(aid,False),toggle=toggle_asset,delete=lambda aid,col:self.safe(lambda:self.delete_asset_cell(aid,col)))
    bind_row_toggle(table,toggle_asset,link_cols)
    # 第 52 期第 3 条：给缩略图那一列盖一层图（#3「导入图片」只盖图）。
    # 第 53 期第 3 条：只盖 #3 一列——「名称」那一列退回原来写的文字（两列同时摆同一张
    # 图是重复，用户点名删掉「名称」列的那个图片）。
    # 没缩略图（还没导入、图不在、Tk 不认这个格式）就不盖，那一格退回原来写的文字。
    # 同一资产在本页生命周期内的缩略图（或后台占位图）是稳定的；CellImages 会在滚动时
    # 多次询问同一行，不能每一帧重复 stat／缓存查询。页面重建会自然丢弃这份映射；后台
    # 完成时会原位填充占位图，因此不需要为等待结果再重复读取。
    thumb_values={}
    def thumb_value(aid,column):
        # 第 54 期第 3 条：图与格子里的字只留一样——文字那一边在建行时就清空了，这里只管盖图。
        if aid in thumb_values:
            return thumb_values[aid]
        image=asset_thumb(aid)
        value=None if image is None else (image,'')
        thumb_values[aid]=value
        return value
    def row_background(aid):
        return COLORS['border_default'] if (registry.get(aid) or {}).get('status')=='已导入' else COLORS['background_card']
    # 第 57 期第 5 条：鼠标停在这一格上就在旁边弹一张大图（够看清人物与背景）。
    table.cell_images=CellImages(table,('#3',),thumb_value,hover=table.cell_hover,background=row_background,
                                 zoom=lambda aid,column:asset_thumb(aid,cell_hover.ZOOM_SIZE),
                                 # 750ms 让连续滚动跨过本机 Tk 的绘制抖动窗口；停止后仍会
                                 # 自动对齐新可见区，且防抖不会退化成逐帧刷新。
                                 view_refresh_delay=750)
    # 第 55 期第 1 条：「视图变了就重排」已经收进盖图那一层自己（watch_view：滚动条动了、
    # 列宽变了、内容框改了尺寸都算），这儿不必再往那两条回调末尾补一次重排。
    # 不在建页路径强制 ``update_idletasks``：它会清空同一 Tcl 解释器里不属于资产表的
    # 空闲队列，慢机上还会让后续补行定时器落进首次 ``update``，退化成首帧一次性建表。
    # CellImages 已在映射事件及自己的空闲回调中补齐覆盖层；首帧之后再按真实 bbox 盖图。
    table.cell_images.schedule_initial_refresh()
    refresh_buttons()
    # 第 72 期（Round 3）：剩下的行按帧补上，补完再重排一次缩略图那一层。
    rest=wanted[ASSET_FIRST_ROWS:]
    if rest:
        done=[0]
        row_job={'id':None}
        def cancel_more_rows(event=None):
            """资产页拆掉时撤销尚未执行的分片插行回调。"""
            if event is not None and event.widget is not table:
                return
            job,row_job['id']=row_job['id'],None
            if job is not None:
                try:
                    table.after_cancel(job)
                except tk.TclError:
                    # 表格销毁后 job 已无须取消。
                    pass
        def more_rows():
            row_job['id']=None
            try:
                alive=bool(table.winfo_exists())
            except Exception:
                alive=False
            if not alive or getattr(self,'asset_rows_token',None)!=asset_rows_token:return
            for aid,asset in rest[done[0]:done[0]+ASSET_ROWS_PER_FRAME]:
                insert_row(aid,asset)
            done[0]+=ASSET_ROWS_PER_FRAME
            if done[0]<len(rest):
                # 小批次之间留出事件循环间隙。短到用户看不到停顿，长到 Tk 不会在一个
                # 回调里把所有剩余行连续插完。
                row_job['id']=table.after(50,more_rows)
            else:
                # 分片完成可能正好撞上用户滚动；已有可视缩略图只需重摆，
                # 仅为刚插入而尚未有图层的行读取 provider，不能在这一帧全量重读。
                table.cell_images.refresh(reuse_existing=True);refresh_buttons()
        table.bind('<Destroy>',cancel_more_rows,add='+')
        # 先把计时器的创建交给首帧空闲队列：计时若从 ``show()`` 中开始，慢机的首次
        # ``update()`` 本身就可能耗尽延迟，让第二批仍落在首帧。这里只在首帧绘制已经
        # 让出事件循环后开始计时，保证首批 24 行是唯一同步工作，随后才渐进补齐。
        def arm_more_rows():
            if (getattr(self,'asset_rows_token',None)!=asset_rows_token
                    or not table.winfo_exists()):
                return
            row_job['id']=table.after(2000,more_rows)
        row_job['id']=table.after_idle(arm_more_rows)
'''

PAGES = {'assets': 'assets'}
OWNER = 'AssetPagesMixin'



TARGET = getattr(module, OWNER) if OWNER else module


def _open_app(tk, td):
    import test_ui_edges
    from desktop import Desktop
    from local_video import open_studio
    win = tk.Tk()
    win.withdraw()
    app = Path(td) / 'app'
    app.mkdir()
    desktop = Desktop(win, root=app)
    desktop.startup_controller.cancel()
    desktop.root = test_ui_edges.make_populated_project(td)
    desktop.studio = open_studio(desktop.root)
    freeze_times(desktop.root)
    return win, desktop


class AssetPageEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            root = tkinter.Tk()
            root.destroy()
            cls.tk = tkinter
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.namespace = dict(vars(module))
        exec(compile(LEGACY_ASSETS, 'legacy_assets', 'exec'), self.namespace)

    def _session(self, name, impl):
        page = pet_state.PAGE_OF[PAGES[name]]
        # 路径要在两次运行里逐字相同（请求宽度随字形变化），所以用按进程号固定的目录，而不是随机临时目录
        td = Path(tempfile.gettempdir()) / ('drama_page_diff_%d' % os.getpid())
        shutil.rmtree(td, ignore_errors=True)
        td.mkdir(parents=True)
        try:
            win, desktop = _open_app(self.tk, td)
            roots = sorted({str(td), Path(td).as_posix(), str(Path(td).resolve()), Path(td).resolve().as_posix()},
                           key=len, reverse=True)
            steps = []
            try:
                with mock.patch.object(TARGET, name, impl):
                    show_catalog_page_ready(desktop, page)
                    poke(desktop, name + '#1', steps, roots)
                    desktop.go_page(pet_state.PAGE_OF['assets'])
                    pump(win, 0.1)
                    steps.append(('left', snapshot(desktop.content, roots)))
                    show_catalog_page_ready(desktop, page)
                    poke(desktop, name + '#2', steps, roots)
            finally:
                desktop.cancel_timers()
                win.destroy()
            return steps
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_assets_is_identical(self):
        self._session('assets', self.namespace['_legacy_assets'])   # 预热：进程里第一次建窗的布局与之后不同，先跑一遍丢掉
        old = self._session('assets', self.namespace['_legacy_assets'])
        new = self._session('assets', getattr(TARGET, 'assets'))
        self.assertEqual(len(new), len(old))
        for a, b in zip(new, old):
            self.assertEqual(a, b, a[0])
        widgets = max(len(step[1]) if isinstance(step[1], list) else 0 for step in new)
        self.assertGreater(widgets, 15)   # 对照不能是空对空：页面真的建出了一棵控件树


if __name__ == '__main__':
    unittest.main()
