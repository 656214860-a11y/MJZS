# 当前快照

更新：2026-10-17。[R1610 评估](../程序/tasks_round/tasks_round_1610_result.md) 的 12 项优化清单（Q1–Q12）已全部完成并合入 master（R1611–R1626）；目标是清单完成后停止，不再自动开新项。

## R1610 清单完成映射
- Q1／Q3 静态卫生门禁＋无效转义修复 → R1611（a074755）
- Q2 函数行数棘轮 → R1612（b7ca5fb）
- Q4 持久化产物版本契约（artifact_schema）→ R1613（ef946f1）
- Q5 适配器失败分类一致性 → R1614（5adbcfa）
- Q6 金额不变量（修 RequestLedger.price 真实缺陷）→ R1615（649ce4c）
- Q7 覆盖率度量＋基线＋门禁 → R1616（b7e8af7）
- Q8 生命周期状态机全转移表 → R1617（7ad55e0）
- Q9 大文件拆分＋运行期诊断统一 → R1618–R1623（a0aa441…d8d0fc5）
- Q10 机器可判定出口（`本地CI.cmd exit` / `scripts/local_ci.py exit`）→ R1624（13dea0a）
- Q11 文档三件（data_model.md / task_states.md / runbook.md）→ R1625（ce35a5f）
- Q12 辅助依赖清单与解释器策略（runbook §8／§9）→ R1626（7188f08）

## 最近一次完整安全全量（真实）
R1624（HEAD 13dea0a）：2026-10-17 02:01:23 绿、502 秒、0 红，凭据 round 1624／内容树 bde64b00，架构门禁含在内。
上一档 R1619（b6863b4）：678 秒、0 红。

## 本轮顺手修掉的真实回归（拆分轮引入）
- R1621 拆 `pet_cloud.py` 时 `pet_cloud_timing._fade_in` 用了没定义的 `SHAPE_ROUND`：`Cloud.show` 必经此路，云朵／对话框／贴纸全部打不开。R1624 把四个形状名改由 `pet_cloud_shape.py` 定义并原样转出，`test_pet_ui` 598 项全绿。
- R1620 拆 `skill_panel.py` 后 `tests/test_skill_notes.py` 的补丁打在被转出的名字上而静默失效。R1624 改打在定义处 `skill_panel_support.markdown_document`。

## 接续
先按 程序/AGENTS.md §0 完成启动阅读，再读本目录入口、风险、待办。清单已闭环，后续工作须由用户新授权，不自动展开。
