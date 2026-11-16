# -*- coding: utf-8 -*-
"""离线语音识别独立运行时（voice_engine）。

本包只在**独立 ASR Python 环境**中运行（见 ``bootstrap.py`` / ``requirements.txt``），
不进入主程序随附运行时；主程序经 stdio JSON Lines 与 ``offline_asr_server`` 通信。
所有第三方依赖（numpy/onnxruntime/funasr_onnx/jieba/modelscope）均在函数内延迟导入，
保证本包在零依赖解释器下也能被导入做协议级测试。
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
