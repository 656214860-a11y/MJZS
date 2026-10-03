# R977 防损可靠性轮：探针暴露 SG-01 既有红灯

[TASK_FAILED]。按用户“探针暴露既有红灯，记录并停下”要求停止。未实施生产修复，未弱化断言。

## 前置与范围

- 主树 master 起点 `7f98f5bcf26aba59879235cb8d0d5faf24e49db6`，任务 A 已合入；开工 git status 为空。
- `round_claim.py next` 领取 977，队列 reliability-loss-guard 由 Codex-guard 认领。
- 优先采用 TDD 技能的真实接口集成测试：临时 Git 仓库、临时项目、stage_parallel.evaluate、stage_completion_service.completion_evidence、storage_maintenance.recycle_paths/restore_latest_recycled_path。
- 探针不接受任何真实路径参数，只在自身创建的系统 TemporaryDirectory 中操作；没有使用程序/episode、private、data、logs 或真实用户项目。

## 发现与实测

命令：项目 Python 执行 `-m unittest tests.test_stage_gate_e2e_probe`。
结果：3 条，2 通过、1 失败，0.755 秒。

1. 空项目 SG-01→SG-05 均允许进入（ok=true、started=false），但完成核验均 false，符合既有“没开始不拦”契约。
2. 构造真实 68 字节 PNG 及锁定角色资产清单；删除前 completion=true。
3. 经 recycle_paths 回收图片：源文件存在=false、回收文件存在=true；然而 SG-01 gate_ok=true、completion=true。
4. finally 经 restore_latest_recycled_path 恢复，文件字节与原图一致；本次操作未生成上次关闭清理/全量凭据/增量缓存文件到项目中。此有限检查不代表全部运行数据边界已验收。

关键失败：`test_deleted_asset_cannot_be_certified_by_manifest_text`，`AssertionError: True is not false`。
CLI 探针输出同样的 findings 并返回 1。

根因证据：`stage_parallel.py:562-563` 的 missing 仅判定 image 字符串非空，未核验图片文件；`stage_completion_service.py:41` 直接采用该门禁的 ok 和 started，因此把已不存在的成果认作完成。清单仍留路径是刻意保留的失配场景，物理成果必须能独立复核。

## 未完成范围与三个基线

- 本轮默认冒烟：未运行（发现红灯立即停止）；最近主树实测 R970 为 8/8。
- 本轮架构：未运行；最近主树实测 R970 为 279/279。
- 本轮完整安全全量：未运行、不写新凭据；最近 R970 为 3816 条/0 红/312.476 秒。新增失败测试使内容树变化，不能以旧凭据宣称本轮通过。
- 未进行要求的综合定向全绿；探针定向明确 1 红。未执行 SG-02→SG-05 成果构造/凭据验收（只验证了它们的空项目行为）。
- 第 1—4 项（脏树诊断开关、凭据镜像归一、WIP 守卫、.gitattributes）均尚未实施；未并发改 run_selftests.py、round_claim.py 或 AGENTS.md；未做 renormalize。
- 本轮不修改生产逻辑解决 SG-01，须用户明确下一步；不把尚未实施的安全措施记为完成。

## 收尾

只提交探针、其测试、本报告和主树轮次状态，前缀 `R977-FAIL:`；不使用 git add -A，无备份文件。提交 hash 用 `git log -1 --format=%H --grep='^R977-FAIL:'` 定位，避免报告自引用改变内容树。
队列释放为 pending，留存 SG-01 阻塞发现，等待是否授权修复或拆分继续的裁定。
