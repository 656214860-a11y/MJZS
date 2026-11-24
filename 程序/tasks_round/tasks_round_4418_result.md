# R4418 结果：FIX-DIST-MANIFEST-DOCS 分发清单补登 4 份开发流程文档排除项
<!-- round-evidence: {"commit_base": "026888c3e", "credential_hits": 0, "evidence_sha256": "db9b3915e4535025", "exit": 0, "failed": 0, "passed": 25, "round": 4418, "tests": "run_selftests.py -k distribution_selfcheck distribution_build"} -->

- 轮次类型（§3）：3.2 修复轮（仅改 `distribution_manifest.md` 一处声明，未改任何 Python 代码或测试）。
- 测试跑了吗：跑了。定向 `run_selftests.py -k distribution_selfcheck distribution_build` 改前 1 条红、改后 25 条全绿；架构门禁 `smoke_test.py --architecture` 708 条全绿。
- 三个基线：默认冒烟本轮未跑（非本卡验收项，工作树分支不累积全量欠账）；架构门禁当轮实测 708/708 绿；全量回归未跑（非本卡验收项）。
- 欠账少了吗：无新增欠账；消除主干 `test_manifest_covers_every_file` 阻塞红 1 条。

## 缺陷复现方式（先红）

卡面禁止改任何 Python 代码或测试，允许修改清单也不含测试文件；缺陷复现直接用既有守卫测试 `tests/test_distribution_selfcheck.py:13-15`（`test_manifest_covers_every_file` 断言 `distribution_build.plan(ROOT)['undecided'] == []`）。改前在未改产品状态下运行验收命令，红 1 条，原因即卡面缺陷：`程序/docs/process/` 下 3 份文档未在 `distribution_manifest.md` 声明保留或排除。

改前命令 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k distribution_selfcheck distribution_build`（目录 `程序`，退出码 1）尾部原文：

```
  test_distribution_selfcheck     3 条     0.3 秒  ✗ 1
  test_distribution_build#2      6 条     1.4 秒
  test_distribution_build#1     16 条     2.0 秒

共 25 条用例，2.7 秒；1 个文件有红

### test_distribution_selfcheck（1 条红）

===== test_manifest_covers_every_file (test_distribution_selfcheck.DistributionSelfCheckTests.test_manifest_covers_every_file) =====
AssertionError: Lists differ: ['程序/docs/process/外发内容清单.md', '程序/docs/pro[40 chars].md'] != []

First list contains 3 additional elements.
First extra element 0:
'程序/docs/process/外发内容清单.md'

+ []
- ['程序/docs/process/外发内容清单.md',
-  '程序/docs/process/外部依赖清单.md',
-  '程序/docs/process/隐私声明草案.md'] : 新增文件必须在 distribution_manifest.md 里声明保留或排除
```

红的条数＝1（`test_manifest_covers_every_file`），未决定文件恰为卡面所列 3 个：`程序/docs/process/外发内容清单.md`、`程序/docs/process/外部依赖清单.md`、`程序/docs/process/隐私声明草案.md`。

## 「实机走通清单」能否预登记的核实

- `程序/docs/process/实机走通清单.md` 在本工作树不存在（docs/process 现有 15 份 .md，已逐一列目核对）。
- `scripts/distribution_build.py:119-133` 的 `plan()` 只对 `candidate_files(root)` 列出的**实际存在**文件分桶；清单里声明了但不存在的排除模式永远不会命中，也没有任何测试要求「声明的模式必须命中现存文件」（`tests/test_distribution_build.py` 与 `tests/test_distribution_selfcheck.py` 均无此断言；架构门禁 `test_dynamic_import_registry.py` 只消费 `plan()` 的分桶结果）。
- 结论：允许预登记，按卡面「若允许则 4 个一起声明」执行，4 份全部写入第 33 行「开发流程」排除行；该文件由其他车道合入后自动落入排除桶，无需再改清单。

## 改动位置（文件:行号）

- `distribution_manifest.md:33`：「必须排除」表「开发流程」行的模式单元格末尾追加 4 个反引号路径——`程序/docs/process/外发内容清单.md`、`程序/docs/process/外部依赖清单.md`、`程序/docs/process/隐私声明草案.md`、`程序/docs/process/实机走通清单.md`。分类与原因列未动（「其余运行时不读取」对这 4 份同样成立）。仅此一处，无其他文件改动。

## 验收命令输出尾部（原文）

命令一 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k distribution_selfcheck distribution_build`（目录 `程序`，退出码 0）：

```
  test_distribution_selfcheck     3 条     0.3 秒
  test_distribution_build#2      6 条     1.1 秒
  test_distribution_build#1     16 条     2.0 秒

共 25 条用例，2.7 秒；0 个文件有红
最慢 3 路工作单元：
  test_distribution_build#1     2.0 秒 / 16 条
  test_distribution_build#2     1.1 秒 / 6 条
  test_distribution_selfcheck    0.3 秒 / 3 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：7.5 秒

ALL TESTS PASSED
```

条数核对：改前 25 条（含红 1），改后 25 条全绿；本卡未新增测试文件，条数不变符合「改前条数 + 新增条数」。

命令二 `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（目录 `程序`，退出码 0）：

```
----------------------------------------------------------------------
Ran 708 tests in 277.090s

OK
✅ 架构治理测试：tests/architecture
```

## 没有验证的地方

- `程序/docs/process/实机走通清单.md` 尚不存在，预登记的排除效果要等该文件实际合入后才被 `plan()` 命中；本轮无法对真实文件验证「落入 excluded 桶」（模式本身已由 `pattern_regex` 按字面路径生成，风险极低）。
- 未跑默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe`（非本卡验收项；本卡只动一份 Markdown 声明）。
- 未执行 `distribution_build.py --build/--verify` 真实构建（非本卡验收项；`plan()` 覆盖检查已由定向测试覆盖）。

## 卡外发现（只记录，不顺手修）

- 改前定向跑出现 `[SUSPECT_CONCURRENCY]` 提示（有其他 PID 持有 GUI 令牌）；失败原因是确定性的 undecided 列表不等，与并发无关，改后复跑全绿。
- `tests/test_distribution_selfcheck.py:25-26` 中 `test_built_copy_imports_entry_modules` 在工作树缺 `运行环境/` 时直接 return 跳过副本自检——属既有设计（干净检出只做覆盖检查），非本卡范围。
