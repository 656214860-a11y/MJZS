# R1318：O08 白模复杂度路由在页面、调度与门禁之间统一

类型：功能轮（§3.1），承接 R1267 清单 O08（O01—O07 已完成）。中央轮次 1318。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 143/143、接缝 398/398、架构门禁 312/312、默认冒烟 8/8，三条基线全绿（见「验证」）。
- 欠账：O08 关闭，清单剩 O09—O48；本轮不新增全量欠账（1318 − 1312 = 4 < 5）。

## 问题
- `previs_routing.py:51` 的 `entries()` 合并 `episode|shot` 手工覆盖，白模页（09）和 Agent 调度用的都是它；而 `stage_parallel.py:726` 的阶段门禁 `previs_ready` 直接 `classify(shot)`，看不到手工覆盖。用户把复杂镜改成简单后，页面显示「无需白模」，门禁却仍要求补预演；反过来把简单镜改成复杂，门禁又不要求任何预演。

## 实现
- `previs_routing.decisions_for(context, source, shots)`（新）：唯一有效决策——`entries()` 的手工覆盖优先，来源读不出来时退回 `classify`，返回 `{sid: {level, reason, route, override}}`。
- 门禁 `stage_parallel.previs_ready` 改用它取每镜等级（保留 `classify` 兜底），不再自行分类。
- `previs_routing.ready(context, sid, source=None)` 增开 `source`，按本次所在集解析白模目录；`dispatch`、`automatic_candidates`、`previs_automation.start` 与 L3 `stage_execution_service.previs_ready(project, shot_id, source=None)` 一并把本次集传进去，跨集复用同一镜头 ID 时三者看到的是同一集、同一决策。
- 覆盖来源与理由随决策一起返回（`override` 为 `auto`／`simple`／`medium`／`complex`，`reason` 为覆盖或自动分类的理由），页面与门禁读同一份。

## 验证
- 新增 `tests/test_previs.py::RoutingGateConsistencyTests` 4 条，正好覆盖验收四场景：
  - 自动→复杂：手工改成复杂后，显示、调度与门禁都算它需要白模（门禁从「没有需要白模的镜头」变为「1 个镜头需要白模，都有预演」）；
  - 复杂→简单：手工改成简单后，门禁不再要求预演；
  - 跨集相同镜头 ID：`EP001|SH001` 覆盖为简单、`EP002|SH001` 仍自动复杂，门禁只对 EP002 那一镜要求预演；
  - 删除覆盖：`set_override(...,'auto')` 清掉记录后，显示、调度与门禁一起回到自动分类。
- 定向 `-k previs stage_parallel` 143/143、0 红；接缝 `previs stage_parallel stage_execution local_previs stage_completion white_model stage_models manual_gate row_targets ui_edges desktop` 398/398、119.2 秒、0 红。
- 架构门禁 `smoke_test.py --architecture` 312/312 OK；默认冒烟 8/8。
- 回归修复：`tests/test_previs_monitor.py`、`tests/test_ui_edges.py` 中把 `previs_routing.ready` 打桩成两参 lambda 的夹具，跟随新签名补 `source=None`；只改夹具，未改断言与业务逻辑。
- 全量：本轮号 1318 − 上次绿全量 1312 = 4 < 5，且改动不命中 §5 升级条件（启动路径／Tk 控件生命周期／删除语义／层级登记表），按用户 2026-10-12 指令本轮不跑全量。

## 风险与边界
- 只统一「谁说了算」，未改复杂度判定规则本身；自动档仍只由 `classify` 的启发式决定，语义调整属后续清单项。
- 门禁现在按集解析预演就绪，依赖 O07 的集目录；未迁移的旧项目在打开白模页迁移前仍走旧布局（同项目两集同镜头 ID 共用目录），此时页面与门禁一起退化为旧行为，属已知窗口。
- 未实发 Blender／线上白模调用、未重启应用；本轮为纯逻辑与静态验证，不等于真实交互验收。

[TASK_COMPLETE] 单一有效决策已统一，四场景显示／调度／门禁一致；定向 143/143、接缝 398/398、架构 312/312、默认冒烟 8/8，0 红。