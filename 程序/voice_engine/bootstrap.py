#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线 ASR 运行环境引导：创建独立 venv 并安装依赖（仅标准库，零第三方依赖）。

用法（Python 3.10–3.12，建议系统 Python 而非随附裁剪运行时；
依赖 numpy<=1.26.4 在 3.13+ 没有预编译轮子，更高版本会直接拒绝）：
  python bootstrap.py [--venv DIR] [--python EXE] [--requirements FILE]

stdout 输出 JSON Lines：{"type":"progress"|"done"|"error", ...}；
退出码：0 成功；2 参数/环境错误；3 依赖安装或导入校验失败。
不引入 get-pip 下载等出站请求——只依赖 venv/ensurepip/pip 本身。
"""

import argparse
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

PROGRAM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VENV = PROGRAM_ROOT / "data" / "voice_asr_venv"
DEFAULT_REQ = Path(__file__).resolve().parent / "requirements.txt"
MIN_PYTHON = (3, 10)
MAX_PYTHON = (3, 12)   # funasr_onnx 依赖 numpy<=1.26.4，无 cp313+ 预编译轮子

EXIT_OK = 0
EXIT_ENV_ERROR = 2
EXIT_INSTALL_ERROR = 3


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def progress(message):
    emit({"type": "progress", "message": message})


def fail(message, code=EXIT_ENV_ERROR):
    emit({"type": "error", "message": message})
    return code


def venv_python(venv_dir) -> str:
    """venv 内解释器路径（Windows: Scripts/python.exe）。"""
    if os.name == "nt":
        return os.path.join(str(venv_dir), "Scripts", "python.exe")
    return os.path.join(str(venv_dir), "bin", "python")


def _run(cmd, timeout, env=None):
    """subprocess.run 统一带 timeout（架构门禁）；UTF-8 容错解码。"""
    return subprocess.run(cmd, capture_output=True,
                          encoding="utf-8", errors="replace",
                          timeout=timeout, env=env)


def _tail(text, limit=5, size=400):
    lines = (text or "").strip().splitlines()
    return "；".join(lines[-limit:])[:size]


def probe_python(exe):
    """返回 (ok, version_str, error_str)。"""
    try:
        proc = _run([exe, "-c",
                     "import sys;print(sys.version.split()[0]);"
                     "print('.'.join(map(str,sys.version_info[:2])))"],
                    timeout=30)
    except Exception as exc:  # noqa: BLE001
        return False, "", "无法执行：%s" % exc
    if proc.returncode != 0:
        return False, "", _tail(proc.stderr or proc.stdout)
    lines = proc.stdout.strip().splitlines()
    version = lines[-1].strip() if lines else ""
    return True, version, ""


def _version_tuple(version):
    try:
        return tuple(int(p) for p in version.split(".")[:2])
    except Exception:  # noqa: BLE001
        return (0, 0)


def ensure_pip(vpy):
    """确保 venv 内有 pip：先试 -m pip，再试 ensurepip。返回错误串或 None。"""
    try:
        proc = _run([vpy, "-m", "pip", "--version"], timeout=60)
        if proc.returncode == 0:
            return None
    except Exception:  # noqa: BLE001 —— pip 缺失属预期分支
        pass
    progress("环境内暂无 pip，尝试 ensurepip 初始化…")
    try:
        proc = _run([vpy, "-m", "ensurepip", "--upgrade"], timeout=300)
    except Exception as exc:  # noqa: BLE001
        return "ensurepip 执行失败：%s" % exc
    if proc.returncode != 0:
        return ("无法初始化 pip（ensurepip 不可用）。请安装完整版 Python %s+，"
                "或用 --python 指定；详情：%s" % (".".join(map(str, MIN_PYTHON)),
                                                _tail(proc.stderr or proc.stdout)))
    try:
        proc = _run([vpy, "-m", "pip", "--version"], timeout=60)
        if proc.returncode == 0:
            return None
    except Exception:  # noqa: BLE001
        pass
    return "pip 初始化后仍不可用"


def create_venv(base_python, venv_dir):
    """创建 venv；with_pip 失败时降级为无 pip 再补 ensurepip。返回错误串或 None。"""
    venv_dir = Path(venv_dir)
    if (venv_dir / "pyvenv.cfg").exists():
        progress("虚拟环境已存在，跳过创建：%s" % venv_dir)
        return None
    progress("正在创建独立 ASR 环境：%s" % venv_dir)
    try:
        venv.EnvBuilder(with_pip=True, symlinks=False).create(str(venv_dir))
        return None
    except Exception as exc:  # noqa: BLE001
        progress("常规创建失败（%s），改用 ensurepip 重试" % str(exc)[:120])
    try:
        venv.EnvBuilder(with_pip=False, symlinks=False).create(str(venv_dir))
    except Exception as exc:  # noqa: BLE001
        return "无法创建 Python 虚拟环境：%s" % exc
    return None


def install_requirements(vpy, req_path):
    """pip install -r；返回错误串或 None。"""
    progress("正在安装离线识别依赖（首次约数百 MB，请耐心等待）…")
    try:
        proc = _run([vpy, "-m", "pip", "install", "-r", str(req_path)], timeout=1800)
    except subprocess.TimeoutExpired:
        return "依赖安装超时（30 分钟），请检查网络后重试"
    except Exception as exc:  # noqa: BLE001
        return "依赖安装失败：%s" % exc
    if proc.returncode != 0:
        return "依赖安装失败：%s" % _tail(proc.stderr or proc.stdout)
    return None


def verify_imports(vpy):
    """校验关键依赖可导入；返回错误串或 None。"""
    try:
        proc = _run([vpy, "-c",
                     "import numpy, onnxruntime, funasr_onnx, jieba, modelscope"],
                    timeout=120)
    except Exception as exc:  # noqa: BLE001
        return "依赖导入校验执行失败：%s" % exc
    if proc.returncode != 0:
        return "依赖安装后导入校验失败：%s" % _tail(proc.stderr or proc.stdout)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="离线 ASR 运行环境引导")
    parser.add_argument("--venv", default=str(DEFAULT_VENV), help="venv 目录")
    parser.add_argument("--python", default=os.environ.get("VOICE_ASR_PYTHON")
                        or sys.executable, help="基座 Python 解释器")
    parser.add_argument("--requirements", default=str(DEFAULT_REQ),
                        help="依赖清单")
    args = parser.parse_args(argv)

    ok, version, err = probe_python(args.python)
    if not ok:
        return fail("基座 Python 不可用（%s）：%s" % (args.python, err))
    if _version_tuple(version) < MIN_PYTHON:
        progress("警告：基座 Python %s 低于建议的 %s，可能缺少依赖轮子"
                 % (version, ".".join(map(str, MIN_PYTHON))))
    if _version_tuple(version) > MAX_PYTHON:
        return fail("基座 Python %s 超出支持范围：离线识别依赖 numpy<=1.26.4 "
                    "仅提供 Python %s–%s 预编译轮子，请用 --python 指定更低版本"
                    % (version, ".".join(map(str, MIN_PYTHON)),
                       ".".join(map(str, MAX_PYTHON))))
    progress("基座 Python %s，正在准备独立环境…" % version)

    err = create_venv(args.python, args.venv)
    if err:
        return fail(err)
    vpy = venv_python(args.venv)
    if not Path(vpy).exists():
        return fail("虚拟环境创建后未找到解释器：%s" % vpy)

    err = ensure_pip(vpy)
    if err:
        return fail(err)

    req = Path(args.requirements)
    if not req.is_file():
        return fail("依赖清单不存在：%s" % req)
    err = install_requirements(vpy, req)
    if err:
        return fail(err, EXIT_INSTALL_ERROR)
    progress("依赖安装完成，正在校验导入…")
    err = verify_imports(vpy)
    if err:
        return fail(err, EXIT_INSTALL_ERROR)

    emit({"type": "done", "venv": str(Path(args.venv)), "venv_python": vpy,
          "python_version": version})
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
