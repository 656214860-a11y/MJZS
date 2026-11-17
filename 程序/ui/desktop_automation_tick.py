"""桌面定时推进、门禁决策与自动成片扫描（从 desktop.Desktop 原样迁出，R1622）。

方法体未改、self 语义不变；Desktop 通过继承 AutomationTickMixin 获得。Tk 回收护栏与页登记表
分别来自 desktop_tk_gc 与 desktop_page_registry。仍与 Tk 控件紧耦合，故与 desktop 同属 L4。
"""
import pet_ui
from pathlib import Path
from orchestrator.desktop_automation_service import PersistentBackgroundTaskQueue
from agent.core import read
from desktop_page_registry import PAGE
from ui.desktop_tk_gc import drain_tk_gc
from ui.desktop_account_page import RENEW_DELAY_MS


def _migrate_imported_skills():
    import skill_import_service
    return skill_import_service.migrate_legacy_imports()


class AutomationTickMixin:
    def _startup_window_held(self):
        """启动器让主窗口保持透明、由启动画面盖住时为真。"""
        return getattr(self.win,'_drama_hold_alpha',False) is True

    def _after_first_paint(self):
        """首帧已交给 Tk 后，才恢复会触发轮询／回填的周期 tick。"""
        self.win._desktop_first_paint_complete=True
        if not getattr(self,'_codex_skill_sync_started',False):
            from orchestrator.codex_skill_sync import start_codex_skill_sync
            self._codex_skill_sync_started=True
            # R2073：旧版导进 skills/ 的用户 SKILL 先迁到 data/skills/，再同步给 Codex；同一后台线程。
            start_codex_skill_sync(before=_migrate_imported_skills)
        self._start_legacy_project_migration()
        # 会员授权续签在首帧之后才排程，启动路径不等网络（设计文档 §5.4）。
        if hasattr(self,'start_account_renewal'):self.win.after(RENEW_DELAY_MS,self.start_account_renewal)
        if hasattr(self,'start_update_check'):self.win.after(RENEW_DELAY_MS*2,self.start_update_check)
        # 首帧通知不能覆盖用户已发起的后台操作（例如“强制关闭 ComfyUI”）；
        # 否则任务实际结束后状态栏仍停在“正在打开今日项目”。
        # 自动续开尚未选择项目时才显示这条启动提示。已有项目（含测试或
        # 外部入口已经装配好的项目）不能让延后的首帧回调覆盖刚完成的操作结果。
        if self.root is None and not self.worker and not self.projects.legacy_migration_pending:
            self.status.set('正在打开今日项目…')
        if isinstance(getattr(self,'task_queue',None),PersistentBackgroundTaskQueue):
            self._start_next_queued()

    def _request_tick_resume_after_first_paint(self):
        """项目页已完成一次构建后再恢复既有 tick，避免回填重入首帧／建页。"""
        if not bool(getattr(self.win,'_desktop_first_paint_complete',False)):
            return None
        if self._startup_tick_resume_id is None:
            self._startup_tick_resume_id=self.win.after_idle(self._resume_tick_after_first_paint)
        return self._startup_tick_resume_id

    def _resume_tick_after_first_paint(self):
        self._startup_tick_resume_id=None
        if getattr(self,'shutting_down',False):
            return
        self._startup_tick_paused=False
        self.win._desktop_startup_settled=True
        self.automation_scheduler.start(
            'tick',150,self._tick_once,
            on_error=lambda exc:self._set_automation_error('后台任务回调异常，已忽略：',exc),
            remember_timer=lambda timer:setattr(self,'_tick_id',timer))

    def _tick_once(self):
        # 启动期是否排期由 ``_resume_tick_after_first_paint`` 控制；这里保留为
        # 可显式调用的一轮处理，供用户主动操作的收尾与无 Tk 调度器的接缝使用。
        # 若在此再按暂停位直接返回，手工交付的后台结果和自动链都会被永久饿死。
        startup_paused=bool(getattr(self,'_startup_tick_paused',False))
        self._tick_stage_model_sync_result()
        if not startup_paused:
            self._tick_pre_automation()
            # 待办裁决属于本轮自动链的前置准备；先处理才能让后续实际
            # 阶段结果落在状态栏，而不是被一条“已按推荐处理”覆盖。
            self._tick_auto_gates()
        self._tick_async_result()
        self._tick_cloud_monitor()
        self._tick_auto_adopt()
        self._tick_auto_final()
        self._tick_auto_edit()
        self._tick_auto_keyframe()
        self._tick_auto_asset()
        self._tick_auto_video()
        # 白模派发是本轮最后一个可见的前置制作结果，避免同轮视频的“缺首帧”
        # 提示覆盖它；后者已在白模之前完成检查。
        self._tick_auto_previs()
        self._tick_auto_handoff()
        self._tick_pet_events()
        self._tick_download_inbox()

    def _tick_pre_automation(self):
        """在自动阶段调度前回收 Tk 任务并轮询流程进程。"""
        drain_tk_gc()
        try:self.poll_flow_processes()
        except (OSError,ValueError,KeyError):pass

    def _tick_pet_events(self):
        """在本轮自动调度完成后聚合三虎事件，不创建额外线程。"""
        pet_ui.pump(self)

    def auto_final_scan(self):
        """自动定稿的只读扫描（第 72 期 Round 5）：采用清单里还有哪几份没同步、该做哪一份、缺什么。

        返回 dict 四项：sources（采用清单原文）、pending（还没同步成定稿的分镜路径，按采用
        顺序）、target（这一轮该同步的那一份，资产已齐）、source／missing（第一份资产没齐的
        分镜与它缺的编号）。判据与 storyboard_final 的定稿口径同一条：分镜 JSON ＋ 它引用的
        资产都在清单里且有图。04 页那条提示条每 1.5 秒问一次，所以这一份必须只读——不动文件、
        不起批次（「把工作稿移进回收站」那件事只有 poll_auto_final 与手动按钮能做）。
        """
        from orchestrator.storyboard_selection import adopted
        from contract.storyboard_paths import is_final_dir
        from domain.asset_context import references
        from domain.asset_batch_state_service import ready_asset_ids
        try:sources=list(adopted(self.root))
        except (OSError,ValueError,KeyError):sources=[]
        available=ready_asset_ids(self.asset_base())
        pending=[];target=None;blocked=None
        for source in sources:
            path=Path(source)
            if is_final_dir(path.parent.name):continue
            if not path.is_file():continue
            pending.append(path)
            if target is not None:continue
            episode=read(source)
            shots=episode.get('shots',[]) if isinstance(episode,dict) else []
            missing={aid for shot in shots for _,aid in references(shot)}-available
            if missing:
                if blocked is None:blocked=(path,missing)
            else:target=path
        return {'sources':sources,'pending':pending,'target':target,
                'source':blocked[0] if blocked else None,'missing':blocked[1] if blocked else set()}

    def auto_final_target(self):
        """无人值守自动定稿这一轮该做哪一份分镜（第 64 期任务 9）。

        原来只看「当前选择的那一份」：它已经是定稿目录就直接收工，采用清单里其余还没同步的
        分镜永远轮不到——用户报的「自动状态下三虎没有自动同步分镜」。现在按采用顺序挑第一份
        「还是工作稿、引用资产已齐」的；资产没齐的那一份在状态栏说明缺什么，04 页那条提示条
        也同步显示（第 72 期），不挡住别的份。
        """
        scan=self.auto_final_scan()
        if not scan['sources']:
            self.auto.final_signature=None;self.auto.final_notice=None;return None
        if scan['target'] is not None:
            self.auto.final_notice=None;return scan['target']
        missing=scan['missing']
        if missing:
            notice=(str(scan['source']),tuple(sorted(missing)))
            if notice!=self.auto.final_notice:
                self.auto.final_notice=notice
                shown='、'.join(sorted(missing)[:6])+('…' if len(missing)>6 else '')
                self.status.set('无人值守自动定稿暂缓：还缺 '+str(len(missing))+' 项资产图片（'+shown+'）；补齐后会自动定稿')
        else:
            # 剩下的都已经定稿（或被移走）了：别再让提示条挂着上一次那句「还缺…」。
            self.auto.final_notice=None
        return None

    def auto_final_state(self):
        """04 页那条「未同步分镜的可见重试」提示条要显示的东西（第 72 期 Round 5）。

        返回 kind／text／retry／pending／missing 五项：页面拿 text 显示、按 retry 决定
        「立即重试」那颗按钮能不能点。kind 七档：
          off      「自动生成定稿」没勾上
          busy     本轮正在同步资产、生成定稿
          blocked  该动手，但要让正在读这份工作稿的制作批次先跑完
          error    上一轮失败（退避 5 分钟中，点「立即重试」可以马上再来）
          ready    资产齐、等下一轮轮询动手
          missing  还缺资产图片（missing 里是编号，text 报份数并列出最多 6 个）
          done     采用清单里没有要同步的分镜了
        text 尾巴永远带一句「还有 N 份没同步成定稿」——这正是原来只写在状态栏、用户切个页面
        就丢了的那条信息（「无人值守走完采用分镜就静默停住」那条现象）。
        """
        if self.root is None or self.studio is None:
            return {'kind':'off','text':'请先选择项目','retry':False,'pending':0,'missing':()}
        scan=self.auto_final_scan()
        pending=scan['pending']
        shown='、'.join(path.name for path in pending[:3])+('…' if len(pending)>3 else '')
        tail=('还有 %d 份已采用的分镜没同步成定稿（%s）'%(len(pending),shown)) if pending else '已采用的分镜都同步成定稿了'
        def state(kind,text,retry=False,missing=()):
            return {'kind':kind,'text':text+'；'+tail,'retry':retry,'pending':len(pending),'missing':tuple(missing)}
        if not self.pet.should_auto_run('final'):
            return state('off','「自动生成定稿」没勾上：勾上之后资产一补齐就自动同步（定稿会把工作稿移入回收站，可恢复）')
        if self.auto.final_busy:return state('busy','正在同步资产、生成定稿…')
        if self.auto.final_blocked:return state('blocked','自动定稿在等：有制作批次正在读这份工作稿，它跑完就自动接手',retry=True)
        if self.auto.final_error:return state('error','上一轮自动定稿失败：'+self.auto.final_error,retry=True)
        if scan['target'] is not None:
            return state('ready','资产已齐，下一轮轮询就动手（点「立即重试」可以马上做）',retry=True)
        if scan['missing']:
            listed='、'.join(sorted(scan['missing'])[:6])+('…' if len(scan['missing'])>6 else '')
            return state('missing','%s 还缺 %d 项资产图片（%s），补齐后自动定稿；也可以点「立即重试」重扫一遍'
                         %(scan['source'].name,len(scan['missing']),listed),retry=True,missing=sorted(scan['missing']))
        return state('done','当前没有要同步的分镜')

    def retry_auto_final(self):
        """04 页那颗「立即重试」（第 72 期 Round 5）：清掉签名与失败退避，马上再跑一轮自动定稿。

        给「资产刚补齐」「上一轮失败」「刚让完路」这三种情况一个能点的入口——不必等下一个
        30 秒轮询周期，也不用重启。让路规则照旧：真有制作批次在读这份工作稿时，它照样只标一句
        「在等」，不会把人家的批次拆掉。返回这一轮之后该显示的那句话（给状态栏用；页面那条
        提示条自己会重新读一次 auto_final_state）。
        """
        try:
            if self.root is None or self.studio is None:return '请先选择项目'
            if not self.pet.should_auto_run('final'):
                return '未开启「自动生成定稿」：勾上之后资产补齐才会自动同步。'
            self.auto.final_signature=None;self.auto.final_notice=None;self.auto.final_error=''
            self.auto.final_blocked=False;self.auto.final_due=0
            self.poll_auto_final()
            return self.auto_final_state()['text']
        except Exception as exc:
            self.auto.final_error=str(exc)
            return '自动定稿重试失败：'+str(exc)

    def reconcile_storyboards(self):
        """启动对账（第 62 期任务 7）：强制关闭后重开，把已完成的分镜同步进工作集。

        强制关闭可能正好落在 adopt() 与 sync_working_episode() 之间：分镜已经记进采用清单，
        config.json 的 episode_file 还停在旧分镜上。重启后 adopt_pending 看到「没有新东西」
        就早退了，这一步没人补，04 之后各步就还按旧分镜走——用户报的「三虎没有自动同步已经
        完成的分镜」就是这个。这里只补指针，不擅自采用用户没勾「自动采用」的东西。
        """
        from orchestrator.storyboard_selection import repair_working_episode
        try:switched=repair_working_episode(self.root)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            self.status.set('工作集同步暂缓：'+str(exc));return None
        if not switched:return None
        try:
            self.align_studio()
            if getattr(self,'page_index',None) in (PAGE['storyboard'],PAGE['final'],PAGE['keyframe']):
                self.show(self.page_index)
        except (OSError,ValueError,KeyError,TypeError):pass
        self.status.set('已把已完成的分镜同步到工作集：'+Path(switched).name)
        return switched

    def pick_gate(self,key,choice,again=None,digest=''):
        """记一次人工确认，顺手把选择写进资产、再刷面板（第 64 期任务 6）。

        原来只调用 record()：选择进的是 gate_confirmations.json，资产清单里该写的
        canonical_board／character_anchor 一个字没写——「采用推荐」点了资产还是空的。
        现在与资产详情页走同一条写入路径（confirm_gates.apply_choice）。
        """
        from stage_execution_service import record_stage_confirmation
        from stage_execution_service import apply_asset_plan_gate_choice
        apply_asset_plan_gate_choice(self.root,key,choice)
        path=record_stage_confirmation(self.root,key,choice,digest=digest)
        if again:again()                      # 先重建页面（重建会重置状态栏），再写状态栏
        self.status.set('已确认：'+str(choice))
        return path

    def gate_level(self):
        """三虎当前那一档（hint／semi／auto）。读不出来按 hint 算——绝不替用户做主。"""
        import pet_agent
        pet=getattr(self,'pet',None)
        if pet is None:return pet_agent.DEFAULT_LEVEL
        try:value=str(pet.level({}) or '')
        except Exception:return pet_agent.DEFAULT_LEVEL
        return value if value in pet_agent.LEVELS else pet_agent.DEFAULT_LEVEL

    def pending_gate_asks(self):
        """这一刻还没点的门禁候选：锚点定稿、正典板、连贯性裁决三处合起来。"""
        from stage_execution_service import run_stage_confirmation_gate
        try:assets=self.asset_requirements()
        except (ValueError,OSError,TypeError,AttributeError,KeyError):assets={}
        try:ledger=self.continuity_ledger_data()
        except (ValueError,OSError,TypeError,AttributeError,KeyError):ledger={}
        asks=[]
        for gate in ('G-05','G-06','G-08'):
            asks.extend(run_stage_confirmation_gate(
                self.root, gate, assets=assets, ledger=ledger).get('ask') or ())
        return asks

    def auto_decide_gates(self):
        """半自动／全自动：三虎自己把「待办与裁决」里没点的候选按推荐选掉。

        第 64 期任务 6：hint（只提示）档一个字都不做；半自动／全自动不该卡在等人点。
        每一条只处理一次（记进 gate_confirmations.json），选择同时写进资产清单。
        """
        import orchestrator.stage_flow as stage_flow
        from domain.confirm_gates import AUTO
        from stage_execution_service import record_stage_confirmation
        from stage_execution_service import apply_asset_plan_gate_choice
        if self.gate_level() not in stage_flow.AUTO_LEVELS:return 0
        done=0
        for item in self.pending_gate_asks():
            key=str(item.get('key') or '');candidates=list(item.get('candidates') or ())
            if not key or not candidates:continue
            try:index=int(item.get('recommended') or 0)
            except (TypeError,ValueError):index=0
            choice=candidates[min(max(index,0),len(candidates)-1)]
            # 写资产清单或确认账本失败不能伪装成“这条已经处理过”。交给外层
            # _poll_auto_due 的节流与可见错误反馈，下一拍才会重试。
            apply_asset_plan_gate_choice(self.root,key,choice)
            record_stage_confirmation(self.root,key,choice,by=AUTO,digest=str(item.get('digest') or ''))
            done+=1
        if done:
            text='已按推荐处理 %d 条待办：锚点、正典板与连贯性裁决。'%done
            self.pet_report('continuity',text)
            if getattr(self,'page_index',None)==PAGE['continuity']:self.show(PAGE['continuity'])
            self.status.set(text)
        return done
