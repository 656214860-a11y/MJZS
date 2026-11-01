# R1173：HOLLMWOOD 四角色结构只读诊断

日期：2026-10-09。类型：结构治理轮／只读诊断。用户授权：“先只做诊断”。
检查基点：master a567bd2，加工作树既有改动；未修改产品、测试、SKILL 或用户数据。
轮次由 round_claim.py next 领取；返回 1173。中央队列无匹配任务，不认领无关 ID。

## A 目标与范围

诊断四角色规则去重后的职责、依赖和交接结构，区分机械治理与行为契约变更。范围是 hollmwood_rules、hollmwood_roles、节奏模板及其 API／桌面消费者和相关测试。自然剧本删除后的分镜计数不在本轮诊断范围；不以本报告判定该问题已修复。

## B 方法与证据等级

静态读取实际代码、调用链与测试断言；未执行模型请求、应用交互或测试。下文“确定”指请求装配代码可证明；生成质量和实际模型遵从性均未验证。历史 R1171 绿色测试不作为本轮验证凭据。

## C 现有结构

| 层／入口 | 当前职责 | 证据 |
| --- | --- | --- |
| L0 hollmwood_rules | 五份角色／审核常量，单窗口协作说明复用常量 | hollmwood_rules.py:3、:13；architecture.md:214 |
| API hollmwood_roles | 构造各角色请求，串行执行与审核返工 | hollmwood_roles.py:243 |
| API writing_api | 加载项目配置与内联 SKILL，调用角色执行器 | writing_api.py:233、:241 |
| 桌面 workflow_settings | 单窗口规则、模板和项目覆盖装配 | workflow_settings.py:452、:460 |

规则正文已共源。没有证据支持再建立一套规则模块或重写串行调度。

## D 高优先级：SKILL 依赖没有随请求交接

确定：导演规划与审核常量要求依据所选 SKILL，但 hollmwood_roles.py:263-271 只给 writer_system 拼接 skill_constraints；导演、编辑、演员、审核都没有该输入。writing_api.py:245 提供了内联 SKILL，缺口发生在执行器内部分发。

_ask 在 hollmwood_roles.py:164-167 每次只发送当前一条 user 消息和本次 system，没有把其他角色历史传入。因此不能假定编剧读过的 SKILL 自动成为审核人的上下文。计划或候选正文可能间接包含部分规则，但不能替代完整规则依据。

风险：去重后仍能运行，却无法保证导演与审核执行所选写作尺度。桌面单窗口声明共享 SKILL，与 API 的可见范围不同。这是输入契约冲突，不能当成纯文案问题。

## E 高优先级：审核缺少已确认简报

确定：DIRECTOR_REVIEW_RULES 要求按简报的“单集时间”审核（hollmwood_rules.py:11）；审核请求仅包含 candidate（hollmwood_roles.py:295-298），未附 brief 或 director_instruction。编剧首轮收到 brief；编辑／演员只收到计划和当前正文；返工请求仅有退回意见和前稿（:235）。

风险：审核无法直接核验单集时间与确认事实，返工也可能丢失原始依据。这里确认的是上下文缺失，未实测其导致时长错误的概率。应与 D 一起设计最小上下文交接，避免两轮重复补丁。

## F 低优先级：模板读取与装配重复

空 rules／constraints 不会引发 YAML 解析错误：load_rhythm_template（hollmwood_roles.py:69）只是读文本。当前占位模板仍作为“每个角色都必须遵守”的文本注入（:259）；桌面另行读同一文件（workflow_settings.py:462）。

两条入口对默认模板读取／空值回退有重复表达，但当前文件路径一致，尚无读取分歧证据。模板为空不是崩溃根因。若后续收口，应保留自定义模板兼容性，不直接清空或删除用户配置。

## G 不应混入治理的事项

ROLE_ORDER、MAX_REVISIONS、三次审核和串行流程按用户要求保留。_approved 当前以 startswith('APPROVED') 判定（hollmwood_roles.py:198），与现有“以 APPROVED 开头”的规则一致；如需标记边界更严格，须另立契约，不在本轮宣称已发现误放行缺陷。

角色职责中的结尾悬念、保留既有结局卡点是用户明确保留的边界，不应仅因出现“卡点”而误报为重复写作指标。不要为了去重删除角色职责。

## H 测试与既有契约冲突

tests/test_hollmwood_roles.py:146 的 test_skill_instructions_are_injected_only_into_writer_and_writer_revision 明确排除其他角色看到 SKILL。这保护的是旧输入分配口径，与去重后导演／审核依赖 SKILL 的规则冲突。现有测试通过不能证明新的上下文要求已经满足。

tests/test_stage_prompt_governance.py、test_hollmwood_agent_delivery.py 主要验证桌面规则组装与去重；test_script_agent_delivery_assembly.py、test_writing_api.py 覆盖 API 接入。后续需要检查实际请求输入，不能只增加规则字符串存在性断言。

## I 后续轮次边界

本次仅诊断完成，未执行结构治理条目，未启动契约轮。AGENTS.md §3.4 的契约轮白名单没有 hollmwood_rules，architecture.md:83、:214 却将其登记为 L0；后续必须先明确契约轮可改范围，不能仅因模块属于 L0 就默认获得白名单授权。D/E 的修复涉及 L1 请求装配，应归入获准的修复或治理执行范围，而非伪装成只改 L0 的契约轮。

## L 实际验证与保护

依 AGENTS.md §5 的只读诊断例外，本轮没有执行测试。默认冒烟、架构门禁、全量回归均为未运行，不引用历史数字作为当前树通过结论。仅进行文档差异检查。既有六项用户源码／测试／SKILL 改动保持原状；不更新架构正文或接力文件，以遵守 §3.5 写入边界。

## M 结论与未完成项

主要根因是规则外置后，请求输入分配仍停留在“只有编剧需要 SKILL”的旧契约。四角色规则共源已具备，优先补齐可审计的上下文交接，价值高于继续拆文件。D/E 未修复，F 未治理；模型效果未验证。后续执行需依据下列 J/K 明确选项，本轮不自动推进。

## J 整改路线

1. **J1 先确定上下文契约，再补齐交接。** 统一规划、写作、改写、表演、审核及返工各自需要的 SKILL／brief／plan；建议四角色和审核共享所选 SKILL，审核持有 brief，返工保留必要原始依据。同时区分 writing_api 当前拼在 skill_instructions 中的阶段交付契约，避免不加区分地复制整段。实现范围预计 hollmwood_roles、writing_api，必要时 hollmwood_rules（最多 3 个产品模块）；不改变调用顺序、预算、取消、日志发布或落盘。此项包含行为变化，须明确执行授权及轮次范围后实施。
2. **J2 按需要收口模板装配。** J1 后评估占位文本是否需要跳过；抽取共用读取入口应放在允许文件读取的层，不能给 L0 规则模块增加 I/O。预计 hollmwood_roles、workflow_settings 与一个共用读取模块，最多 3 个模块。默认占位可跳过，自定义非空文本保留；不删除用户已有配置。本项优先级低，不是修复 D/E 的前置条件。
3. **J3 再开展约定的契约轮。** 先解决 I 中白名单范围不一致；逐项核对职责、交接、审核和所选 SKILL＋brief 的权威来源，不再只重命名 R1171 的轮次标签。

## K 测试迁移计划

| 条目 | 原断言／受影响测试 | 替换或新增的行为证据 |
| --- | --- | --- |
| J1 | test_hollmwood_roles 的 writer-only SKILL 断言 | 按已确认角色矩阵逐请求断言 SKILL 可见范围；登记旧契约作废原因，不简单删除排除断言 |
| J1 | 同文件审核与返工测试 | FakeAdapter 捕获每次 system/user；用独立 brief 单集时间标记验证三次审核及返工保留依据，不能只检查候选正文 |
| J1 | test_writing_api、test_script_agent_delivery_assembly | 验证配置选定的 SKILL 与阶段交付契约正确传递，保持发布、取消、上下文超限拒绝和失败无正文落盘 |
| J1 | test_stage_prompt_governance、test_hollmwood_agent_delivery | 首发／续发规则同源、桌面 SKILL 路径只引用一次、禁输出结构化内容边界仍有效；API 不重复注入写作细则 |
| J2 | 模板默认值／自定义值测试 | 区分空文本、默认占位、自定义模板；API 与桌面得到相同语义，保留自定义内容 |

执行时保留正常串行顺序、审核退回次数上限、最终演员正文交付和异常／取消断言。首轮按用户原定命令运行 hollmwood、stage_prompt_governance、script_agent_delivery_assembly、writing_api 定向测试，再 smoke_test.py --gate；是否全量遵循届时 §5 及真实凭据，不重复使用历史通过结论。结构执行更新 architecture.md；契约轮按明确后的范围单独执行。以上是未来验证计划，本轮未运行。
