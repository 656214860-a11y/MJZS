# R1330：O10 资产「确认并采用」改为可恢复事务

类型：功能轮（§3.1），承接 R1267 清单 O10（O01—O09 已完成）。中央轮次 1330。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 96/96（`confirm_gates`／`asset_detail`／`stage_wiring`／`asset_plan`）、架构棘轮 5/5（`unification_ratchet`／`confirm_gates_json_boundary`）、默认冒烟 8/8，全 0 红；收口安全全量见「验证」。
- 欠账：O10 关闭，清单剩 O11—O48；本轮收口补跑一次安全全量（1330 − 上次绿全量 1322 = 8 ≥ 5，命中五轮周期）。

## 问题
- `adopt_asset_plan_choice`（L3）原来「先记确认、再应用选择」，注释明说第二步失败保留已有确认。应用失败时 `03_continuity/output/gate_confirmations.json` 里已经有这条 key，而 `confirm_gates.pending()/run()` 只按「key 在不在」判断，于是人工门禁 G-05／G-06 按「已确认」跳过——出现「未采用却已审核通过」。
- 同一件事有两条路且语义不一致：`asset_detail._pick` 走「先确认后应用」，`desktop.pick_gate`／`auto_decide_gates` 走「先应用后确认」。`reopen_asset_plan_choices` 也按顺序撤销。

## 实现
- `confirm_gates`（L0 契约）新增相位常量 `PENDING`／`APPLIED`／`FAILED`；`record(..., state=APPLIED)` 把相位写进每条确认；`pending()` 的判据改为「只有 applied 算点过」——pending／failed 视同未确认，候选会重新摆出；旧记录没有 `state` 按 applied 处理，避免升级后把人已经点过的门禁重新问一遍。新增 `state_of(project, key)` 供界面与测试读当前相位。
- `stage_execution_service.record_stage_confirmation(..., state='applied')` 透传相位，默认保持旧语义（`desktop` 的 Agent 自动记录不变）。
- `adopt_asset_plan_choice` 改为「先记 pending → 落盘 → 成功记 applied」：进程中断只留 pending，落盘失败记 failed（写 failed 本身失败时不掩盖原异常并原样抛出）；两种没走完的情况都不被门禁当成已确认，只有落盘成功才记 applied。
- `asset_detail._pick` 把失败包成带恢复入口提示的 `RuntimeError`（「确认没有生效，候选还留着，可再点一次」），仍由 `desktop.safe` 报给用户，且不刷新页面、不写成功状态。

## 验证
- 新增 `tests/test_confirm_gates.py::AdoptTransactionTests` 6 条：应用失败留 failed 且 `run('G-05')` 不通过（未采用不通过门禁）；应用前中断（KeyboardInterrupt，不被 `except Exception` 吞掉）留 pending；成功记 applied 且不再问；重复点击两次仍 applied 且 apply 调两次；旧记录无 `state` 按 applied；未知 key 相位为空串。
- 改 `tests/test_asset_detail.py`：`test_pick_second_step_failure_never_counts_as_confirmed`（事件序列 `['record','apply','record']`＝待办→落盘→失败，不刷新、不报成功）、`test_pick_first_step_failure_stops_before_applying`（第一步失败不落盘）。
- 定向 `-k confirm_gates asset_detail stage_wiring asset_plan` 96/96、0 红；架构棘轮 `-k unification_ratchet confirm_gates_json_boundary` 5/5、0 红；默认冒烟 `python smoke_test.py` 8/8 通过。
- 台账：`stage_execution_service.py` 第四项三处 `json.loads` 行号随 adopt 加长平移（1025／1056／1072 → 1039／1070／1086，仍 exempt）；`confirm_gates.py` 无 `json.loads`，不受影响。
- 全量：本轮收口在干净 master 工作树跑 `run_selftests.py --all --safe`，实测结果与凭据补记在下一提交的「收口记录」一节（本轮先提交实现、测试与台账）。

## 风险与边界
- 相位只解决「谁算确认完成」，不解决「确认绑没绑内容」：同名角色／批次换了候选，旧确认仍可能算数——属 O11，本轮不动。
- `reopen_asset_plan_choices` 仍是按 key 顺序撤销、失败即停；中断会留下「一个撤了、一个没撤」的确定状态（每条各自正确），本轮不改它的语义。
- `record` 的确认字典新增 `state` 键；仓库内没有严格比对该字典的断言，但外部读取方若做全等比较会看到多一个键。
- 未重启桌面应用、未真实点击界面；单元与静态验证不等于真实交互验收。

[TASK_COMPLETE] 采用改为「待办→落盘→确认」可恢复事务，只有落盘成功才计人工确认完成；第二次写入失败、进程中断、重复点击三种场景都有确定状态，不再出现「未采用但已审核通过」。
