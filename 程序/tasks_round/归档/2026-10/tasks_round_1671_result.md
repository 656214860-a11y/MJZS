# R1671 修复轮：按用户裁决落实阶段 12／13 的 ❓ 条目

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（用户对 R1665／R1666 结果文件 C 节逐条裁决为“修复”）。
2. **测试跑了吗？三个基线过了吗？** 定向（editing／delivery／edit_export／stage_flow／stage_exec／stage_completion／desktop／ui_／boundaries／skip／agents_md／distribution_selfcheck／layers）430 条，修复一处测试替身后全绿；分支内默认冒烟 8/8；架构门禁全量与安全全量见最后一轮结果文件。
3. **project_status.md 的欠账少了吗？** 全量欠账 +1，合入后统一补跑。

## A 改动

- REQ-S12-04：`DEPENDS['edit']` 改为 `('video','audio')`；S11 配音与字幕文件只登记路径与摘要到 `edits.json`，不混入画面。
- REQ-S12-25：粗剪时真写 `edits.json`（`Studio.edit_settings`／`save_edit_settings`）。
- REQ-S12-32：后期页新增“导出平台版本”按钮（UI 只注入回调），产物放 `平台版本/`。
- REQ-S12-33：实现镜头间转场与背景音乐（ffmpeg 滤镜，`Studio._join_shots`）；背景音乐先复制进项目并纳入商用授权清单。音效、配音混音、预览生成、音画预检未做，文档与 SKILL 改为真实范围。
- REQ-S13-24／25：确认交付时写 `qc_report.json`、`delivery.json`、`delivery_manifest.json`；质检不通过则拒绝确认，完成判定核对质检结论；`delivery.validate`／`package` 有本地实现。
- REQ-S13-26：导入与完成判定共用同一份扩展名集合，导入也接受 `.mkv`。
- REQ-S13-28：交付页常驻显示商用状态。
- REQ-S13-52：`stage_exec` 按交付模板四步程序化执行。
- 为消除循环依赖调整了 `stage_completion_service` 中 script／script_structure 完成判定的位置，行为不变。
- 测试：`test_delivery_scope`、`test_editing_scope` 的“差距锚点”断言改为正向断言（规格变更，非弱化）；`test_edit_export` 的 `test_encode_does_not_report_success_when_delivery_lists_fail` 替身补 `edit_settings`／`_join_shots`（`_encode` 新增依赖，断言未动）。
- 与 R1670 在 `architecture.md` SKILL 总表同一段冲突，已手动合并。

## B 验证

- 定向 430 条在补齐替身后 0 红；按钮仅做代码与单元层验证，未在真实 Tk 窗口手点。

## C 待用户拍板

- 旧的、不含质检结论的交付确认需要重新确认。
- `delivery.ready` 事件仍无发布方，文档已写明“仅声明”。
- `skills/` 内 SKILL 文本（后期剪辑转场／配乐范围等）清单见分支报告，未改 SKILL 之外的子仓库。

## D 未做与局限

- 未做桌面界面真机手测；未跑架构门禁全量与安全全量。
