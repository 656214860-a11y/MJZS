# 当前快照

## 2026-10-12：O08 完成，继续 O09

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O06 已完成（R1303／R1307），**O07 已完成（R1312 实现 b0c6716，收口全量 R1314）**，**O08 已完成（R1316）**，下一项 O09。
- O07（白模工作目录缺项目唯一身份与集维度）：目录改为「工作区／项目身份／集／镜头」，身份取项目 `config.json` 的 `project_id`，旧布局只读兼容、白模页打开时一次性迁移（可重复／不覆盖／失败滚回）。
- O08（白模页面与阶段门禁的复杂度规则不一致）：新增 `previs_routing.decisions_for` 作唯一有效决策（手工覆盖优先，读不到来源时退回 `classify`），门禁 `stage_parallel.previs_ready` 改用它；`ready(context,sid,source=None)` 与 `dispatch`／`automatic_candidates`／`previs_automation.start`／L3 `previs_ready` 一并按本次集解析。四场景（自动→复杂、复杂→简单、跨集同镜头 ID、删除覆盖）显示／调度／门禁一致。见 [R1316](../程序/tasks_round/tasks_round_1316_result.md)。
- 验证证据：O08 定向 `previs stage_parallel` 143/143、接缝 398/398、架构 312/312、默认冒烟 8/8，0 红；O07 收口全量见 [R1312](../程序/tasks_round/tasks_round_1312_result.md)（4516/4516、tree 12ad4759）。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。
- 轮次：中央已领到 1316；`round_claim.py next` 要求干净工作树，主树不干净，本轮在干净临时 worktree 领取。
- 下一步：O09（P1，M）——`previs_routing.py:89` 就绪只看 preview 后缀与大小，未绑定来源版本／真实可播放性；验收「改镜头调度或替换预演文件后旧就绪失效；来源未变时复用」，依赖 O07／O03／O18。默认只跑 `-k previs white_model` + 默认冒烟。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` + 默认冒烟；全量只在收口／合入 master 前跑一次且用 master 分支临时工作树取凭据；全量失败先按定位文件定向修绿，只复验一次；`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
- 新建 worktree 前置：必须补 4 个 gitlink（`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`skills/01 剧本准备SKILL/编剧技能集`、`reference/HoLLMwood`）与 `维护记录/基准历史.json`、`projects.json`，否则写作／技能组假红。
