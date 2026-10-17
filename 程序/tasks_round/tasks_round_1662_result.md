# R1662 功能轮（文档先行推广）：阶段 09 白模预演的需求／设计／测试锚定

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（文档先行，AGENTS §2.7）。只动文档与新增一个锚定测试，不改运行时代码。
2. **测试跑了吗？三个基线过了吗？** 定向 `run_selftests -k previs_scope agents_md distribution_selfcheck`：42 条全过（含新增锚定测试），未跑架构门禁全量与安全全量（只改 .md＋新增静态测试）。
3. **project_status.md 的欠账少了吗？** 欠账计数不变；后台全量转绿仍待观察。

## A 改动

- `程序/docs/REQUIREMENTS.md`：新增 S09 节（共 27 条 REQ：✅23／🟡0／⬜0／❓4），范围说明追加 S09。
- `程序/docs/DESIGN.md`：新增 S09 节（模块分工、DES-S09-xx、测试锚定表）。
- `程序/tests/test_previs_scope.py`（新增）：锚定本阶段范围类 REQ。
- `程序/architecture.md`／`程序/PROJECT_MAP.md`：仅在与代码事实不符处按事实纠正（见 git diff）。

## C 待用户拍板（文档与代码不一致，按 §2.7 第 3 条标 ❓／🟡）

- **REQ-S09-35**（❓）：阶段产物的名称与位置有四种说法互不一致：`stage_layout` 与 README 声明本阶段产物为 `previs.json`（视频阶段的输入也列它），架构文档与 SKILL 写 `previs_manifest.json`／`previsManifes…
- **REQ-S09-36**（❓）：白模成果在项目目录之外：项目拷贝、备份或移动时预演视频不跟着走，而 SG-05 仍以它判就绪。
- **REQ-S09-37**（❓）：中等动作镜头被标为“线上简单白模，制作后导入”，但 SG-05 只对复杂镜头强制预演，中等镜头不导入也能进视频生成。
- **REQ-S09-41**（❓）：白模引擎的“默认 SKILL”两处说法冲突：`pipeline-previs` 声明外部 `create-blender-story-video` 不是本阶段自动默认入口，而桌面工作流设置里 `previs` 的默认 SKILL 与可选 SKILL 就是 `c…

## D 未做与局限

- 不改运行时代码与既有测试；代码侧声明与实现不一致处只在 REQ 中标注。
- 既有测试未补 REQ docstring，仅在 DESIGN 锚定表中按文件映射。
- `test_agents_md.test_performance_history_is_declared_as_historical_only` 在 worktree 红（`维护记录/基准历史.json` 被 gitignore，只在主树存在），主树绿，非本轮引入。
- `test_round_baselines.test_round_number_continuous` 待全部阶段合入后由主树补记状态页轮次头转绿（本轮未跑该用例）。
