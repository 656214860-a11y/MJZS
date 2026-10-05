# 工作区与命令

- 仓库 D:/漫剧制作助手；Windows PowerShell；产品为 Python/Tk 桌面漫剧制作助手。
- 源码、测试在 程序/；入口及结构以 [项目地图](../程序/PROJECT_MAP.md) 为准。
- 权威：[AGENTS](../程序/AGENTS.md)、[架构](../程序/architecture.md)、[状态](../程序/project_status.md)。
- 解释器：运行环境/Python/python.exe；维护时优先 -B，避免新增字节码缓存。
- 工作目录 程序/：../运行环境/Python/python.exe -B smoke_test.py；定向回归使用该解释器 -m unittest。
- 根目录分配轮次：运行环境/Python/python.exe -B 程序/维护记录/基准脚本/round_claim.py next。
- 中央队列位于 git common-dir，由 round_claim 维护；工作树导出不是手工编辑入口。
- 全量周期、凭据、认领和提交遵循程序 AGENTS，接力不另设例外。
- 不读取或更改无关用户数据、private/、episode/、writing/、配置/宠物/配置.json、密钥。
