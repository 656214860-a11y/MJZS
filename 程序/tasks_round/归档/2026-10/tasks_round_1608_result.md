# R1608 大媒体发布内存（O10）

类型：结构治理轮（执行）。来源：R1596 O10/P2，已授权依序优化。
范围：agent/core.py、stage_execution_service.py 两个产品模块；新增测试、architecture.md 说明与本报告。

## 改动与边界
agent.core.save_file(path, source, digest=None)：按块复制来源文件到目标同目录临时文件，复制期间计算 sha256 并核对来源长度，可选与调用方摘要比对，再走既有 replace（登记发布事务、缓存失效）。失败只清临时文件，旧成果不变。
collect_download_inbox 由 read_bytes 加 save_bytes 改为 save_file，并包在 publication.transaction() 内；空文件与读写失败仍跳过，目标保持待收回，不静默丢弃。
未改文本与既有二进制发布接口（publish_stage_text／publish_stage_bytes／publish_stage_bundle 语义不变）；未改下载匹配、台账字段与阶段权威。

## 验证
tests/test_media_publish_streaming.py 3 项通过：16 MiB 文件 save_file 的 tracemalloc 峰值小于 5 MiB；摘要不符时旧目标保持原字节；collect_download_inbox 收回 16 MiB 下载的峰值小于 5 MiB。
受影响回归通过：tests/test_download_inbox.py、tests/test_stage_execution_service.py、tests/test_publication_recovery.py。
架构门禁 345 项通过（165.908 秒）。首次运行时第四项债务棘轮因 core 插入新函数导致行号下移而失配，已按登记口径把 维护记录/架构统一基数.json 中 agent/core.py 的 point 由 217 同步为 250（同一条已登记豁免，未新增或隐藏债务）。默认冒烟 8 项通过。未跑全量，不冒称同树全量。

## 保留未知
真实播放器与编辑器的超大媒体实测、跨卷移动、磁盘满等外部条件未验证；峰值门槛是进程内 tracemalloc，不含操作系统页缓存与磁盘配额。
