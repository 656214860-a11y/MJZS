# 当前验证索引

## 最近正式全量
R1605：HEAD e59e5136e2992ae18832d05083ab56bb75416242，5346项、410个测试文件、0红，测试615.7秒/执行器631秒。common-dir/full-safe-receipts.json 为权威。

## 本次接续四轮（均只跑定向 + 架构门禁 + 默认冒烟）
- R1606（O8）：架构345项164.456秒 OK、冒烟8项通过。
- R1607（O9）：定向 tests/test_seedream_direct.py 22项、架构345项165.697秒 OK、冒烟8项通过。
- R1608（O10）：定向 tests/test_media_publish_streaming.py 3项与受影响回归通过、架构345项165.908秒 OK（首次第四项债务标识因行号下移失配，已同步 point 217→250）、冒烟8项通过。
- R1609（O12）：定向 tests/test_usage_overview.py 11项、架构345项163.673秒 OK、冒烟8项通过。

日志：程序/outputs/r1606-*.log、r1607-*.log、r1608-*.log、r1609-*.log。四轮均未跑全量，不冒称同树全量。

## 未执行
8项真实验收仍按用户延期处理，不由模拟或全量测试替代。历史索引见 [归档](archive.md)。
