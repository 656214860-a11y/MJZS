# R4256 结果：OPS-LANES-TO-C 车道迁固态盘（junction 脚本＋测试）—— 失败报告（停止）

## 开头三问

- 本轮属于哪种类型：§3.1 功能轮（新增运维脚本与配套测试、runbook 一小节；不改任何既有模块）。实际按失败升级停止。
- 测试跑了吗、三个基线：跑了。定向 `run_selftests.py -k relocate_lanes` 12/12 全绿；架构门禁 `smoke_test.py --architecture` 700 条实测 1 红（`test_structure` 的 STR006 ownership，实证输出见下），验收「退出码 0」无法达成；默认冒烟与全量回归未运行（本卡未列该命令）。
- 欠账少了吗：范围内新增欠账已清零（裸 `json.loads` 棘轮项已在脚本内修掉，见下）。卡本身欠一处 `test_ownership` 登记放行，列入「需要主控决定」。

## 失败报告

```yaml
失败报告:
  任务卡: OPS-LANES-TO-C
  轮次: R4256
  停在哪一步: 实现步骤 6「smoke_test.py --architecture 必须全绿」
  现象: |
    脚本＋测试（先红后绿）已实现并自测全过：
      python.exe -B run_selftests.py -k relocate_lanes → 12 条用例全绿，退出码 0
    但新增的 tests/test_relocate_lanes.py 触发既有结构门禁：
      FAIL test_structure.test_real_repository_has_no_new_structure_violations
      AssertionError: New directory debt:
        [('STR006', '程序/tests/test_relocate_lanes.py', 'ownership')]
      Ran 700 tests in 237.736s / FAILED (failures=1)
  已经试过:
    - 领号 R4256；基线核验通过：commit 79fa309b、分支 codex/ops-lanes-to-c、工作树干净。
    - 先写测试看红：改前 -k relocate_lanes 1 个文件红（Errno 2 脚本缺失，输出见「先红」节）。
    - 补齐 scripts/relocate_lanes.py（plan/apply/rollback＋preflight 全套前置）后 12/12 绿。
    - 第一轮 --architecture 曾报 2 红：本条 STR006＋统一棘轮「裸 json.loads 新增债务」。
      棘轮属范围内可修项：dispatch_state 已改为只做 "status":"claimed" 正则存在性检查，
      不再解析 JSON（见 _queue_claimed，relocate_lanes.py L148 起），复跑后棘轮项消失。
    - 定位 STR006：governance/check_structure.py STR006 要求每个 tests/test_*.py
      在 governance/structure.json 的 test_ownership 登记 kind/contract/targets，
      或存在同名 source 角色生产模块。本测试对应脚本在 程序/scripts/（tooling 角色），
      自动归属不成立，只能登记放行。
    - structure.json 与 structure-baseline.json 均不在本卡「允许修改文件」，
      禁止事项写明「governance 不许改」「不放宽任何门禁／不登记豁免」，按失败协议停下。
    - 先例对照：R3990/R4004 同型（登记文件不在允许范围 → 停下升级，主控裁决后放行）。
  我的判断: |
    任务卡的允许修改文件清单与仓库现行门禁冲突：本仓任何新增 tests/test_*.py 若不能
    自动归属同名 source 模块，都必须同轮登记 structure.json test_ownership；
    且 structure.json 变更会触发 policy_sha256 复核，须配套 --write-baseline 重写
    structure-baseline.json（R4004 实证）。两处都在允许范围外。
    实现本身已按契约完成、定向全绿、棘轮项已清，只差这一处登记。
  需要主控决定: |
    请把 程序/governance/structure.json 与 程序/governance/structure-baseline.json
    加入 OPS-LANES-TO-C 允许修改文件，或明确放行口径。建议改动：
      structure.json test_ownership 补一条：
        "程序/tests/test_relocate_lanes.py": {
          "kind": "module",
          "owner": "项目维护者",
          "contract": "开发车道迁固态盘脚本 plan/apply/rollback 的前置检查、junction 建摘与失败回搬",
          "targets": ["程序/scripts/relocate_lanes.py"]
        }
      随后跑 python -B governance\check_structure.py --write-baseline 重写基线。
    放行后重跑 -k relocate_lanes 与 --architecture，全绿即可按原提交行提交；
    未提交实现留在本车道工作树（未 stash，本卡禁止 stash）。
  工作树状态: |
    未提交改动留在工作树：scripts/relocate_lanes.py（新）、tests/test_relocate_lanes.py（新）、
    runbook.md（+18 行「车道迁到固态盘」节）；本结果文件为唯一提交内容。
```

## 改前红（先红证据，原文）

`python.exe -B run_selftests.py -k relocate_lanes`（产品未改时）：

```
共 0 条用例，0.9 秒；1 个文件有红
### test_relocate_lanes（1 条红）
[Errno 2] No such file or directory: '...\\程序\\scripts\\relocate_lanes.py'
```

1 个文件红，红因即缺陷本体：脚本缺失。

## 改后验证（改后实测）

| 命令 | 结果 |
|---|---|
| `python.exe -B run_selftests.py -k relocate_lanes` | 退出码 0：`共 12 条用例，17.1 秒；0 个文件有红 / ALL TESTS PASSED`（11→12，新增 _queue_claimed 覆盖） |
| `python.exe -B smoke_test.py --architecture` | 退出码 1：`Ran 700 tests in 237.736s / FAILED (failures=1)`，唯一红为上述 STR006 |
| `python.exe -B scripts\relocate_lanes.py --plan` | 未能验证：命令被工具权限层拒绝 3 次（原文见「被拒命令」节） |

## 改了哪几处（工作树内，未提交）

- `程序/scripts/relocate_lanes.py`（新建）：`plan`/`apply`/`rollback`/`main`；前置在 `preflight`；robocopy /MOVE 在 `robocopy_move`；junction 建/摘在 `make_junction`/`drop_junction`；失败自动回搬 `_restore_from_failure`；进程 cwd 探测 `enumerate_cwds`/`process_cwd`（PEB，拿不到如实标 unreadable）；派工状态 `dispatch_state`＋`_queue_claimed`（先 `cpa auto status`，再看共享队列 claimed 存在性，再读不到记 unknown 需 `--i-know-lanes-idle`）。
- `程序/tests/test_relocate_lanes.py`（新建）：临时目录假仓库＋三个假车道（含脏文件），12 条用例：plan 只读、apply 后 junction＋逐字节/git status 一致、rollback 恢复、余量不足/在派项/目录被占用/目标非空/未知状态缺 flag 拒绝、_queue_claimed 存在性判定。
- `程序/runbook.md`：§5 下新增小节「车道迁到固态盘」（+18 行）：执行窗口、三条命令、手动回滚等价命令、不动清单。

## 没有验证的地方

- 真实盘上的 `--plan`/`--apply`/`--rollback` 未执行（--apply 本卡禁止对真实车道跑；--plan 被权限层拒绝）。搬迁正确性由测试在临时目录全真验证（真 git、真 robocopy、真 junction）。
- `cpa auto status` 真实输出格式未核实：exit≠0/读不到一律走队列兜底，判不出按 unknown。
- 进程 cwd 探测受权限/位宽限制的受关注进程如实列「未能检测」，--apply 按 unknown 处理。
- junction 后 `git rev-parse --show-toplevel` 返回 D:/ 还是 C:/ 写法：--plan 内置实测打印，真机结果留验收窗口；测试只断言该命令在 junction 后 exit 0。

## 卡外发现（只记录）

- 工具权限层间歇拒绝若干命令（`git -c` 前缀 status、Select-String、本脚本 --plan 等），按「同一命令拒两次即停」记录，未绕过。

## 被拒绝的命令原文

- `git -c core.quotepath=false status --porcelain`（2 次；改用 `git status --porcelain` 核实，输出为空）
- `..\..\..\..\运行环境\Python\python.exe -B scripts\relocate_lanes.py --plan`（3 次，工作目录 `程序`）
- `Select-String -Path governance\structure.json -Pattern test_ownership -Context 0,40`（1 次；改用文件读取工具看条目格式）

## git diff --numstat 原文（提交前工作树）

```
18	0	程序/runbook.md
```

（relocate_lanes.py、test_relocate_lanes.py、本结果文件为未跟踪新文件，不入 numstat。）

## 提交

- 已提交：本结果文件单独提交（`R4256-FAIL:`），实现文件留工作树待放行；hash 见完成报告。
