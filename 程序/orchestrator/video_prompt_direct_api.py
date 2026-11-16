# -*- coding: utf-8 -*-
"""视频提示词渲染选 API 模型时的直连执行器（REQ-S10-50，DES-S10-50）。

骨架复用 storyboard_direct_api（模型判定、_Batch、_ask、Job／launch、取消登记）；本模块只写提示词专属部分：
一次请求让模型只回 {shot_id, source_signature, video_prompt} 的 JSON，程序校验（镜头号、校验值、非空、1500 字）
通过才用 JSON 序列化器写入 video_prompts/<镜头>.json，不合格带问题清单重试一次，仍不合格不落盘。
导入与保存仍由视频页 PromptResults 轮询经 publish_video_prompt 完成，这里不另立发布器。
"""
import json
import re
import time
from pathlib import Path

import orchestrator.storyboard_direct_api as _base
from orchestrator.storyboard_direct_api import direct_model  # noqa: F401  同一份判定，不另立第二套

MAX_CHARS = 1500
_SIGNATURE = re.compile(r'[a-f0-9]{64}')


def video_prompt_rules():
    return ('【直连输出格式】只回复一个 JSON 对象，不要任何解释或 Markdown 围栏：\n'
            '{"shot_id": "...", "source_signature": "...", "video_prompt": "..."}\n'
            'shot_id 与 source_signature 必须原样复制输入；video_prompt 为 1 至 %d 字的图生视频提示词，'
            '含资产编号、动作起止、运镜、说话人及台词（如有）、环境声，严格使用输入里的 duration；'
            '只整理文本，不调用视频 API，不编造台词，不改镜头与资产。' % MAX_CHARS)


def validate_reply(reply, context):
    """解析并校验模型回复；返回 video_prompt 文本，不合格抛 ValueError（多条问题换行连接）。"""
    try:
        record = _base._extract_json(reply)
    except ValueError as error:
        raise ValueError('回复不是有效的 JSON：%s' % error)
    problems = []
    if record.get('shot_id') != context['shot_id']:
        problems.append('镜头号 shot_id 必须是 %s，实际是 %s' % (context['shot_id'], record.get('shot_id')))
    signature = str(record.get('source_signature') or '')
    if not _SIGNATURE.fullmatch(signature) or signature != context['source_signature']:
        problems.append('校验值 source_signature 必须原样复制输入')
    text = record.get('video_prompt')
    if not isinstance(text, str) or not text.strip():
        problems.append('video_prompt 是空的')
    elif len(text.strip()) > MAX_CHARS:
        problems.append('video_prompt 超过 %d 字（当前 %d 字）' % (MAX_CHARS, len(text.strip())))
    if problems:
        raise ValueError('\n'.join(problems))
    return text.strip()


def _messages(context, draft, prior=None):
    head = ('请为下面这个镜头整理图生视频提示词。\n<镜头数据>\n%s\n</镜头数据>'
            % json.dumps(context, ensure_ascii=False, indent=2))
    if draft:
        head += '\n当前编辑框中的提示词（作为待修订素材，结合以上镜头和资产检查）：\n' + json.dumps(draft, ensure_ascii=False)
    messages = [{'role': 'user', 'content': head}]
    if prior:
        messages += [{'role': 'assistant', 'content': prior[0]},
                     {'role': 'user', 'content': '上一版没有通过本地校验，请修正下列全部问题后按原格式重新回复：\n' + prior[1]}]
    return messages


def _publish(batch, context, text, output):
    from agent.core import save, save_bytes
    output = Path(output)
    if output.is_file():
        save_bytes(output.parent / '历史版本' / ('%s_%s.json' % (output.stem, time.strftime('%Y%m%d_%H%M%S'))),
                   output.read_bytes())
    if batch.cancelled():
        raise _base._Stopped()
    save(output, {'shot_id': context['shot_id'], 'source_signature': context['source_signature'], 'video_prompt': text})
    return output


def run_batch(project, config, skill_text, *, direct, report=None, **services):
    """同步处理一个镜头：一次请求（不合格重试一次）。返回 {'ok','paths','error','stopped'}；report(text) 播报结果。"""
    report = report or (lambda _text: None)
    context, output, draft = direct['context'], direct['output'], direct.get('draft', '')
    batch = _base._Batch(project, config, skill_text, profile=('video', video_prompt_rules()), **services)
    try:
        if batch.cancelled():
            raise _base._Stopped()
        prior = None
        for attempt in range(1, _base.MAX_FORMAT_RETRIES + 1):
            reply = _base._ask(batch, _messages(context, draft, prior))
            try:
                text = validate_reply(reply, context)
                break
            except ValueError as error:
                if attempt == _base.MAX_FORMAT_RETRIES:
                    raise ValueError('两次回复都没有通过校验：' + str(error).replace('\n', '；'))
                prior = (reply, str(error))
                if batch.cancelled():
                    raise _base._Stopped()
                time.sleep(_base.FORMAT_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
        path = _publish(batch, context, text, output)
        report('%s 视频提示词已生成，等待导入保存。' % context['shot_id'])
        return {'ok': True, 'paths': [str(path)], 'error': '', 'stopped': False}
    except _base._Stopped:
        return {'ok': False, 'paths': [], 'error': '已停止', 'stopped': True}
    except Exception as error:
        report('%s 视频提示词没有生成：%s' % (context.get('shot_id', ''), error))
        return {'ok': False, 'paths': [], 'error': str(error), 'stopped': False}


class Job(_base.Job):
    thread_name = 'video-prompt-direct'
    busy_text = '正在直连整理视频提示词，请等当前这个镜头完成，或先点「强制停止制作」。'

    def execute(self, **services):
        return [run_batch(self.project, self.config, self.skill_text, **services, **self.kwargs)]


def launch(project, config, skill_text, *, done=None, **kwargs):
    return _base.launch(project, config, skill_text, done=done, job_class=Job, **kwargs)
