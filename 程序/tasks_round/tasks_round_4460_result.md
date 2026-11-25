# R4460 REL-04B：个人通道 Inno Setup 6 安装脚本、静态守卫与构建入口（功能轮）
<!-- round-evidence: {"commit_base": "1abd6d878", "credential_hits": 0, "evidence_sha256": "22d63a90f69f95e8", "exit": 0, "failed": 0, "passed": 29, "round": 4460, "tests": "run_selftests.py -k installer_script distribution_build"} -->

## 开头三问

1. **本轮类型**：§3.1 功能轮。任务卡 `REL-04B`（车道 `codex/rel-04b`，基准 `1abd6d878`）：交付个人通道 Inno Setup 6 安装脚本、纯静态自检与构建脚本、6 项核心守卫测试（含 1 项扩展守卫，共 7 条用例），并同步规格、发布检查单与结构测试归属。
2. **测试与三个基线**：
   - 默认冒烟 `smoke_test.py`：9/9 通过（含隐藏桌面探针＋8 项检查），退出码 `0`。
   - 定向验收：`run_selftests.py -k installer_script` 7/7 通过（退出码 `0`）；`scripts\installer_build.py --check` 退出码 `0`；`run_selftests.py -k distribution_build` 22/22 通过（退出码 `0`）。
   - 架构门禁 `smoke_test.py --architecture`：提交前实测 707/708 通过，唯一报错为 `tests/architecture/test_structure.py`（因 `structure-baseline.json` 的 `policy_sha256` 未同步且两条新 `scripts/` 文件尚未进入 git 索引）；经需求设计席位批准同步更新 `governance/structure-baseline.json` 中 `policy_sha256` 一行（不放宽任何基线发现数）后，只读复核 `check_structure.py` 确认 0 新增违规，并将在提交后的干净工作树上复跑 `smoke_test.py --architecture` 核验 708/708 全绿。
   - 全量回归 `run_selftests.py --all --safe`：本轮未运行（按 §5 与卡面验收口径，全量欠账以 `full-safe-receipts.json` 为权威）。
3. **欠账是否减少**：无新增欠账，无跳过或弱化既有测试；规格《03 安装、签名与分发》§7 `D-1` 的脚本＋静态自检部分已闭环，实机编译与实机安装升级卸载归用户手动项。

## 建议项标注（建议，待确认）

- **建议①渠道（建议，待确认）**：本卡仅做个人通道（Inno Setup 6 单文件 EXE，规格 §2 已选型）；企业 MSI/WiX（D-2）另立卡，便携 ZIP 维持 `distribution_build.py` 现状。
- **建议②签名（建议，待确认）**：按规格 §3.1 首期不买代码签名证书，`.iss` 中 `SignTool`/`SignedUninstaller` 全部包在 `#ifdef Signed … #endif` 之间（未定义 `Signed` 时整段不编译）；minisign 清单签名归 D-4。

## 改动清单

- `程序/scripts/installer/漫剧制作助手.iss`（新建，UTF-8 BOM）：
  - `[Setup]`：固定 GUID `AppId={{8B4E2C1D-9F3A-4E6B-A7C2-5D1F8E3B9A40}`、`AppName=漫剧制作助手`、`AppVersion={#AppVersion}`、`DefaultDirName={localappdata}\漫剧制作助手`、`PrivilegesRequired=lowest`、`WizardStyle=modern dark`、`Compression=lzma2`、`SolidCompression=yes`、`CloseApplications=yes`、`RestartApplications=no`、`SetupIconFile={#SourceDir}\漫剧制作助手.ico`、`UninstallDisplayIcon={app}\漫剧制作助手.ico`、`OutputBaseFilename=漫剧助手-{#AppVersion}`，`SignTool`/`SignedUninstaller` 包裹在 `#ifdef Signed … #endif` 内。
  - `[Files]`：整目录递归复制 `{#SourceDir}\*`，`Excludes` 覆盖 `.git\*`、`__pycache__\*`、`*.pyc` 与 8 项用户数据/日志/证据模式（`config.json`、`desktop_settings.json`、`projects.json`、`private\*`、`data\*`、`配置\*`、`app.log*`、`tasks_round\evidence\*`），`Flags: ignoreversion recursesubdirs createallsubdirs`；其后单独放回 `{#SourceDir}\程序\data\skill_note_terms_zh.json`（`Flags: ignoreversion`）及两份默认配置种子（`Flags: onlyifdoesntexist`，升级不覆盖用户配置）。
  - `[Icons]` / `[Run]`：桌面＋开始菜单快捷方式通过随附解释器 `{app}\运行环境\Python\pythonw.exe` 启动 `{app}\启动漫剧制作助手.pyw`（`WorkingDir: "{app}"`）；安装完成提供可取消勾选的 `postinstall`「启动漫剧制作助手」。
  - 无 `[InstallDelete]` / `[UninstallDelete]`；`[Code]` 实现升级前只复制不移动备份到 `{app}\_upgrade_backup\<日期时间>\`（失败时 `MsgBox` 提示并允许继续）及卸载时 `CurUninstallStepChanged` 询问是否保留配置（默认保留，绝不删除用户数据）。
- `程序/scripts/installer_build.py`（新建，stdlib-only）：
  - `--check`（默认）：纯静态解析 `.iss`，逐条检查契约并报告精确行号，失败退出码 `1`，通过退出码 `0`。
  - `--build [--destination 目录]`：按 `PATH` / `%LOCALAPPDATA%\Programs\Inno Setup 6\` / `Program Files (x86)\Inno Setup 6\` / `Program Files\Inno Setup 6\` 查找 `ISCC.exe`；未找到时打印提示并退出码 `2`（不创建目标目录）；找到后在 `tempfile` 临时目录调用 `distribution_build.build()` 与 `verify()`，调用 `ISCC.exe /DAppVersion=<VERSION> /DSourceDir=<临时分发副本> /O<临时输出> <iss>`，复制产物至 `--destination`（默认仓库根上一级 `发行包\`，禁止落进仓库）并打印大小与 sha256。
- `程序/tests/test_installer_script.py`（新建）：7 条自动化测试（覆盖卡内全部 6 项＋SignTool/AppVersion 硬编码额外守卫），全部使用临时目录与假 ISCC，不依赖本机 Inno Setup。
- `程序/governance/structure.json`：仅在 `test_ownership` 新增 `程序/tests/test_installer_script.py` 归属条目。
- `程序/governance/structure-baseline.json`（经需求设计席位批准纳入）：仅同步更新 `policy_sha256` 一行（`a4eefd34…` → `2e4e40c8…`），未放宽任何基线发现数。
- `程序/docs/specs/03_安装签名与分发.md`：同步 §1 表「安装器配置」行、§1.1 新增第 2.5 步、`§7` D-1 状态改为「已完成（脚本＋自检）；实机编译待用户安装 Inno Setup 6」。
- `程序/docs/process/发布检查单.md`：§1 新增安装包自检与构建检查项。

## 先红后绿证据

创建 `程序/scripts/installer/漫剧制作助手.iss` 之前执行结果（红）：

```text
$ python.exe -B scripts\installer_build.py --check   (exit 1)
[安装脚本自检] 未通过（共 1 项）：<worktree>/程序/scripts/installer/漫剧制作助手.iss
  - 第 0 行：找不到安装脚本文件 <worktree>/程序/scripts/installer/漫剧制作助手.iss

$ python.exe -B run_selftests.py -k installer_script (exit 1)
  test_installer_script          1 条     0.1 秒  ✗ 1
AssertionError: 1 != 0 : [安装脚本自检] 未通过（共 1 项）：...
  - 第 0 行：找不到安装脚本文件 ...
```

创建 `程序/scripts/installer/漫剧制作助手.iss` 后两项均转为退出码 `0`（绿）。

## `--check` 输出全文与版本／构建口径

- **版本串**：`V0.7`（唯一权威源 `程序/contract/app_metadata.py:VERSION`）。
- **`scripts\installer_build.py --check` 输出全文**（退出码 `0`，路径已做相对脱敏）：

```text
[安装脚本自检] 通过：<worktree>/程序/scripts/installer/漫剧制作助手.iss
  版本权威源：V0.7（.iss 中仅以 {#AppVersion} 引用）
  用户数据保护 Excludes：8 项全覆盖，skill_note_terms_zh.json 随包放回
  安全边界：无 [InstallDelete]/[UninstallDelete]，SignTool 仅位于 #ifdef Signed 内
```

- **`--build` 退出码说明**：按卡执行权限约定，本机未安装 Inno Setup 6，助手不在宿主直接执行 `scripts\installer_build.py --build`（本机预期退出码 `2`，输出「本机未安装 Inno Setup 6，无法编译安装包；请用户安装后重跑」且不创建发行包目录）。该退出码 `2` 路径及假 ISCC 全链路（`distribution_build.build` + `verify` → 传 `/DAppVersion=V0.7` 与 `/DSourceDir=` → 产物复制与 sha256）已由 `tests/test_installer_script.py` 用例 4、5、6 实测通过。

## 验收命令与退出码

| 命令 | 退出码 | 摘要 |
| --- | --- | --- |
| `run_selftests.py -k installer_script` | 0 | 7 条用例全绿（0.3 秒，`ALL TESTS PASSED`） |
| `scripts\installer_build.py --check` | 0 | 静态契约全项通过（版本 `V0.7`） |
| `run_selftests.py -k distribution_build` | 0 | 22 条用例全绿（4.4 秒，`ALL TESTS PASSED`） |
| `smoke_test.py` | 0 | 默认冒烟 9/9 通过（含隐藏桌面探针＋8 项检查） |
| `smoke_test.py --architecture` | 提交前 1（707/708）→ 提交后复跑 | 提交前仅 `test_structure.py` 报 `policy_sha256` 未同步与未跟踪 `tooling` 目标；已同步 `policy_sha256`，只读核验入索引后 0 新增违规，提交后在干净树上复跑核验 708/708 |

## 手动验收项（待用户）

- **待用户**：在本机安装 Inno Setup 6 → 执行 `scripts\installer_build.py --build` 实机编译单文件 EXE（若 Inno Setup 6 具体小版本有指令差异，按报错回写规格）。
- **待用户**：在一台无开发环境的 Windows 机器上安装生成的安装包 → 升级安装后核对 `config.json`、`desktop_settings.json`、`projects.json`、`private/`、`data/`、`配置/` 内容哈希与安装前一致 → 卸载后确认用户数据与项目仍在。

## 回滚与提交

- 回滚方式：删除 3 个新文件（`scripts/installer/漫剧制作助手.iss`、`scripts/installer_build.py`、`tests/test_installer_script.py`）并还原 `docs/specs/03_安装签名与分发.md`、`docs/process/发布检查单.md`、`governance/structure.json`、`governance/structure-baseline.json`（或直接 `git revert` 本提交）。
- 本轮在车道 `codex/rel-04b` 经 `scripts\dev.py commit` 提交，不合入主干、不 push；最终 commit SHA 与提交后 `smoke_test.py --architecture` 复跑结果见完成报告。
