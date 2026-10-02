# R563｜结构治理轮（子场景：执行）

## 开工核对

- 本轮性质：整理轮（结构治理执行），不增加用户功能。
- 测试已运行：相关单测、默认冒烟与架构门禁均通过；三个基线为默认冒烟 8/8、架构门禁 98/98、全量安全自检历史基线 3,230 条（本轮未重跑全量）。
- 欠账已减少：R182 可执行拆分债务由 6 项减至 5 项；P0-3 的既有阻塞不变。

## 来源与执行项

- 来源：`tasks_round/tasks_round_547_result.md` J 节。
- 执行：P2-3——定义文件发布、回收、外部覆盖后的缓存失效事件，替代页面各自刷新或被动依赖 mtime 的做法。

## 完成结果

- `file_cache.py` 成为缓存失效唯一权威：`published(path)`、`recycled((source, target), ...)`、`externally_overwritten(path)` 三个命名事件均通过同一私有缓存清除原语，同时逐出该路径的 JSON、文本（全部编码变体）与字节缓存。
- `agent.core.replace()` 与 `save_bytes_new()` 仅在原子发布实际成功后触发 `published()`；失败、锁冲突重试未成功时不发事件，既有原子写/回滚语义未变。
- `storage_maintenance.recycle_paths()` 和 `restore_recycle_batch()` 只在移动事务成功后触发 `recycled()`，来源、回收站/恢复目标两侧缓存同时失效。没有让页面以“重建/刷新”承担文件一致性。
- 直接由外部程序或未迁移适配器覆写文件时，调用方须在覆写成功后调用 `externally_overwritten(path)`；原有 stat/mtime＋内容哈希检查保留为尚未迁移旧调用的正确性兜底，不再是 UI 一致性主机制。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `file_cache.py` | 新增三类语义化失效事件及逐路径、逐表示缓存清除。 |
| `agent/core.py` | 原子替换和原子新建发布成功后发送发布事件。 |
| `storage_maintenance.py` | 受控回收与恢复成功后发送双路径回收事件。 |
| `tests/test_file_cache.py`、`tests/test_core.py`、`tests/test_storage.py` | 新增事件原语、原子发布和回收/恢复双路径失效回归；测试是在新增内部边界下补覆盖，既有断言未弱化。 |
| `smoke_test.py` | 补齐 `storage_maintenance → storage` 的历史测试文件映射，避免定向验证漏跑回收/恢复用例。 |
| `architecture.md`、`project_status.md` | 同步 L1 缓存失效边界、轮次和债务状态。 |

应用代码仅改动 3 个模块，符合本轮上限；既有分层、文件格式、页面、用户数据和对外接口不变。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_file_cache tests.test_storage`：31/31 通过；`tests.test_core.AgentCoreTests.test_atomic_publish_emits_cache_invalidation`：1/1 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_file_cache tests.test_storage tests.test_core`：137 条中 136 通过；唯一失败是既有 `tests.test_core.ProjectsEngineTests.test_prepare_task_brief_uses_project_title` 缺少随包编剧 SKILL（`writing.py:44`），与本轮缓存改动无关，因此未将该混合集合作为验收。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected file_cache storage_maintenance`：4 个工作单元、31 条通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py`：默认冒烟 8/8 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --architecture`：98/98 通过，无新增红点。

## 债务状态与自审

- P2-3 已完成；文件生命周期写/移边界的缓存一致性不再由页面各自刷新负责。P0-3 的二进制成果发布/分层阻塞仍待用户选择，不受本轮影响。
- 未新增功能；缓存格式和对外读取接口不变；事件只在文件操作完成后执行，失败时不会过早清空可用缓存。
