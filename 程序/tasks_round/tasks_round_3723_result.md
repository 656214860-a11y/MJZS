# R3723：A13 存储维护入口迁移与清退收口
<!-- round-evidence: {"commit_base": "d61203fe", "credential_hits": 0, "evidence_sha256": "04a3b979d61b33f4", "exit": 0, "failed": 0, "passed": 20, "round": 3723, "tests": "run_selftests.py -k storage"} -->

## 三问

1. 类型：AGENTS §3.3 结构治理轮；仅迁移一个生产入口，保留有外部兼容责任的旧门面，不做逻辑重构或测试搬家。
2. 验证：改前新契约 1 红；改后消费者拆分回归 121/121、默认冒烟 9/9。完整架构 601/605，失败集合与 A12 相同四项，未新增失败。
3. 欠账：生产自调用已不依赖顶层脚本；旧扁平补丁/CLI 门面仍保留，退出条件已写入源码与架构映射。A13 没有证据充分的其他删除项。

## 变更与新旧映射

| 对象 | 旧入口 | 新入口 | 兼容处置 |
| --- | --- | --- | --- |
| 退出后存储清理子进程 | `python <程序>/storage_maintenance.py --cleanup` | 在程序目录执行 `python -m infra.storage_maintenance --cleanup` | 生产消费者已迁移；顶层文件继续转发旧外部 CLI，并维持 `sys.modules` 身份与扁平 `mock.patch` |

改动范围：`infra/storage_maintenance.py`、`storage_maintenance.py`、`tests/test_storage.py`、`architecture.md`。没有改删除语义、回收清单、用户路径、注册表或分发排除规则；`cwd=program` 保证包入口在分发程序根可解析。

## 删除与保留结论

- 删除文件：0。R3722 复核确认 D01—D05、D07—D13 仍有生产、CLI、外部进程、宿主复制或兼容责任。
- D06 顶层门面：本轮仅消除生产自调用。退出条件为：仓内扁平导入/补丁路径全部迁移、外部 CLI 完成弃用窗口、发布清单不再承诺旧入口，并以独立可回滚轮验证；条件未满足前删除属于破坏性变更。
- 测试搬家：0；生成缓存清理：0；用户项目、模型、ASR venv、私有配置：未扫描、未修改。

## 测试证据

- 红测：`tests.test_storage -k launch_cleanup` 在实现前按预期失败，实际命令仍指向顶层脚本。
- 改后定向：storage 20/20、exit_maintenance 5/5、force_quit 17/17、critical_chains 17/17、asset_resume 14/14、asset_batch_retention 5/5、layers 匹配组 43/43，共 121/121。
- `smoke_test.py`：9/9。
- `smoke_test.py --affected infra.storage_maintenance`：前置冒烟 9/9；自动扩展 212 个文件后在 GUI 隐藏批次 900 秒超时，日志未出现断言红。未原样重跑超时集合，改按真实调用链拆组并全部通过。
- `smoke_test.py --architecture`：605 条，601 通过；四项与 A12 完全相同：缺 `维护记录/基准历史.json`、共享解释器多 7 个未登记包、`project_status.md` 轮次未同步、缺 `screenplay-gate-engine.md`。这些在 A14/A17 最终候选统一收口，本轮不伪造夹具或改 feature 分支状态页。
- 完整安全全量：未运行；本轮尚非 master 合入点，最终按 A16/A17 在最终内容树执行。

## A13 验收

- [x] 实际迁移有新旧映射与消费者回归；可疑项有退出条件。
- [x] 没有把纯搬家混入逻辑改写，没有搬测试或误清用户内容。
- [x] 不以删除数量作为成果；当前证据只授权生产入口迁移，不授权删除兼容门面。

A13 完成，可以进入 A14 文档与 skill/Git/测试管理收口。
