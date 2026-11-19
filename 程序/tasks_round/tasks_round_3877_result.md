# R3877 修复轮：退役最终验收的检查点产物与接力测量隔离
<!-- round-evidence: {"commit_base": "0d2ede1f", "credential_hits": 0, "evidence_sha256": "c3a71d69b07a85ec", "exit": 0, "failed": 0, "passed": 38, "round": 3877, "tests": "run_selftests.py -k distribution_selfcheck root_layout ui_edges_autopilot"} -->

- 类型：§3.2 修复轮（含全量验收闭环）；只处理阻断本任务验收的已复现前置条件。
- 测试：上一集成树完整安全诊断9383条、1261.1秒、3文件红（分发2、根布局1、自动链1），退出1、无绿凭据；本轮定向正在执行，未预写通过。
- 欠账：总控退役实现与R3860已提交，但合入和任务完成文件尚未完成；本轮闭环后重跑最终全量。

## 根因与最小变化

1. 上游`f583e096`检查点把4份账户文档验证脚本/结果放入根`.agents`，又把全量结果与历史JSON放入`程序/`。`test_root_layout`精确报`.agents`未登记；分发自检精确报`auto-full-safe-result.json`和`full-safe-history.jsonl`未决定。不得为它们扩根白名单或放宽分发边界。
2. 先在Git公共目录rescue按原字节备份6文件，逐一验证SHA-256；再在本分支`git mv`到现有`tasks_round/evidence/R3877_checkpoint_artifacts/`，保留原相对路径、全部内容和来源manifest。合计45181字节，不删除历史证据、不改主工作区或其他会话。归档脚本不再作为生产入口执行。
3. 自动链用例原`for tick in range(400)`每10ms空轮询，将后台图片解码/磁盘复制耗时计为接力轮数，完整树中出现91而断言60。主干原阈值60保留，六阶段真实产物、调用顺序、工作集路径、状态文案、幂等断言全部保留。本轮只在后台busy且所有结果队列为空时等待结果可消费，每步15秒硬上界；队列就绪后仍由真实主线程`_tick_once`推进，接力轮数仍须小于60。不改程序节流、并发、执行器或完成判断。

## 验证与恢复

- 定向命令：`run_selftests.py -k distribution_selfcheck root_layout ui_edges_autopilot --jobs 1 --gui-jobs 1`，真实隐藏桌面，38/38、116.9秒、0skip、退出0。日志`logs/R3877_targeted_utf8.txt`。
- 全量命令仍必须使用原安全全量入口与真实锁，不用白名单/skip掩盖失败。
- 归档清单：`tasks_round/evidence/R3877_checkpoint_artifacts/manifest.json`；原始副本同时保留Git公共rescue，不随分发。
- 回滚以本轮实际提交`git revert`；最终提交号待提交后补。
