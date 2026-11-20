# R3830 目录治理协议、结构检查器与迁移前身份基线
<!-- round-evidence: {"commit_base": "dcfe76db", "credential_hits": 0, "evidence_sha256": "262891ba14b4ced7", "exit": 0, "failed": 0, "passed": 40, "round": 3830, "tests": "run_selftests.py -k architecture.test_structure architecture.test_agent_doc_budget architecture.test_design_coverage"} -->

## 三问

1. 类型：结构治理轮。先建立治理协议与正反行为测试，不移动说明文档、不宣称全部目录治理完成。
2. 验证：结构20条通过；合并文档预算/覆盖/架构清单共39条通过；默认冒烟9/9；文档登记85份一致。完整架构与正式全量留到统一迁移候选，不宣称全绿。
3. 欠账：冻结迁移前6个具体违规身份，新增违规不可用总数相等掩盖；目录迁移、账户全文接入与最终GUI/全量尚未完成。

## 基线与前置

- 车道 codex/directory-governance-execution，领取R3830。
- R3819诊断已提交4d322df6。
- 接收退役检查点59a117ee为b860721f、补充提交7a64e776为dcfe76db；未合master。
- 退役车道正式204条定向通过、独立201条通过、完整架构580/581仅状态编号红；GUI受共享锁阻塞、正式全量未跑。主代理独立复验核心50条通过。此为可集成但未全部验收的候选，不伪称前置正式完成。
- 本工作包是代码与资源退役后的独立开发期治理候选，最终验收包含前置；不在master发布未验内容。

## 实现

- governance/structure.json：目录角色与真实owner、源码根映射、精确第三方/运行/历史排除、跨模块测试归属、命名例外、深度4定义、构建与私钥归属、目录决策落点。
- governance/check_structure.py：stdlib，读取当前Git索引和显式文件候选；拒绝路径穿越/绝对路径/链接逃逸/大小写冲突/gitlink穿透；运行/私有边界不读正文。身份为(rule_id,path,subject)，只读check不会刷新基线，硬错误不得写入接受基线。
- governance/structure-baseline.json：迁移前实际6个旧命名违规身份及来源提交/清单/协议摘要。不是任意阈值，不通过删旧增新绕过。
- governance/README及decisions/0001-directory-layout：开发开工检查、规则语义/限制/归属/例外、目录决策唯一权威。ADR索引只引用不重复编号正文。
- tests/architecture/test_structure.py：20行为测试，覆盖临时Git仓库、合法样本、未跟踪候选、等量置换、旧债消减、硬错误禁baseline、重复baseline、坏schema、禁止整个源码排除、路径安全、private不读、目录候选、大小写、gitlink、legacy静态/动态、退役记录、跨模块测试、运行空目录、分发/忽略和只读check。
- _scan.NON_PRODUCT_PARTS新增governance：仅归开发工具，不伪装产品L层、不增加产品覆盖模块；静态卫生仍覆盖开发脚本。
- .gitignore新增精确outputs/dist/build边界，不全局忽略exe/zip/pyd。
- distribution_manifest排除governance；实际安装/签名配置未实现，不造空packaging目录。
- 文档登记范围加入governance，登记85份一致；architecture清单登记新门禁。

## 实测

- 新结构测试首次20条：19通过、1错误（缺baseline，预期尚未建立），验证真实项目测试不是恒真。
- 冻结基线后 `python -B -m unittest tests.architecture.test_structure`：20/20，11.879秒。
- 结构 + 文档预算 + 设计覆盖 + architecture清单精确匹配：39/39，8.820秒，退出0。
- doc_registry：85份核对通过、快照更新。
- smoke_test：业务8＋隐藏桌面探针=9/9，退出0。

## 后续与退出

当前待接收账户合并8ce2c328；Git因本地未提交治理改动拒绝cherry-pick，未stash/覆盖，先提交本完整工作包再接收。

下一轮必须完成所有说明文档/示例去向、账户唯一权威、真实分发计划、新引用检查与任务完成文件；之后统一候选修状态编号、跑完整回归再合master。临时原型/生成脚本在系统临时目录，不入产品或提交。
