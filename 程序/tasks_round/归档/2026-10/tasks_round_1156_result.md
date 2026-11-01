# R1156：剧本准备四阶段确认与既有分类目录

## §7 三问

1. **轮次类型**：功能轮（用户明确授权指令契约变更）。只调整所列 SKILL、writing 输出契约、首发/续发指令与相应测试，不做代码状态机。
2. **测试及三个基线**：已实跑。默认冒烟 8/8（含在 `--gate` 的 9/9 中）；架构 310/310；全量安全回归本轮未跑，历史最近凭据为 R1155，本轮差 1，未触发 §5 全量升级条件。历史结果不作为本轮通过。
3. **欠账少了吗**：完成本次四阶段指令需求；不消减无关历史欠账。尚未实发模型验证停等确认的稳定性，不能把指令测试冒充模型行为验收。

## 实现与边界

- ①项目设定 → ②剧本大纲 → ③角色卡 → ④自然剧本；缺故事大体环境/小说或漫剧类型先问。一次当前阶段一个文件、末尾“待确认”，明确确认后才推进；修改要求留在当前阶段。
- 按用户最终确认沿用规范目录：设定/角色卡入“项目设定”，大纲入“项目大纲”，最终完整自然剧本入“项目剧本”，不写 `docs/`。路径仍由既有共用函数计算，不新造目录或文件名。
- 角色卡标明“人物设定”，适配既有分类器；同一规范路径更新时保留已确认设定，避免角色卡覆盖设定。未修改分类器/保存器。
- 前三项仅供用户审阅参考，不进入 02；02 唯一来源是最终自然剧本，`character_manifest` 仍由 02 提取。`script_raw.md` 仍是内部工作稿。
- SKILL 定向引用 jingju 前四段模板，分集剧本映射为完整自然剧本；不执行参考图生成或分镜及以后阶段。frontmatter（含 output）原样保留。
- 未改 SKILL 注入策略、四角色执行机制、02 边界、状态机、用户项目数据；未重启应用或实发模型。

## 测试证据（本轮真实执行）

解释器：`D:/漫剧制作助手/运行环境/Python/python.exe`，工作目录为隔离工作树的 `程序/`。完整输出保留在 `C:/Users/LAIBIAO/AppData/Local/Temp/assistant-writing-staged/` 下所列日志，不将日志纳入 Git。

### 用户指定定向命令

`python -B run_selftests.py -k script_agent_delivery_assembly stage_prompt_governance hollmwood_agent_delivery workflow script_contract`

最终输出原文节选（`r1156-targeted-final.log`）：

```text
共 174 条用例，1.3 秒；0 个文件有红
ALL TESTS PASSED
```

首次同命令为 173 条、2.0 秒、0 红；随后补角色卡分类断言并完成最终复跑。新增测试最初在旧实现上失败，再实现修复。

### 用户指定增量门禁

`python -B smoke_test.py --gate`

首次输出（`r1156-gate.log`）：

```text
共 555 条用例，60.2 秒；0 个文件有红
通过：9 项
失败：0 项
```

最终复跑（`r1156-gate-final.log`）：

```text
共 0 条用例，0.0 秒；0 个文件有红
通过：9 项
失败：0 项
```

最终增量自检命中台账而执行 0 条，不能表述成再次执行 555 条；最终定向 174 条与架构 310 条另有实跑证据。

### 适用补充验证

- `python -B smoke_test.py --affected workflow`：104 条、6.4 秒、0 红；冒烟 9/9（`r1156-affected.log`）。
- `python -B smoke_test.py --architecture`：最终 `Ran 310 tests in 109.472s` / `OK`（`r1156-architecture-final.log`）。
- 架构首次 310 条中 1 失败：隔离树缺 Git 子包 `AIGC创作全流程`，既有 `screenplay-gate-engine.md` 不存在。按登记提交 `079df685...` 从本地主库补齐，无代码/断言修补；失败模块定向 9/9 后完整架构复测通过。首次日志保留为 `r1156-architecture.log`，局部复测为 `r1156-architecture-repair.log`。
- 测试环境还按登记提交补齐两个本地 Git 子包“剧本锻造”“编剧技能集”；未改 gitlink。
- `git diff --check` 通过；本轮文件凭据扫描（API key/AWS key/private-key 形态）0 命中文件。
- 未执行全量安全回归、真实模型对话或应用重启；应用 `.skill.md` 使用项目测试验证，未用要求独立 `SKILL.md` 包格式的通用验证器替代项目门禁。

## 有意契约变更对应断言

未删除既有测试或断言；两处旧文案断言按新契约迁移，不以宽松匹配掩盖变化：

1. `test_workflow.py::test_writing_whale_skill_and_agent_gate_are_in_the_claude_prompt`：唯一“交付物”改为唯一“正式交付物”，允许阶段参考文档，保留自然剧本正文限定与后续目录禁写断言。
2. `test_workflow.py::test_chat_creative_is_sent_without_creating_a_script_file`：内部原稿唯一落盘限制改为内部工作稿定位，并新增“由应用按既有分类保存规则落盘”断言；创意传入、续发精简、无提前写文件等断言全部保留。
3. 新增 `test_workflow_writing_stages.py` 三项测试：Agent/API 首发续发及契约的分阶段/目录/02 边界；角色卡标题命中原有分类器；SKILL 引用、前四段限制及 output 保持。

## 自审与提交

- 需求：四处口径一致，按用户最新确认替换旧任务书的 `docs/` 与“内部稿即正式稿”条款。
- 范围：生产改动仅 `workflow_settings.py`、`workflow_tasks.py` 与指定 SKILL；无新依赖、无层级变更、无过程/网络操作。
- 验证：上述实跑与未运行项分列，首次失败已闭环；模型实际停等行为仍需后续真实使用观察。
- 新问题：未新增待修代码缺陷；现有同名设定路径的角色卡合并通过指令保留已确认内容，未擅自扩展命名契约。
- 自审结论：通过。使用 minimal-diff-fix 控制修改范围，scoped-tests 限定回归，skill-creator 保持技能元数据和定向引用边界。
- 提交：实现 `1659831` 已 fast-forward 合入 master；本报告最终登记随 R1156 收尾文档提交，未 push。
- 主目录核对：原有 7 个跟踪路径修改完整保留。6 个非重叠路径文件哈希/删除状态不变；重叠 pipeline SKILL 的用户增删行逐项比较完全相同，仅叠加本轮授权内容。临时保护 stash `4d1e84f7` 已 apply 恢复并保留为恢复凭据，未删除用户内容。
- 合入后在含原有用户修改的主目录实跑 `run_selftests.py -k workflow_writing_stages script_agent_delivery_assembly`：`共 6 条用例，0.4 秒；0 个文件有红` / `ALL TESTS PASSED`，日志 `r1156-integrated.log`。其余上述完整验证在隔离树执行，不将主目录未跑项写为通过。
- 状态轮次头已更新到 1157，接力 snapshot 已记录本轮变更、验证和未运行项。

[TASK_COMPLETE]
