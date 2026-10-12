# 当前快照

## 2026-10-12：O12 完成，继续 O13

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O11 已完成（O11 R1333），**O12 已完成（R1334）**，下一项 O13。
- O12（TTS 批次配置与缓存身份不完整）：`tts_api` 新增 `request_identity`／`freeze_settings`／`batch_identity`；逐句清单带端点＋模型＋音色＋语速，`run_lines` 开批冻结配置（中途改设置不混用），`line_done` 沿用前按 `sha256` 复核成品（旧清单退回「文件非空」），`publish_line` 记 `bytes`／`sha256`，`script_signature` 加 endpoint，`批次.json` 记 `identity`（不含密钥）。见 [R1334](../程序/tasks_round/tasks_round_1334_result.md)。
- 验证证据：O12 定向 49/49、关联 115/115（ui_edges）、架构相关 12/12、默认冒烟 8/8，0 红；夹具跟随 `synthesize(..., settings=)` 新签名补 `**_kwargs`（只改夹具）。O11 定向 101/101、接缝 172/172、架构 15/15。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”（未跟踪 outputs/ 等），`content_tree()` 在脏树返回空，因此全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；在 `o07-fullsafe-master` 干净 worktree 领取。**每次在主树提交后，master ref 前移会让该 worktree 显示自己那几份文档为「已暂存改动」，领取前先 `git reset --hard HEAD` 即可**。本轮 1334。
- 下一步：O13（P2，M）——剧本准备把「对话、工作稿、正式采用」显示为明确状态（报告约 `程序/tasks_round/tasks_round_1267_result.md` O13 条目）。验收按该条目的验收句执行。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次且用 master 分支临时工作树取凭据；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1330，故 1335 起再跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
