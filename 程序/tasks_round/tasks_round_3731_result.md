# R3731：A14 文档、Skill 与测试管理收口
<!-- round-evidence: {"commit_base": "fa43dea8", "credential_hits": 0, "evidence_sha256": "3e9a4acca59cf209", "exit": 0, "failed": 0, "passed": 22, "round": 3731, "tests": "run_selftests.py -k skill_package_pins agents_md"} -->

## 三问

1. 类型：AGENTS §3.3 结构治理轮；修复可复现元数据、外部 Skill 包初始化与文档/测试事实口径，不改生产启动依赖。
2. 验证：A14 定向 215 条全绿，默认冒烟 9/9；完整架构 604/606，只剩共享解释器依赖污染和仅 master 可同步的状态轮次，改前四项红减少为两项。
3. 欠账：A14 范围内两项已清零；依赖环境隔离归 A15，`project_status.md` 按规则只在 A17/master 合入点同步。

## 根因与处置

| 问题 | 根因 | 处置与守卫 |
| --- | --- | --- |
| 新工作树 Skill 71≠73、00 包引用缺失 | 四个 mode 160000 gitlink 没有 `.gitmodules`；过去靠从主工作区临时复制，无法在干净检出复现 | 根目录新增四项 `.gitmodules` HTTPS 映射；父仓继续钉住 SHA；新门禁比较全部 gitlink 与映射集合，禁止孤儿 gitlink |
| `基准历史.json` 缺失导致架构门禁红 | 本机历史按设计被 gitignore，却被架构门禁当版本化输入 | 保留本机历史忽略策略；新增版本化脱敏快照 `维护记录/基准历史契约快照.json`；门禁只读快照；runbook 明确运行历史/门禁输入分离 |
| Skill 更新/停用/删除可能无统一闭环 | 需核对现状而非新造管理器 | 既有 `skill_registry`、`skill_lifecycle_service`、`skill_import_service` 已覆盖三层优先级、占用确认、停用、更新、回收和失败恢复；相关定向全绿，不新增第二套注册表或管理系统 |

## A14 验收映射

- 阶段扫描/注册/配置：`test_skills` 129/129，13 阶段集合与 73 个内置入口一致；注册解析 2/2、配置缓存 6/6。
- 更新/停用/删除：生命周期 20/20、导入校验与失败恢复 21/21、更新及删除台账 18/18。
- 外部包与引用：Skill 引用 9/9、固定提交/内容树/`.gitmodules` 7/7；四个子模块实际检出 SHA 与父仓一致。
- 文档事实：`test_agents_md` 15/15；本机生成历史和版本化快照分离；runbook 不再允许复制未跟踪目录补测试。
- Git/测试系统：沿用 `dev.py commit`、`run_selftests.py`、现有轮次证据和测试发现器；没有新增提交系统、规则台账或文档同步器。

## 完整架构与剩余项

`smoke_test.py --architecture`：606 条，604 通过。剩余两项不是 A14 可用“放宽门禁”解决的错误：

1. `test_site_packages_whitelist`：共享随附解释器多出 annotated-types、nvidia-ml-py、psutil、pydantic、pydantic-core、typing-extensions、typing-inspection；仓库生产锁与开发允许清单均未声明。A15 必须在隔离环境按生产锁验证，不能把共享环境污染加入白名单。
2. `test_round_number_continuous`：功能分支 `project_status.md` 仍为 3409；AGENTS 明确仅 master 可提交状态页，A17 合入时同步到最终结果轮次+1。

架构扫描已初始化的 AIGC 外部包时出现其上游 `check_package.py:2239` 无效转义 `SyntaxWarning`，不影响门禁结果；外部包固定提交不在本轮改写，A15 记录为供应链告警。

A14 完成，可以进入 A15 安装、更新及供应链核验。
