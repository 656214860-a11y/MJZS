# R4145 结果：FIX-AUD-PETSETTINGS-LOCK 宠物设置 save_settings 补发布锁，读—改—写不再丢并发键
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "180d501a1e51a9e9", "exit": 0, "failed": 0, "passed": 154, "round": 4145, "tests": "run_selftests.py -k pet_settings pet_agent"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。任务卡 W7-FIX-AUD-PETSETTINGS-LOCK（波次 W2，审查 AUD-MODEL D2），车道分支 codex/fix-aud-petsettings，基准 3383684c。缺陷：`pet_agent.save_settings`（原 pet_agent.py:647-664）对 `配置/宠物/配置.json` 做整文件读—改—写，但读（`read_json`→`agent.core.read`→`access()`）和写（`save`→`replace`→`access()`）是两次独立取锁，中间窗口可被 `agent.publication.access()` 锁内的读—改—写者插入。该配置与模型池共用（`pet_llm.config_path`→`model_pool.config_file`→`config_snapshot.model_config_file`，均指向 `配置/宠物/配置.json`，infra/pet_llm.py:98-99、infra/model_pool.py:265-266、infra/config_snapshot.py:12-17），`model_pool.record_health` 经 `_update` 在锁内读—改—写（infra/model_pool.py:580-599、776-805）；`save_settings` 写回的是读时的旧快照，对方刚落的键（如 `model_health`）被静默盖掉。账号会话写入（infra/account_store.py）走同一把 `access()` 锁但写另一份文件 session.json，是这把锁的另一位使用者。
- （二）测试跑了吗、三个基线：定向 `run_selftests.py -k pet_settings pet_agent` 改前 154 条 1 红（新增用例复现缺陷），改后 154 条 0 红、退出码 0；`smoke_test.py --architecture` 700 条 OK、退出码 0（中途因模块行数棘轮红过一次，收敛改法后复跑全绿，见下）。默认冒烟未跑（卡面未要求）；全量自测未跑。
- （三）欠账少了吗：无新增欠账；未新增门禁豁免、未动登记基线数值。

## 缺陷复现方式

新增 `tests/test_pet_settings.py` 的 `SaveSettingsLockTests.test_concurrent_record_health_loses_no_keys`（tests/test_pet_settings.py:984-1042）：临时 program 目录预置 `models`/`agent` 键；把 `pet_agent.save` 换成「置 `about_to_write` 事件、等 `proceed` 放行再调真 `save`」的门控函数；线程 A 跑 `pet_agent.save_settings({'level': 'auto'})`，读盘合并后停在写盘前；线程 B 此时跑 `model_pool.record_health('m1', ...)`——修复前它不持锁、毫秒级完成整个读—改—写，测试等 `health_done` 后放行 A，A 把不含 `model_health` 的旧快照写回，健康度键被丢；修复后 B 堵在 `access()` 锁上直到 A 写完放锁，B 锁内重读到含新设置的盘面再合并，两边键都在。交错由事件门控确定，不靠时序概率。

## 改前红的条数和原因（原文）

`run_selftests.py -k pet_settings pet_agent`（改测试、未改产品）：共 154 条用例，8.5 秒；1 个文件有红，退出码 1。唯一红条：

```
===== test_concurrent_record_health_loses_no_keys (test_pet_settings.SaveSettingsLockTests.test_concurrent_record_health_loses_no_keys) =====
Traceback (most recent call last):
  File "D:\漫剧制作助手\.agents\worktrees\fix-aud-petsettings\程序\tests\test_pet_settings.py", line 1041, in test_concurrent_record_health_loses_no_keys
    self.assertTrue(data.get(model_pool.HEALTH_KEY, {}).get('m1', {}).get('ok'),
    ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                    'record_health 写下的键不能被设置写丢')
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: None is not true : record_health 写下的键不能被设置写丢
```

红因与卡面缺陷一致：`record_health` 写下的 `model_health.m1.ok` 在 `save_settings` 的旧快照整文件写回后消失（静默丢更新）；`level`、`models` 断言均过。

## 改了哪几处（文件:行号）

- `程序/pet_agent.py:647-664`（`save_settings`）：读—改—写整体包进 `with access()`（`from agent.publication import access` 惰性导入，与 `model_pool._update` 同一写法）；合并段改写成两条 dict 推导（`updates` 只收 SETTING_KEYS 且非 None 的键，`data.update` 滤掉 `_SKIP`），语义与原 for 循环逐条等价，只为把函数行数压回模块上限（见「过程说明」）；docstring 末行补一句锁内契约说明。公开签名、返回值、SETTING_KEYS 过滤、坏值容错均不变。
- `程序/tests/test_pet_settings.py:26`（加 `import threading`）、`:984-1042`（新增 `SaveSettingsLockTests` 一条用例）。

## 过程说明

第一版修法（保留原 for 循环、docstring 加两行）使 pet_agent.py 涨到 1050 行，超过模块行数棘轮上限 1046，`smoke_test.py --architecture` 报 `pet_agent.py: 1050 行 > 上限 1046`（700 条中 1 红）。收敛为行数中性改法（推导式合并、docstring 说明并入原行）后文件回到 1046 行，复跑架构门禁全绿。合并语义经逐条比对：键不在 SETTING_KEYS、值为 None、规整结果为 `_SKIP` 三种情况与原循环一致；`dict(values or {})` 浅拷贝与遍历顺序不变。

## 改后命令输出尾部原文

定向（`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k pet_settings pet_agent`，退出码 0）：

```
  test_pet_settings#2           15 条    16.1 秒

共 154 条用例，18.3 秒；0 个文件有红
最慢 10 路工作单元：
  test_pet_settings#2          16.1 秒 / 15 条
  test_pet_settings#1          14.3 秒 / 16 条
  test_pet_settings#3          13.5 秒 / 15 条
  test_pet_settings#4          13.1 秒 / 13 条
  test_pet_agent_error_wiring    0.4 秒 / 10 条
  test_pet_agent#2              0.1 秒 / 15 条
  test_pet_agent#1              0.0 秒 / 16 条
  test_pet_agent#6              0.0 秒 / 11 条
  test_pet_agent#4              0.0 秒 / 11 条
  test_pet_agent#5              0.0 秒 / 16 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：2.1 秒

ALL TESTS PASSED
```

条数核对：改前（含新用例、未改产品）154 条 1 红；改后 154 条 0 红 = 153 原有 + 1 新增。

架构门禁（`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`，退出码 0）：

```
----------------------------------------------------------------------
Ran 700 tests in 234.549s

OK
✅ 架构治理测试：tests/architecture
```

## 没有验证的地方

- 未跑默认冒烟 `smoke_test.py`（卡面只点名 `--architecture`）、未跑全量自测、未 push、未 merge。
- 账号会话写入落在 `private/账户/session.json`，与本配置不同文件；本轮按卡面以同文件并发写者 `model_pool.record_health` 验证「锁内读—改—写不丢键」，`access()` 是跨进程同一把 writer.lock，账号写入只是同锁另一使用者，未做三方混合并发实测。
- 并发用例为同进程两线程＋事件门控的确定性交错，未做多进程／真实多用户并发压测；`access()` 的 30 秒锁等待上限在极端争用下的行为未专门验证。
- `save_settings` 其它调用方（pet_ui 档位切换、pet_settings_ui 各保存钮、skill_budget 读侧）未逐个点测，定向 154 条与架构 700 条覆盖其既有契约。
