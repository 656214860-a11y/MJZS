# R3287：残留 SKILL 治理轮 3（D3 孤儿 gitlink 保留内容治理）
<!-- round-evidence: {"commit_base": "d90358b7", "credential_hits": 0, "evidence_sha256": "b8daa51f07eb2fb0", "exit": 0, "failed": 0, "passed": 57, "round": 3287, "tests": "run_selftests.py -k skill_package_pins aigc_package_diff skill_residue_service skill_project_layer line_endings"} -->

- 轮次类型：§3.2 修复轮；仅任务书轮 3 的 AIGC 索引，保留内容转普通文件。
- 测试与三个基线：默认冒烟8核心＋1隐藏桌面probe＝日志9/9；pins2包0问题；技能/索引定向41/41、行尾16/16；最终全部架构532/532、276.203秒、exit 0，较轮2的532不变、失败集合空。全量本轮未运行，最近正式收据R3258，不冒称当前树全量绿色。
- 欠账：AIGC孤儿gitlink已治理且159文件全部保留；其余三个gitlink、历史全量阻断及L2-D22用户本人重装继续保持真实待办。

## 授权、起点与恢复检查点

本轮直接用户授权执行轮 3 实际索引操作、测试与独立提交，需确认事项按最优选择自行确认。选择最安全的“保留内容转普通目录跟踪”；未删除真实总包、未代用户重装。保留 L2-D18/21/22 等全局决策，不改 `_stage_directories` 与阶段注册数。前轮 R3283 独立提交 hash 为 `d90358b7`（按本轮要求接续补记）。R3279 为 `9b620f1c`。

起点：工作树 `dsh-6187d0c7-f35d`，分支 `codex/skill-residue-governance`，HEAD `d90358b7`，`git status --short` 空。已读 AGENTS、runbook §12/13/16、任务书全局决策与轮3、R3276 报告和 R3279/R3283 结果。已加载 minimal-diff-fix、tech-writer、scoped-tests；项目专有命令与本轮范围优先。首次 `dev.py claim --branch codex/skill-residue-governance` 因已有分支拒绝、无修改；确认分支后用 `dev.py claim` 实领 R3287。scope 与另53条活跃分支无重叠，无对应队列项不冒领。

只读基线：本树与主树 AIGC 均无 `.git`、无 symlink/junction；159 文件、3,660,831 字节，路径/大小/SHA256 逐项完全一致。排序文件清单的规范 JSON（UTF8、ensure_ascii=False、sort_keys=True、separators=(',',':')）SHA256=`09c6df97432e76547057e873277764920ccc689f406ef9946d4e8ea135562d54`。无运行数据／配置／凭据文件名、无私钥或 live-token 形态命中。完整原始清单与摘要仅记录源码文件相对路径、大小、摘要，不记录用户数据。

原始输出位于受忽略 `logs/R3287_content_before.json`、`R3287_content_before.log`、`R3287_index_before.log`、`R3287_status_before.log`、`R3287_submodule_before.log`、`R3287_pins_before.log`。修改前 pins exit 0；git status 正常；`git submodule status` exit 128，实际报错对象是范围外 `程序/reference/HoLLMwood`。

## 已实施与原始索引对比

仅执行目标 `git rm --cached -- '程序/skills/00全流程SKILL/AIGC创作全流程'`，随后 `git add` 同一路径原包159文件。未执行目录删除或回收。pins 活跃 `packages` 仅移除 AIGC 旧登记，其他2条对象与原文件完全一致；没有运行全表 `--update`，没有改门禁代码。转换后旧登记如仍保留，实测 `--check` exit 1（“登记表有 … 但主仓库不再固定它”）；移除过期登记后 exit 0、外部技能包2个、问题0个。这是既有行为校验，未弱化断言。

原历史登记（供追溯，不冒称重新联网验证上游）：source=`https://github.com/lixiaoxiao9888-create/manju-laoli-skill.git`，commit=`1a43ae5a019d157eb3d45ad73e800081cb127763`，tree=`d9a208042147179768f0a24dc54bdfbd5374a9e9`。该登记与本次实际文件清单同时保留在 `tasks_round/evidence/R3287_aigc_manifest.json`。

| 路径 | 修改前 | 修改后 |
| --- | --- | --- |
| 程序/skills/00全流程SKILL/AIGC创作全流程 | 160000 `1a43ae5a019d157eb3d45ad73e800081cb127763` | 159条普通100644文件，无160000 |
| 程序/reference/HoLLMwood | 160000 `3ef9f995992edcbf514bed591a54b900b7502f11` | 完全相同 |
| 程序/skills/01 剧本准备SKILL/剧本锻造 | 160000 `6c3d73994f456b696de536c86602b4022824a535` | 完全相同 |
| 程序/skills/01 剧本准备SKILL/编剧技能集 | 160000 `357d1348ccaa1ab75f2f51ef7c90a7f00a686c76` | 完全相同 |

修改后工作区159文件的路径/大小/SHA256与修改前逐项一致，摘要仍为 `09c6df97432e76547057e873277764920ccc689f406ef9946d4e8ea135562d54`。159条索引文件集合精确等于原清单；Git按既有换行策略将157个文本文件CRLF规范为LF，索引内容已逐条验证仅有该规范化（两个JPG字节一致），未改工作区原字节、未全局格式化。原始前/后索引分别存 `logs/R3287_index_before.log` / `R3287_index_after.log`；机器清单含159项前后相同文件摘要和另3gitlink原始记录。统一提交扫描器对当前暂存新增行检查：0个凭据形态命中。

## 验证进展与边界解释

- `scripts/skill_package_pins.py --check`：通过，2包、0问题。
- `run_selftests.py -k skill_package_pins aigc_package_diff skill_residue_service skill_project_layer`：41/41，9.6秒，0 skip，exit 0；原始 `logs/R3287_targeted.log`。
- `smoke_test.py`：8项核心＋1隐藏桌面probe，日志9通过/0失败、exit 0；原始 `logs/R3287_smoke.log`。
- `run_selftests.py -k line_endings`：16/16，1.1秒，0 skip，exit 0；原始 `logs/R3287_line_endings.log`。
- 真实只读注册：73项、13阶段目录、AIGC注册命中0；原始 `logs/R3287_registry.log`。
- 包内13个 `.py` 均内存 `compile` 成功，不写pycache；上游 `short-drama-director/scripts/check_package.py:2239` 原存 `SyntaxWarning`（转义 `\[`），非语法错误，保留原内容。
- 首遍 `smoke_test.py --architecture`：532项、6失败、255.118秒、exit 1，原始 `logs/R3287_architecture.log`。失败均由本轮两个临时核验脚本放在 `程序/logs/*.py` 被扫描器纳入生产导致：coverage审计2项、coverage模块/工具2项（656!=654）、路径字符串1项、subprocess timeout 1项。已核对失败均命中这两临时脚本，原样移到 `<git common-dir>/round-local-evidence/R3287`，未改代码/断言/基线/白名单。全架构重跑job `pwsh-fd8fc969a80e45bf` 已采集exit 0：532/532、276.203秒、失败集合空（与轮2的532持平），原始 `logs/R3287_architecture_final.log`。本地状态页临时投影3288，完成后已与 `git show HEAD:程序/project_status.md` 核对原始字节一致并精确还原3278，`git diff --exit-code -- project_status.md` 为0，不暂存。
- 正式全量本轮未运行；只读common-dir收据最近正式轮次仍3258，verified tree时间为2026-11-18T01:53:50、耗时942.765秒，tree=`31bb237777256535d7001b6850b066cf370996f1`。字段 `last_full_safe_all_at=2026-10-03` 与verified时间不一致，仅如实列示，不在本轮修收据。轮2中断全量不作绿色凭据；lead专轮处理历史语音UI/Tk分类及最终全量。

`git diff --cached --check` exit 2，只有原包已存在的6处空白提示，均已对照原始逐文件摘要证明非本轮修改：README.md:433、short-drama-director/references/asset-spatial-ledger.md:324、short-drama-director/references/quality-gate-review.md:84 为末尾空行；short-drama-director/references/comfyui-canvas-automation.md:36/:47、short-drama-director/scripts/generate_emotion_curve.py:71 为尾随空格。路径均相对 AIGC 包。按授权保留原包，不格式化、不加豁免，不把该检查写成通过。原始 `logs/R3287_diff_check.log`。PowerShell原生重定向部分日志产生UTF16，已保留原文字转UTF8；运行中的架构日志曾因写锁拒绝转换，仅已完成日志转换，未重试改写运行中文件。

任务书“保留内容普通跟踪”与“今后删除后 git 干净”不能同时保证：普通跟踪后用户回收该包会产生 tracked deletion，需要在源码仓库明确提交删除或采用独立运行副本，不能伪称删除即干净。轮3只验收保留方案，轮4由用户本人操作，lead 提供真实操作说明。`git status` 与 `git submodule status` 是两个命令；本轮不为清除范围外 HoLLMwood 的 submodule 错误扩张到另外3条记录。

## 提交检查点与待办

首次统一入口因在工作目录 `程序` 仍传 `程序/` 前缀路径而exit128（pathspec未匹配），核验HEAD仍d90358b7、暂存160条目标记录未变、状态页无差异后，修正为相对当前目录路径重试；不是重复提交。使用统一 `scripts/dev.py commit -m "R3287: 修复AIGC孤儿gitlink并保留原包源码"`，最小清单仅 AIGC 目标删除的旧索引＋159文件、`维护记录/外部技能包哈希.json`、本轮结果与机器清单、统一入口自动生成的 R3287 测试证据。`--tests skill_package_pins aigc_package_diff skill_residue_service skill_project_layer line_endings` 做提交时复验。不使用 add -A，不暂存日志、状态页、临时脚本、复制的另外2个技能包或用户数据。

完成本轮后由lead下一子会话处理历史全量阻断、正式最终全量和合入master；轮4真实删除/重装仍由用户本人按L2-D22操作。其余3个gitlink独立议题保持原样。任务完成文件须等全任务书收口再统一输出，不能把本轮写成整个任务书完成。

本轮 hash 待提交；本结果在提交前冻结，hash 由lead接续补记或引用本文件所在提交，避免为了自引用产生额外提交。完整任务书未完成，不标记整体 TASK_COMPLETE。
