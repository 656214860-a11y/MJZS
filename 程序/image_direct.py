# -*- coding: utf-8 -*-
"""资产／首帧出图选 API 模型时的直连执行器（L3，REQ-S05-50／REQ-S08-52，DES-S05-50）。

image_agent_runner 本来就是确定性出图（Agent 只是命令执行器，没有任何 LLM 调用），
引擎为 qwen 时由程序在后台线程里直接调用 image_agent_runner.execute，不再起 Qwen Code。
作业骨架复用 storyboard_direct_api.Job（线程、取消、项目内唯一登记）；
执行状态.json 由 execute 写 running／complete／failed，线程层再经 asset_batch_lifecycle.fail 兜底，
让既有 watch() 轮询按原语义导入图片。
"""
import storyboard_direct_api as _base


class Job(_base.Job):
    thread_name = 'image-direct'
    busy_text = '正在后台制作图片，请等当前批次完成，或先点「强制停止制作」。'

    def execute(self, **services):
        from image_agent_runner import execute
        manifest = self.kwargs['manifest']
        stop = self.control.stopped
        try:
            execute(self.project, manifest, stop)
        except Exception as error:
            stopped = stop.is_set()
            message = '已强制停止制作，未出图的项可重新提交' if stopped else str(error)
            from asset_batch_lifecycle import fail
            from stage_execution_service import asset_batch_gateway
            fail(manifest, message, gateway=asset_batch_gateway())
            return [{'ok': False, 'stopped': stopped, 'error': message}]
        return [{'ok': True, 'stopped': False, 'error': ''}]


def launch(project, config, *, manifest, done=None):
    return _base.launch(project, config, '', done=done, job_class=Job, manifest=manifest)
