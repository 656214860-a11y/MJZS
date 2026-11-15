# 分发清单

## 用途与边界

本清单定义正式分发副本应包含和排除的路径。它是供未来构建/校验工具消费的声明，**不执行复制、移动、删除或归档**，也不在应用启动时读取。

分发根为 `D:\漫剧制作助手\`。正式副本保留根目录启动器、`运行环境/` 与 `程序/` 的运行所需内容；用户项目 `D:\漫剧下载\` 不属于分发输入。

## 必须保留

| 路径/模式 | 原因 |
| --- | --- |
| `启动漫剧制作助手.pyw`、`开发者工具/启动助手.cmd` | 正式启动入口。 |
| `运行环境/Python/` | 随应用交付的解释器与依赖。 |
| `程序/app.py`、`程序/desktop.py` 及其生产 Python 模块 | 主界面与业务实现。 |
| `程序/assets/`、`程序/skills/`、`程序/workflows/`、`程序/data/` | 内置资源、SKILL、流程和内置数据。 |
| `程序/配置/` 与程序随附说明 | 默认配置和面向用户的资料。 |
| `程序/*.py`（生产 Python 模块）、`程序/agent/**`、`程序/contract/**`、`程序/infra/**`、`程序/说明/**`、`程序/附加工具/**`、`程序/batch_frames_tool/**` | 主界面之外的生产模块、随附说明与独立批处理小工具。 |
| `使用说明.md`、`使用说明.txt`、`漫剧制作助手.ico` | 面向用户的说明与程序图标（根目录唯一正式图标为 git 跟踪的 `漫剧制作助手.ico`）。 |
| `程序/README.md`、`程序/runbook.md`、`程序/配置说明.md`、`程序/批量资产说明.md`、`程序/默认创意示例.md`、`程序/requirements.txt` | 面向用户的随附说明与依赖声明。 |
| `程序/asset_manifest.schema.json`、`程序/flux2_klein_asset_text_api.json`、`程序/z_image_assets_api.json`、`程序/z_image_official.json`、`程序/codex_paste.ps1` | 运行时按文件名读取的内置模板与辅助脚本。 |

## 必须排除

下列模式仅描述构建输出的排除规则；源开发目录保持原样。

| 路径/模式 | 分类 | 原因 |
| --- | --- | --- |
| `程序/tests/**` | 测试 | 仅用于开发验证。 |
| `程序/tasks_round/**` | 开发记录 | 轮次过程产物。 |
| `程序/维护记录/**` | 开发记录 | 维护和自检日志。 |
| `程序/scripts/**` | 开发工具 | 仅供开发/维护人员调用。 |
| `程序/.selftmp/**`、`.selftmp/**` | 临时产物 | 可再生的自检或维护临时文件。 |
| `程序/**/__pycache__/**`、`程序/**/*.pyc` | 字节码缓存 | 可由解释器重新生成。 |
| `程序/**/.git/**` | 源控制元数据 | 不属于运行时。 |
| `程序/logs/**`、`启动错误.log`、`程序/.*.out`、`程序/log.txt` | 历史运行日志与自检输出 | 正式副本不携带既有日志；运行期仍按现有行为创建日志。 |
| `程序/private/**` | 本机私有数据 | 不得随分发副本携带私有配置或密钥副本。 |
| `程序/data/skills/**` | 用户导入的 SKILL | R2073：用户层 SKILL 与导入台账，由目标机器生成；升级只保留不覆盖。 |
| `.claude/**`、`.codex/**`、`.agents/**`、`.tools/**`、`outputs/**`（本机 Agent 草稿目录与第三方下载工具，已被 .git/info/exclude 忽略） | 代理/开发产物 | 不是运行时内容，不进正式副本。 |
| `.wt/**`、`.gitattributes`、`.gitignore`、`.claudeignore`、`AGENTS.md`、`CLAUDE.md`、`开发者工具/BLOCKED_ISSUES.md`、`reorganize_install.py`、`开发者工具/handoff-full-safe.md` | 开发/代理资料 | 不是运行时内容。 |
| `程序/.*.err`、`程序/.*.out`、`程序/.*.log`、`维护记录/**` | 自检与维护产物 | 可再生成的诊断输出。 |
| `程序/outputs/**`、`程序/工作流任务/**`、`工作流任务/**`、`程序/episode/**`、`程序/tasks/**`、`程序/_supervisor/**` | 本地运行产物 | 可再生产物与根目录开发任务现场，不随分发副本携带。 |
| `运行环境/Python_alpha_a2_backup/**`、`运行环境/Python315_pruned_backup/**` | 本机备份 | 解释器旧版与裁剪备份，正式交付只保留 `运行环境/Python/`。 |
| `程序/Tencent/**` | 本机垃圾 | 腾讯输入法 WeType 误写日志/缓存，非项目内容。 |
| `漫剧制作助手_图标_*.ico`、`漫剧助手.lnk` | 本机产物 | 除 `漫剧制作助手_图标_629c80fc.ico`（已列保留）外的本地图标副本与快捷方式，由目标机器生成。 |
| `升级备份/**` | 本机维护产物 | 不属于正式运行所需内容。 |
| `开发者工具/本地CI.cmd`、`开发者工具/ci_clean.cmd`、`开发者工具/ci_targets.cmd`、`开发者工具/ci_unattended.cmd`、`开发者工具/启动助手_测试模式.cmd`、`程序/_diag_window_probe.ps1` | 开发工具 | 本地 CI、测试模式与窗口诊断，仅供开发。 |
| `程序/AGENTS.md`、`程序/PROJECT_MAP.md`、`程序/architecture.md`、`程序/design_tokens.md`、`程序/ui_components.md`、`程序/docs/README.md`、`程序/docs/stages/**`、`程序/docs/review/**`、`程序/data_model.md`、`程序/task_states.md`、`程序/project_status.md`、`程序/distribution_manifest.md`、`程序/文档导航.md` | 开发文档 | 代理协议、架构、设计与状态记录，不是用户资料。 |
| `安装信息.json`、`程序/config.json`、`程序/desktop_settings.json`、`程序/projects.json`、`程序/task-execution.log`、`程序/漫剧制作助手.lnk` | 本机状态 | 安装记录、用户配置、项目索引与本机快捷方式，由目标机器生成；升级也只保留不覆盖。 |
| `程序/h3_launcher.pyw` | 个人开发工具 | 写死本机 ComfyUI 路径的临时启动器，不随分发。 |
| `程序/reference/**` | 参考资料 | 外部参考仓库快照，非运行时内容。 |
| `程序/pyproject.toml`、`程序/dev-requirements.txt`、`程序/.ruff_cache/**`、`程序/.mypy_cache/**`、`程序/.gitleaks.toml`、`程序/external_tools.lock.json`、`程序/SECURITY.md`、`程序/CHANGELOG.md`、`程序/GLOSSARY.md`、`程序/docs/adr/**` | 开发期工具与治理文档 | 静态分析、密钥扫描配置与治理文档；运行时仍零第三方依赖，不进分发副本。 |

## 运行期维护与分发的区别

程序日志保留、轮转与容量限制已由 `log_maintenance.py` 实现，并由桌面退出路径调用 `launch_cleanup()`；可再生产物维护由 `workspace_maintenance.py` 承担。具体阈值以代码常量为准。本清单只排除分发副本中的历史日志，不定义或执行运行期清理，更不授权删除用户作品或配置。

## 后续构建器约束

未来的构建器必须先根据本清单生成候选文件集并报告命中项，再复制到新的输出目录；不得对开发目录执行原地删除、移动或重命名。构建校验应确认“必须保留”入口存在，并确认“必须排除”模式在输出中为零项。

## 可复验构建器

`程序/scripts/distribution_build.py` 按本清单工作，只读源目录、只往新的输出目录写：

    python.exe -B scripts\distribution_build.py --plan
    python.exe -B scripts\distribution_build.py --build --destination <新目录>
    python.exe -B scripts\distribution_build.py --verify --destination <新目录>

- `--plan` 生成候选文件集并报告三类命中：清单要保留的、清单要排除的、以及清单没提、需要人工决定的（避免悄悄漏文件）。
- `--build` 拒绝把输出写到开发目录内部、拒绝覆盖非空目录、拒绝在还有未决定文件时静默继续；输出里写 `分发清单.json`（版本＋逐文件 sha256）。
- `--verify` 校验输出里没有排除项、必需入口齐全、摘要自洽，并确认 `程序/skills/00全流程SKILL/jingju-skills` 整包仍在（安装验收的隔离要求）。
