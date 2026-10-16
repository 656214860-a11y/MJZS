# 当前验证索引

## 最近正式全量
R1605：HEAD e59e5136e2992ae18832d05083ab56bb75416242，5346项、410个测试文件、0红，测试615.7秒/执行器631秒。程序/logs/auto_full_safe.log显示ALL TESTS PASSED与凭据刷新；common-dir/full-safe-receipts.json为权威。后续文档提交7b49faf，不声称修改中的R1606同树全量通过。
R1604首次全量5345项4失败且测试输出污染，已由R1605闭环；不能引用首次失败作为当前未修复。

## 当前R1606
- `.wt/architecture-assessment/程序/outputs/r1606-targeted.log`：独立页面及既有交付路径7项通过，0.625秒。
- 同目录 `outputs/r1606-architecture.log`：`python -B smoke_test.py --architecture`已退出1；345项176.231秒，2失败：test_round_number_continuous（1606 != 1607）、test_keyword_comments_match_the_reviewed_snapshot（desktop.py行号1203→1206）。默认冒烟未确认独立完成，接续时单独跑8项。
- 本轮没有再跑全量；只改两个产品模块的服务注入，未改Tk销毁/重建。

## 已完成修复验证
R1605：发布兼容/恢复16项、队列6项、资产关闭1项、启动零递归1项通过；宠物原17项和新增单项修复后通过；受影响回归及8项冒烟通过；主干轮次5项通过。详见[报告](../程序/tasks_round/tasks_round_1605_result.md)。
O1–O11各轮证据见R1597–R1604报告；旧验证索引见[归档](history/r1606-handoff-before/validation.md)。8项真实验收未执行，不由模拟或全量测试替代。

## 本次交接检查
主树文档与轮次一致性19项通过（3.582秒）；7个更新文件已复读，当前交接链接有效，4份旧文档保留归档。日志程序/outputs/r1606-handoff-check.log。此结果不消除工作树R1606的2项失败。
