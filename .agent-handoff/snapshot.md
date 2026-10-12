# 当前快照

## 2026-10-12：O34 完成，继续 O35

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O33 已完成，**O34 已完成（R1359）**，下一项 O35（SKILL 引用闭包与依赖类型应明确，P2／事实·建议，M）。
- O34（交付包可独立检查、剪映交接能力如实标注）：`handoff_service.py`（L2）新增 `BUNDLE_MANIFEST_NAME='交接包清单.json'` 与 `MEDIA_PACKAGE_*`，`publish_bundle` 产出 `summary`（镜头覆盖 included/expected/missing、是否带字幕、逐镜来源版本），新增 `build_bundle_manifest`（逐文件 size＋sha256，清单不自列）与纯函数 `verify_manifest`（缺失／大小／摘要不符、声明齐全却漏镜、声明含字幕却无 `对白.srt` → 缺陷；声明缺镜只登记不算失败）；`stage_execution_service.py`（L3）`publish_handoff_bundle` 把清单并入同一原子成果包，新增只读 `verify_handoff_bundle`（拒 `../`、流式核对，换目录解包也能验）；`desktop.py`（L4）后期页新增「校验交接包」按钮与说明「素材交接包只给有序视频与字幕，不是剪映草稿」。见 [R1359](../程序/tasks_round/tasks_round_1359_result.md)。
- 验证证据：定向 `-k test_handoff_bundle test_handoff_service` 16/16；关联 `-k test_copy_rules` 14/14＋`architecture.test_handoff_publication_boundary` 4/4、`-k test_ui_edges` 115/115、`-k stage_execution stage_completion final_viewer handoff delivery skill_tools engine_probe` 107/107；架构 `--layer architecture --all` 312/312；默认冒烟 8/8，0 红。1359 − 1356 = 3 < 5 且未命中 §5，本轮不跑全量。**上次绿全量：1356（tree 006d0295、4749/4749、425.3 秒、0 红），下一五轮欠账点 1361。**
- 环境观察（与本轮改动无关）：主树 `程序/desktop.py` 工作树为 LF，而 `.gitattributes` 钉 `程序/desktop.py text eol=crlf`，故主树 `test_line_endings` 的 victims 用例红；干净 master 工作树按 checkout 为 CRLF，同一用例 16/16 绿。提交后 blob 归一化，不影响产物。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`，不读取、不暂存、不覆盖；提交只点名自己的路径。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：中央号靠 `round_claim.py next`（R1359 已在干净 master 工作树领到）；`project_status.md` 的 `当前轮次` 须＝最新结果报告号＋1（现为 1360）。
- 提交：R1359 待提交，路径＝`程序/handoff_service.py`、`程序/stage_execution_service.py`、`程序/desktop.py`、`程序/tests/test_handoff_bundle.py`（新）、`程序/tests/test_ui_edges.py`、`程序/维护记录/架构统一基数.json`、`程序/tasks_round/tasks_round_1359_result.md`（新）、`程序/project_status.md`、`.agent-handoff/{snapshot,work-log,validation,backlog}.md`；门禁与提交姿势见 [work-log](work-log.md)。
- 下一步：O35——证据 `workflow_settings.py:549` 内联只处理直接 Markdown 里的 md/txt 引用、不递归全部嵌套引用，`skill_registry.py:403` 未注册 `dependsOn` 可被视为外部子模块而非一律错误；建议区分技能依赖／文档引用／可执行工具／可选资源，确需递归时检测环／路径边界／重复／深度／预算，清单显示实际闭包，保留全流程 AIGC 引用、不恢复对可删除 jingju 副本的隐式依赖；验收：直接／嵌套／循环／缺失／外部工具依赖均得明确结果，改删非依赖 jingju 包不影响剧本技能，必要引用缺失阻止发送而非静默忽略。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑。`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
