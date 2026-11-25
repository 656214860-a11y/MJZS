# -*- coding: utf-8 -*-
"""统一状态栏桥接 Mixin（R3056 收尾）：把 R2989/R3016 加进 Desktop 的桥接与左区段方法
拆到独立 L4 模块，保住 Desktop 类行数棘轮；status_kind 一并迁来，desktop 只保留别名导入。
"""
from __future__ import annotations

import re

from ui.ui_status_bus import Message

STATUS_ERROR_MARKERS=('失败','错误','异常','无法','未能','未完成','未启动','出错','中断','超时','暂缓')
STATUS_RUNNING_MARKERS=('正在','处理中','执行中','生成中','加载中','检测中','排队','请稍候','等待')
# 数量为零的写法（「失败 0 个」「0 个失败」「失败：0」）只报计数，不算错误；分色前先把这些片段抹掉。
_STATUS_ZERO_COUNT=re.compile(r'(?:'+('|'.join(STATUS_ERROR_MARKERS))+r')\s*[:：]?\s*0(?![\d.])|(?<![\d.])0\s*个?\s*(?:'+('|'.join(STATUS_ERROR_MARKERS))+r')')


def status_kind(message):
    """把状态栏文本归为就绪／执行中／失败三类；失败优先于执行中，零计数的失败不算错误。"""
    text='' if message is None else str(message)
    if any(marker in _STATUS_ZERO_COUNT.sub('', text) for marker in STATUS_ERROR_MARKERS):return 'error'
    if any(marker in text for marker in STATUS_RUNNING_MARKERS):return 'running'
    return 'ready'


class StatusBridgeMixin:
    """Desktop 的统一状态栏桥接与左区段管理（R2989 P1／R3016 P2／R3056 拆类）。"""

    def _init_status_bridge(self):
        """桥接私有状态只在本 Mixin 内初始化（共享状态棘轮：单一写者）。"""
        self._status_bridge_active=False
        self._segment_traces={}

    def _bus_to_status(self,event):
        """总线当前消息镜像回旧 StringVar：三虎、忙碌态等既有消费方继续工作。"""
        kind,message,_previous=event
        if kind!='current' or message is None or self._status_bridge_active:return
        self._status_bridge_active=True
        try:self.status.set(message.text)
        finally:self._status_bridge_active=False

    def _status_to_bus(self,*_unused):
        """旧 StringVar 写入桥接进总线（常驻，沿用旧栏「不自动消失」语义）。"""
        if self._status_bridge_active:return
        text=self.status.get()
        kind=status_kind(text)
        level={'error':'error','running':'warning','ready':'info'}[kind]
        self.status_bus.publish(Message.make(level,text,source='status',auto=False))

    def _set_status_quiet(self,text):
        """只更新 StringVar 的既有消费方（三虎、忙碌态、启动验收探针），不桥进右区消息。"""
        self._status_bridge_active=True
        try:self.status.set(text)
        finally:self._status_bridge_active=False

    def set_status_segment(self,key,text,*,tooltip=None):
        """把页面上下文信息写进统一底栏左区常驻段；返回该段标签。"""
        return self.status_bar.set_segment(key,text,tooltip=tooltip)

    def bind_status_segment(self,key,var):
        """把 StringVar 实时绑定为左区常驻段（视频页生成状态等高频更新场景）。"""
        self._unbind_status_segment(key)
        def _sync(*_unused):
            value=str(var.get())
            self.set_status_segment(key,value,tooltip=value)
        trace_id=var.trace_add('write',_sync)
        self._segment_traces[key]=(var,trace_id)
        _sync()

    def _unbind_status_segment(self,key):
        pair=self._segment_traces.pop(key,None)
        if pair is None:return
        var,trace_id=pair
        try:var.trace_remove('write',trace_id)
        except Exception:
            import infra.app_logging as app_logging
            app_logging.swallowed('解除状态段绑定')

    def clear_page_segments(self):
        """换页时清空页面专用段并解除其 StringVar 绑定（page/path/用量指示器为全局常驻）。"""
        for key in ('usage','script_note','storyboard','video_model','video','animatic_note'):
            self.status_bar.clear_segment(key)
            self._unbind_status_segment(key)
