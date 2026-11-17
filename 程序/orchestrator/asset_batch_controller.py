"""无 Tk 的资产批量窗口状态、检测与启动决策。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from domain.asset_batch_selection_service import initial_excluded, pending_rows, selectable_rows, select_category


WORKFLOW_MODEL = '使用 API 工作流内模型'


@dataclass(frozen=True)
class BatchStartDecision:
    items: list[tuple[str, dict]]
    options: dict[str, str]
    uncertain_ids: list[str]


class AssetBatchController:
    """资产批量页的可测试表单状态和编排判断。"""

    def __init__(self, project, base, sources, scope, engine, selected_ids, saved, sync_plan):
        self.project = Path(project)
        self.base, self.sources, self.scope = base, sources, scope
        self.engine, self.selected_ids = engine, selected_ids
        self.saved = dict(saved) if isinstance(saved, dict) else {}
        self._sync_plan = sync_plan
        self.rows = self._sync_plan(self.project, self.base, self.sources, scope=self.scope)
        self.excluded = initial_excluded(self.rows, engine, selected_ids)

    def category_defaults(self, kinds, workflow_asset_kind='all'):
        return {prefix: (workflow_asset_kind in ('all', value[0]) or self.selected_ids is not None)
                if self.engine == 'workflow' else self.saved.get(prefix, prefix != 'PROP')
                for prefix, value in kinds.items()}

    def form_defaults(self, workflow_default, current_model):
        fields = {'url': self.saved.get('url', 'http://127.0.0.1:8189'), 'model': self.saved.get('model', ''),
                  'workflow': self.saved.get('workflow', workflow_default), 'node': self.saved.get('node', '4'),
                  'field': self.saved.get('field', 'text')}
        if not str(fields['model']).strip() and str(fields['workflow']).strip():
            fields['model'] = WORKFLOW_MODEL
        return fields, self.saved.get('aspect_ratio', '1:1'), self.saved.get('quality', 'medium'), current_model

    def toggle_category(self, prefix, checked):
        if checked:
            self.excluded = select_category(self.rows, self.excluded, prefix)

    def available(self, enabled):
        return selectable_rows(self.rows, enabled)

    def pending(self, enabled):
        return pending_rows(self.rows, enabled, self.excluded)

    def reload_rows(self):
        self.rows = self._sync_plan(self.project, self.base, self.sources, scope=self.scope)
        return self.rows

    def options(self, fields, backend, aspect_ratio, quality):
        options = {key: str(value).strip() for key, value in fields.items()}
        if options.get('model') == WORKFLOW_MODEL:
            options['model'] = ''
        options.update(backend=backend, aspect_ratio=aspect_ratio, quality=quality)
        return options

    def detect(self, fetch_models, url, deleted, identity, timeout=90, clock=time.monotonic, sleep=time.sleep):
        deadline = clock() + timeout
        while True:
            try:
                return [model for model in fetch_models() if identity(url, model) not in deleted]
            except Exception:
                if clock() > deadline:
                    raise ValueError('无法连接到 ' + url + '。请确认 ComfyUI 已完成启动，并检查实际端口；若使用自定义 API 工作流，可保存工作流后直接生成。')
                sleep(1)

    def start_decision(self, context_matches, enabled, issues, options, backend, local, uncertain_ids):
        if not context_matches:
            raise ValueError('分镜或资产范围已切换，请重新打开批量资产窗口')
        self.reload_rows()
        items = self.pending(enabled)
        if not items:
            raise ValueError('请至少勾选一项待生成资产')
        missing = [aid + '：' + '、'.join(errors) for aid, asset in items if (errors := issues(aid, asset))]
        if missing:
            raise ValueError('请先在第1／2步补齐资产清单：\n' + '\n'.join(missing))
        if backend == local and any(not asset.get('reference_images') for _, asset in items) and not options['workflow'] and not options['model']:
            raise ValueError('请先启动并检测，选择模型；或选择API工作流')
        selected = {aid for aid, _ in items}
        return BatchStartDecision(items, options, [aid for aid in uncertain_ids if aid in selected])
