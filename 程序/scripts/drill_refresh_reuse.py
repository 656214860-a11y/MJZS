r"""Manual drill: renew the local account session once through AccountController.renew.

Prints only the result code, never tokens. On success the new refresh token is written back to
``private\账户\session.json`` exactly as the app does; on a dead session the session is cleared.
Used to rehearse "reused old refresh token -> all sessions revoked" against the test server.

Run with the bundled interpreter:
``D:\漫剧制作助手\运行环境\Python\python.exe -B scripts\drill_refresh_reuse.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import account_store  # noqa: E402
from account_controller import AccountController  # noqa: E402


def main():
    print('会话文件：%s' % account_store.session_path())
    if not account_store.load().get('refresh_token'):
        print('没有刷新令牌：请先在助手里登录，或先放回备份文件')
        return 2
    out = {}
    ctrl = AccountController(submit=lambda work, done, label: done(work()))
    ctrl.renew(done=lambda result: out.setdefault('r', result))
    result = out['r']
    if getattr(result, 'ok', False):
        print('续签成功：服务端发了新刷新令牌，已写回会话文件')
        return 0
    code = (getattr(result, 'data', None) or {}).get('code', '?')
    print('续签失败：code=%s；本机会话还在=%s' % (code, bool(account_store.load().get('refresh_token'))))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
