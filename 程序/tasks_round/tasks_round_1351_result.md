# R1351：O26 白模及外部工具工作区可配置且可写

类型：功能轮（§3.1；本项为「事实/建议」→ 实现＋回归）。承接 R1267 清单 O26（O01—O25 已完成）。中央轮次 1351。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k white_model previs native_apps` 160/160；`-k white_model_workspace file_cache` 47/47；`-k ui_edges core paths stage_flow stage_parallel notification` 360/360（含渲染白模页的 Tk 用例）；`-k stage_execution stdlib_closure import_error` 20/20；`-k todo_comment_snapshot unification_ratchet coverage_audit_ratchet skip_hygiene` 全绿；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O26 关闭，清单剩 O27—O48；1351 − 1346 = 5 ≥ 5，本轮命中五轮一次的全量欠账。干净 master 工作树（HEAD=a40426f）**第 1 次全量**：4680 条／419.9 秒／1 个文件红——`tests/test_copy_rules.py` 第三人称文案规则命中 `continuity_ledger.py:596` 历史备注 `人工处理`（R1347 遗留，当时定向用例未覆盖；本轮改动未触碰该文件）。按整改路线定向把该短语改为 `人工关闭`（`-k copy_rules continuity` 54/54 绿）后复验。**第 2 次全量**：干净 master 工作树（HEAD=a480338）`run_selftests.py --all --safe` 4680 条／416.2 秒／0 文件红（`test_desktop_startup_perf` 13.8 秒、`test_perf_baseline` 20.5 秒均过，未出现已知阈值抖动）；凭据刷新 round=1351、tree=c97c1336，`last_full_safe_all_round`=1351。

## 目标（R1267 清单 O26）
- 证据：`white_model_service.py`（清单所引 `:77`／`:88` 附近）查找固定盘符／安装路径，默认在 Blender 安装目录旁或 `E:/Blender` 下建工作区。
- 影响：无 E 盘、标准用户安装在 Program Files、便携安装迁移时可能不可写。此轮未在干净系统复现。
- 建议：工具可执行文件与用户成果目录分离；首次配置检查版本和写权限，使用可配置的用户数据目录，保留旧路径只读发现。
- 验收：无 E 盘、无管理员权限、中文/空格路径、移动安装位置都能给出可执行提示，不把作品写入程序安装区。

## 实现（`white_model_service.py`，L2）
- 成果目录与工具位置解耦：`default_workspace()` = 用户数据目录 `%LOCALAPPDATA%/漫剧制作助手/白模项目`（不再取 `blender.parent/'白模项目'`，也不再退回 `E:/Blender`）；`configured_workspace()` 支持环境变量 `MANJU_WHITE_MODEL_WORKSPACE` 与设置文件 `white_model_settings.json` 的 `workspace`；`workspace()` 配置优先、否则默认，按目录缓存。
- `settings_path()`／`read_settings()`：设置文件默认落在 `%LOCALAPPDATA%/漫剧制作助手/white_model_settings.json`（可用 `MANJU_WHITE_MODEL_SETTINGS` 改），读不出来当没有。
- Blender 发现保留旧路径只读：`blender_candidates()` 顺序＝配置（`MANJU_BLENDER_EXE`／设置 `blender`）→ PATH → `D:/`、`E:/Blender` → 两个 Program Files；`find_blender()` 语义与缓存（含未命中缓存、PATH 只扫一次）不变。
- 首次配置检查：`write_check(path, create=)`（写探针即删，轻量档不建目录）、`blender_version(exe)`（`blender --version` 解析，失败不报错）、`legacy_workspaces()`（旧目录只读发现）、`diagnose()`／`diagnose_text()`（版本＋写权限＋可执行提示：缺 Blender／目录不可写改用户目录／发现旧成果目录）。`environment_summary()` 给页面一行摘要。

## 实现（`file_cache.py`，L1）
- 新增 `probe_writable(path, *, create=True)`：用 `tempfile.mkstemp` 建探针即删判断能否落文件；`create=False` 只看最近已存在父目录、不建目录；失败原样抛 `OSError` 由调用方翻成用户提示。真正的写入留在这一层，L2 领域服务不直接写盘（不新增统一棘轮第三项债务）。

## 实现（`white_model.py`／`local_previs.py`，L4）
- `white_model.py` 暴露 `environment_summary()`／`diagnose()`／`diagnose_text()`／`workspace_settings_path()`。
- 白模页（`local_previs.py`）新增只读环境摘要标签与「白模环境检查」按钮（走统一通知入口 `notify`）：打开页面即显示成果目录与写权限，按需看完整检查（版本＋可执行提示）。

## 验证
- `tests/test_white_model_workspace.py`（新）21 条：默认成果目录在用户数据目录且不等于 Blender 安装目录旁；环境变量／设置文件都能改成果目录与 blender 路径；`workspace()` 随目标变更失效；中文＋空格目录可写且探针不留痕；权限不足／缺盘符给可执行提示；轻量检查不建目录；版本读取与缓存、失败返回空串、无 exe 不执行；配置路径优先、旧盘符仍在候选表、PATH 只扫一次；旧成果目录只读发现且不误报当前目录；诊断给出缺 Blender／不可写／旧目录提示与版本，`diagnose_text` 成文。
- 台账同步：`file_cache.py` 的两处 `json.loads` 行号因新增导入平移（54→55、140→141），同步 `维护记录/架构统一基数.json` 第四项（`-k unification_ratchet` 绿）。
- 定向 160/160＋47/47＋360/360＋20/20＋注释快照／统一棘轮／覆盖率棘轮／跳过卫生全绿；架构 312/312；默认冒烟 8/8，全 0 红。

## 边界
- 成果目录默认改成用户数据目录后，旧项目成果仍在旧位置（Blender 安装目录旁）；`legacy_workspaces()` 只读发现并在检查里提示，可用配置把 workspace 指过去或手工搬移，不自动写旧位置、不删旧文件。
- `write_check` 只判「能否落文件」，不校验剩余空间／配额；探针写在最近可写目录，轻量档不建目录。
- Blender 版本读取失败只显示「未知」，不作为可用性前提；`blender --version` 经 `platform_tools.run_process`（15 秒超时）。
- 未命中 §5 升级条件（非启动路径／Tk 控件生命周期销毁重建／`storage_maintenance` 删除语义／层级登记表；改动均在已登记模块 L1/L2/L4）；但本轮号为五轮欠账点，仍按 §5 跑一次全量。
- 未实发模型请求、未重启、未真实手动点击界面（白模页 Tk 用例已在 `-k ui_edges` 中渲染通过）。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿。

[TASK_COMPLETE] O26 白模及外部工具工作区可配置且可写：成果目录默认改为用户数据目录 `%LOCALAPPDATA%/漫剧制作助手/白模项目`，与 Blender 安装位置解耦，可用环境变量或 `white_model_settings.json` 配置；Blender 发现保留 PATH／`D:`、`E:/Blender`／Program Files 旧路径只读候选；新增 `write_check`／`blender_version`／`legacy_workspaces`／`diagnose` 首次配置检查（版本＋写权限＋可执行提示）与白模页环境摘要标签＋「白模环境检查」按钮；探针写入下沉 L1 `file_cache.probe_writable`；新增 21 条用例，定向 160/160＋47/47＋360/360＋20/20、架构 312/312、默认冒烟 8/8，0 红；1351−1346=5≥5 命中五轮欠账，收口跑一次全量。
