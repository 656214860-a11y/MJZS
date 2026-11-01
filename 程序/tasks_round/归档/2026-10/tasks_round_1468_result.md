# R1468 结构治理轮：根目录整理（优化清单第 14 项）

1. **本轮类型？** 结构治理轮（只搬文档，不改代码逻辑）。
2. **测试与基线？** `test_root_layout`、`test_app_metadata`、分发清单／分发自检、文档相关测试通过；默认冒烟、架构门禁见提交前运行。断言未动，仅同步被搬文件的路径。
3. **是否欠账？** 无源码风险路径改动。

## 改动（git mv，历史保留）

- `AGENT_HANDOFF.md`、`AGENT_SESSION_PROMPTS.md`、`GLOSSARY.md` → `.agent-handoff/`；根 `AGENTS.md` 里的接力链接同步；`test_app_metadata` 里术语表路径同步。
- `outputs/`（R1063–R1068 历史代码腐烂审计证据，仅被分发清单当排除项提到）→ `程序/维护记录/代码腐烂审计/`（已在分发排除范围 `维护记录/**` 内）。
- `distribution_manifest.md` 同步；`test_root_layout` 登记表同步，根目录跟踪入口由 22 项降到 17 项。

## 仍留在根目录的原因

- `启动助手.cmd`／`启动助手_测试模式.cmd`／`启动漫剧制作助手.pyw`／`使用说明.*`：用户直接使用的入口。
- `本地CI.cmd`、`ci_*.cmd`：钩子、`.wt/ci` 流程与其他车道按文件名调用。
- `reorganize_install.py`：升级安装脚本，按根目录相对位置工作。
- `漫剧制作助手.ico`（以及未入库的 `漫剧制作助手_图标_629c80fc.ico`）：桌面快捷方式的图标路径指向后者，不能删。
- `AGENTS.md`、`CLAUDE.md`：代理工具按约定在根目录读取。

## 提交

已提交，见 git log 标题 `R1468:`。
