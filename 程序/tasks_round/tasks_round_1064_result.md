# R1064 验证/基线轮：死代码候选隔离副本验证

## A 结论

INCONCLUSIVE。基线架构门禁未通过，未执行任何候选删除；不能宣称清理完成。三个候选仍为 REVIEW，共 54 行、2790 字节潜在删除量。

## B 授权

用户批准 R1063 提议的 CRT-026～028 临时副本验证及三条命令；未批准真实源码清理或新增全量命令。

## C 环境

原仓库起点 d464cfacab597d28dd1b4c60da5c6ea3de63a315。隔离副本位于系统临时目录 `code-rot-R1064-1e410f664b9e4d5389d2fba9cb92e457`，不链接原仓库。复制 1757 个白名单已跟踪文件，不复制用户数据、配置、private、日志、密钥、运行环境；仅允许三个已跟踪架构基线 JSON。

## D 候选

CRT-026：idea_chat.py:459 project_document_kind；CRT-027：projects.py:316 Projects.remove_internal_links；CRT-028：workflow_process_registry.py:70 cancel_process_slot_request。精确静态证据见 R1063，不重复声称静态扫描等于安全删除。

## E 定向结果

`python.exe -B run_selftests.py --safe -k idea_chat projects workflow_process_registry`：90 项通过、0 个文件失败，44.3 秒。首次普通副本因缺少 Git 锁位置停在测试前；初始化独立 Git 后同命令通过。

## F 冒烟结果

`python.exe -B smoke_test.py`：8/8，exit 0。全部运行于副本，不代表真实删除后的结果。

## G 架构结果

`python.exe -B smoke_test.py --architecture`：309 项运行，308 通过、1 失败，118.576 秒，exit 1。失败为 tests/architecture/test_round_baselines.py:68 的全量凭据检查；新建副本没有有效凭据，默认最近全量轮次为 0。

## H 失败处理

基线未全绿，按 code-rot-cleaner 要求停止删除实验。没有跳过检查、弱化断言、伪造凭据或复制原仓库凭据。三个候选的原文件与副本 SHA-256 一致。

## I 修改边界

真实仓库仅新增验证证据、结果报告，更新状态页顶部轮次；未改生产 .py、测试、用户数据、配置或历史结果报告。未删除 logs、缓存或任何原项目文件。

## J 后续路线

先申请额外批准：在正确目录布局的独立 Git 副本建立干净内容树，并运行 `python.exe -B run_selftests.py --all --safe --force`，取得副本自己的可信全量基线。再重验已批准命令；全绿后才执行三个符号的副本删除实验。真实源码清理仍须另行明确批准。

## K 测试迁移计划

不迁移或删除测试。现有三个验证命令保持不变；新增全量命令尚未运行。不得通过分支绕过、篡改轮次或人为填入凭据让基线变绿。

## L 证据与提交

[完整验证报告](../../outputs/code-rot-cleaner/R1064/CODE-ROT-REPORT.md)，同目录 proof.json、cleanup-plan.csv。中央任务 R1064-CODE-ROT-PROOF：本轮诊断验证结束，删除阶段未开始。状态页当前轮次 1065，最新报告 1064。提交前尚未提交；最终 Git 回执以 `R1064: 记录副本验证基线阻断` 为准。

## M 收尾

按 tech-writer 区分历史结果、当前副本结果与未执行步骤。按 post-task-cleanup 核对本轮产物：副本含源码、独立 .git 和验证日志，保留复核，不递归删除；不扩大到原项目缓存。副本非 .git 文件约 13.51 MB。本轮生产代码清理量为 0。
