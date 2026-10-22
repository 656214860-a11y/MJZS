"""压平 workflow_engines.run_background：HEAD 旧实现原样内嵌，与抽出 _run_claude_json 后的新实现
按 Claude/codex 引擎、退出码、响应内容逐例对照报告文件、响应文件、异常与 _run 调用。"""
import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import workflow_engines as we

LEGACY = "def run_background(config,project,output,report,logfile,prompt):\n    prompt=ensure_request_context(prompt, config.get('stage', '当前阶段'))\n    slot=reserve_stage_process_slot(project, config.get('stage', '当前阶段'))\n    try:\n        if config['engine']=='client-cli':\n            prompt_file=Path(report).with_suffix('.client-prompt.md')\n            save_text(prompt_file,prompt)\n            args=background_command(config,project,output,report,prompt_file,prompt=prompt)\n            response=Path(report).with_suffix('.client-response.txt')\n            response_temp=temporary_path(response)\n            item=_client_profile(config)\n            try:\n                with response_temp.open('w',encoding='utf-8') as out, Path(logfile).open('w',encoding='utf-8') as log:\n                    returncode=_run(args,project,client_profiles.stdin_text(item,prompt),out,log)\n                text=response_temp.read_text(encoding='utf-8-sig').strip()\n                replace(response_temp,response)\n                if returncode:\n                    raise ValueError('%s 执行失败（退出码 %s）；任务文件已保留，请查看运行日志或改用交互式窗口'\n                                     % (item['display'],returncode))\n                if not text:\n                    raise ValueError('%s 未返回制作报告正文；请查看运行日志或改用交互式窗口' % item['display'])\n                save_text(Path(report),text)\n            finally:\n                if response_temp.exists():remove_temporary_file(response_temp)\n            return None\n        if config['engine']=='qwen':\n            from qwen_adapter import run_background as run_qwen\n            return run_qwen(config,project,output,report,logfile,prompt)\n        if config['engine']=='opencode':\n            return _run_opencode(config,project,output,report,logfile,prompt)\n        args=background_command(config,project,output,report)\n        with Path(logfile).open('w',encoding='utf-8') as log:\n            if config['engine']=='codex':\n                returncode=_run(args,project,prompt,log,log)\n            else:\n                response=Path(report).with_suffix('.response.json')\n                response_temp=temporary_path(response)\n                try:\n                    with response_temp.open('w',encoding='utf-8') as out:\n                        returncode=_run(args,project,prompt,out,log)\n                    if returncode==0:\n                        result=json.loads(response_temp.read_text(encoding='utf-8-sig'))\n                        replace(response_temp,response)\n                        report_text = str(result.get('result', '')).strip()\n                        if not report_text:\n                            raise ValueError('Claude 未返回制作报告正文，请查看响应记录')\n                        save_text(Path(report), report_text)\n                        if result.get('is_error') or result.get('permission_denials'):\n                            raise ValueError('Claude 未完成任务或所需操作未获授权，请查看制作报告及响应记录')\n                finally:\n                    if response_temp.exists():remove_temporary_file(response_temp)\n        if returncode:raise ValueError(ENGINES[config['engine']]+' 执行失败，请查看运行日志（安装版本、登录、额度或权限）')\n    finally:\n        release_process_slot(slot)\n"

CASES = [('claude', 0, {'result': '报告'}), ('claude', 0, {'result': ''}), ('claude', 0, {'result': '报', 'is_error': True}),
         ('claude', 0, {'result': '报', 'permission_denials': [1]}), ('claude', 2, {'result': '报'}),
         ('claude', 0, None), ('codex', 0, None), ('codex', 1, None)]


def _drive(get_fn, engine, code, payload):
    calls = []
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'r.md'
        def fake_run(args, project, prompt, out, log, timeout=None):
            calls.append((args, project, prompt, out is log))
            if out is not log:
                out.write(json.dumps(payload) if payload is not None else '{bad')
            return code
        patches = dict(_run=fake_run, background_command=lambda *a, **k: ['cmd'],
                       reserve_stage_process_slot=lambda *a: 'slot', release_process_slot=lambda s: calls.append(('rel', s)),
                       ensure_request_context=lambda p, s: p)
        with contextlib.ExitStack() as stack:
            fn = get_fn(stack, patches)
            try:
                fn({'engine': engine}, 'P', 'O', str(report), str(Path(tmp) / 'l.log'), '提示')
                err = None
            except Exception as exc:
                err = (type(exc).__name__, str(exc))
        files = sorted((p.name, p.read_text(encoding='utf-8')) for p in Path(tmp).iterdir() if p.name != 'l.log')
    return calls, err, files


def _legacy(stack, patches):
    ns = dict(vars(we))
    exec(LEGACY, ns)
    ns.update(patches)
    return ns['run_background']


def _current(stack, patches):
    stack.enter_context(mock.patch.multiple(we, **patches))
    return we.run_background


class RunBackgroundEquivalenceTest(unittest.TestCase):
    def test_legacy_self_consistent(self):
        for case in CASES:
            with self.subTest(case=case):
                self.assertEqual(_drive(_legacy, *case), _drive(_legacy, *case))

    def test_matches_legacy(self):
        for case in CASES:
            with self.subTest(case=case):
                self.assertEqual(_drive(_current, *case), _drive(_legacy, *case))


if __name__ == '__main__':
    unittest.main()
