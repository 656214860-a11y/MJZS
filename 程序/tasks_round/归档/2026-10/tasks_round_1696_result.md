# R1696 功能轮（维护工具）：AIGC 创作全流程包「更新核对」只读脚本

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（维护工具）：新增只读核对脚本、阶段归属表和临时仓库测试；不改变任何制作阶段行为，也不改 `docs/`、阶段契约或 `程序/skills/`。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟通过（8/8）；架构门禁通过（368/368）；`test_aigc_package_diff` 用直接 unittest 为 9/9 OK。定向执行器 `run_selftests.py -k aigc_package_diff` 已跑出 9 条、0 红，但进程在汇总后未退出，未打印 `ALL TESTS PASSED`；`smoke_test.py --gate` 两次均在 900 秒上限超时（8 项通过、1 项失败），超时前停在等待跨树 GUI 令牌。全量回归按任务书未运行。因此三个基线没有全部取得有效通过结果。
3. **project_status.md 的欠账少了吗？** 没有减少；本轮是维护工具，不改变 13 阶段产出，未改 `project_status.md`，也未触发全量升级条件。

## A 为什么做这一轮

`程序/skills/00全流程SKILL/AIGC创作全流程/` 是自带 Git 历史的外部 SKILL 包。用户更新包后，目前没有统一入口回答三件事：哪些 Markdown/Python/JSON 新增、修改、删除或改名；变更文件由哪个阶段负责；删除或改名后是否仍有阶段 SKILL 链接指向旧文件。另需识别整个引擎目录完全未被任何阶段引用的情况。本轮只做报告工具，唯一写文件动作是显式 `--accept` 更新归属表基线，避免更新核对反过来改动包内容。

## B 改动

- 新增 `程序/维护记录/基准脚本/aigc_package_diff.py`：
  - 纯标准库；Git 子进程全部使用参数列表和 `shell=False`，兼容 `python -I -B`。
  - 从 `维护记录/AIGC包阶段归属.json` 读取 `absorbed_commit`，执行 `git diff --name-status -z --find-renames <baseline>..HEAD --`，解析 A/M/D/R；改名同时保留旧名与新名。
  - 只列出 `.md`、`.py`、`.json`；忽略 `.git`、包根 `assets/` 与图片扩展名。
  - 扫描 `程序/skills/**/*.skill.md` 与 `00全流程SKILL/总控.json` 的包内链接，去掉 `#锚点` 后解析相对路径；优先复用 `skill_registry.reference_targets`，不可用时退回本地最小解析，未修改 `skill_registry.py`。
  - 输出变动清单、`断链风险`、未链接引擎三部分；支持 `--json`、`--baseline-show`、`--accept`，并额外提供测试用 `--package`、`--ownership`、`--skills-root`。
  - 包目录不存在、不是独立 Git 仓库、归属表缺失或不可读、基线缺失或不在历史中，均输出中文提示并返回 0；异常也统一返回 0。
- 新增 `程序/维护记录/AIGC包阶段归属.json`：
  - `schema_version` 为 1，`absorbed_commit` 为 `1a43ae5a019d157eb3d45ad73e800081cb127763`。
  - 覆盖包根全部 14 个一级目录；按任务书写入确定种子，`sd-asset-engine`、`sd-feed-engine`、`sd-qc-engine` 等不确定职责保留 `stages: []`、`note: "待定"`，没有猜测归属。
- 新增 `程序/tests/test_aigc_package_diff.py`：
  - 9 个测试方法，使用临时目录中的独立 Git 仓库夹具，不依赖真实嵌套包。
  - 覆盖 A/M/D/R 与改名旧名/新名、链接去锚点、总控 JSON 路径、断链风险、未链接引擎、`--accept` 只写归属表、基线缺失/不在历史/包目录缺失退出码 0、`--json` 可解析。
  - 子进程统一使用 `sys.executable -I -B` 调脚本。
- 未修改 `程序/skills/`、`project_status.md`、`AGENTS.md`、`architecture.md` 或任何既有断言。
- 按接力协议更新 `.agent-handoff/snapshot.md`、`.agent-handoff/risks.md`、`.agent-handoff/backlog.md`，只记录 R1696 完成项、门禁阻塞和下一步，不复制日志。

## C 验证

| 项 | 实际结果 |
| --- | --- |
| 真实包核对 | 基线 `1a43ae5a019d157eb3d45ad73e800081cb127763` 等于包 HEAD；变动 0、断链风险 0、未链接引擎 1（`assets`） |
| 真实包 `--baseline-show` | 基线 commit 与 HEAD 均为 `1a43ae5a019d157eb3d45ad73e800081cb127763` |
| 真实包 `--json` | `json.loads` 成功；`ok=True`、`changes=0`、`broken_links=0`、`unlinked_engines=['assets']` |
| 直接 unittest `tests.test_aigc_package_diff` | `Ran 9 tests in 9.082s`，`OK`，9/9 |
| 定向 `run_selftests.py -k aigc_package_diff` | 打印 `9 条`、`9.4 秒`、`0 个文件有红`；但进程随后被 8 个工作进程挂住，未退出、未打印 `ALL TESTS PASSED`，不能记作命令通过 |
| 默认冒烟 `smoke_test.py` | 通过 8 项，失败 0 项 |
| 架构门禁 `smoke_test.py --architecture` | `Ran 368 tests in 208.700s`，`OK`，368/368；仅有包内 `check_package.py:2239` 的既有 `SyntaxWarning` |
| `smoke_test.py --gate` | 两次均为 900 秒超时（8 项通过、1 项失败）；超时前日志停在「申请跨树 GUI 令牌（最多等待 900.0 秒）」，未进入用例执行结果 |
| `run_selftests.py --all --safe` | 未运行（任务书明确禁止） |
| 真实包 `--accept` | 未运行；基线已等于 HEAD，无需更新。写入范围仅由临时夹具测试覆盖 |

真实包核对输出：

```text
AIGC 创作全流程包核对
当前基线 commit：1a43ae5a019d157eb3d45ad73e800081cb127763
包 HEAD：1a43ae5a019d157eb3d45ad73e800081cb127763

变动清单（0）
  无

断链风险（0）
  无

未链接引擎（1）
  - assets | 建议阶段: 任务书忽略其差异与图片；归属待定
```

`--baseline-show` 输出：

```text
当前基线 commit：1a43ae5a019d157eb3d45ad73e800081cb127763
包 HEAD：1a43ae5a019d157eb3d45ad73e800081cb127763
```

改动边界核对：`程序/skills` 变更 0 处；`维护记录/测试分层基线.json` 的 `git diff --numstat` 为 0 行。排查过程中曾临时调用保存函数写入该基线文件，随后已从 HEAD blob 恢复原始字节并确认无差异，因此不列为本轮交付改动。

## D 留给用户的事项

1. **门禁超时需要单独复跑。** 两次 `--gate` 都在跨树 GUI 令牌等待处耗尽 900 秒，未得到用例级门禁结果。需要在没有并行 GUI 自检的会话中重跑；本次不把超时写成通过，也没有终止其他会话的进程。
2. **归属表里仍有待定引擎。** `sd-asset-engine`、`sd-feed-engine`、`sd-qc-engine` 按任务书保留空阶段和「待定」，需要后续根据包内实际职责确认；`assets` 也被报告为未链接引擎，但任务书要求忽略其差异和图片。
3. **真实包当前没有可吸收更新。** 基线等于 HEAD；以后更新包时先跑本脚本，确认断链和未链接引擎，再决定是否显式执行 `--accept`。
4. **定向执行器存在退出异常。** `run_selftests.py -k aigc_package_diff` 的用例结果为 9/9、0 红，但进程未正常收尾；直接 unittest 已给出真实通过结果。该执行器问题不属于本轮脚本改动范围。

## E 提交

未提交，由 Claude 验收后提交。
