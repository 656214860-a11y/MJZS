# R1139：Codex 技能同步器

## §7 三问

1. 本轮类型：功能轮；将应用阶段单文件技能同步为 Codex 可发现的技能，不改提示词内联策略。
2. 本轮验证：定向 197 条通过、默认冒烟 8/8；全量安全回归待执行，尚不声明 TASK_COMPLETE。
3. 债务变化：补齐技能引用与 Codex 发现之间的缺口；未新增 JSON 读写入口或直接删除入口。TODO 快照仅更新代码位移行号，断言未弱化。

## 实现与边界

- 通过 default_registry 同步全部注册阶段的 .skill.md，包含新增第 13 阶段；外部技能包保持既有路径引用，不展开。
- 目标为 CODEX_HOME/skills/<name>/SKILL.md，未设置时使用用户 .codex/skills。仅 name/description 元数据，正文保留；采用方案 A，将 ../00全流程SKILL/ 改为应用源码的绝对路径。
- 首帧后后台同步；Codex 投递 worker 在提示词构建前校验。无 Tk 线程文件扫描，不内联技能正文。
- 来源 hash 与产物 hash 保证幂等；所有权标记隔离安装。手工技能、手改产物、额外文件或链接冲突保留并报告。来源不可读不回收；可确认的孤儿走 storage_maintenance.recycle_paths，可恢复。
- 主目录原有 script_contract/skill_notes/阶段技能及其测试修改保持原状；本轮在独立工作树实施，无匹配队列 ID。

## 本轮真实证据

- run_selftests.py -k skill codex：197 条，7.0 秒，全部通过（含同步器新增 11 条）。
- smoke_test.py：8/8。
- 架构首跑 310 条有 2 处失败：新增裸 JSON 读取、desktop 注释行号位移。前者改为 agent.core.read_json，后者仅同步快照行号。
- run_selftests.py -k unification_ratchet coverage_audit：7 条，23.5 秒，通过。
- run_selftests.py --layer architecture 因增量缓存执行 0 条，不能当作架构通过凭据。
- 实际安装：67 written，0 conflicts，0 errors；重复同步：67 unchanged，0 written。
- Codex app-server 的只读 skills/list（forceReload=true）返回 pipeline-script-preparation、enabled=true、scope=user，目标为用户 .codex/skills/pipeline-script-preparation/SKILL.md。只读探针未启动模型或提交创作任务。

## 未运行项与风险

- 尚未执行真实创作投递或让模型复述技能名；复述名称本身也不能证明正文已加载。当前证明是 Codex 的实际技能发现结果，不虚报模型行为。
- 方案 A 要求应用安装目录及共享资料仍可读取；移动应用后需重新同步。
- 多安装目录的同名技能不会相互接管，冲突时需要用户明确选择保留来源。
- 全量安全回归、正式 tree/round/seconds/at 凭据及最终提交待收尾更新。
