# 工作区与命令

- 仓库 D:/漫剧制作助手；Windows PowerShell；产品为 Python/Tk 桌面漫剧助手。
- 源码、测试在 程序/；入口及结构以 [项目地图](../程序/PROJECT_MAP.md) 为准。
- 权威：[AGENTS](../程序/AGENTS.md)、[架构](../程序/architecture.md)、[状态](../程序/project_status.md)。
- 解释器：运行环境/Python/python.exe；维护时优先 -B，避免新增字节码缓存。
- 工作目录 程序/：../运行环境/Python/python.exe -B smoke_test.py；定向回归使用该解释器 -m unittest。
- 根目录分配轮次：运行环境/Python/python.exe -B 程序/维护记录/基准脚本/round_claim.py next。
- 中央队列位于 git common-dir，由 round_claim 维护；工作树导出不是手工编辑入口。
- 全量周期、凭据、认领和提交遵循程序 AGENTS，接力不另设例外。
- 不读取或更改无关用户数据、private/、episode/、writing/、配置/宠物/配置.json、密钥。

## 备份与 Git 目录（2026-10-18）

- Git common-dir：`D:\repo-meta\漫剧制作助手.git`；主工作树只登记 `D:\漫剧制作助手`。
- 工作树补丁／bundle：`D:\repo-meta\wt-backup-20261018`；恢复备份：`D:\repo-meta\漫剧制作助手恢复备份`（982 文件、73.2MB）。
- 后台全量工作树 `.wt/ci` 由 `scripts/auto_full_safe.py` 按 HEAD 重建；缺失时不要手工复用旧目录，先看 `auto_full_safe.py --status` 与 `程序/logs/auto_full_safe.log`。

## 干净全量工作树依赖（R1418 实核）

- 使用仓库随附 Python 的绝对路径，不复制用户配置或项目登记表。
- 四个 gitlink 须按父仓库索引提交初始化：`程序/reference/HoLLMwood`、`程序/skills/00全流程SKILL/AIGC创作全流程`、`程序/skills/01 剧本准备SKILL/剧本锻造`、`程序/skills/01 剧本准备SKILL/编剧技能集`。可从本机嵌套仓库创建 detached worktree，核对 HEAD 与父索引一致。
- `程序/维护记录/基准历史.json` 依 `.gitignore` 约定仅供本机诊断，不作为可重现测试输入或验收凭据；R1418 首轮复制后暴露历史测试隔离缺陷，修复采用明确标注来源的脱敏固定样本，原诊断历史保留。其余性能脚本与阈值随 Git 检出。
- 正式全量需干净 master，执行器写 common-dir 凭据；验收期间不提交、不移动 HEAD。用临时 master 验证工作树可保留主目录的未跟踪用户数据。
