# 当前快照

## 2026-10-12：O20 完成，继续 O21

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O19 已完成，**O20 已完成（R1344）**，下一项 O21。
- O20（保留 Animatic 强校验并降低大媒体重复读取成本）：`file_cache.file_digest` 新增 1 MiB 分块流式 sha256 + `(mtime_ns,size)` 缓存（`clear`/`invalidate` 同步清理）；`animatic_service.evidence` 源分镜与全体成果摘要从 `read_bytes()+sha256` 改为 `file_digest`，不再整份读媒体；三项人工确认与 `validate_bundle` 的「发布前不得代签」不变（写 True 只经桌面用户勾选）。实测 64 MiB 文件峰值内存 64.1→2.1 MiB、重复校验 114ms→0.21ms。见 [R1344](../程序/tasks_round/tasks_round_1344_result.md)。
- 验证证据：O20 定向 `-k animatic file_cache` 41/41、锚定 `-k animatic_timeline stage_completion previs` 117/117、架构 312/312、默认冒烟 8/8，0 红；1344 − 1341 = 3 < 5 且未命中 §5，本轮不跑全量。台账第四项 `file_cache.py` 两处 json.loads（53→54、112→140）已同步。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只能点名自己的路径。主树永远“脏”，`content_tree()` 在脏树返回空，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`（要求干净工作树）；本轮 1344；收口全量在干净 master 工作树 `run_selftests.py --all --safe`。**每次在主树提交后，master ref 前移会让 `o07-fullsafe-master` 显示自己的文档为「已暂存改动」，领取／全量前先 `git reset --hard HEAD` 即可**。
- 下一步：O21（见 `tasks_round_1267_result.md` O21 条目）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑（上次绿全量 1341；到 1346 起跑）。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
