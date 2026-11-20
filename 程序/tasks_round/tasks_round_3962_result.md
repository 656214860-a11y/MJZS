# R3962 — 修复轮：两条发布测试在锁外摆事务目录，全量里偶发红
<!-- round-evidence: {"commit_base": "91d2d803", "credential_hits": 0, "evidence_sha256": "e4d2e4c9595ff523", "exit": 0, "failed": 0, "passed": 20, "round": 3962, "tests": "run_selftests.py -k test_publication"} -->

## 1. 三问

1. **轮次类型**：修复轮（测试夹具）。只改两条测试摆夹具的方式，断言和产品代码没动。
2. **测试跑了吗、三个基线过了吗**：改之前先用干扰线程量了失败次数，改完用同样的做法再量一遍（§3）。定向跑 `-k test_publication`，条数以本文件第 2 行的证据为准。没有跑完整全量；三个基线由合入时的出口检查跑。
3. **欠账少了吗**：主干全量里 `test_publication_fsync_budget` 的偶发红关闭。新记一条欠账：全量里是哪个测试单元留下了后台线程，没有查明（§4 第 1 条）。

## 2. 问题

**现象。** `.git/full-safe-history.jsonl` 记了 296 次全量（2026-11-15 至 11-20），`test_publication_fsync_budget` 红过 2 次：11-19 06:37（检出 `f82f40f3`）和 11-20 23:43（主干 `c6ae9f72`）。两次都是当次唯一的红。从第一次红算起共 10 次全量，红了 2 次。`git log -S` 显示这条用例随 `fbb56c29`（11-19 12:03）进入主干。

`c6ae9f72` 那次的报错：子用例 `state='pending'` 期望 `RuntimeError` 匹配 `旧版.*保留备份`，实际拿到「发布事务日志损坏，已停止读取以保护旧成果」，内层是 `agent/publication.py` `_recover` 里的 `ValueError: missing backup`。

**原因。** 两条用例都在发布锁外面手工摆事务目录：先 `mkdir`，再写备份文件和 `journal.json`。`agent/core.py` 的 `read()` 和 `replace()` 每次都进 `publication.access()`；`access()` 对事务根目录下每个 32 位目录跑 `_recover`，没有 `journal.json` 的目录按「还没登记或已提交」清掉。同一进程里只要有别的线程在这个空档读写任何 JSON，摆到一半的目录就会被清掉，或者只清掉一半：

- 备份文件被删，目录因为用例刚写进了日志而删不掉：恢复时报「日志损坏」。全量里的红就是这一种。
- 整个目录被删：用例写文件时 `FileNotFoundError`，或者恢复时什么都没有，报 `RuntimeError not raised`。

**产品代码不受影响。** 事务目录只在 `publication.transaction()` 里创建，创建到提交全程在 `access()` 的进程内锁和文件锁里面，别的线程和进程进不来。空档只存在于测试的手工摆放。

**全量里为什么会有别的线程。** `selftest_scheduling.run_units` 让非界面单元复用工作进程（`max_tasks_per_child=None`），前一个单元留下的后台线程会活到后面的单元里。具体是哪个单元留下的，没有查明。

## 3. 改动与验证

| 文件 | 改动 |
|---|---|
| `tests/test_publication_fsync_budget.py` | `test_legacy_journal_preserves_unverifiable_target_and_backup`：每个子用例从摆放到断言拿住 `publication._LOCK`（`with self.subTest(state=state), publication._LOCK:`），加两行注释 |
| `tests/test_publication_recovery.py` | `test_corrupt_journal_blocks_read_without_touching_target`：摆坏日志之前 `publication._LOCK.acquire()`，用 `self.addCleanup` 在用例收尾时放锁；加一行注释。只插入 3 行，原有的行没有动 |

`_LOCK` 是可重入锁，用例自己调用的 `core.save_text`、`recover_pending`、`file_cache.read_json` 照常进 `access()`。断言一条没改。按 `publication.ROOT / ` 和手写 `journal.json` 搜，全仓库手工摆事务目录的测试只有这两处（接手后重新搜过，结论相同）。

**第二处为什么用 `acquire` 加 `addCleanup`。** 上一个会话的写法是把那一段放进 `with publication._LOCK:`，要把 5 行往里缩进。提交时车道范围门禁拒绝（退出码 5）：活跃车道 `codex/l2-maturity-takeover` 改了同一条用例里的 `assertRaisesRegex` 那一行（加 `as caught`，后面加一条 `assertNotIn`），试合并有真实冲突。按门禁的提示错开改动位置：改成只在那一行上方隔 3 行的地方插入，不动原有的行。那条车道里 `_LOCK` 仍是 `threading.RLock()`，合到一起以后做法不变。锁因此拿到用例收尾，比原写法多盖住了删临时目录那一段。

**量法。** 一个一次性脚本（没有入库）：先不带干扰把两条用例各跑若干遍；再起一个后台线程不停地 `core.read()` 一个无关的 JSON 文件，同时把每条用例重复跑，按报错的最后一行分类。一遍可能同时落进几类，所以各类相加会超过遍数。

上一个会话量的（2026-11-21 00:09 前后，不带干扰 20 遍、带干扰 200 遍；第二处当时是 `with` 写法；当时主干的自动全量正在跑）：

| | 用例 | 不带干扰 | 带干扰 200 遍里全过的遍数 | 失败分类 |
|---|---|---|---|---|
| 改之前（`91d2d803`） | `fsync_budget` 那条 | 20/20 | 0 | 「日志损坏」对不上期望 69；`RuntimeError not raised` 122；`FileNotFoundError` 25；清理临时目录时的系统错误 2 |
| | `recovery` 那条 | 20/20 | 197 | `RuntimeError not raised` 3 |
| 改之后 | `fsync_budget` 那条 | 20/20 | 200 | 无 |
| | `recovery` 那条 | 20/20 | 200 | 无 |

- 「日志损坏对不上期望」就是全量里那次红的报错。
- 改之后那次，干扰线程读成功 3158 次、被拦 214 次，说明它一直在抢；改之前那次是 9551 次和 674 次。

接手的会话重量的（00:34–00:37，另写的脚本，不带干扰 10 遍；当时另一条车道的全量正在跑）：

| | 用例 | 不带干扰 | 带干扰全过的遍数 | 失败分类 |
|---|---|---|---|---|
| 改之前（主干 `75068bde`，两个测试文件与 `91d2d803` 相同） | `fsync_budget` 那条 | 10/10 | 1/100 | `RuntimeError not raised` 49；「日志损坏」对不上期望 46；`FileNotFoundError` 18；清理临时目录时的 `PermissionError` 2 |
| | `recovery` 那条 | 10/10 | 100/100 | 无（上表 200 遍里红 3 遍，这次没有撞上） |
| 改之后，第二处还是 `with` 写法 | 两条 | 各 10/10 | 各 100/100 | 无 |
| 改之后，第二处改成现在提交的写法 | 两条 | 各 10/10 | 各 200/200 | 无 |

最后一行那次干扰线程读成功 4139 次、被拦 102 次；改之前那次是 6418 次和 671 次。

## 4. 没做的事与已知边界

1. **没有查明留下后台线程的是哪个单元。** 按 `threading.enumerate`、`active_count` 搜，测试框架里没有线程泄漏检查，只有 `tests/test_leak_teardown.py` 一条用例用到。可行的查法：每个单元跑完记下还活着的线程名，或者按单元单独起进程扫一遍。两种都要把整套测试跑一遍，这一轮没做。
2. **还剩一种可能的偶发，只在 `fsync_budget` 那条。** 泄漏的线程如果在用例放锁之后、临时目录删除之前正好进了 `access()`，它会开着临时目录里的 `writer.lock`，Windows 上删临时目录可能报错。改之前的测量里出现过（两张表各 2 次），改之后的测量里没有出现；没有出现不等于排除。根治要靠第 1 条。`recovery` 那条的锁拿到用例收尾，没有这个空档。
3. **没有改产品代码。** `access()` 清掉没有日志的事务目录是设计（日志落盘前不替换任何目标），不是缺陷。
4. **表里的失败比例不代表全量里的概率。** 干扰线程是不停地读，比真实泄漏的线程频繁得多。
5. 两个测试文件都在冻结契约测试名单里（名单管的是归属豁免）。这次只加了锁和注释，没有增删用例。
6. **与 `codex/l2-maturity-takeover` 的关系。** 那条车道没有改 `tests/test_publication_fsync_budget.py`；`tests/test_publication_recovery.py` 两边改的行不相邻，是否还有冲突以提交时门禁的试合并为准（本文件能提交即表示门禁放行）。没有动那条车道的工作树和分支。

## 5. 回退

`git revert` 本提交。两处改动互不依赖，可以分开还原。

## 6. 提交

已提交：是，在车道分支 `codex/publication-test-fixture-lock`。hash 以 `git log --grep "^R3962:"` 为准（同一提交无法回填自身 hash）。合入主干由合并轮另记。第一处改动和 §2 由上一个会话完成；接手的会话复核了差异，改写了第二处，补了复测并提交。
