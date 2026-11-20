# R3819 目录治理前置诊断与迁移冻结清单
<!-- round-evidence: {"commit_base": "839ef93a", "credential_hits": 0, "evidence_sha256": "cc8a8e3627e00466", "exit": 0, "failed": 0, "passed": 0, "round": 3819, "tests": "docs-only"} -->

## 三问

1. 类型：AGENTS §3.5 只读诊断轮；仅新增本结果文件。生产代码、需求设计、目录与规则均未修改。
2. 验证：文档预算与设计覆盖基线 18/18 通过，命令见下。默认冒烟、完整架构、安全全量本轮未运行，不宣称三个基线全绿。
3. 欠账：未修复生产问题；明确前置不成立、冻结文档迁移范围与已知冲突，防止盲迁移和示例丢失。

## 目标与现场

- 用户要求持续执行《目录治理与结构门禁任务书_R3812.md》，各轮验证后合入 master。
- 本轮基准 master：839ef93a（R3810）。本工作树：codex/directory-governance-execution。
- 文件名 R3811/R3812 是历史标签；执行轮次独立领取。本诊断轮实际领取 R3819。
- 主树有两份未跟踪任务书，不纳入其他修改、不暂存主树、不切换主树分支。
- 本工作树因嵌套路径较长，已移动至 `D:/漫剧制作助手/.agents/worktrees/directory-governance-execution`，用 `round_claim.py record 3819` 更新归属。

## 1. 前置未完成：不能直接迁移

master 仍跟踪 `skills/00全流程SKILL/` 223 文件；存在 `infra/aigc_lint.py`、`aigc_package_diff.py`，ui/skill_tools.py 的五个 feed/style 工具仍注册。

真实依赖包括 skill_command、共享发送、agent_skill_sync、skill_residue_service，以及 01–13 阶段 SKILL 中引用的创作职责。尤其准备 SKILL 中的节拍、六阶段剧本链、长剧批次、台词拟人化等不能只删链接。

已开独立前置车道 codex/retire-builtin-prerequisite，真实轮次 R3820，由实施代理负责完整退役及测试、提交。该车道不动治理目录/文档位置；本车道前置验收前仅只读准备。

## 2. 文档迁移冻结清单

执行时重新核对数量与摘要。以下 old 相对 程序/说明/，new 相对 程序/。

| old | new / 处置 |
|---|---|
| 产品需求规格.md | docs/requirements/产品需求规格.md |
| 发布检查单.md | docs/process/发布检查单.md |
| 商用交付资料.md | docs/process/商用交付资料.md |
| 制作失败与人工替代.md | docs/process/制作失败与人工替代.md（用户出包所需） |
| 存储盘点与保留.md | docs/process/存储盘点与保留.md |
| 维护约定.md | docs/process/维护约定.md |
| 版本控制处置说明.md | docs/process/版本控制处置说明.md |
| 联调测试出口基线.md | docs/process/联调测试出口基线.md |
| 每分钟成本核算.md | docs/process/每分钟成本核算.md |
| 编剧功能说明.md | docs/guides/编剧功能说明.md |
| 工程文档登记表.md | docs/records/工程文档登记表.md |
| 已知坑与不可破坏契约.md | docs/contracts/已知坑与不可破坏契约.md |
| 模型金额预算.md | docs/contracts/模型金额预算.md |
| 生成服务失败处理契约.md | docs/contracts/生成服务失败处理契约.md |
| 更新记录.md | 内容并入根 CHANGELOG.md；保留 V0.7 与既有未发布记录 |
| 账户会员云端设计.md | 完整合入 docs/specs/07_业务域规格.md 的稳定章节，不覆盖设置/模型/授权域 |
| 账户会员云端立项前清单.md | 完整历史材料归 docs/records/账户会员立项历史.md；D1–D16、D11b、Q1–Q8 的现行状态映射到07 |
| 已并入设计规格.md | docs/records/文档迁移台账.md；改错链并补本批逐项映射 |
| 总控包脚本机检桥接入边界.md | 前置退役处理，不重新创建 |
| 示例/雨夜修伞/episode.json | resources/examples/rainy_umbrella/episode.json |
| 示例/雨夜修伞/assets.json | 同目录 assets.json，保持与 episode 同级 |
| 示例/雨夜修伞/开始练习.md | 同目录开始练习.md，修复包内指南链接 |

不得把说明目录中的非md文件漏出迁移清单，不为兼容保留第二份正文。

## 3. 必须同步的消费者

- ui/desktop_project_pages.py:604 的示例根、605读取episode、609打开练习说明；domain/projects.py 按 episode 同级找 assets.json 及素材相对路径。
- tests/test_projects.py 练习隔离用例保留原断言，更新 fixture 地址。
- 维护记录/基准脚本/doc_registry.py:27 REGISTRY、31 SCOPES、130 快照 registry 字段；增加重复主题/重复路径与递归新目录测试。
- tests/architecture/test_agent_doc_budget.py 的登记表/契约/PRD地址；保留原 16KB/96KB 阈值与正反自测。
- tests/architecture/test_design_coverage.py 的 PRD 地址；07节号和覆盖映射一致。
- tests/test_version_record.py 改读合并后 CHANGELOG；test_app_metadata.py 改维护约定地址。
- distribution_manifest.md 原来整包保留说明目录，新结构必须显式保留示例与练习指南，排除开发 docs、governance 与实际退役 legacy。排除规则优先于保留，不能让真实示例变成 undecided。
- 根 AGENTS/CLAUDE、程序AGENTS/PROJECT_MAP/runbook/导航、现行队列与specs引用须同步。project_status 仅master更新；历史 tasks_round/归档原文不批量改写。
- selftest_env.NON_SOURCE_DIRS、package_dep_scan 的目录边界应核对，避免把governance/资源识别为运行时模块。

## 4. 账户全文合并与冲突处置

保留旧设计全部十节的条款，新增07的账户完整契约章节，不替换7.1–7.8现有其他域。逐节记录原文摘要与新落点，保留D1–D16、D11b、Q1–Q8 ID。

| 冲突 | 事实/应采用状态 |
|---|---|
| 旧设计39/99/399 vs用户确认19/49/189 | 以本会话明确用户价格为现行需求，旧价格明确标历史被替代，不继续列未决 |
| 旧全文首部“未授权实现”，正文已记已实现 | 把初稿时间与当前实现状态分开，不把全部标未实现 |
| specs/02存在 /v1/metering 示意接口 | 当前服务端无此路由，计量上报是待实现需求，不得标API已实现 |
| 会话/时钟安全缺口在07/06仍列待修 | 与当前客户端及ADR核对已实现边界，不能只按旧缺口文案搬迁 |
| 退款接口 | 服务端有POST/GET /v1/refund-request，客户端无封装；准确分端标状态 |
| 07第5行 ../说明 错链 | 已在原树存在，迁移时修到唯一07内部条款 |
| 用户隐私/注销/试用台账 | 必须保留注销后单向哈希保留及披露要求，不能笼统写删光所有记录 |

服务端只读取公开源码接口，不访问线上、不读取环境密钥、不改独立服务端仓库。运行时API事实以客户端调用和服务端路由交叉核对；需求/已接受设计不由现实现覆盖。

## 5. 结构治理方案的约束

- 代码与治理机器配置英文小写，文档中文可用；标准入口/阶段编号/ADR与vendor分类例外明确。
- 检查范围为跟踪文件 + 显式新候选，排除用户/运行/私有/缓存/第三方与gitlink内部；不得rglob整个主仓库工作树。
- 新违规比较路径+规则身份集合，防等量置换；baseline只显式写入，不随check更新。
- 目录所有者以当前单人责任角色表示，不能虚构多人团队。
- 源码技术层目录现状保留并如实记接受例外，不能宣称已经按业务域重排。
- legacy 仅实际对象确认退役时创建。reference/HoLLMwood 是gitlink，不能将reference整体当普通文件夹移动。
- outputs 当前只在本机exclude中忽略，应使用共享精确规则；不添加全局 *.exe/*.zip/*.pyd 误伤合法资源。
- 构建/签名未来配置只指定落点，不先建空目录；私钥不进仓库。
- 新治理脚本进入开发扫描时需明确归属，不能因未登记而放宽层级/静默异常等门禁。

## 验证记录

在本工作树 程序/ 目录使用随附解释器：

`python -X utf8 -B -m unittest tests.architecture.test_agent_doc_budget tests.architecture.test_design_coverage`

实测：18 tests，OK，退出码0。此检查只证明现状既有局部门禁通过，不能证明所有docs链接有效、账户全文覆盖或设计评审通过。

## 下一轮

1. 等待R3820独立前置交付，核验提交与测试，不混入其他车道。
2. 按任务书建立结构规则/检查器/测试，先冻结现状身份基线。
3. 完成账户全文迁移与逐项去向/摘要，再统一文档地址和示例出包。
4. 跑适用门禁与完整回归，逐项完成退出清单后提交、合并、主树验证。

本报告不宣称任务书完成，目标保持active。
