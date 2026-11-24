# tasks_round_4323_result — FIX-AUD-CERT-WIRE 证书到期告警接线
<!-- round-evidence: {"commit_base": "493479834", "credential_hits": 0, "evidence_sha256": "f2c7093e1960eb2c", "exit": 0, "failed": 0, "passed": 83, "round": 4323, "tests": "run_selftests.py -k account_page account_client"} -->

## 三问

- 本轮类型：§3.2 修复轮（缺陷：FIX-AUD-CERT-EXPIRY 提供的 `domain/account_client.pinned_cert_warning()` 在会员账户页无调用方，用户看不到告警）。
- 测试跑了吗、基线过了吗：跑了卡面两条验收命令，全绿。定向 `-k account_page account_client` 83 条（改前 81 + 新增 2）退出码 0；`smoke_test.py --architecture` 702 条退出码 0。默认冒烟基线本卡未跑（卡面未列），记「未运行」。
- 欠账少了吗：少了——告警 API 从「有实现无界面」变为账号页可见；无新增欠账。

## 缺陷复现方式

`domain/account_client.py:116` 的 `pinned_cert_warning()` 全仓库仅 `scripts/release_gate.py:207` 调用；`ui/desktop_account_page.py` 的 `account_page()` 不触达它，临期（到期前 60 天内）与已过期告警用户在界面上永远看不到。用 `unittest.mock.patch.object(account_client,'pinned_cert_warning',return_value=告警文案)` 后强制重画账号页即可复现：页面文案集合里没有「证书到期提醒」。

## 改前红（改产品前，同一条定向命令）

共 83 条用例，1 红：

```
===== test_pinned_cert_warning_shows_alert_card_when_expiring =====
AssertionError: '证书到期提醒' not found in ['当前状态：未登录', '新账号免费试用 3 天；「剧本准备」「剧本结构」永久免费。', '注册表时钟基线不可用，会员授权暂使用本机会话基线。', '登录', '注册', ...]
```

退出码 1；失败原因与卡面缺陷一致（界面无告警卡）。另一新用例 `test_pinned_cert_warning_empty_renders_no_card` 改前即绿（空串本来就不该有卡），作为回归护栏保留。

## 改动（文件:行号）

- `程序/ui/desktop_account_page.py:186-193`：新增 `AccountPageMixin._account_cert_warning_card()`——调 `account_client.pinned_cert_warning()`，空串/空白直接 return（不建控件、不占位）；非空用 `Card(self.content)` 渲染「证书到期提醒」卡，标题与正文均用既有 `style='Warn.TLabel'`（`ui_theme.py:45` 已注册），正文 `wraplength=TEXT_DESC['wraplength']`、`justify='left'`。不写 `font=`/`foreground=`：`tests/architecture/test_text_component_boundary.py` 对本文件棘轮登记 4 处 = 实测 4 处，新增 `font=` 会破门禁。
- `程序/ui/desktop_account_page.py:257`：`account_page()` 紧跟 `self._account_update_card()` 调 `self._account_cert_warning_card()`，未登录与已登录视图都能看到，不阻断状态卡、登录表单或授权展示。
- `程序/tests/test_account_page.py:16`：新增 `import account_client`（顶层门面即 `domain.account_client` 本体，patch 面一致）。
- `程序/tests/test_account_page.py:406-426`：新增两用例——非空文案出现「证书到期提醒」卡＋完整文案＋登录表单仍在；空串与 `'   '` 均不渲染且 `self.content` 顶层子控件数不变。

## 改后命令输出（尾部原文）

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k account_page account_client`（退出码 0）：

```
共 83 条用例，20.6 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：21.5 秒

ALL TESTS PASSED
```

`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：

```
----------------------------------------------------------------------
Ran 702 tests in 301.487s

✅ 架构治理测试：tests/architecture
OK
```

## 未验证项

- 默认冒烟 `python smoke_test.py`：本卡卡面未列，未运行。
- 真机窗口肉眼效果未看：断言基于隐藏桌面真 Tk 控件文本与子控件计数；`Warn.TLabel` 颜色为既有注册样式。
- 真实临期态未验证：今天距证书到期日 2027-10-22 约 332 天，真实调用返回空串；非空分支经 patch 覆盖，`pinned_cert_warning` 自身的到期/已过期文案由 `test_account_client.test_pinned_cert_warns_within_sixty_days` 覆盖。

## 卡外发现（只记录）

- 无。
