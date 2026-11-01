# R1424 结果：自动搜寻识别商店版 Claude Desktop

- 轮次类型：§3.2 修复轮。范围：`workflow_settings.py`、`tests/test_claude_program_detection.py`。无对应维护队列 ID；领号方式同 R1423（临时忽略用户未跟踪的 `.claude/`、`projects.json`）。

## 根因

`find_program` 的 `claude-desktop-app` 分支只检查旧安装器路径（`%LOCALAPPDATA%\AnthropicClaude`、`Programs\Claude`）。商店版装在 `C:\Program Files\WindowsApps\Claude_<版本>_x64__<发布者>\app\Claude.exe`，目录不可列举，因此模型管理「自动搜寻」报未找到。

## 修改

- 新增 `workflow_settings.store_package_program(package, relative)`：读取 HKCU 已装包清单（与 `current_store_program` 共用 `_STORE_PACKAGES_KEY`、`platform_tools.windows_registry`），按版本从新到旧取 `PackageRootFolder`（缺值时回退 `%ProgramFiles%\WindowsApps\<包名>`），返回首个存在的程序。
- `find_program`：旧安装器路径优先不变；都不存在时再查商店包 `Claude` 的 `app\Claude.exe`；仍找不到保持原错误文案。
- 不改模型池、路由与用户配置。

## 测试

- 新增 `StoreDesktopDetectionTests` 3 项：商店版新版本优先、新版缺失回退旧版；注册表无根目录值回退 Program Files；无注册表保持「未找到」。
- 实测环境：远端 Linux 源码副本（Python 3.12.13，非随附解释器）。`test_claude_program_detection` 8 项中 7 通过；唯一失败 `test_stale_store_version_path_follows_installed_package` 依赖 `os.name == 'nt'`，未改代码上同样失败。`ModelPoolTests` 唯一失败与 R1423 记录相同。架构抽样（layers、平台进程边界、workflow_settings JSON、token、统一棘轮、覆盖率、密钥审计）均通过。
- 未运行：随附解释器冒烟、完整架构、全量；1424−1420=4<5，未命中 §5。

## 自审

验收满足；仅改授权文件；本轮实测与未运行项已区分；无新依赖。同类问题：Codex 桌面已有自身路径逻辑，未改。

提交：已本地提交（`R1424:`，未推送）；hooks 因 CRLF 无法在 Linux 启动，已去 CR 手动执行 pre-commit／commit-msg 均通过后 `--no-verify` 提交；凭据扫描 0 命中。
