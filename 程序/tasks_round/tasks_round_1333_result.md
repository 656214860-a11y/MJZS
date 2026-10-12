# R1333：O11 人工确认绑定被确认的内容摘要

类型：功能轮（§3.1），承接 R1267 清单 O11（O01—O10 已完成）。中央轮次 1333。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 101/101（confirm_gates／asset_detail／stage_wiring／asset_plan）、接缝 172/172（ui_edges／stage_execution／stage_parallel）、架构相关 15/15、默认冒烟 8/8，全 0 红。
- 欠账：O11 关闭，清单剩 O12—O48；本轮号 1333 − 上次绿全量 1330 = 3 < 5，且改动不命中 §5 升级条件（启动路径／Tk 控件生命周期／删除语义／层级登记表 `tests/architecture/_layers.py`），按用户 2026-10-12 指令本轮不跑全量。

## 问题
- 主观门禁的 key 用名称拼（`anchor:<角色编号>`／`canon:<角色编号>`／`conflict:<批次或镜头编号>`），确认记录只存 choice／by（O10 后加了 state）；`pending()` 只看 key 在不在，于是同名角色／同批次的候选换掉、优先级改了、台账被外部改过，确认记录自己判断不出过期。
- 已有 `reopen_asset_plan_choices` 能显式撤销，但那是「用户主动重开」；风险在没经过这个入口的内容变化。

## 实现
- `confirm_gates.content_digest(*parts)`：候选内容的 sha1 前 12 位，只喂「决定候选长什么样」的字段。
- 三条候选各自带 `digest`：G-05 = 角色编号＋名字＋简介（description＋appearance）；G-06 = 角色编号＋名字；G-08 = 批次名＋优先级列表。
- `record(..., digest='')` 把摘要存进确认记录；`pending()` 的判据变成「已确认 **且** 摘要还对得上」，对不上就重新摆出候选。
- 摘要缺一边（旧记录没有 `digest`，或调用方传的是裸 key）按升级前口径放行，老项目不会因为升级被重新问一遍。
- 打通三条写入路径：`adopt_asset_plan_choice(..., digest=)`（资产详情页 `_pick` 从候选项带上来）、`desktop.pick_gate(..., digest=)`（连贯性页「采用推荐」）、`desktop.auto_decide_gates`（Agent 自动那一拍）。
- 摘要只含「输入」，不含确认结果本身（不喂已写入的 anchor／canonical_board），否则一确认就把自己作废。

## 验证
- 新增 `tests/test_confirm_gates.py::ConfirmationBindingTests` 5 条：
  - 替换候选（改角色 description）只让那一个角色的 G-05 重新摆出、另一个角色不受影响，且 `run('G-05')` 不再通过；
  - 改冲突优先级（外部改台账那一行）让该批次重新问；
  - 跨集同批次 ID 共用一个键，但内容不同就必须复核（宁多问不漏放）；
  - 与候选无关的字段（`costume_id`）变化不扰动；
  - 旧记录没有摘要仍按已确认处理。
- 定向 `-k confirm_gates asset_detail stage_wiring asset_plan` 101/101、0 红；接缝 `-k ui_edges stage_execution stage_parallel` 172/172、0 红；架构相关 `-k unification_ratchet confirm_gates_json_boundary todo_comment_snapshot layers no_circular_import stage_paths` 15/15、0 红；默认冒烟 8/8。
- 台账：`stage_execution_service.py` 的 `json.loads` 仍为 108／1039／1070／1086（本轮全是单行替换，行数未变）；TODO 注释快照无变化。

## 风险与边界
- 跨集共用一个键的旧问题没解决（key 里没有集身份，属 O07 同类）；本轮只能做到「内容不同就复核」，做不到「两集各自独立记住」。真正分开要动 key 形状与 `reopen` 语义，留给后续清单项。
- 老项目里已有的确认记录没有摘要，升级后仍按已确认处理：这些历史确认不会因为内容变化自动失效，要等用户主动重开一次才会带上新摘要。
- 摘要只覆盖「候选怎么生成」，不覆盖资产图片本身换没换；图片级证据属 O03／O09／O18 线。
- 未重启应用、未真实点击界面；单元与静态验证不等于真实交互验收。

[TASK_COMPLETE] 确认记录绑住候选内容摘要，内容变了只失效受影响的那条并重新摆出候选；替换候选／改冲突优先级／外部改台账／跨集同 ID 四种变化都触发复核，无关字段不扰动；定向 101/101、接缝 172/172、架构 15/15、默认冒烟 8/8，0 红。
