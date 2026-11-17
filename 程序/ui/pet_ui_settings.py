"""三虎的模型、档位、预算与设置。

从 ``pet_ui.Pet`` 原样迁出（R1506）：方法体未改，``self`` 语义不变，``Pet`` 通过继承
``PetSettingsMixin`` 获得；用到的模块级名字来自 ``pet_ui_support``。
"""
import model_pool
import infra.model_router as model_router
import pet_agent
import infra.token_saver as token_saver
from contract.app_metadata import APP_NAME
from pet_ui_support import Autostart, GearButton, PROGRAM, autostart_command
from ui_tokens import SPACING


# 开机自启开／关的提示只留一份（set_autostart 与 toggle_autostart 共用）。
AUTOSTART_NOTICE = ('开机自启已开启：下次登录会自动启动助手',
                    '开机自启已关闭（或本机不支持）')


class PetSettingsMixin:
    """Pet 的设置方法集（见模块说明）。"""
    def switch_model(self):
        """「切换模型」：在「自动」与池里的模型之间按顺序换一档（下一次调用生效）。

        只换三虎自己用的模型，绝不替用户切生图／视频等会产生费用的引擎——那些开关留在各页面由人来按。
        """
        cycle = [model_pool.AUTO] + list(self.agent_model_records())
        index = (cycle.index(self.tier) + 1) % len(cycle) if self.tier in cycle else 0
        return self.set_tier(cycle[index])
    def _apply_tier(self):
        """把档位写进正在用的那份客户端：换档不换会话，失败清单、通知与 Token 台账都不受影响。

        只改 force_tier 一项，其余设置原样保留（直接整份换掉会把配置文件里的设置一起丢掉）。
        """
        core = self._core
        for client in (self._client, getattr(core[2], 'client', None) if core else None):
            if client is None:
                continue
            try:
                client.config = {**(client.config or {}), **self.tier_config()}
            except Exception as exc:
                self.errors.append(('tier', str(exc)))
        return self.tier
    def model_label(self):
        """菜单文字直接反映当前档位，不另存一份状态。"""
        return '切换模型（当前：%s）' % self.tier_name()
    # ── 模型池（第 43 期：规格里的「模型管理」＋「三虎设置 → 模型」） ─────────────
    def agent_model_records(self):
        """模型池：界面上的选项与写进客户端的覆盖都从这一份读（模型管理是唯一入口）。"""
        return model_pool.pool(program=self.program)
    def agent_model_tasks(self):
        """三虎四个任务维度各用哪一条（缺项补出厂默认）。"""
        return model_pool.agent_models(program=self.program)
    def resolve_agent_model(self, task='default', context=None):
        """规格里的 resolveAgentModel：这一档实际会用哪条模型（挑不出来时说清为什么）。"""
        return model_router.resolve_agent_model(task, records=self.agent_model_records(),
                                                context=context, program=self.program)
    def apply_agent_models(self):
        """把「三虎设置 → 模型」叠进正在用的客户端，并重建「切换模型」子菜单。

        规格里「配置修改后无需重启」就落在这里：读一次盘上的设置就地换掉客户端配置
        （不换会话：失败清单、通知、Token 台账都不受影响），菜单文字与 ✓ 跟着重排。
        """
        tasks = self.agent_model_tasks()
        self.tier = str(tasks.get('default') or model_pool.AUTO)
        self._apply_tier()
        self._fill_model_menu()
        self.refresh_menu_labels()
        return self.tier
    def save_agent_models(self, tasks, notice=None):
        """写「三虎设置 → 模型」：全局配置落盘 ＋ 就地生效 ＋ 用气泡说一句。"""
        data = model_pool.with_tasks(model_pool.raw(self.program), tasks)
        self._agent_file = model_pool.store(data, self.program)
        self.apply_agent_models()
        self.notice = notice or ('已保存三虎模型设置：默认 %s' % self.tier_name())
        self.speak()
        return self.tier
    def save_pool(self, value, old_id=''):
        """模型管理里加／改一条：写盘 ＋ 重建菜单（池子变了，两处下拉立刻跟着变）。"""
        data = model_pool.raw(self.program)
        key = model_pool.model_id_of(value, old_id)
        if str(old_id or '').strip() and str(old_id).strip() != key:
            data = model_pool.remove(data, old_id)      # 改了模型 ID：旧键让位，不留两条
        data = self._prune_tasks(model_pool.upsert(data, value))
        self._agent_file = model_pool.store(data, self.program)
        self.apply_agent_models()
        self._refresh_model_choices()
        self.notice = '已保存模型「%s」' % (model_pool.record(value, key)['label'] or key)
        self.speak()
        return key
    def delete_pool_model(self, model_id):
        """模型管理里删一条：顺手把四个维度里指向它的那一项退回默认、SKILL 预设与当前项目各阶段里指向它的模型改回「自动」，不留死引用。"""
        import orchestrator.stage_config as stage_config
        names, keep = self._pool_model_names(model_id)
        data = self._prune_tasks(model_pool.remove(model_pool.raw(self.program), model_id))
        self._agent_file = model_pool.store(data, self.program)
        released = stage_config.release_preset_model(names, keep, self.program)
        try:
            stages = stage_config.release_project_model(self._current_project(), names, keep)
        except OSError:
            stages = []          # 项目目录写不进去不拦删除：池里已经删掉了
        self.apply_agent_models()
        self._refresh_model_choices()
        self.notice = '已从模型池里删掉「%s」' % str(model_id) + (
            '，%d 个预设的模型已改为「自动」' % len(released) if released else '') + (
            '，当前项目 %d 个阶段的模型已改为「自动」' % len(stages) if stages else '')
        self.speak()
        return model_id
    def _current_project(self):
        """桌面当前打开的项目目录；没开项目（或宠物脱离桌面单独跑）时为 None。"""
        from pathlib import Path
        root = getattr(getattr(self, 'desktop', None), 'root', None)
        return Path(root) if root else None
    def pool_model_stages(self, model_id):
        """删除前给确认框用：当前项目里会改成「自动」的阶段名。"""
        import orchestrator.stage_config as stage_config
        from contract.pet_bus import STAGE_NAMES
        found = stage_config.project_model_references(self._current_project(), *self._pool_model_names(model_id))
        return [STAGE_NAMES.get(stage, stage) for stage in found]
    def _pool_model_names(self, model_id):
        """被删那条的 ID／显示名／模型名，以及池里其余各条的这三项（预设可能按任一种写）。"""
        records = model_pool.pool(program=self.program)
        names_of = lambda key, item: (key, (item or {}).get('label'), (item or {}).get('model'))
        keep = [name for key, item in records.items() if key != model_id for name in names_of(key, item)]
        return names_of(model_id, records.get(model_id)), keep
    def pool_model_presets(self, model_id):
        """删除前给确认框用：会改成「自动」的预设，[(阶段名, 预设名)]。"""
        import orchestrator.stage_config as stage_config
        from contract.pet_bus import STAGE_NAMES
        found = stage_config.preset_model_references(*self._pool_model_names(model_id), program=self.program)
        return [(STAGE_NAMES.get(stage, stage), label) for stage, label in found]
    def _refresh_model_choices(self):
        """池子变了：把还开着的「阶段配置」下拉框也刷一遍（规格：改完不用重启）。"""
        try:
            import ui.skill_panel as skill_panel
            return skill_panel.refresh_all()
        except Exception as exc:
            self.errors.append(('model.refresh', str(exc)))
            return 0
    def _prune_tasks(self, data):
        """池里没有的那一条不能在四个维度里留着：退回出厂默认（默认那一栏退回「自动」）。"""
        records = model_pool.pool(data)
        tasks = model_pool.agent_models(data)
        changed = False
        for key in model_pool.TASK_KEYS:
            value = str(tasks.get(key) or '')
            if value and value != model_pool.AUTO and value not in records:
                tasks[key] = model_pool.AUTO if key == 'default' else model_pool.TASKS_DEFAULT[key]
                changed = True
        return model_pool.with_tasks(data, tasks) if changed else data
    def open_model_settings(self):
        """「三虎设置 → 模型…」：窗口交给 pet_models_ui，改完由本类落盘并立刻生效。"""
        import ui.pet_models_ui as pet_models_ui
        return pet_models_ui.open_settings(self)
    def open_model_manager(self):
        """「模型管理…」：模型池＋API 配置的唯一入口（「+ 新增模型…」也走这里）。"""
        import ui.pet_models_ui as pet_models_ui
        return pet_models_ui.open_manager(self)
    # ── 设置（第 44 期：左上角那颗齿轮 → 基础功能／模型配置／自动化等级／预算） ──────
    def open_settings(self, tab=None):
        """齿轮与右键「设置」都走这里：一扇窗七格；tab 给了就直接落在那一格。

        规格（用户附件第二节 ＋ 本轮要求）：三虎设置改名「设置」；R3089（生命周期
        任务书 T7）把「SKILL 管理」格落地为安装级增删查页，阶段勾选仍归阶段面板。
        """
        import ui.pet_settings_ui as pet_settings_ui
        return pet_settings_ui.open_hub(self, tab)
    def build_gear(self, parent=None):
        """设置入口齿轮（第 R2946 期：真桌面改由侧栏图标轨末尾的 settings 钮承担）。

        真 Desktop 建有 ``settings_rail_button`` 时直接返回——齿轮不再进底栏；
        没有该控件的宿主（自检里的假桌面）照旧建齿轮，退回 pet_dock／标题行／根窗。
        """
        if self.gear is not None:
            return self.gear
        desktop = getattr(self, 'desktop', None)
        if getattr(desktop, 'settings_rail_button', None) is not None:
            return None
        gear_layer = getattr(desktop, 'settings_gear_layer', None)
        holder = parent if parent is not None else gear_layer
        holder = holder if holder is not None else getattr(desktop, 'pet_dock', None)
        holder = holder if holder is not None else getattr(desktop, 'sidebar_head', None)
        holder = holder if holder is not None else self.win
        try:
            self.gear = GearButton(holder, command=lambda: self.act(self.open_settings))
            if holder is self.win:
                # 主窗口根层不受侧栏、标题行或页面画布的裁剪；它在页面控件之后创建，
                # 因而位于根层子控件的最前。
                x, y = getattr(desktop, 'settings_gear_position', (112, 8))
                self.gear.canvas.place(x=x, y=y, anchor='nw')
            elif holder is gear_layer:
                # 底栏齿轮行：画布保持 36px 命中区，pack 居中、不拉伸。
                self.gear.canvas.pack()
            else:
                # 无真实 Desktop 的轻量宿主仍嵌入其标题行，方便复用与无界面自检。
                self.gear.canvas.pack(side='right', padx=(SPACING['none'], SPACING['xs']))
        except Exception as exc:
            self.errors.append(('gear', str(exc)))
            self.gear = None
        return self.gear
    def pet_settings(self):
        """「设置 → 基础功能」那一页要的四件事：名字、贴片动画、免打扰窗口、开机自启。"""
        control = self.autostart()
        try:
            opened = bool(control.enabled()) if control.available else False
        except Exception as exc:
            self.errors.append(('autostart', str(exc)))
            opened = False
        return {'name': pet_agent.PET_NAME, 'anim': self.animation_enabled(),
                'dnd': self.dnd_window(), 'autostart': opened, 'ready': bool(control.available)}
    def token_settings(self):
        """「设置 → Token 节省」那八档现在的样子（没存过就是附件那组出厂值）。"""
        try:
            return token_saver.normalize(pet_agent.load_settings(program=self.program).get('token'))
        except Exception as exc:
            self.errors.append(('settings.token', str(exc)))
            return token_saver.normalize()
    def set_token_settings(self, values):
        """把这八档写进全局配置；顺手过一遍钳制（压缩阈值不许高过窗口的 90%），返回落盘那份。"""
        table = token_saver.normalize(values)
        try:
            pet_agent.save_settings({'token': table}, self.program)
        except Exception as exc:
            self.errors.append(('settings.token', str(exc)))
        return table
    def animation_enabled(self):
        """贴片动画开着吗（设置里关掉就停在那一帧）；配置读不出来＝照旧动，不因为读盘失败变木头。"""
        try:
            return bool(self.agent.settings.get('anim', True))
        except Exception as exc:
            self.errors.append(('settings.anim', str(exc)))
            return True
    def set_anim(self, value):
        """贴片动画开关：写进全局配置 ＋ 立刻生效（关掉＝三虎站着不动，省一点 CPU）。"""
        state = bool(value)
        try:
            pet_agent.save_settings({'anim': state}, self.program)
        except Exception as exc:
            self.errors.append(('settings.anim', str(exc)))
        # 立刻生效：正在用的那份 Agent 设置也换过来（不然要等下一次重启才认）。
        try:
            self.agent.settings['anim'] = state
        except Exception as exc:
            self.errors.append(('settings.anim', str(exc)))
        self.notice = '贴片动画已%s' % ('打开' if state else '关掉')
        return state
    def dnd_window(self):
        """免打扰窗口（起止两个整点）：配置里有就用配置的，读不出来退回规格定的 23:00-07:00。"""
        try:
            window = tuple(self.agent.settings.get('dnd') or pet_agent.DND)
        except Exception as exc:
            self.errors.append(('settings.dnd', str(exc)))
            return tuple(pet_agent.DND)
        return window if len(window) == 2 else tuple(pet_agent.DND)
    def set_dnd(self, start, end):
        """免打扰时段：起止各一个 0-23 的整点；写盘 ＋ 立刻作用到这一批通知上。

        首尾对得一样（23 点到 23 点）＝ 一整天都不打扰，显然不是用户想说的，退回 None 让他改。
        """
        try:
            pair = (int(start), int(end))
        except (TypeError, ValueError):
            return None
        if not all(0 <= hour <= 23 for hour in pair) or pair[0] == pair[1]:
            return None
        try:
            pet_agent.save_settings({'dnd': pair}, self.program)
        except Exception as exc:
            self.errors.append(('settings.dnd', str(exc)))
            return None
        try:
            self.agent.settings['dnd'] = pair
            self.agent.notifier.window = pair
        except Exception as exc:
            self.errors.append(('settings.dnd', str(exc)))
        self.notice = '免打扰时段已改成 %02d:00 - %02d:00' % pair
        return pair
    def set_autostart(self, value):
        """开机自启开／关到指定的样子（界面用；开不了就老实报没开，不留假状态）。"""
        control = self.autostart()
        want = bool(value)
        try:
            if not control.available:
                state = False
            elif want:
                state = bool(control.set(autostart_command(PROGRAM)) and control.enabled())
            else:
                control.clear()
                state = False
        except Exception as exc:
            self.errors.append(('autostart', str(exc)))
            state = False
        self.notice = AUTOSTART_NOTICE[0] if state else AUTOSTART_NOTICE[1]
        return state
    def budget_limits(self):
        """五类配额现在的样子（进度面板与「设置 → 预算」读的是同一本账）。"""
        try:
            return dict(self.agent.budget.limits)
        except Exception as exc:
            self.errors.append(('budget', str(exc)))
            return dict(pet_agent.DEFAULT_BUDGET)
    def budget_usage(self, at=None):
        """用掉了多少：Token 先跟台账对一次表，其余读计数器。"""
        try:
            self.agent.budget.sync_tokens(getattr(self.agent.client, 'ledger', None), at)
            return self.agent.budget.snapshot()
        except Exception as exc:
            self.errors.append(('budget', str(exc)))
            return {'used': {}, 'limits': {}}
    def save_budget_limits(self, values):
        """「设置 → 预算」保存：五类一起写盘 ＋ 立刻作用到正在用的账本（越线即拦）。

        写盘落在全局配置的 budget_limits；缺项按出厂值补齐——面板那一行「x/y」两边都得有数。
        值不合法（空、零、负数、认不出的类别）一律抛 ValueError，界面把那句话照原样显示出来。
        """
        limits = {}
        for kind, raw in dict(values or {}).items():
            name = pet_agent.normalize_kind(kind)
            text = str(raw).strip()
            if not text:
                continue
            try:
                number = int(float(text))
            except (TypeError, ValueError):
                number = 0
            if number <= 0:
                raise ValueError('%s 要填一个正整数。' % pet_agent.BUDGET_NAMES.get(name, name))
            limits[name] = number
        try:
            pet_agent.save_settings({'budget_limits': limits}, self.program)
        except Exception as exc:
            self.errors.append(('settings.budget', str(exc)))
            raise ValueError('预算没写进配置：%s' % exc)
        merged = dict(pet_agent.DEFAULT_BUDGET)
        merged.update(limits)
        try:
            self.agent.budget.limits = dict(merged)
        except Exception as exc:
            self.errors.append(('budget', str(exc)))
        self.notice = '预算已保存：%s' % '、'.join(
            '%s %d' % (pet_agent.BUDGET_NAMES.get(kind, kind), merged[kind])
            for kind in pet_agent.BUDGET_KINDS if kind in merged)
        return merged
    def quit_app(self):
        """「退出程序」（第 44 期按附件放回功能栏）：先问一句再关，别让误按把活儿关掉。"""
        if not self.confirm_start('退出程序', f'要关掉{APP_NAME}吗？没跑完的活留在原地，下次开机接着来。'):
            self.notice = '已取消退出'
            return False
        close = getattr(self.desktop, 'close', None)
        if not callable(close):
            self.notice = '这扇宿主没有退出通道，请从主窗口右上角关掉程序'
            return False
        self.notice = '正在退出：先把没写完的日志收尾'
        close()
        return True
    # ── 开机自启（只写当前用户的 Run 项） ───────────────────────────────────
    def autostart(self):
        """注册表封装按需建一个（拿不到 winreg 的机器上就是「不可用」，不是错误）。"""
        if self._autostart is None:
            self._autostart = Autostart()
        return self._autostart
    def autostart_label(self):
        """菜单文字直接反映注册表里的现状，不另存一份状态。"""
        control = self.autostart()
        if not control.available:
            return '开机自启（本机不支持）'
        value = control.get()
        if value is None:
            return '开机自启（读不到）'
        return '开机自启（已开启）' if value else '开机自启（未开启）'
    def toggle_autostart(self):
        """切换开机自启并把菜单文字改成最新状态；返回切换后的状态。"""
        try:
            state = self.autostart().toggle(PROGRAM)
        except Exception as exc:
            self.errors.append(('autostart', str(exc)))
            state = False
        self.notice = AUTOSTART_NOTICE[0] if state else AUTOSTART_NOTICE[1]
        self.refresh_menu_labels()
        return state
    def autostart_default(self):
        """开机自启默认开着（第 19 期）：注册表里还没这一项就补上；本机不支持就当没这回事。"""
        control = self.autostart()
        if not control.available:
            return False
        try:
            if control.enabled():
                return True
            return bool(control.set(autostart_command(PROGRAM)) and control.enabled())
        except Exception as exc:
            self.errors.append(('autostart.default', str(exc)))
            return False
    def refresh_menu_labels(self):
        """菜单文字跟着状态走（模型档位、「暂停 / 播放」与静默倒计时；不用 Tk 变量）。

        心跳每 150ms 调一次，所以先跟上一份文字比对：没变就不碰菜单（改文字会重排菜单）。
        """
        # 第 22 期：这三条都在一级栏上（静默那条原来在子菜单里，改文字不用整栏重建了）。
        for name, label in (('model', self.model_label()), ('mode', self.mode_label()),
                            ('pause', self.pause_label()), ('snooze', self.snooze_label())):
            if self._menu_labels.get(name) == label:
                continue
            index = self.menu_index.get(name)
            if index is None or self.menu is None:
                continue
            try:
                self.menu.configure_entry(index, label=label)
            except Exception as exc:
                self.errors.append(('menu', str(exc)))
            else:
                self._menu_labels[name] = label
        return self.menu_index.get('pause')
