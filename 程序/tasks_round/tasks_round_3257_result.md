# R3257：将漏分的soak性能预算测试放入既有独占性能队列
<!-- round-evidence: {"commit_base": "e3ae52d5", "credential_hits": 0, "evidence_sha256": "8924d9f14989ae35", "exit": 0, "failed": 0, "passed": 69, "round": 3257, "tests": "run_selftests.py -k selftests soak_light"} -->

## 三问

1. 类型：修复轮；根因为测试调度分类，不改产品代码、性能阈值或soak断言。
2. 验证：新增分类行为测试先红后绿；正式run_selftests.py -k selftests soak_light共69条、15.0秒、0红/0skip，日志明确先普通池、后soak独占12.3秒。主树最近完整回归0838f1ed：8493条、1022.8秒、3文件红；其中distribution缺项已R3256合入修复，性能soak/asset边界需一致低负载复验。本轮未提前标全量绿。
3. 欠账：解决soak在普通池与tracemalloc并行引发耗时预算失真的分类遗漏；保留既有性能门槛，最终主树完整凭据仍需收口。

## 根因与两文件改动

selftest_discovery.split_performance_units只认test_perf前缀或selftest_env.PERFORMANCE_MODULES。test_soak_light启用tracemalloc且有每轮10秒预算，却未列PERFORMANCE_MODULES，故与大量普通测试并行，反复出现13–22秒预算红；串行定向已经绿。selftest_env.PERFORMANCE_MODULES仅增加test_soak_light，使它复用现有“等并行池退出再测”机制，无新增调度器。

新增tests/test_selftests.py行为测试：普通/性能顺序、输入未变、所有unit对象完整且无重复、soak分片同入性能池。原集合其它项和断言不变。先红时soak仍在normal，改名单后绿。

## 当前交付与主树状态

R3249主体、R3253两P2修复、R3256分发缺项均已标准队列合入。主树requests已备份后升级到锁版2.34.2，15条依赖门禁、9项冒烟绿。候选持久包保存在Git common-dir/deliverables（原.agents/deliverables已移出以保持源码干净），zip152625323字节，SHA256 c1366c9c1bf51c3d1b513d16e6ca36e9a86c6fd6de8781842780ef9274101799；生产0838f1ed与之后仅文档/运行器改动无产品差异。

最近e3ae52d5 --gui-jobs1全量已确实观察soak失败（旧分类），继续耗时不可能产绿；本会话按锁PID52408核实后停止自己已红进程树，不触他人锁；保留full-main-r3256-interrupted-red.log，不计通过。中断时内置SKILL测试夹具处于临时搬移态：仅恢复该测试已删的受控pipeline/short-drama-storyboard文件，从本功能树已核验资料副本还原gitlink AIGC内容，移动测试临时副本到common-dir证据，未删除用户数据；主树受控状态已恢复干净。此中断不作为任何绿色凭据。

## 验证命令与提交

UTF8=1，随附主树Python，在本功能树程序：

`run_selftests.py -k selftests soak_light`：3文件/6单元，69条全通过，实际0skip；完整输出common-dir/requests-migration-evidence/r3257-runner-soak.txt。

git diff --check通过。提交经dev.py commit生成证据，hash以git log/evidence/R3257.json为准。下一步合入本调度修复，在干净主树执行一次最终 --all --safe，全部通过后才写任务完成文件和正式完成声明。
