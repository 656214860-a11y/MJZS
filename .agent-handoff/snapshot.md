# 当前快照

## 2026-10-12：O45 完成，继续 O46
- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O44 已完成，**O45 已完成（R1372）**，下一项 O46（模块治理和性能按热点逐段推进，P3／事实·建议，M/L）。
- O45（把分发声明变为可复验的干净安装流程）：新增 `程序/scripts/distribution_build.py`——`parse_manifest` 从 `distribution_manifest.md` 两张表取反引号模式（声明唯一来源）；`pattern_regex`（`**` 跨目录、`*` 不跨、目录以 `/` 结尾＝整棵子树）；`plan(root, manifest)` 分「keep／excluded／undecided」三桶；`build(destination, ...)` 只把清单内文件复制到**全新**输出目录并写 `分发清单.json`（版本＋逐文件 sha256＋字节数；拒绝输出到源目录内部、拒绝覆盖非空目录、拒绝未决定未清时静默继续），全程不删除不移动、源目录零改动；`verify(destination, ...)` 校验「输出零排除项／必需入口齐全／摘要自洽／`程序/skills/00全流程SKILL/jingju-skills` 整包仍在」。精化 `distribution_manifest.md`（补保留：生产 `程序/*.py`／`程序/agent/**`／说明／附加工具／batch_frames_tool／用户说明与图标；补排除：`.wt/**`／`.agent-handoff|.claude|.codex/**`／`outputs/**`／程序本地产物／`程序/logs/**`／`程序/.*.out`／`维护记录/**`／开发文档），并加「可复验构建器」一节。见 [R1372](../程序/tasks_round/tasks_round_1372_result.md)。
- O45 实测与边界：真实开发目录 `--plan` → keep 1170／excluded 4684／undecided 36（未决定项故意留给人工，不是欠账）；本轮**未**在真实目录执行 `--build`（只用临时合成树验证）；新 Windows 用户／非管理员／离线链路／覆盖式升级这些验收**未实机验证**；jingju 按「保留整包并校验存在」处理（代码仍引用它）。
- O45 契约变化：只新增 `scripts/` 工具与新测试、扩清单文档，未改任何运行期模块／配置默认值／界面；`scripts/` 不参与分层扫描（未改 `_layers.py`），但会被 `test_unification_ratchet` 扫到——读摘要改用 `agent.core.read_json`（裸 `json.loads` 会被判「未登记新增债务」）。
- O45 验证证据：新增 `tests/test_distribution_build.py` 12/12；定向 `-k distribution_build` 12/12；架构 312/312；默认冒烟 8/8。
- O45 全量：1372−1371=1<5 无五轮欠账且未命中 §5，收口在干净 master 工作树跑一次 `--all --safe`：全量结果待收尾补记。

## 2026-10-12：O44 完成（历史）
- O44 = R1371（密钥四态可诊断＋诊断预览与回显脱敏）；全量 4912/4912、0 红、752.38 秒（凭据 round=1371、tree=de0084a9…）。详情见 [R1371](../程序/tasks_round/tasks_round_1371_result.md)。

## 2026-10-12：R1335 并入 master（阶段④分集增量上下文）
- 分支 `codex/episode-incremental-context` 已合入 master。`script_contract.split_script_episodes`＋分集账本 `write_dir(project,'script')/剧本分集增量账本.json`（每集 sha256＋based_on 其余集快照）；`writing_api.reply()` 前注入「只贴改动集正文」、唯一发布点 `_save_formal_script()` 后更新账本；`workflow_tasks._episode_change_notice()` 只给本地 Agent 报集号；首次／无账本退化为全量。见 [R1335](../程序/tasks_round/tasks_round_1335_result.md)。
- 未改 `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md` 与 `structure_script()` 场次解析。
## 2026-10-12：O43 完成（历史）
- O43 = R1370（检查点版本化＋只读恢复预览）；全量 4899/4899、0 红、963.97 秒（凭据 round=1370、tree=4a7be90a…）。详情见 [R1370](../程序/tasks_round/tasks_round_1370_result.md)。

## 2026-10-12：O40 完成（历史）

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O40 已完成（见上一节）。
- O40（项目管理、备份与清理统一空间和恢复说明）：`projects.py`（L2）新增 `_drop_registration_entry`（登记移出索引一律先改 deepcopy、发布成功才提交 `self.info`；`OSError` 时内存回退到磁盘事实并带 `ui_message` 重抛），`delete`／`unlink_registered_project`／`clear_missing_registration` 三条删除／清除路径统一改走它，删除路径在登记写失败时给出「内容已移入回收站、点『重新查找项目』或『重建项目索引』、仍可从回收站恢复」的定向指引；新增模块级 `_discover_candidates`（把 `reconcile_missing` 的一级目录扫描抽出复用、行为不变）与 `Projects.rebuild_registry`（按磁盘事实保留仍在的登记、移除失效登记、补登新目录；无变化不写盘；只读写一级目录与登记文件，不移动也不删除任何项目内容，回收站永不回流）。`desktop.py`（L4）新增 `Desktop.rebuild_project_index` 与主页「重建项目索引」按钮，主页状态栏与删除确认框把清屏／删历史／移入回收站／永久清除／可再生缓存分开表述（移入回收站＝可恢复、不是永久清除、同盘回收不等于释放空间）。见 [R1367](../程序/tasks_round/tasks_round_1367_result.md)。
- 契约变化：删除／清除路径的登记写失败不再让内存先显示成「已删除」（内存与磁盘登记都停在删除前状态）；新增 L2 公开方法 `rebuild_registry`（返回 `{kept,dropped,added,changed}`）；「永久清除」只做界面单独明示，**未新增任何永久删除入口**（`projects.py` 只回收，无 `rmtree`／`unlink()`）；「从备份恢复」本轮按「项目库回收站即删除前可恢复副本」实现与验证，未新建独立备份子系统。
- 验证证据：新增 `tests/test_project_recovery.py` 8/8；定向 `-k projects project_ backup recovery reconcile desktop storage recycle` 149/149；架构 `--layer architecture --all` 312/312；默认冒烟 `smoke_test.py` 8/8；0 红。
- 全量：1367−1364=3<5 无五轮欠账，但改动命中 §5（项目删除语义），收口在干净 master 工作树 `o40-fullsafe-master` 跑 `--all --safe`：第 1 次为新工作树环境未就绪（缺 4 个嵌套仓库与 3 个忽略运行文件）假红，补齐后定向修绿，第 2 次 4859/4859、0 红、527.6 秒，凭据 round=1367、tree=1d7630f1（＝`HEAD:程序`），`last_full_safe_all_round=1367`。
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`、`.codex/`、`.agent-handoff/archive/`、`程序/outputs/`、`程序/配置/宠物/配置.json`，不读取、不修改、不暂存、不覆盖；提交只点名自己的路径，绝不 `git add -A`。
- 干净 master 工作树：`o07-fullsafe-master`（与主树共享 git common dir；勿动 `o06-fullsafe*` 等）；领号／全量前先 `git reset --hard HEAD`。
- 轮次：O40 为 R1367、O41 为 R1368；`project_status.md` 的 `当前轮次` 已改为 1369（＝最新结果报告号＋1）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟 `smoke_test.py`；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`），并先查 `full-safe-receipts.json` 有无 7 天内同 `HEAD:程序` 内容树绿凭据可复用，只有命中 §5（启动路径／Tk 控件生命周期／删除语义／层级登记表）才强制重跑；全量失败先按定位文件定向修绿、只复验一次（报告写「第 N 次全量」，2 次仍不过就升级单独修复轮）；`test_desktop_startup_perf`／`test_perf_baseline` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
