"""资产管理页与资产相关方法。

从 ``desktop.Desktop`` 原样迁出（R1505）：方法体未改，``self`` 语义不变，``Desktop`` 通过继承
``AssetPagesMixin`` 获得。测试按 ``desktop.<名字>`` 打补丁的名字（confirm／open_path 等）经
``Desktop`` 注入的 ``AssetPageServices`` 在调用时取 ``desktop`` 的当前值，补丁照常生效（R1983 J2）。
"""
import infra.pet_state as pet_state
from dataclasses import dataclass
from typing import Callable
import time
import domain.asset_resume as asset_resume
import ui.asset_thumbs as asset_thumbs
import tkinter as tk
import infra.ui_plugin_registry as ui_plugin_registry
from agent.core import read
from ui.desktop_auto_flows import ASSET_RETRY_LIMIT
from pathlib import Path
from contract.platform_tools import open_target
from responsive_ui import CheckboxColumn, FlowBar, MIN_COL, auto_columns, bind_row_toggle, bind_space_toggle, bind_show_all, configure_check_column, fit_row_height, refresh_check_heading, refresh_request_width, remember_columns
from tkinter import ttk
from ui_tokens import TEXT_ROWS, COLORS, SPACING, TABLE_HEADER_FONT, TABLE_ROW_FONT, TEXT_HINT
from ui_widgets import BaseDialog, Card, DataTable, PrimaryButton, SecondaryButton, TextArea, ask_string
from ui.desktop_page_support import ASSET_FIRST_ROWS, ASSET_ROWS_PER_FRAME, ASSET_ROW_HEIGHT, ASSET_ROW_LABEL, STAGE_ACTION_WIDTH, THUMB_SIZE

PAGE = pet_state.PAGE_OF


@dataclass(frozen=True)
class AssetPageServices:
    """资产页用到的宿主服务；``Desktop`` 注入，页面不读全局宿主。"""
    open_path: Callable
    file_dialog: Callable
    confirm: Callable


def _configure_table_style(tree, style, thumb):
    """表格行高与表头共用 ui_tokens，页面只给样式名和缩略图尺寸。"""
    current = ttk.Style(tree)
    current.configure(style, font=TABLE_ROW_FONT)
    current.configure(style + '.Heading', font=TABLE_HEADER_FONT,
                      foreground=COLORS['text_primary'])
    fit_row_height(tree, thumb, style=style)


class AssetPagesMixin:
    """Desktop 的资产页方法集（见模块说明）。"""
    @staticmethod
    def asset_batch_gateway():
        """L4 只装配资产批处理的 L3 读写入口。"""
        from stage_execution_service import asset_batch_gateway
        return asset_batch_gateway()
    def asset_pending_ids(self):
        """没人值守这一路还缺图的资产编号（第 6 轮：收尾与台账都按编号记账）。

        原来只问一句「还有没有」（asset_work_left），于是每个编号试了几次、下次该什么时候
        接着试，全在内存里——窗口一关就没了。
        """
        from stage_execution_service import plan_unattended_assets as auto_plan
        from domain.asset_context import scope_sources
        try:
            missing,_skipped,_saved=auto_plan(self.root,self.asset_base(),scope_sources(self.root,'adopted'),'adopted')
        except (OSError,ValueError,KeyError,TypeError):
            return []
        return [aid for aid,_ in missing]
    def asset_work_left(self):
        """无人值守资产清单里还有没有缺图项（第 62 期任务 10：一轮跑完后的收尾判定）。"""
        return bool(self.asset_pending_ids())
    def note_asset_resume(self,ids):
        """这一轮又没做出图：把「第几次、下次从什么时候接着退避」记进项目台账（第 6 轮）。

        次数从台账里读回来（不是内存里自增的那个），`auto_asset_attempt` 因此与落盘的一致：
        重启后 poll_auto_asset 读同一份台账接着往后数、到顶就停下等人。台账写不动时退回内存里
        的计数（宁可多试几次，也不把这条路弄丢）。返回「离该重试还差几秒」，没有等待中的项返回 None。
        """
        from stage_execution_service import note_asset_resume_round
        fallback=self.auto.asset_attempt+1
        try:
            note_asset_resume_round(self.root,ids,limit=ASSET_RETRY_LIMIT)
            counted=asset_resume.attempts(self.root,ids)
            left=asset_resume.delay(self.root)
        except (OSError,ValueError,TypeError,KeyError):
            counted=0;left=None
        self.auto.asset_attempt=max(fallback,counted)
        return left
    def clear_asset_resume(self):
        """缺图补齐了、或用户亲手关掉这一档：把跨重启台账整份删掉（第 6 轮）。"""
        try:
            result=asset_resume.clear(self.root)
            if not result.ok:
                self.status.set('自动补资产续跑记录未清除：'+result.reason)
        except (OSError, ValueError, TypeError) as exc:
            # 续跑台账仍会在下次启动出现；不能把“已经清掉”的假象留给用户。
            self.status.set('自动补资产续跑记录未清除：%s；请稍后重试。' % exc)
    def restore_asset_resume(self):
        """打开项目时把跨重启续跑台账读回来（第 6 轮）。

        与 `prune_asset_leftovers` 同一条规矩：台账读不出来一律当没记过，绝不因此把
        「打开项目」拦下来；读得出来就接着上次的次数与退避时刻继续（台账记的是挂钟时刻，
        换算回 monotonic 后才好排下一次）。
        """
        try:
            self.auto.asset_attempt=asset_resume.attempts(self.root)
            left=asset_resume.delay(self.root)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            self.auto.asset_attempt=0;left=None
            # 续跑失败可以降级为不续跑，但不能让用户误以为没有待续跑的资产任务。
            self.status.set('自动补资产续跑记录未恢复：%s；请稍后重试。' % exc)
        if left is not None:
            self.auto.asset_due=time.monotonic()+left
    def auto_asset_log(self,ticket,text):
        # 工作线程回调：只入队，由主循环写状态栏，线程里不碰 Tk。
        self.auto.asset_messages.put((ticket,str(text)))
    def prune_asset_leftovers(self):
        """打开项目时清掉资产库里没登记过的原始取回图（第 64 期任务 1／4）。

        这类 comfy_<随机>_1.png 是旧版本留下的中间产物，内容与登记过的那张完全一样，
        用户看到的就是「自动生成的图片中有重复项」。只删没被 assets.json 登记的 comfy_*.png，
        登记过的一个字节都不动；异常一律吞掉，绝不因此把「打开项目」拦下来。
        """
        if not self.root:return []
        try:
            from domain.asset_batch_state_service import prune_raw_outputs
            from contract.stage_path_service import LEGACY_NUMBERED
            if self.asset_base() == Path(self.root)/LEGACY_NUMBERED['assets']:
                return []
            removed=prune_raw_outputs(self.asset_base())
        except Exception as exc:
            # 清理是可选维护，不能拦住打开项目；但失败也不能伪装成没有重复图。
            self.status.set('重复原始取回图未清理：%s；请稍后重试。' % exc)
            return []
        if removed:
            self.status.set('已清理 '+str(len(removed))+' 张重复的原始取回图（登记过的一张没动）')
        return removed
    def import_generated_assets(self):
        """项目加载后自动导入生成目录里尚未登记的资产图：重启软件即可生效，无需先进资产页。"""
        if not self.root:return
        try:
            from stage_execution_service import pending_generated_assets
            if not pending_generated_assets(self.root,self.asset_base()):return
        except Exception as exc:
            self.status.set('生成资产检查未完成：%s；请稍后重试。' % exc)
            return
        def work():
            from stage_execution_service import import_pending_generated_assets
            imported=import_pending_generated_assets(self.root,self.asset_base())
            return ('已自动导入生成资产图：'+'、'.join(imported)) if imported else '生成资产检查完成'
        try:self.async_(work)
        except Exception as exc:
            self.status.set('生成资产导入未启动：%s；请稍后重试。' % exc)
    def reference_sites(self):
        self.note('点击网站名称，在默认浏览器中打开。')
        groups=[
            ('模型与 API 控制台',[
                ('阿里云百炼控制台','https://bailian.console.aliyun.com/','管理通义千问等模型的 API、用量与费用。'),
                ('火山方舟控制台','https://console.volcengine.com/ark','管理火山方舟模型、API 密钥和视频生成任务。')]),
            ('创意与剧本辅助',[
                ('Google Gemini','https://gemini.google.com/app','AI对话，辅助构思故事、整理资料和修改文案。'),
                ('DeepSeek','https://chat.deepseek.com/','AI对话，辅助剧本构思、对白润色和提示词整理。')]),
            ('图片、视频与动画创作',[
                ('即梦 AI','https://jimeng.jianying.com/','AI图片与视频创作，用于角色视觉、场景和动态画面。'),
                ('小云雀网页版','https://xyq.jianying.com/','AI内容创作，辅助制作图片和短视频。'),
                ('Seko','https://seko.sensetime.com/','AI视频与短剧创作，辅助故事画面制作。'),
                ('OiiOii','https://www.oiioii.ai/','AI动画创作，辅助把故事制作成动画。'),
                ('LibLibAI','https://www.liblib.art/','AI绘画与模型社区，查找风格模型及生成图片。')]),
            ('模型与素材资源',[
                ('Hugging Face','https://huggingface.co/','查找开源模型、数据集及在线演示。'),
                ('Civitai','https://civitai.com/','查找绘画模型、LoRA及作品参数参考。')]),
            ('Agent 与技能工作流',[
                ('LobeHub','https://lobehub.com/','AI助手与Agent工作空间，组织对话和工作流。'),
                ('SkillsMP','https://skillsmp.com/zh','搜索Agent技能，查看技能说明与源代码入口。')])]
        for category,sites in groups:
            group=Card(self.content)
            group.pack(fill='x',pady=SPACING['xs'])
            ttk.Label(group,text=category).grid(row=0,column=0,columnspan=2,sticky='w')
            cards=[]
            for name,url,description in sites:
                card=ttk.Frame(group,padding=(SPACING['xs'],SPACING['xs']))
                SecondaryButton(card,text=name,command=lambda u=url:self.safe(lambda:open_target(u))).pack(anchor='w')
                link=ttk.Label(card,text=url,style='Muted.TLabel',cursor='hand2',wraplength=TEXT_HINT['wraplength'],justify='left')
                link.local_wrap=True;link.pack(anchor='w',fill='x',pady=(SPACING['xs'],SPACING['none']))
                link.bind('<Button-1>',lambda event,u=url:self.safe(lambda:open_target(u)))
                detail=ttk.Label(card,text=description,wraplength=TEXT_HINT['wraplength'],justify='left')
                detail.local_wrap=True;detail.pack(anchor='w',fill='x')
                cards.append((card,link,detail))
            def arrange(event,box=group,items=cards):
                columns=2 if event.width>=620 else 1
                available=max(120,(event.width-SPACING['2xl'])//columns-SPACING['xl'])
                layout=(columns,available)
                if getattr(box,'site_layout',None)==layout:return
                box.site_layout=layout
                for col in range(2):box.columnconfigure(col,weight=1 if col<columns else 0,uniform='sites' if col<columns else '',minsize=0)
                for index,(card,link,detail) in enumerate(items):
                    card.grid(row=index//columns+1,column=index%columns,sticky='nsew',
                              padx=(SPACING['none'],SPACING['sm']) if columns==2 and index%2==0 else SPACING['none'],
                              pady=SPACING['xs'])
                    link.configure(wraplength=available);detail.configure(wraplength=available)
            group.bind('<Configure>',arrange)
            # Mount cards before the first layout event; width is then set by the page.
            for index,(card,_,_) in enumerate(cards):card.grid(row=index//2+1,column=index%2,sticky='nsew')
    def open_asset_detail(self,aid=None):
        """进「资产详情页」（第 64 期任务 13；附件 v3.0 任务 2.3 的「点击进入详情」）。

        主页面布局一个像素都不动，只在「资产编号」那一格加这个入口：传 aid 用传进来的那一个，
        没传就看资产表里高亮的那一行。返回按钮走 close_asset_detail。
        """
        value=str(aid or '').strip()
        if not value:
            table=getattr(self,'asset_table',None)
            if table is not None and table.winfo_exists() and table.selection():
                value=str(table.selection()[0]).strip()
        if not value:raise ValueError('先在资产表里点选一项资产，再点「资产编号」进详情')
        self.asset_detail_id=value;self.asset_roster=False
        self.show(PAGE['assets'])
        return value
    def close_asset_detail(self):
        """从资产详情页／资产清单页回资产管理主页面（附件任务 2.3 的返回按钮）。"""
        self.asset_detail_id=None;self.asset_roster=False
        self.show(PAGE['assets'])
    def open_asset_roster(self):
        """进「资产清单」（第 71 期任务 2）：一页看完每个角色的正典板与换状态面板。

        与详情页一样挂在「05 资产管理」下面，只是不含单张表格——清单页只摆展示，
        要改内容点每一项下面的「编辑这一项」进详情页，两页写的是同一份资产 json。
        """
        self.asset_detail_id=None;self.asset_roster=True
        self.show(PAGE['assets'])
        return True
    def asset_page(self):
        from ui.asset_skill_batch import resume
        from asset_reference_images import prepare_folders
        from contract.stage_path_service import write_dir
        resume(self)
        if self.asset_base() == write_dir(self.root,'assets'):
            prepare_folders(self.asset_base())
        if not hasattr(self,'asset_checks'):self.asset_checks={}
        self.asset_gated_buttons=[]
        # L4-U7b：行首标签放在 FlowBar 外面，按钮换行后回到本行第一颗按钮下面，而不是标签下面。
        toolbar_row=ttk.Frame(self.content);toolbar_row.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        # 第 31 期第 7 条：这一行的标签与下面「参考图」「资产图片」两行同宽，三行按钮左边缘对齐。
        ttk.Label(toolbar_row,text='资产',width=ASSET_ROW_LABEL).pack(side='left')
        toolbar=FlowBar(toolbar_row);toolbar.pack(side='left',fill='x',expand=True)
        def choose_all():self.asset_kind='all';self.show(PAGE['assets'])
        (PrimaryButton if self.asset_kind=='all' else SecondaryButton)(toolbar,text='全部',command=lambda:self.safe(choose_all)).pack(side='left')
        for label,kind in [('角色','characters'),('场景','scenes'),('道具','props')]:
            def choose(k=kind):self.asset_kind=k;self.show(PAGE['assets'])
            (PrimaryButton if self.asset_kind==kind else SecondaryButton)(toolbar,text=label,command=lambda fn=choose:self.safe(fn)).pack(side='left')
        b=SecondaryButton(toolbar,text='检查提示词',command=lambda:self.safe(lambda:ui_plugin_registry.module('asset_prompt_check_dialog').check(self)));b.pack(side='left')
        b=SecondaryButton(toolbar,text='识别背景人物',command=lambda:self.safe(lambda:ui_plugin_registry.module('background_characters').show(self)));b.pack(side='left')
        # 第 31 期第 7 条：参考图／资产图片这两行的按钮挪到「资产」这一行下方，两行标签给同一个
        # 宽度，按钮左边缘对齐——它们本来就是一组资产的动作，摊在表格下面白占两行高度。
        # 第 46 期第 2 条：这两行按钮原来引用的 import_refs／open_ref_folder／delete_image／selected
        # 只长在 self.assets() 的函数体里（按钮一点就是 NameError），「导入资产图片」还把上一个
        # for 循环残留的 kind（永远是道具）当类别用。现在四件事各归各位、都走 Desktop 上的方法：
        #   参考图行＝导入（要选中）／候选图墙（要选中）／参考图目录（选中就开它那一类）
        #   资产图片行＝导入（要选中）／批量删除资产（只删勾选行）／资产目录
        # 第 55 期第 5 条：「资产目录」删掉——它与「生成图目录」打开的是同一个资产库，
        # 用户判它重复（导入图片落到资产库哪一格，右键／「生成图目录」都看得见）。
        # 第 55 期第 6 条：参考图那一行补一颗「查看参考图」——原来「查看」只藏在「参考图」
        # 那一格的单击里，入口看不出来。
        # 第 57 期第 6 条：「查看参考图」又删了——参考图那一格单击打开的就是它（同一件事两个
        # 入口，用户点名去重）；「批量删除图片」改名「批量删除资产」；「生成图目录」改名
        # 「资产目录」，改开 episode 根目录（它下面才是资产库、参考图与生成资产）。
        refs_row=ttk.Frame(self.content);refs_row.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        ttk.Label(refs_row,text='参考图',width=ASSET_ROW_LABEL).pack(side='left')
        refs=FlowBar(refs_row);refs.pack(side='left',fill='x',expand=True)
        b=SecondaryButton(refs,text='导入参考图',command=lambda:self.safe(lambda:self.import_reference_images()));b.pack(side='left',padx=SPACING['xs'],pady=SPACING['xs']);self.asset_gated_buttons.append(b)
        b=SecondaryButton(refs,text='候选图墙',command=lambda:self.safe(lambda:ui_plugin_registry.module('reference_wall').show(self,self.require_asset_selected('先点选一项资产，再打开候选图墙'))));b.pack(side='left',padx=SPACING['xs'],pady=SPACING['xs']);self.asset_gated_buttons.append(b)
        SecondaryButton(refs,text='参考图目录',command=lambda:self.safe(lambda:self.open_reference_folder())).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        imgs_row=ttk.Frame(self.content);imgs_row.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
        ttk.Label(imgs_row,text='资产图片',width=ASSET_ROW_LABEL).pack(side='left')
        imgs=FlowBar(imgs_row);imgs.pack(side='left',fill='x',expand=True)
        b=SecondaryButton(imgs,text='导入资产图片',command=lambda:self.safe(lambda:self.asset_import(self.asset_kind,selected=self.asset_selected())));b.pack(side='left',padx=SPACING['xs'],pady=SPACING['xs']);self.asset_gated_buttons.append(b)
        # 第 57 期第 6 条：「批量删除图片」→「批量删除资产」（它删的本来就不止图片：资产图上
        # 那一行的登记一并撤掉）。
        b=SecondaryButton(imgs,text='批量删除资产',command=lambda:self.safe(lambda:self.delete_asset_images()));b.pack(side='left',padx=SPACING['xs'],pady=SPACING['xs']);self.asset_gated_buttons.append(b)
        SecondaryButton(imgs,text='恢复删除资产',command=lambda:self.safe(lambda:self.restore_asset_image(self.asset_selected()))).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        def open_library():
            # 第 57 期第 6 条：「生成图目录」→「资产目录」，开的是上一级的 episode 根目录
            # （资产库、参考图、生成资产都在它下面）。
            self.asset_page_services.open_path(self.asset_base())
        SecondaryButton(imgs,text='资产目录',command=lambda:self.safe(open_library)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        try:
            from stage_execution_service import import_pending_generated_assets
            imported=import_pending_generated_assets(self.root, self.asset_base(), self.status.set)
            if imported:self.status.set('已自动导入生成资产图：'+'、'.join(imported))
        except Exception as exc:
            self.note('生成图自动导入暂缓：'+str(exc))
        self.assets(self.asset_kind)
        def start_assets():
            """手动制作资产（第 59 期第 3 条）：勾到「已制作」的那几项先问一句重做不重做。

            以前这里只写一句「已跳过 N 个已导入资产」就继续：用户勾了已制作的行去点制作，界面上
            看不出它们会被跳过（只在状态行上闪一句）；现在：确认重做就把旧图移进项目回收站
            （可恢复）、资产回到待导入，批次自然会重做它；不重做就把这几项剔出来，只做剩下的。
            """
            registry=self.asset_requirements()
            controller=self.asset_page_controller(registry)
            selected=controller.checked_ids()
            made=controller.imported_ids(selected)
            if made and self.asset_page_services.confirm(self.win,'重新制作资产',
                    '勾选的 %d 项已经做好了：%s\n\n要删掉旧图重做一遍吗？'
                    '（旧图移入项目回收站，可恢复）'%(len(made),'、'.join(made[:8])),
                    dangerous=True):
                for aid in made:
                    try:
                        self.delete_asset_image(aid,ask=False)
                    except (OSError,ValueError,KeyError) as exc:
                        self.note(aid+'旧图未能删除：'+str(exc))
            else:
                selected=[aid for aid in selected if aid not in made]
                if not selected:
                    self.status.set('没有要制作的资产：勾选的都已经做好了。要重做，先删掉它的资产图片。')
                    return
            ui_plugin_registry.module('asset_batch').show(self,'workflow',selected_ids=selected)
        production=FlowBar(self.content);production.pack(fill='x',pady=(SPACING['sm'],SPACING['xs']))
        # 第 32 期第 1／5 条：按钮改名「手动制作资产」，并把「手动XX」摆到最左边（左对齐）——
        # 「制图」那个行首标签去掉，按钮自己说得清是干什么的。
        # 第 47 期第 3 条：点「手动制作资产」先问一句模型配没配（没配就问要不要现在去「阶段配置」）。
        from orchestrator.stage_models import manual_command as _manual
        b=PrimaryButton(production,text='手动制作资产',width=STAGE_ACTION_WIDTH,command=lambda:self.safe(_manual(self,'assets',start_assets,self.win)));b.pack(side='left',padx=(SPACING['none'],SPACING['xs']),pady=SPACING['xs']);self.asset_gated_buttons.append(b);self.asset_start_button=b
        ui_plugin_registry.module('stage_flow').follow(b,'assets')       # 三虎在跑这一步就写「自动执行中」并置灰
        # R2942：「阶段配置」按钮＋模型下拉框删除（模型选择已收进共享输入框，技能走 ✦ 图标）。
        # 第 65 期任务 1：这两颗从「资产图片制作」弹窗搬到「阶段配置」右边（原话：移到主界面阶段配置旁）。
        def kill_comfy_here():
            # taskkill 逐个镜像、每个最长 10 秒，按下时 ComfyUI 通常正卡着——不能在界面线程上等。
            from infra.native_apps import force_close_comfy
            def work():
                try:return force_close_comfy(self.settings)
                except Exception as exc:return '强制关闭失败：'+str(exc)
            self.async_(work,lambda text:self.status.set(str(text)),show_progress=False,label='正在强制关闭 ComfyUI…')
        SecondaryButton(production,text='强制关闭 ComfyUI',width=STAGE_ACTION_WIDTH,command=lambda:self.safe(kill_comfy_here)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        def asset_records():
            folder=self.root/'workflows/Comfy资产批次';folder.mkdir(parents=True,exist_ok=True);self.asset_page_services.open_path(folder)
        SecondaryButton(production,text='制作记录',width=STAGE_ACTION_WIDTH,command=lambda:self.safe(asset_records)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        SecondaryButton(production,text='桌面打开 ComfyUI',width=STAGE_ACTION_WIDTH,command=lambda:self.safe(self.launch_comfy)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        SecondaryButton(production,text='浏览器打开 ComfyUI',width=STAGE_ACTION_WIDTH,command=lambda:self.safe(self.open_comfy_browser)).pack(side='left',padx=SPACING['xs'],pady=SPACING['xs'])
        # 自动制作开关由三虎模式统一控制；变量保留给活动页面即时同步，初始为关闭。
        self.pet.auto_variable('auto_asset_var')
        self.update_asset_buttons()
    def asset_base(self):
        # 资产库属于项目：不跟着当前选择的分镜走，工作集切到别的分镜时资产库位置必须保持稳定。
        from domain.asset_context import library_dir
        return library_dir(self.root)
    def asset_write_base(self):
        from stage_execution_service import prepare_legacy_asset_base
        return prepare_legacy_asset_base(self.asset_base())
    def asset_scope(self):
        from orchestrator.storyboard_selection import prefs
        return 'current' if prefs(self.root).get('asset_scope')=='current' else 'adopted'
    def asset_sources(self):
        from domain.asset_context import scope_sources
        return scope_sources(self.root,self.asset_scope())
    def asset_requirements(self):
        from stage_execution_service import sync_asset_plan
        from contract.stage_path_service import write_dir, LEGACY_NUMBERED
        base=self.asset_base()
        if base == Path(self.root)/LEGACY_NUMBERED['assets']:
            # 查看历史清单不触发复制或自动同步；第一次修改由 L3 复制。
            path=base/'assets/资产清单/assets.json'
            return read(path) if path.is_file() else {}
        try:return sync_asset_plan(self.root,self.asset_base(),self.asset_sources(),scope=self.asset_scope())
        except (ValueError,OSError,TypeError,AttributeError,KeyError) as e:
            # 门禁会在后台预读资产清单；剧本准备等非资产页不应因此叠出资产错误。
            if getattr(self,'page_index',None)==PAGE['assets']:
                self.note('资产清单暂未同步：'+str(e)+'。请重新采用当前项目的分镜JSON。')
            return {}
    def asset_page_controller(self,registry=None,kind=None):
        """资产页的无 Tk 筛选与勾选编排；控件状态仍由本页面持有。"""
        from orchestrator.asset_page_controller import AssetPageController
        if not hasattr(self,'asset_checks'):self.asset_checks={}
        root=getattr(self,'root',None)
        checks=self.asset_checks.setdefault(str(Path(root).resolve()),{}) if root is not None else {}
        selected_kind=getattr(self,'asset_kind','all') if kind is None else kind
        return AssetPageController(self.asset_requirements() if registry is None else registry,checks,selected_kind)
    def update_asset_buttons(self):
        has=bool(getattr(self,'asset_checked_count',0))
        pending=bool(getattr(self,'asset_has_pending',True))
        start=getattr(self,'asset_start_button',None)
        for button in getattr(self,'asset_gated_buttons',[]):
            if button.winfo_exists():
                enabled=has and pending if button is start else has
                button.configure(state='normal' if enabled else 'disabled')
    def assets(self, kind):
        return _AssetPage(self, kind).build()
    # ── 第 46 期第 2／9 条：资产管理那两行按钮 + 内容框右键删除的公共实现 ────────
    # 这些活原来散在 assets() 的函数体里，页面上的按钮却摆在 assets() 外面——按下去
    # 找不到名字（NameError）。收到 Desktop 上以后，按钮、右键菜单与内容框走同一份实现。
    def asset_selected(self):
        """资产表当前点中的那一行（没高亮时退回第一个勾选行，都没有就是 None）。

        第 47 期第 1 条：查看／定位这一类是高亮优先、勾选兜底——勾了一行却没高亮时，
        点「查看参考图」不该回一句「先点选一项资产」。
        """
        table=getattr(self,'asset_table',None)
        if table is None or not table.winfo_exists():return None
        from responsive_ui import view_row
        checked=self.asset_checks.get(str(Path(self.root).resolve()),{}) if self.root is not None else {}
        return view_row(table,lambda aid: checked.get(aid,False)) or None
    def require_asset_selected(self,hint='先在资产表里点选一项资产'):
        """按钮要的那一项资产；没点选就报同一句人话（各按钮共用）。"""
        aid=self.asset_selected()
        if not aid:raise ValueError(hint)
        return aid
    def asset_checked_ids(self):
        """资产表里勾选的编号（只认勾选，不看高亮——第 46 期第 9 条的批量删除就按它来）。"""
        table=getattr(self,'asset_table',None)
        if table is None or not table.winfo_exists():return []
        return self.asset_page_controller(getattr(self,'asset_registry',{}),kind='all').checked_ids(table.get_children())
    def asset_work_ids(self):
        """批量删除／批量制作的目标（第 47 期第 1 条）：勾选优先；一个都没勾就按高亮那一行算。

        返回 (ids, 来源)：来源 'checked'／'shown'／''，文案里那句说明由 asset_work_hint 补。
        """
        table=getattr(self,'asset_table',None)
        if table is None or not table.winfo_exists():return [],''
        selected=table.selection()[0] if table.selection() else None
        return self.asset_page_controller(getattr(self,'asset_registry',{}),kind='all').work_ids(list(table.get_children()),selected)
    def asset_work_hint(self,ids,how):
        """统一口径下的一句说明（只有按高亮算的时候才有内容）。"""
        from responsive_ui import work_hint
        return work_hint(ids,how)
    def import_reference_images(self,aid=None):
        """导入参考图：给点中的那一项资产加参考图（没点选就提示先点选）。"""
        aid=aid or self.require_asset_selected('先点选一项资产，再导入参考图')
        return ui_plugin_registry.module('asset_reference_import').show(self,aid,pending=False)
    def view_reference_images(self,aid=None):
        """查看参考图（只读）：与「参考图」那一格单击同一条路。"""
        aid=aid or self.require_asset_selected('先点选一项资产，再查看参考图')
        return ui_plugin_registry.module('asset_reference_images').view_references(self,aid)
    def open_reference_folder(self,aid=None):
        """参考图目录：点选了资产就开它那一类的参考图目录，没点选就开参考图根目录。

        第 46 期第 2 条：原来按「全部／角色／场景／道具」这一档算目录，选「全部」时
        直接拿 None 去 rstrip（崩），而且开着角色页去开道具的文件夹也不合直觉。
        """
        from asset_reference_images import CATEGORIES,prepare_folders
        base=AssetPagesMixin.asset_write_base(self);prepare_folders(base)
        folder=base/'assets/参考图'
        category=CATEGORIES.get(str(aid or self.asset_selected() or '').split('_')[0])
        if category:folder=folder/category
        self.asset_page_services.open_path(folder)
        return folder
    def asset_field_column(self,field):
        """资产表里某一栏的列号（'#4' 这种）：表没建起来或没有这一栏就是 None。

        第 57 期第 3 条：右键删哪一样要看「落在哪一列」，列号按字段名现算——写死 '#4' 的话，
        以后哪一栏一挪位置，删的就不是用户点的那一格了。
        """
        table=getattr(self,'asset_table',None)
        if table is None or not table.winfo_exists():return None
        columns=[str(item) for item in table['columns']]
        return '#'+str(columns.index(field)+1) if field in columns else None
    def delete_asset_cell(self,aid,column):
        """这一格右键的「删除」（第 57 期第 3 条）：落在「参考图」那一格删的是这一项的参考图，
        别的格删的才是这一项已导入的资产图片。"""
        if column==self.asset_field_column('references'):
            return self.delete_asset_references(aid)
        return self.delete_asset_image(aid)
    def delete_asset_references(self,aid,ask=True):
        """删除这一项资产的参考图（第 57 期第 3 条）：解除全部绑定，问一句再动手。

        参考图登记在「资产库/资产清单/assets.json」的 reference_images／reference_roles 里
        （与已导入的资产图片是两回事），删的时候交回 asset_reference_images.unbind——照看
        「同一个文件还绑在别的资产上」这类情况，不误删。
        """
        if not aid:raise ValueError('先在资产表里点选一项资产')
        from asset_reference_images import unbind
        base=self.asset_base()
        entry=read(base/'assets/资产清单/assets.json').get(aid,{}) or {}
        values=[value for value in entry.get('reference_images',[]) if isinstance(value,str) and value]
        values=list(dict.fromkeys(values))
        if not values:raise ValueError(aid+' 还没有参考图')
        if ask and not self.asset_page_services.confirm(self.win,'删除参考图',
                '%s 的 %d 张参考图将移入项目回收站，可在需要时恢复。\n是否继续？'%(aid,len(values)),
                dangerous=True):
            return False
        base=AssetPagesMixin.asset_write_base(self)
        unbind(base,aid,values)
        self.show(PAGE['assets'])
        self.status.set(aid+' 的 '+str(len(values))+' 张参考图已移入回收站。')
        return True
    def _delete_image_confirm_text(self,aid,image):
        """单项删图确认文案：原文案后追加 deletion_references 摘要（UX-S05-54）。"""
        text=('删除 %s 的已导入图片？\n%s\n\n图片将移入项目回收站，该资产恢复为待导入。'
              %(aid,image))
        try:
            from stage_execution_service import deletion_references
            summary=deletion_references(self.root,aid).get('summary') or ''
            if summary:text+='\n\n'+summary
        except Exception:
            import infra.app_logging as app_logging
            app_logging.swallowed()
        return text

    def _batch_delete_images_confirm_text(self,targets,shown,how):
        """批量删图确认文案：追加「其中 N 项被采用镜头引用」（UX-S05-55）。"""
        text=('删除勾选的 %d 项资产的已导入图片？\n%s\n\n图片将移入项目回收站，'
              '这些资产恢复为待导入；未勾选资产不受影响。%s'
              %(len(targets),shown,self.asset_work_hint(targets,how)))
        try:
            from stage_execution_service import deletion_references
            cited=[]
            for aid in targets:
                refs=deletion_references(self.root,aid)
                if refs.get('protected'):cited.append(aid)
            if cited:
                head='、'.join(cited[:6])+('…' if len(cited)>6 else '')
                text+='\n\n其中 %d 项被采用镜头引用：%s'%(len(cited),head)
        except Exception:
            import infra.app_logging as app_logging
            app_logging.swallowed()
        return text

    def delete_asset_image(self,aid,ask=True):
        """逐个删除：把这一项的已导入图片移进项目回收站，资产恢复为待导入。

        ask=False 供批量删除复用（确认框在批量那一步只弹一次）。
        """
        if not aid:raise ValueError('先在资产表里点选一项资产')
        base=self.asset_base()
        assets=read(base/'assets.json')
        entry=assets.get(aid,{})
        image=entry.get('image')
        if not image:raise ValueError('该资产尚未导入图片')
        path=(base/image).resolve()
        if not path.is_relative_to(base):raise ValueError('资产路径越界')
        if not path.is_file():raise ValueError('图片文件已不存在，请刷新列表')
        if ask:
            fn=getattr(self,'_delete_image_confirm_text',None)
            text=fn(aid,image) if callable(fn) else AssetPagesMixin._delete_image_confirm_text(self,aid,image)
            if not self.asset_page_services.confirm(self.win,'删除已导入图片',text,dangerous=True):
                return False
        from domain.asset_batch_service import remove_asset_image
        base=AssetPagesMixin.asset_write_base(self)
        remove_asset_image(base,aid,gateway=AssetPagesMixin.asset_batch_gateway())
        if ask:
            self.show(PAGE['assets'])
            self.status.set(aid+' 已导入图片已删除，恢复为待导入。')
        return True
    def delete_asset_images(self):
        """批量删除：勾选的那几行；一个都没勾就按高亮那一行算（第 46 期第 9 条 ＋ 第 47 期第 1 条）。

        第 47 期第 1 条统一了「选中」的口径：高亮一行却没勾上时不再一句「请先勾选」打回去，
        而是按高亮那一行删（提示里写明），与右键的逐个删除、各页的批量删除都是同一副规矩。
        """
        ids,how=self.asset_work_ids()
        if not ids:raise ValueError('先在资产表里勾选要删除图片的资产')
        base=self.asset_base()
        assets=read(base/'assets.json')
        targets=[aid for aid in ids if assets.get(aid,{}).get('image')]
        if not targets:raise ValueError('勾选的资产都没有已导入图片')
        shown='、'.join(targets[:8])+('…' if len(targets)>8 else '')
        fn=getattr(self,'_batch_delete_images_confirm_text',None)
        text=fn(targets,shown,how) if callable(fn) else AssetPagesMixin._batch_delete_images_confirm_text(self,targets,shown,how)
        if not self.asset_page_services.confirm(self.win,'批量删除已导入图片',text,dangerous=True):
            return []
        done=[]
        for aid in targets:
            try:
                if self.delete_asset_image(aid,ask=False):done.append(aid)
            except (OSError,ValueError,KeyError) as exc:
                self.note(aid+' 图片未删除：'+str(exc))
        self.show(PAGE['assets'])
        self.status.set('已删除 %d 项资产的已导入图片（移入项目回收站，可恢复）：%s'%(len(done),'、'.join(done)))
        return done
    def restore_asset_image(self,aid,ask=True):
        """恢复当前资产最近一次删除的图片；绝不覆盖新导入的同名文件。"""
        if not aid:raise ValueError('先在资产表里点选要恢复的资产')
        base=self.asset_base().resolve()
        assets=read(base/'assets.json')
        entry=assets.get(aid,{})
        if entry.get('image'):raise ValueError(aid+' 已有导入图片，无需恢复')
        prefix=str(aid).split('_',1)[0]
        kind={'CHAR':'characters','LOC':'scenes','PROP':'props'}.get(prefix)
        if not kind:raise ValueError('资产ID格式错误，无法确定恢复目录')
        folder=(base/'assets'/kind).resolve()
        if ask and not self.asset_page_services.confirm(self.win,'恢复资产图片',
                f'恢复 {aid} 的最近删除图片？'):
            return False
        from domain.asset_batch_service import restore_asset_image
        base=AssetPagesMixin.asset_write_base(self)
        restore_asset_image(base,aid,gateway=AssetPagesMixin.asset_batch_gateway())
        self.show(PAGE['assets'])
        self.status.set(aid+' 的资产图片已从项目回收站恢复。')
        return True
    def rename_asset(self,aid,name=None,refresh=True):
        if not aid:raise ValueError('请先选择资产')
        rows=self.asset_requirements();old=rows[aid].get('name',aid)
        if name is None:name=ask_string(self.win,'修改资产名称','新的名称：',initialvalue=old)
        if name is None:return
        name=name.strip()
        if not name:raise ValueError('资产名称不能为空')
        from domain.asset_batch_service import rename_asset as _rename_asset
        _rename_asset(AssetPagesMixin.asset_write_base(self),aid,old,name,gateway=AssetPagesMixin.asset_batch_gateway())
        if refresh:self.show(PAGE['assets'])
        self.status.set('名称已保存')
    def asset_import(self,kind,initial=None,selected=None):
        base=self.asset_base()/'assets'
        p=self.asset_page_services.file_dialog(self.win).open_file(initialdir=initial or (base/kind if kind!='all' else base),filetypes=[('图片','*.png *.jpg *.jpeg *.webp')])
        if not p:return
        aid=selected or ask_string(self.win,'资产编号','例如 CHAR_001 / LOC_001 / PROP_001')
        if not aid:return
        from domain.asset_batch_service import import_asset_image
        kind,result=import_asset_image(AssetPagesMixin.asset_write_base(self),self.root,aid,p,self.asset_requirements(),gateway=AssetPagesMixin.asset_batch_gateway())
        self.asset_kind=kind;self.show(PAGE['assets']);self.status.set(result)
    def dialogue_assets(self):
        """角色名 → 音色／名称的对照表（资产库）；没有或读坏都当空表。"""
        asset_file=self.asset_base()/'assets.json'
        assets=read(asset_file) if asset_file.is_file() else {}
        return assets if isinstance(assets,dict) else {}


class _AssetPage:
    """资产管理页（从 AssetPagesMixin.assets 的闭包原样改写成类，R1816）：共享的局部变量成了实例属性，嵌套函数成了方法；原来的 self（桌面主窗）改叫 page。"""
    def __init__(self, page, kind):
        self.page = page
        self.kind = kind

    def build(self):
        from domain.asset_context import ensure_browser_directory
        from contract.stage_path_service import LEGACY_NUMBERED
        base=self.page.asset_base()
        folder=ensure_browser_directory(base,self.kind,create=base != Path(self.page.root)/LEGACY_NUMBERED['assets'])
        self.registry=self.page.asset_requirements()
        try:source=self.page.current_frame_json();episode=read(source)
        except ValueError:source=None;episode={}
        self.controller=self.page.asset_page_controller(self.registry)
        count=len(self.controller.rows())
        record=self.page.asset_base()/'assets/资产清单/来源.json'
        current_ids=read(record).get('asset_ids',[]) if record.is_file() else []
        used=sum(self.controller.matches(aid) for aid in current_ids)
        label={'scenes':'场景','characters':'角色','props':'道具','all':'全部资产'}[self.kind]
        scope_label={'all':'全部资产','adopted':'已采用分镜','current':'选择分镜'}[self.page.asset_scope()]
        used_label='本集' if self.page.asset_scope()=='current' else '已采用分镜'
        from orchestrator.storyboard_selection import summary
        self.page.note(f'{label} {count} 项 · {scope_label}')
        from domain.asset_reference_prompts import display_prompt
        from ui.asset_reference_prompts_dialog import show_prompt
        self.display_prompt = display_prompt; self.show_prompt = show_prompt
        from asset_reference_images import role_summary
        self.role_summary = role_summary
        table_box=ttk.Frame(self.page.content);table_box.pack(fill='both',expand=True,pady=SPACING['xs']);table_box.columnconfigure(0,weight=1);table_box.rowconfigure(0,weight=1)
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
        table_shell=DataTable(table_box,columns=compact,show='tree headings',height=TEXT_ROWS['lg'],
                              style='Asset.Treeview',empty_text='暂无资产',
                              auto_hide_scrollbars=True)
        self.table=table_shell.tree
        _configure_table_style(self.table,'Asset.Treeview',THUMB_SIZE);configure_check_column(self.table)
        for col,title,width in asset_columns:
            self.table.heading(col,text=title);self.table.column(col,width=MIN_COL,minwidth=MIN_COL,stretch=col in ('note','prompt'))
        remember_columns(self.table,[(col,width) for col,title,width in asset_columns]);auto_columns(self.table)
        refresh_request_width(self.table)
        self.table.tag_configure('completed',background=COLORS['row_completed'],foreground=COLORS['success'])
        table_shell.grid(row=0,column=0,sticky='nsew')
        from responsive_ui import auto_height
        auto_height(self.table, table_box, row_height=ASSET_ROW_HEIGHT)      # 行高了，按 80 算，别再按 34
        self.page.asset_table=self.table          # 第 46 期第 2 条：两行按钮要问「选中／勾选了哪几行」
        self.page.asset_registry=self.registry
        self.checked=self.controller.checks
        # 第 54 期第 3 条：「导入图片」那一列盖得上缩略图就只留图，格子里的「已导入」不再显示
        # （图与字叠着用户判是多此一举）；还没导入／图解不开的照旧写原来的状态文字。
        self.asset_dir=self.page.asset_base()
        # 第 72 期（Round 3）：分段建行。原来一口气把整份清单 insert 完，几千项的时候打开
        # 这一拍界面完全不动；现在先建够第一屏＋余量的那些（ASSET_FIRST_ROWS），剩下的按帧
        # 补（ASSET_ROWS_PER_FRAME）。界面立刻可用、列表随后长齐；中途换页或重建时令牌一过期，
        # 上一串没跑完的分片自己作废，不会往新表里插旧行。
        wanted=self.controller.rows()
        self.controller.initialize_checks()

        self.asset_rows_token=self.page.asset_rows_token=getattr(self.page,'asset_rows_token',0)+1
        for aid,asset in wanted[:ASSET_FIRST_ROWS]:
            self.insert_row(aid,asset)
        self.box=CheckboxColumn(self.table,self.page.win._tick_images,lambda aid:self.checked.get(aid,False),lambda aid,v:self.checked.__setitem__(aid,v),self.refresh_buttons)
        self.table.heading('#0',command=self.toggle_all_assets)
        bind_space_toggle(self.table,self.toggle_asset)
        from cell_hover import CellHover,CellImages
        import cell_hover
        self.cell_hover = cell_hover
        link_cols=('#0','#1','#2','#3','#4','#5','#6')
        # 第 46 期第 1／9 条：同一张表上，「查看」认点中的那一格（仍先补勾选再打开，规矩没变），
        # 「删除」只认右键那一行——高亮不再兼作删除目标，逐个删与批量删从此不会互相误伤。
        # 第 57 期第 3 条：「删除」还要认「右键落在哪一列」——「参考图」那一格删的是这一项的
        # 参考图（原来一律删资产图片，用户在参考图上右键就把导入的图删了）。
        self.table.cell_hover=CellHover(self.table,link_cols,lambda aid,col:self.page.safe(lambda:self.open_cell(aid,col)),cell_image=lambda aid,col:(self.page.win._tick_images[int(self.checked.get(aid,False))] if col=='#0' else None),checked=lambda aid:self.checked.get(aid,False),toggle=self.toggle_asset,delete=lambda aid,col:self.page.safe(lambda:self.page.delete_asset_cell(aid,col)))
        bind_row_toggle(self.table,self.toggle_asset,link_cols)
        # 第 52 期第 3 条：给缩略图那一列盖一层图（#3「导入图片」只盖图）。
        # 第 53 期第 3 条：只盖 #3 一列——「名称」那一列退回原来写的文字（两列同时摆同一张
        # 图是重复，用户点名删掉「名称」列的那个图片）。
        # 没缩略图（还没导入、图不在、Tk 不认这个格式）就不盖，那一格退回原来写的文字。
        # 同一资产在本页生命周期内的缩略图（或后台占位图）是稳定的；CellImages 会在滚动时
        # 多次询问同一行，不能每一帧重复 stat／缓存查询。页面重建会自然丢弃这份映射；后台
        # 完成时会原位填充占位图，因此不需要为等待结果再重复读取。
        self.thumb_values={}
        # 第 57 期第 5 条：鼠标停在这一格上就在旁边弹一张大图（够看清人物与背景）。
        self.table.cell_images=CellImages(self.table,('#3',),self.thumb_value,hover=self.table.cell_hover,background=self.row_background,
                                     zoom=lambda aid,column:self.asset_thumb(aid,self.cell_hover.ZOOM_SIZE),
                                     # 750ms 让连续滚动跨过本机 Tk 的绘制抖动窗口；停止后仍会
                                     # 自动对齐新可见区，且防抖不会退化成逐帧刷新。
                                     view_refresh_delay=750)
        # 第 55 期第 1 条：「视图变了就重排」已经收进盖图那一层自己（watch_view：滚动条动了、
        # 列宽变了、内容框改了尺寸都算），这儿不必再往那两条回调末尾补一次重排。
        # 不在建页路径强制 ``update_idletasks``：它会清空同一 Tcl 解释器里不属于资产表的
        # 空闲队列，慢机上还会让后续补行定时器落进首次 ``update``，退化成首帧一次性建表。
        # CellImages 已在映射事件及自己的空闲回调中补齐覆盖层；首帧之后再按真实 bbox 盖图。
        self.table.cell_images.schedule_initial_refresh()
        self.refresh_buttons()
        # 第 72 期（Round 3）：剩下的行按帧补上，补完再重排一次缩略图那一层。
        self.rest=wanted[ASSET_FIRST_ROWS:]
        if self.rest:
            self.done=[0]
            self.row_job={'id':None}
            def cancel_more_rows(event=None):
                """资产页拆掉时撤销尚未执行的分片插行回调。"""
                if event is not None and event.widget is not self.table:
                    return
                job,self.row_job['id']=self.row_job['id'],None
                if job is not None:
                    try:
                        self.table.after_cancel(job)
                    except tk.TclError:
                        # 表格销毁后 job 已无须取消。
                        pass
            def more_rows():
                self.row_job['id']=None
                try:
                    alive=bool(self.table.winfo_exists())
                except Exception:
                    alive=False
                if not alive or getattr(self.page,'asset_rows_token',None)!=self.asset_rows_token:return
                for aid,asset in self.rest[self.done[0]:self.done[0]+ASSET_ROWS_PER_FRAME]:
                    self.insert_row(aid,asset)
                self.done[0]+=ASSET_ROWS_PER_FRAME
                if self.done[0]<len(self.rest):
                    # 小批次之间留出事件循环间隙。短到用户看不到停顿，长到 Tk 不会在一个
                    # 回调里把所有剩余行连续插完。
                    self.row_job['id']=self.table.after(50,more_rows)
                else:
                    # 分片完成可能正好撞上用户滚动；已有可视缩略图只需重摆，
                    # 仅为刚插入而尚未有图层的行读取 provider，不能在这一帧全量重读。
                    self.table.cell_images.refresh(reuse_existing=True);self.refresh_buttons()
            self.table.bind('<Destroy>',cancel_more_rows,add='+')
            # 先把计时器的创建交给首帧空闲队列：计时若从 ``show()`` 中开始，慢机的首次
            # ``update()`` 本身就可能耗尽延迟，让第二批仍落在首帧。这里只在首帧绘制已经
            # 让出事件循环后开始计时，保证首批 24 行是唯一同步工作，随后才渐进补齐。
            def arm_more_rows():
                if (getattr(self.page,'asset_rows_token',None)!=self.asset_rows_token
                        or not self.table.winfo_exists()):
                    return
                self.row_job['id']=self.table.after(2000,more_rows)
            self.row_job['id']=self.table.after_idle(arm_more_rows)

    def asset_thumb(self, aid,size=THUMB_SIZE):
        """这一项资产已经导入的那张图的小图（路径不安全或没导入就是 None）。

            第 57 期第 5 条：多了 size 一档——鼠标停上去要放大时另解一张大图，不是把小图拉大
            （Tk 只认整数倍抽点，小图放大必然糊）。
            """
        asset=self.registry.get(aid) or {}
        if asset.get('status')!='已导入' or not asset.get('image'):return None
        root=self.asset_dir.resolve();path=(root/asset['image']).resolve()
        if path!=root and root not in path.parents:return None
        return asset_thumbs.thumbnail(self.page.win,path,size)

    def insert_row(self, aid,asset):
        prompt=self.display_prompt(asset)
        # 第 55 期第 3 条：这一格要不要写字交给盖图那一层（盖上收走、撤掉写回）。
        # 原来这里为了判「有没有缩略图」把整个资产库的图都解了一遍——100 项资产就是
        # 100 张图，其中绝大多数根本不在可视区，打开这一页就卡在这儿。
        self.table.insert('','end',iid=aid,text='',image=self.page.win._tick_images[int(self.checked[aid])],values=(aid,asset.get('name',aid),asset['status'],self.role_summary(asset),asset.get('description',asset.get('reference_region','')),prompt.replace('\n',' ') if prompt else '待第1／2步补齐提示词'),tags=('completed',) if asset.get('status')=='已导入' else ())

    def checked_ids(self):
        return self.controller.checked_ids()

    def update_header_check(self):
        refresh_check_heading(self.table, self.page.win._tick_images, lambda aid: self.checked.get(aid,False))

    def refresh_buttons(self):
        self.page.asset_checked_count=len(self.checked_ids())
        self.page.asset_has_pending=self.controller.has_pending()
        self.page.update_asset_buttons()
        self.update_header_check()

    def toggle_asset(self, aid):
        self.box.toggle(aid)

    def toggle_all_assets(self):
        self.box.toggle_all()

    def preview(self):
        if not self.table.selection():raise ValueError('先在资产表中选择一项')
        asset=self.registry[self.table.selection()[0]]
        if asset['status']!='已导入':raise ValueError('该资产尚未导入图片，请先导入')
        p=(self.page.asset_base()/asset['image']).resolve()
        if not p.is_relative_to(self.page.asset_base()):raise ValueError('资产路径越界')
        self.page.asset_page_services.open_path(p)

    def selected(self):return self.table.selection()[0] if self.table.selection() else None

    def detail(self, aid,field):
        asset=self.registry[aid]
        text={'name':asset.get('name',aid),'note':asset.get('description',asset.get('reference_region',''))}.get(field,'')
        win=BaseDialog(self.page.win,aid+' · '+('名称' if field=='name' else '外观要求'),geometry='650x340',modal=False,chrome=False)
        box=TextArea(win,wrap='word',height=TEXT_ROWS['xl'],padx=SPACING['md'],pady=SPACING['md']);box.pack(fill='both',expand=True,padx=SPACING['md'],pady=SPACING['md'])
        box.insert('1.0',text or '暂无内容');box.configure(state='disabled');bind_show_all(box)
        if field=='name':SecondaryButton(win,text='修改名称',command=lambda:(win.destroy(),self.page.safe(lambda:self.page.rename_asset(aid)))).pack(anchor='e',padx=SPACING['md'],pady=(SPACING['none'],SPACING['md']))
        # 第 64 期任务 13（附件任务 4.1）：正典板不再嵌在主页面这个弹窗里，搬进了资产详情页。
        PrimaryButton(win,text='打开资产详情页',
                      command=lambda:(win.destroy(),self.page.safe(lambda:self.page.open_asset_detail(aid)))).pack(anchor='e',padx=SPACING['md'],pady=(SPACING['none'],SPACING['md']))

    def open_cell(self, aid,col):
        self.table.selection_set(aid);self.table.focus(aid)
        if col=='#0':
            self.toggle_asset(aid);return
        if col=='#1':
            # 第 64 期任务 13：「资产编号」那一格就是进详情的入口（主页面不再嵌正典板）。
            # 走 after_idle：点这一格的是内容框自己的事件处理，等它结束再整页重建。
            self.page.win.after_idle(lambda:self.page.safe(lambda:self.page.open_asset_detail(aid)));return
        if col=='#2':
            def save_name(name):
                self.page.rename_asset(aid,name,refresh=False)
                self.registry[aid]['name']=name;self.table.set(aid,'name',name)
            self.table.cell_hover.edit_name(aid,self.registry[aid].get('name',aid),save_name,self.page.status.set,'#2');return
        if col=='#3' and self.registry[aid]['status']=='已导入':self.preview()
        elif col=='#4':self.page.view_reference_images(aid)
        elif col=='#5':self.detail(aid,'note')
        elif col=='#6':self.show_prompt(self.page,aid,self.registry[aid])

    def thumb_value(self, aid,column):
        # 第 54 期第 3 条：图与格子里的字只留一样——文字那一边在建行时就清空了，这里只管盖图。
        if aid in self.thumb_values:
            return self.thumb_values[aid]
        image=self.asset_thumb(aid)
        value=None if image is None else (image,'')
        self.thumb_values[aid]=value
        return value

    def row_background(self, aid):
        return COLORS['row_completed'] if (self.registry.get(aid) or {}).get('status')=='已导入' else COLORS['background_card']
