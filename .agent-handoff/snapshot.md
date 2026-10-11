# 当前快照

## 2026-10-12：O06 完成，继续 O07

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O05 已完成（R1303），**O06 已完成（R1307）**，O07 起继续。
- O06（首帧图片可用性与版本校验）：新增 L2 `keyframe_evidence.py` —— PNG 块 CRC、FFmpeg `-err_detect explode` 完整解码、尺寸/画幅、按内容摘要缓存解码事实；`source_evidence`/`make_evidence`/`frame_problem` 记录并核对分镜、提示词与参考资产版本；接入 `keyframe_lifecycle_service.replace_keyframe`、`keyframe_import.register`/`publish_frame_reference`、`keyframe_comfy.run_seedream`、`batch_frames_tool/batch_frames._run`、`stage_parallel.frames_ready`（SG-04 收紧）。
- 收口修复：`test_pet_ui`、`test_aspect_ratio_priority`、`探针_阶段门禁端到端.py` 改用真实可解码 PNG 并登记 `frame_evidence`（探针另补 config.json、已登记资产表与角色/场景图片，并修正内嵌 base64 PNG 的损坏 IDAT CRC）；`platform_tools.tool_path` 未命中不再把 None 写进缓存，否则先发生的无兜底查询会让后续带兜底的调用拿到 None（首帧完整解码 TypeError）。
- 验证证据：定向（含接缝）591/591、修复后相关 128/128、默认冒烟 8/8；干净内容树 `0e2a2f06` 全量 4504/4504、536.7 秒通过。**执行器未写绿凭据**：`save_full_safe_verification` 要求检出在 master 分支，本轮全量在 detached 工作树；`full-safe-receipts.json` 仍为 R1306/tree 48d5df7e。全量细节见 [R1307](../程序/tasks_round/tasks_round_1307_result.md)。
- 提交：实现 `a167b7c`、回归与台账 `8760e41`、`tool_path` `fbdd23d`；`project_status.md` 当前轮次 1308。
- 工作区：主树另有他人未提交改动（`程序/idea_chat.py`、`程序/idea_attachments.py`）与用户改动 `程序/配置/SKILL/预设.json`，不读取、不暂存、不覆盖；同时有并发车道在跑 `程序/smoke_test.py --architecture`，全量/提交前先看 `git status` 与本机进程。
- 下一步：O07（白模工作目录缺项目唯一身份与集维度，P1）。验证策略：默认只跑 `run_selftests.py -k <本轮模块>` + 默认冒烟；收口/合入 master 才全量，且用 master 分支临时工作树取凭据；全量失败先按定位文件定向修绿，只复验一次。
