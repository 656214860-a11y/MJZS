# R1322：O09 白模就绪绑定来源版本与预演文件

类型：功能轮（§3.1），承接 R1267 清单 O09（O01—O08 已完成）。中央轮次 1322。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 138/138、关联 172/172（stage_* 57 ＋ ui_edges 115）、默认冒烟 8/8，全 0 红；架构 312/312；收口安全全量 4522/4522、0 红（tree 42e782ea）。
- 欠账：O09 关闭，清单剩 O10—O48。本轮号 1322 − 上次绿全量 1312 = 10 ≥ 5，且 R1318 已欠账（O08 报告把 1318 − 1312 记成 4 是算错了），因此收口补跑一次安全全量。

## 问题
- 证据 `previs_routing.py:89`：就绪只读这一镜 `预演记录.json` 的 `preview`，判存在／后缀／非空。镜头调度改过之后旧预演仍算就绪；换个同后缀文件顶名字也一样过。O07 的「项目身份／集／镜头」目录隔离把这个问题按集放大。
- 三处就绪口径各自为政：`previs_routing.ready`（门禁与调度）、`white_model_ref.descriptor`（上传接口，另有 sha256 与大小上限）、`local_previs.record_status`（白模页文案）。

## 实现
- `white_model_service` 新增（L2，仍无 `agent.core` 直写，写入由 L3 注入的 `publish` 完成）：
  - `SOURCE_FIELDS`／`shot_digest(shot)`：采用分镜里这一镜的调度摘要（动作、机位、时长、首帧、角色／资产等；数值 5 与 5.0 归一，不制造假版本变化）。
  - `source_digest(source, sid)`：按本轮采用分镜算出这一镜的来源摘要；分镜缺失或镜头不在其中返回空串。
  - `evidence_state(record, preview, source, sid)`：`ok`／`changed`／`unbound`／`missing`——来源摘要变了，或预演文件的字节数／修改时间变了，就是 `changed`。
  - `record_evidence(root, sid, source, *, publish, media=None, preview=None)`：登记 `evidence`（来源路径与摘要、预演字节数与 mtime、媒体事实、登记时间）；只导入工程还没有预演视频时不写、也不报错。
- `previs_routing.ready(context, sid, source=None)`：保留原文件口径（存在／后缀／非空），再按 `evidence_state` 收口——`changed` 判失效；`unbound` 且知道来源时也判未就绪（旧成果没绑来源，先重新校验／制作一次）；`source=None`（不知道是哪一集）时保持旧口径不变。
- `previs_automation.verify(project, sid, seconds, source=None)`：ffprobe 之前先看证据，来源变过直接不复用（旧成果留着，重做这一镜）；校验通过后写证据，来源未变时复用、不重复渲染。
- `stage_execution_service.record_previs_evidence(project, sid, source, media=None)`：L3 注入 `agent.core.save` 的登记入口。
- `local_previs`：白模页状态列改走同一判据（来源变过显示「预演已过期，请重新校验」）；「导入该镜头白模」导入视频后当场登记证据。
- 台账：`维护记录/架构统一基数.json` 第四项三处 `json.loads` 行号随代码插入平移（`previs_automation.py` 21→23、`stage_execution_service.py` 1017／1048／1064→1025／1056／1072），处置仍是 `exempt`，没有新增债务。

## 验证
- 新增 `tests/test_previs.py::PrevisEvidenceTests` 2 条，覆盖验收：改镜头调度 → 旧就绪失效；改回原调度 → 复用；替换预演文件（字节数变）→ 失效且成果文件仍在；升级前的旧记录（无 `evidence`）在有来源时判未就绪、无来源时退回旧的文件口径。
- 夹具跟随：`tests/test_previs.py` 的 `mark_ready` 由「只写 preview」改为「写 preview ＋ 与当前来源一致的 evidence」（O08 的门禁用例因此仍按同一语义断言）。
- 定向 `-k previs white_model` 138/138、0 红；关联 `-k stage_execution_service stage_parallel` 57/57、0 红；`-k ui_edges` 115/115、0 红（含白模页显示与导入路径）；默认冒烟 8/8。
- 回归修复：阶段门禁端到端探针 `维护记录/基准脚本/探针_阶段门禁端到端.py` 的 SG-05 夹具原来只写 `preview`，按新语义不构成就绪；改为经 `white_model_service.record_evidence` 登记采用分镜摘要（定向 `-k stage_gate_e2e_probe` 4/4）。只改夹具，未改探针断言。
- 架构：干净 master 工作树 `run_selftests.py --layer architecture --all` 312/312、0 红。主树因未跟踪 `outputs/` 等始终为脏（`content_tree()` 返回空），架构与全量的干净树门禁只能在临时工作树验。
- 全量：干净 master 工作树（`HEAD=e4a721a`、`HEAD:程序`=42e782ea）`run_selftests.py --all --safe`——第 1 次 4522 条／475.5 秒／1 文件红（就是上面那条探针）；定向修绿后第 2 次 4522 条／437.4 秒／0 红，凭据 round=1322、tree=42e782ea 写入 `.git/full-safe-receipts.json`，`last_full_safe_all_round` 刷到 1322（顺带清掉 R1318 欠的五轮全量。另：第 1 次全量跑在 e4a721a 前一棵树，修复提交 R1328）。

## 风险与边界
- 旧成果（没有 `evidence`）在知道来源时被判未就绪：这是有意的「宁缺勿假」，代价是升级后第一次要么重新校验、要么重做；成果文件一个不删。自动线的复用通道（`verify`）第一次跑批就会重新校验并登记，不会触发重新渲染；线上导入走登记入口。
- 失效判据用字节数＋mtime，不是内容哈希：极端情况下「同字节数且 mtime 被保留（`copy2`／改名）的替换文件」不会被判失效；真正的技术校验仍在 `previs_automation.verify`（ffprobe 时长 ±0.5）与 `white_model_ref.descriptor`（sha256 ＋接口上限）。
- 未实发 Blender／线上白模、未重启应用；单元与静态验证不等于真实交互验收。O07 的目录迁移未覆盖到的旧项目仍走旧布局。
- 台账行号平移属机械记账，未改任何处置；`tests/architecture/_layers.py`（层级登记表）、启动路径、Tk 控件生命周期、删除语义都没动，未命中 §5 强制升级条件——本次全量是为补五轮欠账而非本项强制。

[TASK_COMPLETE] 白模就绪已绑定来源分镜摘要与预演文件：改调度或换文件即失效、来源未变即复用、只判过期不删成果；定向 138/138、关联 172/172、默认冒烟 8/8、架构 312/312、收口安全全量 4522/4522（0 红，tree 42e782ea）。
