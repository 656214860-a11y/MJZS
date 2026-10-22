# R1844 修复轮：恢复被误删的启动动画

## 问题
软件启动时没有启动画面。

## 根因
R1788（`9e9dc3a8`）按“全仓零引用”删除了 `ui_widgets.Splash` 及 13 个 `SPLASH_*` 令牌。唯一调用方是根目录 `启动漫剧制作助手.pyw`，不在当时的扫描范围；启动器又用 `try/except Exception` 包住 `from ui_widgets import Splash`，ImportError 被吞，直接 `reveal()`，动画静默消失。

## 改动
- `ui_widgets.py`、`ui_tokens.py`、`tests/test_app_metadata.py`：对 R1788 中这三处做反向补丁，原样恢复 `Splash`、`SPLASH_*` 和 `DISPLAY_SOURCES` 登记（断言未动）。
- 新增 `tests/test_launcher_imports.py`：解析两个 `.pyw` 启动器，凡 `from <程序模块> import <名>` 的名都必须存在；先红：在 R1843 主干上 `ui_widgets.Splash` 不存在，该用例必红。

## 验证（本轮实跑）
- `tests.test_launcher_imports` + `tests.test_app_metadata`：7 项 OK。
- `smoke_test.py`：通过。
- 架构门禁（隐藏桌面）：376 项，4 红，均与本轮无关：3 条是 R1842 新增 `script_structure_edit_controller` 未登记覆盖率基线／L2 审计清单；1 条“欠一次完整安全全量”由后台补跑。
- 未在真实界面目视启动动画，待用户复验。
