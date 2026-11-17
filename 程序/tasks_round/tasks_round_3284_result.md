# R3284 结果：L2领域服务层优化任务书轮3（修复轮：三模块并发缓存 RLock 加锁）
<!-- round-evidence: {"commit_base": "8f5a1414", "credential_hits": 0, "evidence_sha256": "8112162b332a73b8", "exit": 0, "failed": 0, "passed": 371, "round": 3284, "tests": "run_selftests.py -k domain_cache_locks white_model idea video_task_state"} -->

## 三问

**1. 本轮属于 §3 哪种类型？**
§3.2 修复轮。任务书轮 3 预设「3 处并发缓存加锁」：`white_model_service` 六个模块级缓存、`idea_transcript._history_cache`、`video_task_state._OTHER_ACTIVE` 的 get/set/clear/move_to_end/popitem 复合序列全部纳入 `threading.RLock` 临界区，并补 `_reset_caches()` 测试重置入口。先红后绿：新增 `tests/test_domain_cache_locks.py` 三个并发用例，改前 3/3 必红（KeyError/IndexError），改后全绿。不改分层、不改签名、不改返回值。

**2. 测试跑了吗、三个基线过了吗？**

| 基线 | 结果 |
| --- | --- |
| 先红（加锁前） | **红**：`python -B tests/test_domain_cache_locks.py` → Ran 3 tests in 63.716s，FAILED (failures=3)：white_model 5×`KeyError(white_model_settings.json)`、idea_transcript 1×`KeyError(chat/c17.json)`、video_task_state 5×`KeyError(_OTHER_ACTIVE 键)`；补跑白模单类另见 `KeyError('X:\\Blender\\blender_2.exe')`（`_VERSION_CACHE`）与 `IndexError`（`_BLENDER_CACHE[0]`） |
| 转绿（加锁后） | **绿**：同文件 Ran 3 tests in 11.126s，OK |
| `run_selftests.py -k domain_cache_locks white_model idea video_task_state` | **绿**：27 个测试文件 / 42 条路由 / 371 条用例 ALL TESTS PASSED（136.1s，含隐藏桌面 GUI 用例；`test_domain_cache_locks` 3 条 13.2s） |
| `smoke_test.py --affected white_model_service idea_transcript video_task_state` | **绿**：定向 39 个测试文件 ALL TESTS PASSED（152s 0 红）＋冒烟检查 10/10 |
| 默认冒烟 `smoke_test.py` | **9/9 通过**（8 项本轮检查＋隐藏桌面 `--probe`，exit 0） |
| 架构门禁 `--architecture` | **未单独运行**——§3.2 修复轮不触发 §5「结构治理／跨层」门禁；`--affected` 定向已含相关边界门禁（`architecture.test_white_model_*_boundary`、`test_idea_attachment_publication_boundary`、`test_service_return_contract`、video/previs 各 boundary），全部通过 |
| 全量回归 `--all --safe` | **未运行**——功能分支开发轮，全量按 §5 由合入 master 前触发；如实标注 |

**3. 欠账少了吗？**
减少。任务书 §2.4 点名的 3 处「模块级缓存无锁、满即 `clear()`，并发读会得到空结果或 `KeyError`」全部消除：`_SETTINGS_CACHE`/`_VERSION_CACHE` 的 `in`→`[]`、`_BLENDER_CACHE` 的「判空→取首元素」、`_history_cache` 的「命中→move_to_end」与「写入→淘汰」、`_OTHER_ACTIVE` 的「set→按键回读」五处真实竞态窗口（均有改前红证据）现已由锁内原子序列覆盖。`contract/storyboard_paths.py` 的 `_RESOLVED`/`_LISTINGS` 两个未保护缓存不在本轮范围，已记录为后续观察项。

---

## 改动与锁点清单

只 `import threading`，无新依赖；锁名模块私有；不改任何函数对外签名与返回值。计算（JSON 读、路径 resolve、Blender 探测、状态文件签名）一律在锁外，避免把 IO 拖进临界区；锁均为 `threading.RLock`（可重入，模块内函数互调安全）。

### `domain/white_model_service.py`（+`_CACHE_LOCK`，覆盖全部六个缓存）

| 位置 | 锁内序列 |
| --- | --- |
| `_base()` | `_BASE_CACHE.get(key)` 锁内；miss 时 `project_identity`+`resolve` 锁外；`len>=1024→clear()`+`set` 锁内 |
| `read_settings()` | `not refresh and key in _SETTINGS_CACHE → return _SETTINGS_CACHE[key]` 判定＋取值同锁内（原 `in`/`[]` 两步分离是 KeyError 源）；`_json_quiet` 锁外；`len>=256→clear()`+`set` 锁内 |
| `workspace()` | `_WORKSPACE_CACHE.get(key)` 锁内；`target.resolve()` 锁外；`clear()`+`set` 锁内（clear+set 为原子对，保持「只留最新」语义） |
| `find_blender()` | `if _BLENDER_CACHE and not refresh → return _BLENDER_CACHE[0]` 判空＋取下标同锁内（IndexError 源）；`blender_candidates()`+`is_file()` 锁外；`_BLENDER_CACHE[:] = [result]` 锁内 |
| `blender_version()` | `key in _VERSION_CACHE → return _VERSION_CACHE[key]` 锁内；`run_process` 子进程（timeout≤15s）**必须**锁外；`len>=64→clear()`+`set` 锁内 |
| `shot_directory()` | `_DIR_CACHE.get(key)` 锁内；`root.resolve()` 锁外；`len>=1024→clear()`+`set` 锁内（仅 `resolved == root` 时写入，口径不变） |
| `migrate_legacy_directories()` | 收尾 `_BASE_CACHE.clear(); _DIR_CACHE.clear()` 改为同一把锁内原子执行 |
| `_reset_caches()`（新增） | 锁内依次 `clear()` 六个缓存，供并发回归与单测隔离使用；测试「清空」侧优先走此入口 |

### `domain/idea_transcript.py`（+`_HISTORY_CACHE_LOCK`）

| 位置 | 锁内序列 |
| --- | --- |
| `_read_rows()` stat 失败分支 | `_history_cache.pop(path, None)` 锁内 |
| `_read_rows()` 命中分支 | `get(path)`→fingerprint 比对→`move_to_end(path)`→返回行拷贝，同锁内（原 `move_to_end` 可在并发 `popitem` 后对已淘汰键抛 KeyError） |
| `_read_rows()` 未命中写入 | `set`→`move_to_end`→`while len>_HISTORY_CACHE_LIMIT: popitem(last=False)` 淘汰循环整体锁内；`gateway['read_json']` 与 `ensure_parts`/`has_content` 行处理锁外 |
| `save_rows()` | `set`→`move_to_end`→淘汰 while 锁内；`except OSError: pop(path, None)` 锁内 |
| `_drop_rows()` | 每个改写文件发布后 `_history_cache.pop(path, None)` 锁内 |

### `domain/video_task_state.py`（+`_OTHER_ACTIVE_LOCK`）

| 位置 | 锁内序列 |
| --- | --- |
| `_other_active_ids()` 命中 | `_OTHER_ACTIVE.get(key)`→`hit[0]==signature` 比对→`return hit[1]` 同锁内 |
| `_other_active_ids()` 写入 | `len>64→clear()`→`set`→`return _OTHER_ACTIVE[key][1]` 同锁内（原 set 与按键回读之间可被并发 clear 插入 → KeyError）；`config_listing`/`file_signature`/`read_cached` 等签名与状态文件 IO 全部锁外 |

## 并发用例设计（`tests/test_domain_cache_locks.py`，3 条）

- 竞态窗口用「让出 GIL 的测试替身」确定性放大：`_TrapContainsDict.__contains__`（命中后 sleep 0.5ms）、`_TrapBoolList.__bool__`（判空为真后 sleep）、`_TrapHistoryCache.move_to_end/popitem`（执行前 sleep）、`_TrapSetDict.__setitem__`（写后 sleep）。加锁前对端 clear/淘汰必然插入临界区；加锁后被同一把锁挡住，故先红后绿可复现。
- `WhiteModelCacheLockTests.test_concurrent_reads_and_resets`：6 worker × 350 迭代混合调 `read_settings`/`blender_version`/`workspace`/`find_blender`/`shot_directory`（六缓存各自的真实公开入口），2 个 clearer 线程走 `_reset_caches()`（改前回退裸 `clear()`）高频清空；断言无异常、命中类型正确、清空后可重建、各缓存不超上限（256/64/1024/1024/1/1）。
- `IdeaTranscriptCacheLockTests.test_concurrent_reads_writes_and_evictions`：4 reader × 800 迭代 `_read_rows`（20 个真实聊天文件 > `_HISTORY_CACHE_LIMIT=16`，命中→move_to_end 与 LRU 淘汰持续发生，含 stat 失败 `pop` 分支）＋2 writer × 300 迭代 `save_rows`（真实 `agent.core.save` 原子发布）；断言返回 list、缓存 ≤16、清空后可重建。
- `VideoTaskStateCacheLockTests.test_concurrent_other_active_ids`：6 worker × 600 迭代真实 `_other_active_ids()`（200 个 own_root > 64 上限，内部 clear 持续触发）；断言返回 frozenset、缓存 ≤65（64 上限＋1 口径）。
- **测试替身说明**：白模用例对叶子 IO 口打桩——`blender_candidates`→固定候选、`_json_quiet`→`{}`、`project_identity`→`None`、`blender_version(run=...)` 注入假 `run_process` 输出。原因：`read_json→agent.publication.access()` 内是 `msvcrt.locking` OS 文件锁，并发全 miss 下每个 miss 串行排队，实测首次跑 63.7s 仍在收集 KeyError；打桩后 miss 路径只剩纯缓存复合操作（被测对象），竞态依旧确定复现。缓存 get/set/clear/move_to_end/popitem 全部走被测模块真实代码；`project_identity` 打桩先例见 `test_white_model_workspace.py`。清空侧补 1ms `sleep` 防两个空转线程抢 GIL（实测不补时 worker 每迭代被拖慢约一个数量级）。idea/video 两例不用桩，走真实文件与真实函数路径。

## 先红后绿证据

加锁前（`tests/test_domain_cache_locks.py` 定稿后、三个 domain 文件未动）：

```
FAIL: WhiteModelCacheLockTests.test_concurrent_reads_and_resets
    并发操作抛出异常（5 条）：
    race-5/4/2/3/1: KeyError('...\\cfg\\white_model_settings.json')
    （read_settings 的 `key in _SETTINGS_CACHE`→`_SETTINGS_CACHE[key]` 之间被 clear 插入）
FAIL: IdeaTranscriptCacheLockTests.test_concurrent_reads_writes_and_evictions
    并发操作抛出异常（1 条）：
    race-2: KeyError(WindowsPath('.../chat/c17.json'))
    （命中→move_to_end 窗口内被并发 popitem 淘汰）
FAIL: VideoTaskStateCacheLockTests.test_concurrent_other_active_ids
    并发操作抛出异常（5 条）：
    race-0/1/2/3/5: KeyError((project, own_root, source) 元组)
    （`_OTHER_ACTIVE[key]=(…)` 与 `return _OTHER_ACTIVE[key][1]` 之间被 clear 插入）
Ran 3 tests in 63.716s — FAILED (failures=3)
```

补跑白模单类（清空侧未限速版）另捕获 `KeyError('X:\\Blender\\blender_2.exe')`（`_VERSION_CACHE` 的 `in`→`[]`）与 `IndexError('list index out of range')`（`_BLENDER_CACHE` 判空→`[0]`）——五处竞态向量全部有红证据。

加锁后：同文件 `Ran 3 tests in 11.126s — OK`；`run_selftests.py -k domain_cache_locks white_model idea video_task_state` 27 文件 371 用例 ALL TESTS PASSED。

## 验收对照（任务书轮 3）

- [x] 多线程并发读写用例：写入×命中 `clear()` 交错不得出现 `KeyError` 或空结果——改前 3/3 必红（KeyError×11、IndexError×1），改后 0 异常
- [x] 三模块各自用例绿——`test_domain_cache_locks.py` 3 条全绿；既有 `test_white_model_workspace`/`test_white_model_identity`/`test_white_model_ref`、`test_idea_chat_remove_restore`/`test_idea_chat*`、`test_video_task_state_cache`/`test_video_task_status` 全部回归通过
- [x] `smoke_test.py --affected white_model_service idea_transcript video_task_state` 绿——定向 39 文件 0 红＋检查 10/10

## 实测基线

- 默认冒烟：`python -B smoke_test.py` → 通过 9 项 / 失败 0 项（8 项检查＋隐藏桌面探测）。
- 定向自检：`python -B run_selftests.py -k domain_cache_locks white_model idea video_task_state` → 27 文件 / 371 用例 0 红（136.1s）。
- 受影响门禁：`python -B smoke_test.py --affected white_model_service idea_transcript video_task_state` → 定向 39 文件 ALL TESTS PASSED（152s）＋检查 10/10。
- 架构门禁：未单独跑 `--architecture`（见三问第 2 行）；`--affected` 内架构边界用例全绿。
- 全量回归：未运行（见三问）。

## 偏差与说明

1. **白模用例的 IO 替身**：如上「并发用例设计」所述，对 `blender_candidates`/`_json_quiet`/`project_identity`/`run_process(run=)` 打桩以避开 `access()` 的 OS 文件锁串行化；被测缓存复合操作全部真实执行。此为测试性能处理，不改变被测语义；先红证据在打桩后版本上重新取得（63.7s FAILED），与实现无关。
2. **`_reset_caches()` 为新增模块私有入口**：任务书要求「补 reset 入口供测试」，命名按任务书口径；仅测试与本模块内部使用，不改公开 API。
3. **双检式加锁**：miss 分支的计算（读 JSON、resolve、子进程）放在锁外、set 段在锁内——并发 miss 最多重复计算同值（幂等），换取不把 IO/子进程拖进临界区；`blender_version` 的 `run_process` timeout≤15s 若在锁内会把全部缓存访问阻塞秒级，已刻意置于锁外。
4. **未动**：`L2领域服务层优化任务书.md`（含外来勘误改动）、`project_status.md`（仅 master 可提交）、R3276 外来未跟踪三件（诊断报告/结果文件/任务书）一律不入暂存区。
5. **范围外观察项**：`contract/storyboard_paths.py` 的 `_RESOLVED`/`_LISTINGS` 模块级缓存同样无锁，但属 L0 契约层、不在本轮三模块范围内，记录待后续轮次评估。

## 遗留欠账

- `storyboard_paths._RESOLVED`/`_LISTINGS` 无锁缓存：范围外，待立项评估（L0 契约层改动需契约轮流程）。
- 并发用例的 trap sleep 为 0.5ms 量级，依赖 GIL 释放时序；在带自由线程（no-GIL）Python 上放大机制可能失效——当前运行环境为标准 GIL 构建，用例有效。
- 分支侧历史架构红（R3275/R3282 已记录的 2 条存量失败）与本轮无关，未触碰。

## 提交

- 分支 `codex/wip-r3282`（领号 R3284，工作树 `dsh-864fd932-4054`；`round_claim.py` 因 GBK 解码环境问题不可用，经 `.git/round-claims.json` 核实 3284 已登记本工作树，3285–3287 为其他车道）。
- commit：见 `git log`（代码＋测试＋结果文件＋轮次证据主提交）；本补记行由后续提交写入，不另占轮次。轮次证据以 `tasks_round/evidence/R3284.json` 为准。
- 全量回归：未运行（见三问）；合入 master 前按 §5 触发 `--all --safe`。
