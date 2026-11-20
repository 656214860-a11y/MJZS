# R3836 文档入口统一、账户设计归并与示例分发迁移结果

## 三问

1. 类型：结构治理/文档与资源迁移轮。范围是《目录治理与结构门禁任务书_R3812》所要求的文档归并、账户现行唯一权威、演示资源搬迁及相应消费者路径；不改用户项目或服务端。
2. 测试：文档登记82份通过；活跃文档67份链接审计零断链；迁移与结构定向74/74通过；退役补充关键18/18；默认冒烟9/9。完整架构首跑605项603通过2失败，`test_coverage_tool_runs_on_bundled_interpreter`（governance新脚本误入覆盖率模块计数，已同步coverage_report.NON_PRODUCT_PARTS并定向1/1通过）；`test_round_number_continuous`（项目状态页3784对现有结果号不连续，仅master可提交，最终合并轮处置）。正式全量还未运行，当前不宣称全绿。
3. 欠账：文档双入口和账户重复现行设计已消除；账户API /v1/metering 明确标未实现；目录治理基线五项旧违规消除。完整架构剩状态轮次红、GUI受影响及正式全量留最终合并候选闭环，不伪称完成。

## 输入与迁移范围

- 本车道基点839ef93a；R3819诊断、R3820退役候选、R3831退役补足、R3830治理结构、R3832账户全文吸收已逐轮提交/接收。R3836为独立迁移轮。
- 本轮通过显式映射执行 `git mv` 24项、合并删除2份重复文档（旧账户设计、旧更新记录）；`docs/records/document-migration.json`记录26项old/new、迁前/迁后摘要。台账自身是派生索引不自引用哈希。
- `说明/` 退出；PRD在docs/requirements；流程、契约、指南、历史与登记归入docs对应职责。review里三份一次性记录归records、两份历史任务归tasks_round；四份高危时序评审留review。
- 账户设计全文实质条款进入docs/specs/07 §7.9，D1–D16、D11b、Q1–Q8状态见账户设计条款迁移映射。旧39/99/399明确为历史，用户确认现价19/49/189；当前两端无/v1/metering，计量仍是需求而非已上线功能。两端源码只读核验，无线上验证。
- 演示项目三文件从旧说明/示例整体迁到resources/examples/rainy_umbrella；UI入口、test_projects与分发清单同步。包内失败处理指南仍keep，开发文档/governance排除，真实构建plan `keep=3`示例、`undecided=0`。
- 文档登记脚本迁至docs/records单一输入，扫描root/docs/governance；新增重复现行权威主题检测与test_doc_registry_migration 4条；快照82份一致。
- 目录协议旧债身份保持原始基线；`--check`：新增违规0、已消除5、存量旧命名1；手工临时Git测试证明等量置换不能绕过。
- docs/README是唯一工程文档导航；现行有效链接按旧文件原地址解析后更新，历史轮次与维护历史正文不批量修改，追溯由迁移台账保留。
- 根标准入口仍由现有权威控制，不复制文档全文。`legacy/`无经验证的可迁入退役对象所以不建空目录；reference/HoLLMwood为gitlink未移动，h3_launcher仍是本机工具不冒充退役。

## 已实测

| 操作 | 结果 |
|---|---|
| 迁移前业务消费基线 `run_selftests.py -k distribution_build projects version_record --safe` | 23条全通过 |
| 迁移后registry `doc_registry.py --check` 与快照生成 | 82份通过，路径与字段双向一致 |
| docs活跃67份Markdown链接审计 | 迁移前九处已定位修复，最终0断链（账户旧来源只在追溯表） |
| 结构+登记+文档预算+覆盖+分发+项目+版本+任务书定向 | 74条通过、0红 |
| 退役补充 `-k builtin_controller_retirement script_preparation_roles req_s05_anchors` | 18条通过、0红 |
| 默认 `smoke_test.py` | 业务8+隐藏探针1=9/9 |
| `smoke_test.py --architecture` 首跑 | 605条；覆盖工具计数673≠672与status3784≠3833两红；前者修复后单测1/1绿，后者不能在分支提交状态页 |
| `distribution_build.plan(root)` | 示例三文件keep，包内指南keep，docs/governance排除，undecided=0 |

## 范围和后续

- `project_status.md`曾在本轮迁移工具中仅更新两处历史链接，已在功能分支精准 `git restore -- 程序/project_status.md` 恢复；仅master合并轮负责改轮次头和现行引用。主树有其他会话未提交改动，本轮不碰主树。
- `tests/architecture/_scan`与`coverage_report.NON_PRODUCT_PARTS`均将governance归开发工具，不能通过扩大产品覆盖基线掩盖误计。
- 本轮代码、资源和文档同一提交；最终全量/GUI绿凭据尚未获得，不能宣称任务书完成。下一轮必须用真实合并候选修状态编号并跑全量，再更新《任务完成》文件后合master。
