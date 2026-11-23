# R4242 FIX-DIST-MANIFEST：分发清单「开发流程」行补登记两份文档（修复轮）
<!-- round-evidence: {"commit_base": "72b61f8b", "credential_hits": 0, "evidence_sha256": "bed0a144da2c005f", "exit": 0, "failed": 0, "passed": 0, "round": 4242, "tests": "docs-only"} -->

## 三问
- 轮次类型：§3.2 修复轮（L0 分发清单契约补登记，document-only）。
- 测试跑了吗、三个基线过了吗：跑了卡面指定的定向 `run_selftests.py -k distribution_selfcheck`——改前红（`undecided` 含目标两文件），改后 3 条用例全绿、退出码 0；`git diff --check` 退出码 0、无输出。默认冒烟、架构门禁与全量 `--all --safe` 未跑（卡面验收只要求定向与 diff 检查）。
- 欠账少了吗：消除 `test_manifest_covers_every_file` 的 `undecided` 非空欠账；无新增欠账。

## 范围与基线
- 基准版本：`72b61f8b4d70019618838f9dc33a8534ea9aa6ac`（开工时 `git log -1 --format=%h` 输出 `72b61f8b`，`git status --short` 无输出，`git rev-parse --abbrev-ref HEAD` 输出 `codex/fix-dist-manifest`）。
- 任务：FIX-DIST-MANIFEST / 波次 W2 / 共享资源 `distribution-manifest`。
- 缺陷：`distribution_build.plan(ROOT)['undecided']` 含 `程序/docs/process/三虎框架评估.md` 与 `程序/docs/process/产物命名盘点.md`；两文件是已验收开发资料，但 `distribution_manifest.md` 未声明保留或排除，触发 `tests/test_distribution_selfcheck.py:15` 断言红。
- 改动文件：`distribution_manifest.md`、`tasks_round/tasks_round_4242_result.md`；`tasks_round/evidence/R4242.json` 由 `scripts\dev.py commit` 生成。
- 产品与测试零改动：未修改任何 `.py`、`tests/`、`scripts/`、配置或清单其它行；未把两文件列入「必须保留」。

## 改动内容
在「必须排除」表「开发流程」分类行（`distribution_manifest.md:33`）的路径/模式列末尾追加 `` `程序/docs/process/三虎框架评估.md` ``、`` `程序/docs/process/产物命名盘点.md` ``；分类仍为「开发流程」，原因原文不变。

## 改前红输出
命令 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k distribution_selfcheck`（工作目录 `程序`），退出码 1：

```text
  test_distribution_selfcheck     3 条     0.3 秒  ✗ 1
共 3 条用例，1.0 秒；1 个文件有红
===== test_manifest_covers_every_file (test_distribution_selfcheck.DistributionSelfCheckTests.test_manifest_covers_every_file) =====
AssertionError: Lists differ: ['程序/docs/process/三虎框架评估.md', '程序/docs/process/产物命名盘点.md'] != []
First list contains 2 additional elements.
First extra element 0:
'程序/docs/process/三虎框架评估.md'
- ['程序/docs/process/三虎框架评估.md', '程序/docs/process/产物命名盘点.md']
+ [] : 新增文件必须在 distribution_manifest.md 里声明保留或排除
```

## 验证命令与结果
Python 命令工作目录均为 `程序`；git 命令工作目录为工作树根。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k distribution_selfcheck`（改前）
   - 退出码：1（红因与卡面一致：`undecided` 恰为上述两文件）。
2. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`
   - 退出码：0，输出 `4242`。
3. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k distribution_selfcheck`（改后，卡面验收命令原样）
   - 退出码：0
   - 输出尾部：
     ```text
       test_distribution_selfcheck     3 条     0.2 秒
     共 3 条用例，0.9 秒；0 个文件有红
     ALL TESTS PASSED
     ```
4. `git diff --check`（卡面验收命令原样）
   - 退出码：0，无输出。

## diff 原文
```diff
diff --git "a/程序/distribution_manifest.md" "b/程序/distribution_manifest.md"
index ece0ea90..17e57c68 100644
--- "a/程序/distribution_manifest.md"
+++ "b/程序/distribution_manifest.md"
@@ -30,7 +30,7 @@
 | `程序/tests/**` | 测试 | 仅用于开发验证。 |
 | `程序/docs/specs/**` | 设计规格 | 开发权威与技术边界，不是运行时输入。 |
 | `程序/docs/requirements/**`、`程序/docs/adr/**`、`程序/docs/stages/**`、`程序/docs/review/**`、`程序/docs/guides/**`、`程序/docs/contracts/**`、`程序/docs/records/**` | 开发文档 | 用户运行所需的流程指南在单文件保留规则中明确列出，其余工程资料不入包。 |
-| `程序/docs/process/发布检查单.md`、`程序/docs/process/商用交付资料.md`、`程序/docs/process/存储盘点与保留.md`、`程序/docs/process/维护约定.md`、`程序/docs/process/版本控制处置说明.md`、`程序/docs/process/联调测试出口基线.md`、`程序/docs/process/每分钟成本核算.md` | 开发流程 | 保留仅被用户练习引用的制作失败与人工替代说明，其余运行时不读取。 |
+| `程序/docs/process/发布检查单.md`、`程序/docs/process/商用交付资料.md`、`程序/docs/process/存储盘点与保留.md`、`程序/docs/process/维护约定.md`、`程序/docs/process/版本控制处置说明.md`、`程序/docs/process/联调测试出口基线.md`、`程序/docs/process/每分钟成本核算.md`、`程序/docs/process/三虎框架评估.md`、`程序/docs/process/产物命名盘点.md` | 开发流程 | 保留仅被用户练习引用的制作失败与人工替代说明，其余运行时不读取。 |
 | `程序/governance/**` | 开发治理 | 目录协议、检查器与基线只在开发与CI中使用，不进入产品。 |
 | `程序/legacy/**` | 退役内容 | 未来经确认保留的退役代码不得进入运行时和分发；当前不创建空目录。 |
 | `程序/tasks_round/**` | 开发记录 | 轮次过程产物。 |
```

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit --agent "Devin SWE-2 Flash High" -m "R4242: FIX-DIST-MANIFEST 补分发清单排除项" distribution_manifest.md tasks_round/tasks_round_4242_result.md`
- `tasks_round/evidence/R4242.json` 由 `scripts\dev.py commit` 生成；提交哈希无法在同批文件内自引用，以证据回执与完成报告为准。

## 未验证项
- 未跑默认冒烟 `smoke_test.py`、`--architecture` 架构门禁与全量 `run_selftests.py --all --safe`；卡面验收只要求定向 `distribution_selfcheck` 与 `git diff --check`。
- 未跑 `scripts/distribution_build.py --plan/--build/--verify`；清单覆盖契约由 `test_distribution_selfcheck` 守卫。
- 未合入 master、未 push；合入由合并车道按正式流程处理。
