# R1285：Claude CLI 剧本准备限定输入

类型：修复轮。用户要求附件先转 Markdown、减少重复读取和 token 消耗；无对应维护队列 ID，不认领其他任务。

## 根因与修改

- 上传服务已保存 Markdown，但本地投递仍引用原附件，让 CLI 重复解析。Claude 现在仅引用已有 Markdown；原件与转换件去重，不同时内嵌全文。副本缺失、空文件或不支持转换时，在发送前明确提示转换重传，不让模型无限寻找原件。API/Codex 保持原行为。
- desktop 每次生成全项目 snapshot、初发索引和续接摘要，可能引导遍历其他模型成果与历史日志。Claude writing 跳过这些装配，保留 SKILL、制作锁、交付路径和当前输入；阶段①不再要求读取旧 brief。后续用当前会话，缺资料询问用户提供明确文件。
- 移除扫描后，用本轮请求标识区分不同阶段的相同“确认”；同一轮内部重试保留标识。无新增状态文件或付费调用。
- Markdown 使用既有转换器，不做有损摘要、不截断故事细节、不修改用户原件。此项主要避免 Office 重解析与重复读文；不声称固定 token 降幅。
- desktop 注释审计行号后移 7；stage_execution_service 三处既有内存 JSON 校验登记后移 3。只同步位置，未新增豁免或弱化断言。

## 实测

1. 先红：两文件 33 条，1 failure、2 errors，分别证明仍调用 snapshot 和缺少限定输入/Markdown 选项。
2. 定向 `run_selftests.py -k claude_writing_session idea_attachment script_agent_delivery stage_prompt_governance workflow_writing_stages workflow`：14 文件，178 条，0 红。
3. 增加重复“确认”防误去重回归后，两文件最终 34/34，0.949 秒。
4. 默认 `smoke_test.py` 最终 8/8。
5. `smoke_test.py --architecture`：311 条，1 失败（三处审计行号漂移）；修正后原棘轮与 TODO 审计文件 5/5。未把首次失败记为全绿，未重复全架构。
6. 另任务的正式 R1284 全量凭据已记录 465.245 秒、tree=76421bd992ce09d5b4cc45a5d27be080fae2edd1；不代表本轮树全量。本轮无升级项，不重复全量。

日志：临时目录 r1285-targeted.log、r1285-final-unit.log、r1285-smoke-final.log、r1285-architecture.log、r1285-audit-recheck.log。未启动真实 CLI/API，未重启应用，未修改用户剧本。

## 使用与限制

重启助手加载。旧 Claude 对话已有的冗余上下文不会因代码修改消失；明确“重新输出项目设定”使用此前已实现的新会话入口。模型是否完全遵从读文件指令未实测，不保证以后绝不压缩。旧附件没有 Markdown 时会提示重传，不静默丢弃材料。

提交：待中央编号收口和主目录集成；并行任务已推进中央编号，保留本报告原始验证记录，提交编号另附收口报告。
