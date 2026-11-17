"""Asset image batch executor shared by the window and the Skill subprocess.

This module intentionally has no Tk dependency.  The batch window owns user
settings and presentation; an external Agent process must only depend on this
execution boundary.
"""
import time
from pathlib import Path

from agent.core import read
from domain.asset_batch_service import KINDS, asset_prompt, image_ready, register_image
from domain.asset_batch_state_service import read_ledger, save_ledger
from infra.comfy_service import Comfy, ComfyGenerationFailed, ComfySubmissionUncertain


class AssetSubmissionUncertain(ValueError):
    """A submit response cannot be verified, so never submit it a second time."""


def _resumable_record(record):
    try:
        info = read(Path(record))
    except (OSError, ValueError):
        return False
    return isinstance(info, dict) and bool(info.get('prompt_id') or info.get('client_id') or info.get('state') == 'downloaded')


def eligible_items(base, items, requires_asset, image_ready_fn=image_ready):
    """筛出应独立生成且尚无可用图片的资产；不访问 Comfy 或台账。"""
    return [(aid, asset) for aid, asset in items
            if requires_asset(aid, asset) and not image_ready_fn(base, aid)]


def validation_errors(items, issues):
    """汇总待生成资产的结构化提示词/素材缺失项。"""
    return [aid + '：' + '、'.join(errors) for aid, asset in items
            if (errors := issues(aid, asset))]


def generation_settings(options):
    """返回用于断点恢复一致性比较的稳定生成配置快照。"""
    return {key: options.get(key, '') for key in ('backend', 'aspect_ratio', 'quality', 'workflow', 'model', 'node', 'field')}


def wait_for_comfy(client, stop, timeout=90, clock=time.monotonic):
    """等待 ComfyUI 就绪；停止信号优先结束重试。"""
    deadline = clock() + timeout
    while True:
        try:
            client.request('/system_stats')
            return True
        except Exception:
            if clock() > deadline:
                raise ValueError('ComfyUI未就绪，请检查地址和启动状态')
            if stop.wait(1):
                return False


def collect_result(client, project, record, timeout=3600, clock=time.monotonic, sleep=time.sleep):
    """轮询已提交任务，直到获得文件列表或达到接续超时。"""
    deadline = clock() + timeout
    while True:
        files = client.collect(project, record)
        if isinstance(files, list):
            return files
        if clock() > deadline:
            raise ValueError('等待超时，保留任务编号，下次可继续获取')
        sleep(2)


def resume_record(aid, job, prompt, url, references, generation, cloud, resumable=_resumable_record):
    """校验并返回可接续的旧任务记录；未确认提交禁止再次提交。"""
    if job.get('record') and job.get('state') not in ('imported', 'failed') and resumable(job['record']):
        if job.get('prompt') != prompt or job.get('url') != url or job.get('references', []) != references:
            raise ValueError('存在不同提示词、参考图或地址的未完成任务，请先核实旧任务')
        if job.get('generation') != generation and (cloud or job.get('generation')):
            raise ValueError('此资产已有其他模型或工作流的未完成任务，请先处理旧任务')
        return Path(job['record'])
    if job.get('state') == 'submitting':
        raise AssetSubmissionUncertain(aid + ' 上次提交结果无法确认：没有可接续的任务编号，已跳过，未重复提交')
    return None


def _record_failure(project, state, aid, exc, publish_ledger):
    """把单个资产的失败写回台账：提交不确定的保留可续取状态，确定失败的标为 failed。"""
    if aid not in state: return
    state[aid]['error'] = str(exc)
    if isinstance(exc, AssetSubmissionUncertain): pass
    elif isinstance(exc, ComfySubmissionUncertain):
        state[aid]['state'] = 'submitting'
        if getattr(exc, 'record', ''): state[aid]['record'] = str(exc.record)
    elif isinstance(exc, ComfyGenerationFailed) or state[aid].get('state') == 'submitting' and isinstance(exc, ValueError): state[aid]['state'] = 'failed'
    save_ledger(project, state, publish=publish_ledger)


def run_batch(project, base, items, options, events, stop, client_factory=Comfy):
    """Generate and register one image per eligible asset without UI access."""
    from infra.cloud_assets import LOCAL, MODELS, validate as validate_cloud, graph as cloud_graph, get_key
    from contract.prop_assets import requires_asset
    from stage_execution_service import asset_batch_gateway, prepare_asset_write
    base = prepare_asset_write(project, base)
    gateway = asset_batch_gateway()
    publish_ledger = gateway['publish_json']
    items = eligible_items(base, items, requires_asset)
    if not items:
        return '没有需要独立生成的资产；普通道具随镜头画面生成。'
    from infra.asset_prompt_rules import issues
    from asset_reference_images import snapshot, resolve
    missing = validation_errors(items, issues)
    if missing:
        raise ValueError('结构化资产清单尚未补齐：\n' + '\n'.join(missing))
    items = [(aid, snapshot(base, asset)) for aid, asset in items]
    cloud = options.get('backend', LOCAL) in MODELS
    generation = generation_settings(options)
    state = read_ledger(project)
    if cloud:
        from infra.comfy_service import cloud_price_model
        from infra.pet_llm import RequestLedger
        count = 0
        for aid, asset in items:
            try:
                old = resume_record(aid, state.get(aid, {}), asset_prompt(asset, KINDS[aid.split('_')[0]][0]),
                                    options['url'], asset['_reference_signature'], generation, cloud)
            except ValueError:
                continue  # 原有任务冲突或待核实：执行循环报告，不计作新增付费请求。
            if not old:count += 1
        if count:
            from contract.asset_contract import resolve_aspect_ratio
            inputs = {'model': options['backend'], 'quality': options.get('quality', 'medium'),
                      'aspect_ratio': resolve_aspect_ratio(options.get('workflow_lock'), options.get('aspect_ratio'), '1:1')}
            model = cloud_price_model({'30': {'class_type': 'DramaCloudImage', 'inputs': inputs}})
            events.put(RequestLedger(project).preview_text(model, 'images', {'images': count}))
    client = client_factory(options['url'])
    if not wait_for_comfy(client, stop):
        return '已停止'
    if cloud: validate_cloud(client, options, items)
    if not cloud and any(not asset.get('reference_images') for _, asset in items) and not options['workflow'] and not options['model']:
        raise ValueError('请先检测并选择基础模型')
    reference_cfg = client.reference_config() if not cloud and any(asset.get('reference_images') for _, asset in items) else None
    success = failed = 0
    for index, (aid, asset) in enumerate(items, 1):
        if stop.is_set(): break
        if image_ready(base, aid): events.put(aid + '：图片已就绪，跳过'); continue
        kind = KINDS[aid.split('_')[0]][0]; events.put(f'{index}/{len(items)} · {aid} {asset.get("name", aid)}：生成中')
        try:
            prompt = asset_prompt(asset, kind); job = state.get(aid, {})
            record = resume_record(aid, job, prompt, options['url'], asset['_reference_signature'], generation, cloud)
            if record:
                if job.get('state') == 'submitting': state[aid].update(state='queued', note='找到上次已提交的任务，接续取回'); save_ledger(project, state, publish=publish_ledger)
            else:
                images = resolve(base, asset)
                workflow = cloud_graph(client, aid, asset, prompt, images, options) if cloud else (client.reference_graph(prompt, images, reference_cfg) if images else None)
                from contract.platform_tools import execution_metadata
                state[aid] = {'state':'submitting','prompt':prompt,'url':options['url'],'asset':asset,'references':asset['_reference_signature'],'generation':generation,
                              'execution': execution_metadata('assets', aid)}; save_ledger(project, state, publish=publish_ledger)
                record = client.submit_graph(project, kind, prompt, workflow, extra_data={'api_key_comfy_org':get_key()}) if cloud else (client.submit_graph(project, kind, prompt, workflow) if images else client.submit(project, kind, prompt, options['model'], options['workflow'] or None, options['node'], options['field']))
                state[aid].update(state='queued', record=str(record)); save_ledger(project, state, publish=publish_ledger)
            files = collect_result(client, project, record)
            if len(files) != 1: raise ValueError('工作流输出了多张图片，已保留，请手动选择登记；批量流程要求每个资产只输出一张图')
            result = register_image(base, aid, asset, files[0], gateway=gateway); state[aid].update(state='imported', result=result); save_ledger(project, state, publish=publish_ledger)
            success += 1; events.put(aid + '：' + result)
        except Exception as exc:
            failed += 1; events.put(aid + '：' + str(exc))
            _record_failure(project, state, aid, exc, publish_ledger)
    return f'批量完成：成功 {success}，未完成 {failed}' + ('；已停止后续资产' if stop.is_set() else '')
