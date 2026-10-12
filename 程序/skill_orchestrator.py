# -*- coding: utf-8 -*-
"""SKILL 编排器：校验 → 拓扑分层（DAG）→ 逐层执行 → 汇总与「只重试失败项」。

规格（第 28 期第 6 条）要求四件事：
- validate：依赖／冲突／预算三条都要在动手之前拦下来，别做了一半才发现跑不了；
- buildDAG：把选中的 SKILL 排成分层的有向无环图，同层里 parallelizable 的可以并行；
- expand：选中父 SKILL 时自动把它依赖的子 SKILL 一起带上（依赖指向子模块的不算，见
  skill_registry.warnings：那是资产检索这类外部步骤，不是注册表里的 SKILL）；
- execute：付费先确认（免打扰时段排队）→ 预算够不够 → 参数抽取 → 逐个 tool 交回现有子模块 →
  进度事件 → 异常处理（工具没实现／只能回页面按，都算一类结果，不许把整件活带崩）。

进度与汇报全部走 pet_bus 里已经登记的事件：stage.* 报进度、notify.aggregate 报结论、budget.* 报额度
——不为 SKILL 新加事件种类，界面那边照旧订阅原来那几个。SKILL 本身不绑定模型：要模型的地方问
model_router.select，问不出就照旧往下走（工具不吃模型）。

一句话：编排器只管「顺序、预算、确认、汇总」，真正干活的仍是 skill_tools 后面那些子模块。
"""
import hashlib
import json
import time
from pathlib import Path

import pet_bus
import pet_llm
import script_contract
import skill_budget
import skill_registry
import skill_templates
import skill_tools
import stage_parallel
from file_cache import read_json
from model_router import spend_kind

DONE, PAGE, INPUT, PENDING, BUDGET, FAILED, MISSING = ('done', 'page', 'input', 'pending',
                                                      'budget', 'failed', 'missing')
STATUSES = (DONE, PAGE, INPUT, PENDING, BUDGET, FAILED, MISSING)
# 不算失败的几种收场：得回页面按、还缺用户手上的文件、等用户为付费点头、额度不够先停下。
OK_STATUSES = (DONE, PAGE, INPUT)
STOP_STATUSES = (PAGE, INPUT, PENDING, BUDGET)
PARAM_KEYS = ('project', 'episode', 'shots', 'shot', 'shotId', 'stage', 'model',
              'selection', 'assets', 'studio', 'selection_key')
PROJECT_STATUS_FILE = 'sanhu_project_status.json'
# O43：检查点格式版本。旧检查点没有 version，一律当「需人工核实」处理，不假设它和
# 现在的步骤／技能集对得上；版本只在检查点结构变化时 +1。
CHECKPOINT_VERSION = 2


def verified_stage_output(project, stage):
    """返回编排器可独立验证的阶段成果。

    SKILL 的返回值只说明工具函数跑完，不能作为三虎“阶段完成”的证据。只有这里
    明确检查到磁盘上的当前阶段成果，编排器才可发送完成事件；其余阶段由各自的
    生成→校验→采用服务在真正收尾时上报，避免“页面仍未制作却显示已完成”。
    """
    root = Path(project or '')
    if not root.is_dir():
        return False
    try:
        if stage == 'script':
            return script_contract.resolve_script_source(root) is not None
        if stage == 'script_structure':
            output = script_contract.structured_script_path(root)
            return script_contract.is_structured_script(output)
    except (OSError, TypeError, ValueError):
        return False
    return False


def project_status_path(project=None):
    """返回项目运行状态文件；无项目时不把临时状态写入程序目录。"""
    return Path(project) / PROJECT_STATUS_FILE if project not in (None, '') else None


def load_project_status(project=None):
    """读取项目运行状态；损坏或不存在时从空状态开始。"""
    path = project_status_path(project)
    if path is None:
        return {}
    try:
        data = read_json(path)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_project_status(status, project=None):
    """原子写入每个项目的三虎运行状态。"""
    path = project_status_path(project)
    data = dict(status or {})
    if path is None:
        return data
    from agent.core import save_text
    save_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    return data


def checkpoint_digest(stage, step, step_name):
    """检查点身份摘要：阶段＋步骤序号＋步骤名。

    O43：恢复预览用它判断「这一步还是不是当初那一步」——步骤重排、模板步骤改名或技能集
    改动导致步骤名变化时摘要就换一串。技能名相同的原地替换摘不出来，那种情况以磁盘成果
    与采用台账为准（见 resume_preview 的 artifact_verified）。
    """
    body = json.dumps({'stage': str(stage or ''), 'step': int(step or 0),
                       'step_name': str(step_name or '')}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(body.encode('utf-8')).hexdigest()[:32]


class Run(dict):
    """一次 run 的结果：本身就是个字典（好存好传），另外挂上「只重试失败项」这个动作。"""

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.orchestrator = None
        self.context = {}

    def retry_failed(self, context=None):
        """失败项只重试失败项（规格第 6 条）：成功的那些不重跑，省时间也省额度。"""
        if self.orchestrator is None:
            return Run({'ok': False, 'results': [], 'failed': [], 'errors': ['这份结果没带着编排器，重试不了'],
                        'retried': [], 'text': '重试不了。'})
        return self.orchestrator.retry(self, context)

    def text(self):
        return str(self.get('text') or '')


class Orchestrator:
    """把选中的 SKILL 跑起来：校验、分层、执行、汇总、重试，都在这里。"""

    def __init__(self, registry=None, budget=None, router=None, bus=None, errors=None, clock=time.time,
                 trigger='manual', governor=None, project=None, status=None):
        self.registry = registry or skill_registry.default_registry()
        self.budget = budget if budget is not None else skill_budget.Budget(clock=clock)
        self.router = router
        self.bus = bus
        self.errors = errors if errors is not None else []
        self.clock = clock
        self.confirmations = []        # 待用户点头的付费 SKILL（免打扰时段先排队，不弹泡）
        self.approved = set()          # 用户已经点过头的 SKILL 名
        # 第 54 期：手动与自动共用同一台编排器，只有这个标记不同——面板／页面按钮按
        # 「手动」，三虎的自动推进按「自动」。它随 stage.executing 一起发出去，
        # 界面据此决定那颗按钮写「自动执行中」还是「手动执行中」。
        self.trigger = trigger if trigger in ('manual', 'auto') else 'manual'
        # 第 63 期任务 4.2：同层并行的并发号走三虎那份全局控制器（stage_parallel.shared），
        # 这里不另建一个——原来这一路是无条件开线程，开几条由当层的 SKILL 数量说了算。
        self.governor = governor if governor is not None else stage_parallel.shared()
        self.project = project
        self.status = dict(status) if isinstance(status, dict) else load_project_status(project)

    # ── 查表 ────────────────────────────────────────────────────────────────
    def _canonical_id(self, sid):
        """兼容旧版/轻量注册表：没有规范化接口时按原 ID 查询。"""
        name = str(sid or '').strip()
        canonical = getattr(self.registry, 'canonical_id', None)
        return canonical(name) if callable(canonical) else name

    def skill(self, sid):
        return self.registry.getById(self._canonical_id(sid))

    def stage_order(self):
        return {item.name: index for index, item in enumerate(self.registry.getAll())}

    def _skills(self, names):
        out = []
        for name in names or []:
            item = self.skill(name)
            if item is not None and item not in out:
                out.append(item)
        return out

    def _deps(self, sid):
        item = self.skill(sid)
        return list(getattr(item, 'dependsOn', None) or []) if item is not None else []

    # ── 一、校验 ────────────────────────────────────────────────────────────
    def validate(self, ids, context=None):
        """依赖／冲突／预算：动手之前先把话说明白，返回 {'ok': ..., 'errors': [...], ...}。"""
        errors, warnings, missing = [], [], []
        known = []
        for sid in ids or []:
            name = str(sid or '').strip()
            if not name:
                continue
            item = self.skill(name)
            if item is None:
                errors.append('不认识的 SKILL：%s' % name)
            elif item.name not in known:
                known.append(item.name)
        chosen = set(known)
        for item in self._skills(known):
            for dep in item.dependsOn:
                if dep in chosen:
                    continue
                if self.skill(dep) is not None:
                    missing.append({'skill': item.name, 'missing': dep})
                else:
                    warnings.append('%s 依赖的 %s 是子模块／页面上的步骤，不算缺 SKILL' % (item.name, dep))
            for other in item.conflictsWith:
                if other in chosen and other != item.name:
                    errors.append('%s 与 %s 互斥，不能放在一批里跑' % (item.displayName, other))
        cost = {}
        for item in self._skills(known):
            kind = spend_kind(item)
            cost[kind] = cost.get(kind, 0) + 1
            enough, note = self.budget.check(kind, 1)
            if not enough:
                errors.append('%s：%s' % (item.displayName, note))
                if self.bus is not None:
                    pet_bus.emit_safe(self.bus, self.errors, 'budget.exceeded', budget=kind,
                                      used=self.budget.used(kind), limit=self.budget.limit(kind))
        return {'ok': not errors, 'errors': errors, 'warnings': warnings, 'missing_deps': missing,
                'cost': cost, 'skills': known}

    # ── 二、展开与分层 ──────────────────────────────────────────────────────
    def expand(self, ids):
        """父 SKILL 自动展开子 SKILL：按 dependsOn 递归，去重，最后按阶段顺序排队。"""
        out, seen = [], set()

        def visit(name):
            name = self._canonical_id(name)
            if name in seen:
                return
            seen.add(name)
            item = self.skill(name)
            if item is None:
                return
            for dep in item.dependsOn:
                if self.skill(dep) is not None:
                    visit(dep)
            out.append(name)

        for sid in ids or []:
            visit(str(sid or '').strip())
        order = self.stage_order()
        return sorted(out, key=lambda sid: (order.get(sid, 999), sid))

    def buildDAG(self, ids):
        """拓扑分层：返回 {'layers': [[名字]], 'order': [...], 'problems': [...]}。"""
        order = self.stage_order()
        remaining = [sid for sid in dict.fromkeys(str(item or '') for item in (ids or [])) if self.skill(sid)]
        layers, problems = [], []
        while remaining:
            pool = set(remaining)
            layer = [sid for sid in remaining if not (set(self._deps(sid)) & pool)]
            if not layer:
                problems.append('依赖成环：' + '、'.join(sorted(remaining)))
                layer = list(remaining)       # 环里的硬着头皮当一层：卡死比跑歪更糟
            layer.sort(key=lambda sid: (order.get(sid, 999), sid))
            layers.append(layer)
            for sid in layer:
                remaining.remove(sid)
        return {'layers': layers, 'order': [sid for layer in layers for sid in layer], 'problems': problems}

    # ── 三、付费确认（免打扰时段排队） ──────────────────────────────────────
    def quiet_now(self, at=None):
        try:
            return bool(pet_llm.in_off_peak(at if at is not None else self.clock()))
        except Exception as exc:
            self.errors.append(('in_off_peak', str(exc)))
            return False

    def confirm_text(self, item, quiet=False):
        if quiet:
            return '这会儿夜深了，先不打扰您：「%s」要花钱，我给您排上队，天亮了再问您一声。' % item.displayName
        return '「%s」要花钱，做不做？点个头我就开工。' % item.displayName

    def pending_confirmations(self):
        return [dict(row) for row in self.confirmations]

    def approve(self, names):
        for name in names or []:
            text = str(name or '').strip()
            if text:
                self.approved.add(text)
        return sorted(self.approved)

    def confirm_all(self, ok=True, at=None):
        """把排队的付费确认一次答完（三虎把那几件并成一个气泡问，用户点一次头）。"""
        rows = list(self.confirmations)
        self.confirmations = []
        if ok:
            for row in rows:
                self.approved.add(row['skill'])
        if rows and self.bus is not None:
            names = '、'.join(row['name'] for row in rows)
            text = ('好，这几件付费的活我这就去做：' if ok else '行，这几件先搁着：') + names
            pet_bus.emit_safe(self.bus, self.errors, 'notify.aggregate', text=text)
        return rows

    def _confirmed(self, item, context):
        flag = context.get('confirm')
        if flag is True:
            return True
        if isinstance(flag, (list, tuple, set, frozenset)) and item.name in flag:
            return True
        return item.name in self.approved

    def _queue(self, item, context):
        quiet = self.quiet_now(context.get('at'))
        row = {'skill': item.name, 'name': item.displayName, 'paid': True, 'queued': quiet,
               'at': context.get('at') or self.clock(), 'text': self.confirm_text(item, quiet)}
        if not any(other['skill'] == item.name for other in self.confirmations):
            self.confirmations.append(row)
        if self.bus is not None and not quiet:
            pet_bus.emit_safe(self.bus, self.errors, 'notify.aggregate', text=row['text'])
        return row

    # ── 四、执行 ────────────────────────────────────────────────────────────
    def params(self, item, context):
        """参数抽取：把上下文里这件 SKILL 用得到的那几样挑出来存进结果，别的原样留在 context 里。"""
        return {key: context.get(key) for key in PARAM_KEYS if context.get(key) not in (None, '', [], {})}

    def _brief(self, out):
        if isinstance(out, dict):
            for key in ('detail', 'text', 'path', 'manifest', 'saved', 'count'):
                if out.get(key) not in (None, ''):
                    return str(out[key])[:160]
            return '、'.join('%s=%s' % (key, out[key]) for key in sorted(out)[:4])[:160]
        return str(out)[:160]

    def before_step(self, stage, step, skills=None):
        """每个 SKILL 实际执行前记录可恢复检查点（O43：带格式版本、项目身份与步骤摘要）。

        检查点写不进去就抛，调用方据此在动手之前收场——付费动作绝不先于检查点落盘。
        """
        stage_id = str(getattr(stage, 'id', None) or getattr(stage, 'stage', None) or stage or '')
        try:
            step_index = int(getattr(step, 'index', None) or 0)
        except (TypeError, ValueError):
            step_index = 0
        if step_index < 1:
            raise ValueError('检查点步骤序号必须从 1 开始')
        step_name = str(getattr(step, 'name', None) or getattr(step, 'displayName', None) or step or '')
        try:
            at = float(self.clock())
        except (TypeError, ValueError):
            at = 0.0
        checkpoint = {
            'stage': stage_id,
            'step': step_index,
            'step_name': step_name,
            'completed_steps': list(range(1, step_index)),
            'version': CHECKPOINT_VERSION,
            'at': at,
            'project': str(self.project or ''),
            'skills': [str(name) for name in (skills or [])],
            'digest': checkpoint_digest(stage_id, step_index, step_name),
        }
        # 写成功才认这份内存状态：写失败（磁盘满／没权限）时不许留下一个没落盘的检查点，
        # 也不许接着往下跑付费动作（save_project_status 会抛，调用方据此收场）。
        pending = dict(self.status)
        pending['current_stage'] = stage_id
        pending['checkpoint'] = checkpoint
        save_project_status(pending, self.project)
        self.status.clear()
        self.status.update(pending)
        return dict(checkpoint)

    def clear_checkpoint(self, stage):
        """阶段成功收尾后清掉自己的检查点，避免下次启动误报中断。"""
        stage_id = str(getattr(stage, 'id', None) or getattr(stage, 'stage', None) or stage or '')
        checkpoint = self.status.get('checkpoint') if isinstance(self.status, dict) else None
        if not isinstance(checkpoint, dict) or checkpoint.get('stage') != stage_id:
            return False
        self.status.pop('checkpoint', None)
        save_project_status(self.status, self.project)
        return True

    def _checkpoint_step(self, item):
        """将注册表中的 SKILL 映射为该阶段的稳定步骤序号。"""
        steps = list(self.registry.getByStage(item.stage))
        try:
            index = steps.index(item) + 1
        except ValueError:
            index = 1
        return type('CheckpointStep', (), {'index': index, 'name': item.displayName})()

    def _template_steps(self, stage_id):
        """模板存在时优先使用它作为恢复时的用户可见步骤。"""
        try:
            return skill_templates.load_template(stage_id).steps
        except (OSError, ValueError, UnicodeError):
            return ()

    def recover_from_checkpoint(self, wait_for_user=None, broadcast=None):
        """询问中断检查点，并返回应继续执行的步骤序号或 False。"""
        checkpoint = self.status.get('checkpoint') if isinstance(self.status, dict) else None
        if not isinstance(checkpoint, dict):
            return False
        stage_id = str(checkpoint.get('stage') or '')
        steps = self._template_steps(stage_id) or list(self.registry.getByStage(stage_id))
        try:
            step_index = int(checkpoint.get('step') or 0)
        except (TypeError, ValueError):
            return False
        if not stage_id or step_index < 1 or step_index > len(steps):
            return False
        stage_name = pet_bus.STAGE_NAMES.get(stage_id, stage_id)
        default_name = getattr(steps[step_index - 1], 'name',
                               getattr(steps[step_index - 1], 'displayName', ''))
        step_name = str(checkpoint.get('step_name') or default_name)
        messages = (
            '【恢复】检测到中断',
            '【恢复】阶段：%s，步骤 %d/%d：%s' % (stage_name, step_index, len(steps), step_name),
            '【恢复】是否从步骤 %d 继续？[继续/跳过/重做]' % step_index,
        )
        emit = broadcast if callable(broadcast) else (lambda text: None)
        for message in messages:
            emit(message)
        if not callable(wait_for_user):
            return False
        choice = str(wait_for_user(messages[-1]) or '').strip()
        if choice == '继续':
            return step_index
        if choice == '跳过':
            return step_index + 1 if step_index < len(steps) else False
        if choice == '重做':
            return 1
        return False

    def resume_preview(self, context=None):
        """恢复预览（只读）：核对中断检查点与现在的项目／步骤／技能，给一份续跑计划（O43）。

        与 recover_from_checkpoint 的区别在「核对」而不只是「问」：先把检查点格式版本、项目
        身份、步骤摘要与磁盘成果都比一遍，再按步骤给出「续做／跳过／需人工核实」。

        两个「完成」分得很清楚：
        - **工具调用完成**：检查点里的 completed_steps 只说明那几步的工具跑过了；
        - **阶段成果完成**：以 verified_stage_output 为准（磁盘上真有可采用的成果）。
        版本／项目／步骤摘要任何一条对不上都标「需人工核实」，不自动续跑；已存在可验证阶段
        成果时整段标「跳过」，不重复付费、不重复发布。本方法不改状态、不写文件、不发事件。
        """
        checkpoint = self.status.get('checkpoint') if isinstance(self.status, dict) else None
        if not isinstance(checkpoint, dict):
            return {'found': False, 'stage': '', 'stage_name': '', 'step': 0, 'step_name': '',
                    'total_steps': 0, 'version': None, 'version_ok': False, 'project': '',
                    'project_ok': False, 'digest_ok': False, 'scope_ok': False, 'skills': [],
                    'artifact_verified': False, 'tools_done': [], 'steps': [],
                    'continue_count': 0, 'skip_count': 0, 'verify_count': 0, 'paid': [],
                    'lines': ['没有中断检查点：本次从头开始，不涉及恢复。'],
                    'text': '没有中断检查点：本次从头开始，不涉及恢复。'}
        stage_id = str(checkpoint.get('stage') or '')
        steps = list(self._template_steps(stage_id) or self.registry.getByStage(stage_id))
        total = len(steps)
        try:
            step_index = int(checkpoint.get('step') or 0)
        except (TypeError, ValueError):
            step_index = 0

        def name_at(index):
            if 1 <= index <= total:
                item = steps[index - 1]
                return str(getattr(item, 'name', None) or getattr(item, 'displayName', '') or '')
            return ''

        step_name = str(checkpoint.get('step_name') or name_at(step_index))
        recorded_project = str(checkpoint.get('project') or '')
        version_ok = checkpoint.get('version') == CHECKPOINT_VERSION
        # 旧检查点没有 project 键：记不清就不当成「另一个项目」，交给版本检查去提示。
        project_ok = (not recorded_project) or recorded_project == str(self.project or '')
        scope_ok = bool(stage_id) and 1 <= step_index <= total
        digest = checkpoint.get('digest')
        digest_ok = bool(digest) and scope_ok and digest == checkpoint_digest(
            stage_id, step_index, name_at(step_index))
        artifact_verified = bool(verified_stage_output(self.project, stage_id))

        plan = []
        for index in range(1, total + 1):
            if not scope_ok:
                verdict, reason = 'verify', '检查点步骤 %d 落在当前 %d 步之外，需人工核实' % (step_index, total)
            elif index < step_index:
                verdict, reason = 'skip', '检查点之前的步骤：工具已跑过（工具调用完成，不等于成果已采用）'
            elif index > step_index and artifact_verified:
                verdict, reason = 'skip', '该阶段成果已验证，不重复执行'
            elif index > step_index:
                verdict, reason = 'continue', '后续步骤'
            elif not version_ok:
                verdict, reason = 'verify', '检查点由旧版格式写入，需人工核实'
            elif not project_ok:
                verdict, reason = 'verify', '检查点属于另一个项目，需人工核实'
            elif not scope_ok or not digest_ok:
                verdict, reason = 'verify', '这一步与现在的步骤／技能集对不上，需人工核实'
            elif artifact_verified:
                verdict, reason = 'skip', '该阶段成果已验证，不重复执行这一步'
            else:
                verdict, reason = 'continue', '从这一步续做'
            plan.append({'index': index, 'name': name_at(index), 'verdict': verdict, 'reason': reason})

        counts = {key: sum(1 for row in plan if row['verdict'] == key)
                  for key in ('continue', 'skip', 'verify')}
        paid = sorted({item.name for item in self.registry.getByStage(stage_id)
                       if getattr(item, 'paid', False)})
        tools_done = [index for index in range(1, step_index) if 1 <= index <= total]
        stage_name = pet_bus.STAGE_NAMES.get(stage_id, stage_id)
        lines = ['【恢复预览】阶段：%s，步骤 %d/%d：%s' % (stage_name or stage_id, step_index, total,
                                                          step_name or '—'),
                 '【恢复预览】将续做 %d 步、跳过 %d 步、需人工核实 %d 步。' % (
                     counts['continue'], counts['skip'], counts['verify'])]
        if not version_ok:
            lines.append('【恢复预览】检查点由旧版格式写入（版本 %s，当前 %d）：请人工核实步骤边界后再续跑。' % (
                checkpoint.get('version'), CHECKPOINT_VERSION))
        if not project_ok:
            lines.append('【恢复预览】检查点属于「%s」，与当前项目「%s」不一致。' % (
                recorded_project, self.project))
        if version_ok and project_ok and (not scope_ok or not digest_ok):
            lines.append('【恢复预览】这一步与现在的步骤／技能集对不上，需人工核实后再续跑。')
        if artifact_verified:
            lines.append('【恢复预览】该阶段成果已验证（阶段成果完成）：整段跳过，不重复付费、不重复发布。')
        elif tools_done:
            lines.append('【恢复预览】已完成的是工具调用（步骤 %s），尚未确认阶段成果。' % '、'.join(
                str(index) for index in tools_done))
        if paid:
            lines.append('【恢复预览】本阶段含付费步骤：%s；只有标「续做」的才会重新提交。' % '、'.join(paid))
        return {'found': True, 'stage': stage_id, 'stage_name': stage_name, 'step': step_index,
                'step_name': step_name, 'total_steps': total, 'version': checkpoint.get('version'),
                'version_ok': version_ok, 'project': recorded_project,
                'project_ok': project_ok, 'digest_ok': digest_ok, 'scope_ok': scope_ok,
                'skills': [str(name) for name in (checkpoint.get('skills') or [])],
                'artifact_verified': artifact_verified, 'tools_done': tools_done, 'steps': plan,
                'continue_count': counts['continue'], 'skip_count': counts['skip'],
                'verify_count': counts['verify'], 'paid': paid,
                'lines': lines, 'text': '\n'.join(lines)}

    def execute(self, sid, context=None):
        """跑一个 SKILL：返回一条结果（字典）。任何一步出岔子都只记在结果里。"""
        context = context if isinstance(context, dict) else {}
        item = self.skill(sid)
        if item is None:
            return self._result(sid, MISSING, False, detail='注册表里没有这个 SKILL')
        if item.paid and not self._confirmed(item, context):
            row = self._queue(item, context)
            return self._result(item.name, PENDING, False, detail=row['text'], paid=True,
                                queued=row['queued'], name=item.displayName)
        kind = spend_kind(item)
        enough, note = self.budget.check(kind, 1)
        if not enough:
            if self.bus is not None:
                pet_bus.emit_safe(self.bus, self.errors, 'budget.exceeded', budget=kind,
                                  used=self.budget.used(kind), limit=self.budget.limit(kind))
            return self._result(item.name, BUDGET, False, detail=note, kind=kind, name=item.displayName)
        model, reason = '', ''
        if self.router is not None:
            try:
                choice = self.router.select(item, context)
                model, reason = getattr(choice, 'model', '') or '', getattr(choice, 'reason', '') or ''
            except Exception as exc:
                self.errors.append((item.name, str(exc)))
        try:
            template_step = context.get('_template_step')
            self.before_step(item.stage, template_step or self._checkpoint_step(item), [item.name])
        except (OSError, TypeError, ValueError) as exc:
            self.errors.append((item.name + '.checkpoint', str(exc)))
            return self._result(item.name, FAILED, False, detail='检查点写入失败：%s' % exc,
                                name=item.displayName)
        if self.bus is not None:
            pet_bus.emit_safe(self.bus, self.errors, 'stage.executing', stage=item.stage,
                              skill=item.name, trigger=self.trigger)
            pet_bus.emit_safe(self.bus, self.errors, 'stage.started', stage=item.stage, skill=item.name)
        rows, errors, page, page_title, need = [], [], '', '', ''
        for tool in item.tools:
            try:
                out = skill_tools.call(tool, context)
                rows.append({'tool': tool, 'status': DONE, 'detail': self._brief(out)})
            except skill_tools.ToolNeedsPage as exc:
                page = page or exc.page
                page_title = page_title or exc.title()
                rows.append({'tool': tool, 'status': PAGE, 'page': exc.page,
                             'pageTitle': exc.title(), 'hint': exc.hint})
            except skill_tools.ToolNeedsInput as exc:
                need = need or str(exc)
                rows.append({'tool': tool, 'status': INPUT, 'detail': str(exc)})
            except skill_tools.ToolMissing as exc:
                errors.append('%s：%s' % (tool, exc))
                rows.append({'tool': tool, 'status': MISSING, 'detail': str(exc)})
            except Exception as exc:
                errors.append('%s：%s' % (tool, exc))
                rows.append({'tool': tool, 'status': FAILED, 'detail': str(exc)})
        worked = any(row['status'] == DONE for row in rows)
        if errors:
            status, detail = FAILED, '；'.join(errors)[:200]
        elif worked:
            status, detail = DONE, (('这一步剩下的得回「%s」页面上按' % (page_title or page))
                                    if page else '做完了')
        elif page:
            status, detail = PAGE, '这一步得回「%s」页面上按' % (page_title or page)
        elif need:
            status, detail = INPUT, need
        else:
            status, detail = DONE, '做完了'
        # ``script.completed`` 是三虎自动链的唯一启动信号。工具本身返回完成，
        # 并不等同于自然剧本已经保存；没有可读原稿时绝不能让下游结构化阶段抢跑。
        output_verified = status == DONE and verified_stage_output(context.get('project'), item.stage)
        if status == DONE and item.stage in ('script', 'script_structure') and not output_verified:
            if item.stage == 'script':
                status = FAILED
                detail = '剧本步骤未保存可读取的自然剧本，不能标记完成或启动自动流程'
            else:
                status = FAILED
                detail = '剧本结构步骤未保存可读取的结构剧本，不能标记完成或启动自动流程'
        if status == DONE:
            self.budget.spend(kind, 1)
        if self.bus is not None:
            if status == DONE:
                if item.stage == 'script' and output_verified:
                    # 第 54 期附件四第 3 条：剧本做完就是自动推进那条链的起点。
                    pet_bus.emit_safe(self.bus, self.errors, 'script.completed', stage=item.stage,
                                      skill=item.name)
                # 只有当前模块能直接验证成果的两段剧本可以在此收场。初步分镜及
                # 其他阶段的 SKILL “done”常只是派发或检查完成，必须由对应服务在
                # 生成→校验→采用后发 stage.completed，不能让三虎产生假完成提示。
                if output_verified:
                    pet_bus.emit_safe(self.bus, self.errors, 'stage.completed', stage=item.stage, skill=item.name)
                else:
                    # 释放按钮的“执行中”视觉状态，但不改变 pet_state 的成功状态，也
                    # 不触发自动链。用户仍可继续操作或等待后台产物校验完成。
                    pet_bus.emit_safe(self.bus, self.errors, 'stage.paused', stage=item.stage,
                                      reason='SKILL 已执行，等待已验证的阶段成果')
            elif status == FAILED:
                pet_bus.emit_safe(self.bus, self.errors, 'stage.failed', stage=item.stage,
                                  error=detail, skill=item.name)
        return self._result(item.name, status, status in OK_STATUSES, detail=detail, name=item.displayName,
                            page=page, pageTitle=page_title, kind=kind,
                            model=model, reason=reason, paid=bool(item.paid),
                            parallelizable=bool(item.parallelizable), params=self.params(item, context),
                            tools=rows)

    def _result(self, skill, status, ok, **extra):
        row = {'skill': skill, 'status': status, 'ok': bool(ok), 'at': self.clock()}
        row.update(extra)
        return row

    def _template_groups(self, names, step_count):
        """将当前阶段已启用的细粒度 SKILL 平均归入业务模板步骤，确保不会漏跑。"""
        rows = list(names or ())
        groups, start = [], 0
        for index in range(step_count):
            remaining = len(rows) - start
            slots = step_count - index
            size = (remaining + slots - 1) // slots if remaining else 0
            groups.append(rows[start:start + size])
            start += size
        return groups

    @staticmethod
    def _template_summary(rows):
        if isinstance(rows, dict):
            return str(rows.get('summary') or rows.get('detail') or rows.get('text') or '已执行')[:160]
        if isinstance(rows, (list, tuple)):
            return '；'.join(str(row.get('detail') or row.get('skill') or '') for row in rows
                            if isinstance(row, dict))[:160] or '已执行'
        return str(rows or '已执行')[:160]

    def run_stage_with_template(self, stage_id, context=None, names=None, mode='manual', wait_for_user=None,
                                broadcast=None, execute_action=None, start_step=1):
        """载入阶段模板，以其业务步骤驱动已启用 SKILL 或注入的动作执行器。

        ``execute_action`` 是给页面适配器和回归测试的明确动作边界；缺省时仍执行注册表中
        该阶段已启用的全部 SKILL，不因四步业务模板而遗失第五项细粒度工作。
        """
        template = skill_templates.load_template(stage_id)
        context = dict(context or {})
        emit = broadcast if callable(broadcast) else (lambda text: None)
        manual = mode != 'auto'
        try:
            start_step = int(start_step)
        except (TypeError, ValueError):
            start_step = 1
        start_step = min(max(start_step, 1), len(template.steps) + 1)
        selected = [item for item in (names or [row.name for row in self.registry.getByStage(template.stage_id)])
                    if self.skill(item) is not None and self.skill(item).stage == template.stage_id]
        if not callable(execute_action) and not selected:
            message = '【阻塞】%s 未启用可执行 SKILL' % template.name
            emit(message)
            return Run({'ok': False, 'results': [], 'failed': [], 'errors': [message], 'text': message})
        stage_number = list(pet_bus.STAGES).index(template.stage_id) + 1
        emit('【阶段 %d/%d】%s' % (stage_number, len(pet_bus.STAGES), template.name))
        groups = self._template_groups(selected, len(template.steps))
        results, failed, skipped = [], [], []
        for step, group in zip(template.steps, groups):
            if step.index < start_step:
                continue
            emit('【步骤 %d/%d】%s' % (step.index, len(template.steps), step.name))
            if step.needs_confirmation and manual:
                question = step.question.format(count=context.get('count', 0))
                emit('【门禁】%s' % question)
                answer = str(wait_for_user(question) if callable(wait_for_user) else '').strip()
                if answer not in ('确认', '需要', '继续', '是', 'yes', 'YES', 'Yes'):
                    skipped.append(step.name)
                    emit('【警告】未确认，已跳过%s' % step.name)
                    continue
            try:
                self.before_step(template.stage_id, step, [str(name) for name in group])
                step_context = dict(context, _template_step=step)
                if callable(execute_action):
                    outcome = execute_action(step.action, step_context)
                    rows = [outcome]
                else:
                    rows = [self.execute(name, step_context) for name in group]
            except (OSError, TypeError, ValueError) as exc:
                rows = [self._result(step.action, FAILED, False, detail=str(exc))]
            results.extend(rows)
            bad = [row for row in rows if isinstance(row, dict) and not row.get('ok', False)]
            if bad:
                failed.extend(bad)
                detail = self._template_summary(bad)
                emit('【阻塞】%s：%s' % (step.name, detail))
                break
            emit('【完成】%s：%s' % (step.name, self._template_summary(rows)))
        ok = not failed
        text = ('%s已完成' % template.name) if ok else ('%s未完成' % template.name)
        if ok:
            self.clear_checkpoint(template.stage_id)
            emit('【完成】%s' % text)
        run = Run({'ok': ok, 'results': results, 'failed': failed, 'skipped': skipped,
                   'errors': [row.get('detail', '') for row in failed], 'text': text,
                   'template': str(template.path)})
        run.orchestrator, run.context = self, context
        return run

    # ── 五、按层跑完一批 ────────────────────────────────────────────────────
    def run(self, ids, context=None, trigger=None):
        """跑一批 SKILL：先展开、再校验、再按层走，最后给一份汇总。

        trigger 是「这一趟谁发起的」（'manual'／'auto'，第 54 期）：手动按钮与三虎自动
        共用这台编排器，只有它不同；不给就沿用构造时那一档。
        """
        context = dict(context or {})
        if trigger in ('manual', 'auto'):
            self.trigger = trigger
        wanted = self.expand(ids)
        check = self.validate(wanted, context)
        run = Run({'ok': False, 'skills': wanted, 'layers': [], 'results': [], 'failed': [],
                   'errors': list(check['errors']), 'warnings': list(check['warnings']),
                   'missing_deps': check['missing_deps'], 'cost': check['cost'],
                   'pending': [], 'problems': [], 'parallel': bool(context.get('parallel')),
                   'at': self.clock()})
        run.orchestrator = self
        run.context = context
        if not wanted:
            run['text'] = '没点到要跑的 SKILL，那就先不动手。'
            return run
        if check['errors']:
            run['text'] = '先别动手：' + '；'.join(check['errors'])
            return run
        dag = self.buildDAG(wanted)
        run['layers'], run['problems'] = dag['layers'], dag['problems']
        for layer in dag['layers']:
            run['results'].extend(self._run_layer(layer, context))
        run['failed'] = [row['skill'] for row in run['results'] if row['status'] == FAILED]
        run['pending'] = [row for row in run['results'] if row['status'] == PENDING]
        run['ok'] = not run['failed']
        run['text'] = self.describe(run)
        if self.bus is not None:
            pet_bus.emit_safe(self.bus, self.errors, 'notify.aggregate', text=run['text'])
        return run

    def _run_layer(self, layer, context):
        parallel = bool(context.get('parallel')) and len(layer) > 1
        if parallel:
            parallel = all(bool(getattr(self.skill(sid), 'parallelizable', False)) for sid in layer)
        return self._run_parallel(layer, context) if parallel else [self.execute(sid, context) for sid in layer]

    def _run_parallel(self, layer, context):
        """同层的并行：交给 stage_parallel.parallel_map（第 63 期任务 4.2）。

        在飞几个由「这一步的并行度上限」与「全局 8 路」取小决定，同一资源撞车先排队；
        结果按原顺序收回（工具那边只碰自己的文件）。
        """
        stage = str((context or {}).get('stage') or '')

        def work(sid):
            try:
                return self.execute(sid, context)
            except Exception as exc:
                self.errors.append((sid, str(exc)))
                return self._result(sid, FAILED, False, detail=str(exc))

        rows = stage_parallel.parallel_map(stage, list(layer), work, governor=self.governor)
        out = []
        for sid, row, error in rows:
            if isinstance(row, dict):
                out.append(row)
            else:
                out.append(self._result(sid, FAILED, False, detail=str(error) or '这一路没回结果'))
        return out

    def retry(self, run, context=None):
        """只重试失败项：拿上一次的 failed 列表再跑一遍，成功的那些不重跑。"""
        failed = list(run.get('failed') or [])
        merged = dict(run.context or {})
        merged.update(context or {})
        again = Run({'ok': True, 'skills': failed, 'layers': [], 'results': [], 'failed': [],
                     'errors': [], 'warnings': [], 'missing_deps': [], 'cost': {}, 'pending': [],
                     'problems': [], 'retried': failed, 'at': self.clock()})
        again.orchestrator = self
        again.context = merged
        if not failed:
            again['text'] = '没有失败项，不用重试。'
            return again
        again.update({key: value for key, value in self.run(failed, merged).items()
                      if key in ('layers', 'results', 'failed', 'errors', 'warnings', 'pending', 'cost', 'ok')})
        again['retried'] = failed
        again['text'] = '重试了一遍：' + self.describe(again)
        return again

    # ── 六、说人话 ──────────────────────────────────────────────────────────
    def describe(self, run):
        """把一份结果说成三虎能直接播报的几句话（编号交给聊天框那边统一加）。"""
        rows = list(run.get('results') or [])
        done = [row for row in rows if row['status'] == DONE]
        page = [row for row in rows if row['status'] == PAGE]
        need = [row for row in rows if row['status'] == INPUT]
        pending = [row for row in rows if row['status'] == PENDING]
        failed = [row for row in rows if row['status'] == FAILED]
        lines = []
        lines.append('这一批 %d 个 SKILL：成了 %d 个，等您点头 %d 个，没成 %d 个。'
                     % (len(rows), len(done), len(pending), len(failed)))
        if done:
            lines.append('做完的：' + '、'.join(row.get('name') or row['skill'] for row in done))
        if page:
            lines.append('要您回页面：' + '、'.join('%s（%s）' % (row.get('name') or row['skill'],
                                                    row.get('pageTitle') or row.get('page') or '页面上')
                                                for row in page))
        if need:
            lines.append('还缺您手上的东西：' + '、'.join(row.get('name') or row['skill'] for row in need)
                         + '（' + (need[0].get('detail') or '') + '）')
        if pending:
            lines.append('等您点头：' + '、'.join(row.get('name') or row['skill'] for row in pending))
        if failed:
            lines.append('没成的：' + '、'.join(row.get('name') or row['skill'] for row in failed))
        if run.get('problems'):
            lines.append('依赖有点绕：' + '；'.join(run['problems']))
        if run.get('errors'):
            lines.append('还有几句要说：' + '；'.join(run['errors'])[:200])
        return '\n'.join(lines)


def default_orchestrator(program=None, bus=None, errors=None, project=None, router=None, clock=time.time):
    """进程里共用的一套编排器（注册表是单例，预算挂在本项目上）。"""
    # 第 44 期：额度取「设置 → 预算」那一份（配置/宠物/配置.json），不写死模块默认值。
    budget = skill_budget.for_project(project, program=program, clock=clock)
    return Orchestrator(registry=skill_registry.default_registry(program), budget=budget,
                        router=router, bus=bus, errors=errors, clock=clock, project=project)
