r"""界面截图基线（手动工具，不进全量门禁）：抓一扇窗的像素存成 PNG，与基线比较。

为什么不进门禁：像素受字体、DPI、系统主题影响，放进并行全量会随机变红。所以做成按需命令，
换机器或改界面后先 ``--update`` 重拍基线，再用 ``--check`` 看改动前后差了多少。
零第三方依赖：ctypes 调 GDI 抓屏，zlib 手写 PNG。目前覆盖「运行状况」弹窗（固定样例数据）。

    python.exe -B scripts\ui_snapshot.py --check     # 与基线比较（缺基线则提示先 --update）
    python.exe -B scripts\ui_snapshot.py --update    # 重拍并覆盖基线
"""
from __future__ import annotations

import argparse
import ctypes
import struct
import sys
import zlib
from ctypes import wintypes
from pathlib import Path
from ui_tokens import TEXT_ROWS

PROGRAM = Path(__file__).resolve().parents[1]
BASELINES = PROGRAM / 'tests' / 'ui_baselines'
sys.path.insert(0, str(PROGRAM))
TOLERANCE = 2.0  # 平均每通道绝对差上限（0–255）


def write_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    rows = b''.join(b'\x00' + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def read_png(path: Path):
    data = path.read_bytes()
    pos, idat, size = 8, b'', None
    while pos < len(data):
        length, tag = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if tag == b'IHDR':
            size = struct.unpack('>II', body[:8])
        elif tag == b'IDAT':
            idat += body
        pos += 12 + length
    width, height = size
    raw = zlib.decompress(idat)
    stride = width * 3
    return width, height, b''.join(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)] for y in range(height))


def mean_abs_diff(a: bytes, b: bytes) -> float:
    if len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / max(1, len(a))


def capture_window(hwnd: int):
    """抓窗口外框的像素（PrintWindow，窗口被遮挡也能取）；返回 (宽, 高, RGB 字节)。"""
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bitmap = gdi32.CreateCompatibleBitmap(hdc, width, height)
    gdi32.SelectObject(mem, bitmap)
    user32.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT
    header = struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 24, 0, 0, 0, 0, 0, 0)
    stride = (width * 3 + 3) // 4 * 4
    buffer = ctypes.create_string_buffer(stride * height)
    gdi32.GetDIBits(mem, bitmap, 0, height, buffer, header, 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    raw = buffer.raw
    out = bytearray()
    for y in range(height):
        row = raw[y * stride:y * stride + width * 3]
        out += b''.join(row[x * 3 + 2:x * 3 + 3] + row[x * 3 + 1:x * 3 + 2] + row[x * 3:x * 3 + 1] for x in range(width))
    return width, height, bytes(out)


SAMPLE_SNAPSHOT = {
    'last_task': {'ticket': 3, 'state': 'succeeded'},
    'queued': ['示例排队任务'],
    'task_history': [{'ticket': 2, 'state': 'failed', 'label': '示例任务', 'elapsed_s': 1.5},
                     {'ticket': 3, 'state': 'succeeded', 'label': '导出', 'elapsed_s': 0.4}],
    'timings': {'page.show': {'count': 4, 'total_ms': 600.0, 'max_ms': 300.0, 'slow': 0}},
    'counters': {'model.http.ok': 5, 'model.http.network': 1},
    'swallowed': ['12:00:00 demo.py:1 KeyError: 示例'],
    'degradations': [],
}


def shoot_runtime_dialog():
    import tkinter as tk
    import task_center_service
    from ui_widgets import BaseDialog, TextArea
    root = tk.Tk()
    root.geometry('+40+40')
    try:
        dialog = BaseDialog(root, '运行状况', geometry='640x520+60+60', minsize=(420, 320), modal=False)
        text = TextArea(dialog.content, wrap='word', height=TEXT_ROWS['4xl'])
        text.pack(fill='both', expand=True)
        text.insert('1.0', '\n'.join(task_center_service.format_lines(SAMPLE_SNAPSHOT)))
        text.set_readonly(True)
        dialog.add_action('关闭', dialog.close, primary=True)
        dialog.update()
        return capture_window(int(dialog.wm_frame(), 16))
    finally:
        root.destroy()


SHOTS = {'runtime_dialog': shoot_runtime_dialog}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--update', action='store_true')
    args = parser.parse_args(argv)
    status = 0
    for name, shoot in SHOTS.items():
        width, height, rgb = shoot()
        target = BASELINES / (name + '.png')
        if args.update or not target.is_file():
            if args.check:
                print(f'[截图基线] {name}: 缺基线，请先 --update')
                status = 1
                continue
            write_png(target, width, height, rgb)
            print(f'[截图基线] {name}: 已写入 {target.name}（{width}×{height}）')
            continue
        bw, bh, base = read_png(target)
        diff = mean_abs_diff(base, rgb) if (bw, bh) == (width, height) else 255.0
        ok = diff <= TOLERANCE
        print(f'[截图基线] {name}: {"一致" if ok else "有差异"}（基线 {bw}×{bh}，当前 {width}×{height}，平均差 {diff:.2f}）')
        status |= 0 if ok else 1
    return status


if __name__ == '__main__':
    raise SystemExit(main())
