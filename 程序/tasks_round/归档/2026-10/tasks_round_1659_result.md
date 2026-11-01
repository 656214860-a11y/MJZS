# R1659 功能轮（文档先行推广）：阶段 06 连贯性清单的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k continuity_scope agents_md distribution_selfcheck`：28 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S06 节（共 23 条 REQ：✅16／🟡3／⬜0／❓4），范围说明追加 S06。
- `程序/docs/DESIGN.md`：新增 S06 节（模块分工、DES-S06-xx、测试锚定表）。
- `程序/tests/test_continuity_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S06-16**（🟡）：漂移只比较角色锚点，不比较场景和道具；重建台账时冻结值与现值取自同一份资产，恒为一致，只有把已落盘台账与当前资产对比（G-09 `check_drift`）才有意义。
- **REQ-S06-24**（❓）：SG-02 只读已落盘台账，不核对它是否对应当前分镜／资产：台账生成后再改分镜或资产仍放行；另外，空分镜也能生成 0 批次的通过台账并被判完成。
- **REQ-S06-25**（🟡）：页面为现场计算、不落盘；只有“手动生成连贯性清单”才写盘并同步问题登记。
- **REQ-S06-26**（❓）：主观门禁 G-08（“多图抢同一件事”的优先级裁决）不计入台账待办，SG-02 不要求先裁决，只有“职责自相矛盾”阻塞；而 `confirm_gates` 和恢复提示（`stage_flow` RECOVERY_HINTS）把“人工裁决”写成本阶段要做的事。
- **REQ-S06-27**（🟡）：台账 `stage` 字段与 SG-02 返回的 artifacts 仍写旧内部标识 `03_continuity`（实际目录 `06连贯性清单`，artifacts 指向不存在的路径）；`stage_layout` 别名兼容读写，功能不受影响。
- **REQ-S06-32**（❓）：`pipeline-continuity` 声明由模型执行（capabilities 含 reasoning、vision，preferredModels qwen-max，输出 `continuityLedger`、`repairList`），实际实现是纯本…
- **REQ-S06-33**（❓）：三虎自动链没有自动生成台账的入口：`PET_STAGE_POLL` 不含 continuity，`desktop.pet_start` 对本阶段返回空串；自动档只会按推荐自动选 G-05／G-06／G-08 候选。

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
