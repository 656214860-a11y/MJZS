# 分发清单

## 用途与边界

本清单定义正式分发副本应包含和排除的路径，由仓库现有 `scripts/distribution_build.py` 构建/校验工具消费；清单本身不执行复制、移动、删除或归档，也不在应用启动时读取。

分发根为 `D:\漫剧制作助手\`。正式副本保留根目录启动器、`运行环境/` 与 `程序/` 的运行所需内容；用户项目 `D:\漫剧下载\` 不属于分发输入。

## 必须保留

| 路径/模式 | 原因 |
| --- | --- |
| `启动漫剧制作助手.pyw`、`开发者工具/启动助手.cmd` | 正式启动入口。 |
| `运行环境/Python/` | 随应用交付的解释器与依赖。 |
| `运行环境/ffmpeg/` | 随应用交付的 Gyan FFmpeg 9.0.1 essentials build（`ffmpeg.exe`/`ffprobe.exe`，`bin/` 下）；实测构建参数含 `--enable-gpl --enable-version3`，许可证按 `GPL-3.0-or-later` 而非 LGPL 声明。来源、版本与二进制 SHA256 由 `external_tools.lock.json` 锁定并投影到 SBOM。运行时经 `contract.platform_tools.tool_path` 按「显式有效配置 > 随包 > PATH」定位，用户仍可在配置中改用自备 FFmpeg。 |
| `程序/app.py`、`程序/desktop.py` 及其生产 Python 模块 | 主界面与业务实现。 |
| `程序/assets/`、`程序/skills/`、`程序/workflows/`、`程序/data/` | 内置资源、SKILL、流程和内置数据。 |
| `程序/配置/`、`程序/resources/examples/rainy_umbrella/**`、`程序/docs/process/制作失败与人工替代.md` | 默认配置、完整练习示例（三文件同级）与包内失败处理指南。 |
| `程序/*.py`（生产 Python 模块）、`程序/agent/**`、`程序/contract/**`、`程序/domain/**`、`程序/infra/**`、`程序/orchestrator/**`、`程序/ui/**`、`程序/voice_engine/**`、`程序/resources/examples/**`、`程序/docs/process/制作失败与人工替代.md`、`程序/附加工具/**`、`程序/batch_frames_tool/**` | 主界面之外的生产模块、随附说明与独立批处理小工具；`voice_engine/` 为离线语音识别独立 ASR 运行时（引擎、模型配置、ModelScope 下载、venv 引导），模型与依赖在运行时落 `data/`。 |
| `使用说明.md`、`使用说明.txt`、`漫剧制作助手.ico` | 面向用户的说明与程序图标（根目录唯一正式图标为 git 跟踪的 `漫剧制作助手.ico`）。 |
| `程序/README.md`、`程序/runbook.md`、`程序/配置说明.md`、`程序/批量资产说明.md`、`程序/默认创意示例.md`、`程序/requirements.txt` | 面向用户的随附说明与依赖声明。 |
| `程序/asset_manifest.schema.json`、`程序/flux2_klein_asset_text_api.json`、`程序/z_image_assets_api.json`、`程序/z_image_official.json`、`程序/codex_paste.ps1` | 运行时按文件名读取的内置模板与辅助脚本。 |

## 必须排除

下列模式仅描述构建输出的排除规则；源开发目录保持原样。

| 路径/模式 | 分类 | 原因 |
| --- | --- | --- |
| `程序/tests/**` | 测试 | 仅用于开发验证。 |
| `程序/docs/specs/**` | 设计规格 | 开发权威与技术边界，不是运行时输入。 |
| `程序/docs/requirements/**`、`程序/docs/adr/**`、`程序/docs/stages/**`、`程序/docs/review/**`、`程序/docs/guides/**`、`程序/docs/contracts/**`、`程序/docs/records/**` | 开发文档 | 用户运行所需的流程指南在单文件保留规则中明确列出，其余工程资料不入包。 |
| `程序/docs/process/发布检查单.md`、`程序/docs/process/商用交付资料.md`、`程序/docs/process/存储盘点与保留.md`、`程序/docs/process/维护约定.md`、`程序/docs/process/版本控制处置说明.md`、`程序/docs/process/联调测试出口基线.md`、`程序/docs/process/每分钟成本核算.md` | 开发流程 | 保留仅被用户练习引用的制作失败与人工替代说明，其余运行时不读取。 |
| `程序/governance/**` | 开发治理 | 目录协议、检查器与基线只在开发与CI中使用，不进入产品。 |
| `程序/legacy/**` | 退役内容 | 未来经确认保留的退役代码不得进入运行时和分发；当前不创建空目录。 |
| `程序/tasks_round/**` | 开发记录 | 轮次过程产物。 |
| `程序/维护记录/**`、`程序/auto-full-safe-result.json`、`程序/full-safe-history.jsonl` | 开发记录 | 维护和自检日志及历史验收凭据；不作为产品运行输入。 |
| `程序/scripts/**` | 开发工具 | 仅供开发/维护人员调用。 |
| `程序/.selftmp/**`、`.selftmp/**` | 临时产物 | 可再生的自检或维护临时文件。 |
| `程序/**/__pycache__/**`、`程序/**/*.pyc` | 字节码缓存 | 可由解释器重新生成。 |
| `程序/**/.git/**` | 源控制元数据 | 不属于运行时。 |
| `程序/logs/**`、`启动错误.log`、`_wm.log`、`程序/.*.out`、`程序/log.txt` | 历史运行日志与自检输出 | 正式副本不携带既有日志；运行期仍按现有行为创建日志。 |
| `程序/private/**` | 本机私有数据 | 不得随分发副本携带私有配置或密钥副本。 |
| `程序/data/skills/**` | 用户导入的 SKILL | R2073：用户层 SKILL 与导入台账，由目标机器生成；升级只保留不覆盖。 |
| `程序/skills/01 剧本准备SKILL/剧本锻造/**` | 无可确认再分发许可证的外部 Skill | 上游固定提交未提供 LICENSE；源码工作树保留作审计，正式副本排除。取得书面授权或上游补许可证后才可重新纳入。 |
| `.claude/**`、`.codex/**`、`.agents/**`、`.agent-handoff/**`、`.tools/**`、`outputs/**`（本机 Agent 草稿目录与第三方下载工具，已被 .git/info/exclude 忽略） | 代理/开发产物 | 不是运行时内容，不进正式副本。 |
| `.wt/**`、`.gitmodules`、`.gitattributes`、`.gitignore`、`.claudeignore`、`AGENTS.md`、`CLAUDE.md`、`开发者工具/BLOCKED_ISSUES.md`、`reorganize_install.py`、`开发者工具/handoff-full-safe.md` | 开发/代理资料 | 子模块来源映射与其他开发元数据不属于运行时；Skill 内容由构建器从已初始化的固定提交复制。 |
| `程序/.*.err`、`程序/.*.out`、`程序/.*.log`、`维护记录/**` | 自检与维护产物 | 可再生成的诊断输出。 |
| `程序/outputs/**`、`程序/工作流任务/**`、`工作流任务/**`、`程序/episode/**`、`程序/tasks/**`、`程序/_supervisor/**` | 本地运行产物 | 可再生产物与根目录开发任务现场，不随分发副本携带。 |
| `运行环境/Python_alpha_a2_backup/**`、`运行环境/Python315_pruned_backup/**`、`运行环境/Python.bak*/**` | 本机备份 | 解释器旧版、裁剪与换版前的 `.bak_*` 快照备份，正式交付只保留 `运行环境/Python/`。 |
| `程序/Tencent/**` | 本机垃圾 | 腾讯输入法 WeType 误写日志/缓存，非项目内容。 |
| `漫剧制作助手_图标_*.ico`、`漫剧助手.lnk` | 本机产物 | 除 `漫剧制作助手_图标_629c80fc.ico`（已列保留）外的本地图标副本与快捷方式，由目标机器生成。 |
| `升级备份/**` | 本机维护产物 | 不属于正式运行所需内容。 |
| `开发者工具/本地CI.cmd`、`开发者工具/ci_clean.cmd`、`开发者工具/ci_targets.cmd`、`开发者工具/ci_unattended.cmd`、`开发者工具/启动助手_测试模式.cmd`、`程序/_diag_window_probe.ps1` | 开发工具 | 本地 CI、测试模式与窗口诊断，仅供开发。 |
| `程序/AGENTS.md`、`程序/PROJECT_MAP.md`、`程序/architecture.md`、`程序/design_tokens.md`、`程序/ui_components.md`、`程序/docs/README.md`、`程序/docs/stages/**`、`程序/docs/review/**`、`程序/docs/specs/**`、`程序/data_model.md`、`程序/task_states.md`、`程序/project_status.md`、`程序/distribution_manifest.md`、`程序/文档导航.md` | 开发文档 | 代理协议、架构、设计与状态记录，不是用户资料。 |
| `安装信息.json`、`程序/config.json`、`程序/desktop_settings.json`、`程序/projects.json`、`程序/task-execution.log`、`程序/漫剧制作助手.lnk` | 本机状态 | 安装记录、用户配置、项目索引与本机快捷方式，由目标机器生成；升级也只保留不覆盖。 |
| `程序/h3_launcher.pyw` | 个人开发工具 | 写死本机 ComfyUI 路径的临时启动器，不随分发。 |
| `程序/reference/**` | 参考资料 | 外部参考仓库快照，非运行时内容。 |
| `程序/pyproject.toml`、`程序/dev-requirements.txt`、`程序/.ruff_cache/**`、`程序/.mypy_cache/**`、`程序/.gitleaks.toml`、`程序/external_tools.lock.json`、`程序/SECURITY.md`、`程序/CHANGELOG.md`、`程序/GLOSSARY.md`、`程序/docs/adr/**` | 开发期工具与治理文档 | 静态分析、密钥扫描配置与治理文档；运行时仅包含requirements.txt锁定的白名单依赖，开发工具不进分发副本。 |

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
- `--build` 同时生成 CycloneDX 1.5 `sbom.cdx.json` 与人读 `THIRD_PARTY_NOTICES.txt`，两者进入 `分发清单.json` 的逐文件 sha256。
- 随附 Python 运行时只保留 `requirements.txt` 精确锁定的 distribution；开发工具和其他未声明包仅从新建分发副本裁剪，源安装目录不被修改。缺包、错版、缺 RECORD 时拒绝构建；被生产包共享的文件不得随未知包误删。
- `--verify` 校验输出里没有排除项、必需入口齐全、摘要与 SBOM 自洽，保留 SKILL 均通过摘要逐项校验，不再强制退役包存在；`distribution_selfcheck.py --release` 还会拒绝 `NOASSERTION` 等发布阻断。

内建总控资源已退役，不再要求其专用包存在；其余 `skills/` 资源仍按清单保留。
