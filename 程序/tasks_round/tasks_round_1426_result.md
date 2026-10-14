# R1426 结果：环境自检（路线图 B）

- 轮次类型：§3.3 功能轮（小）。范围：新增 `environment_check.py`（L4，只读）、`pet_settings_ui.py`（「设置 → 开发信息」加「环境自检」按钮）、`tests/architecture/_layers.py`（登记层级）、新增 `tests/test_environment_check.py`、`tests/test_pet_settings.py` 1 项、路线图状态。工作位置：独立 git 工作树 `.wt-r1426`（分支 `codex/r1426-env-check`），原因是主目录有另一任务未提交的 `desktop.py`／`idea_chat.py`／`platform_tools.py`／`stage_execution_service.py` 改动，`round_claim` 拒绝在脏树领号；未触碰这些文件。

## 内容

只读核对并给出「正常／提示／缺失」与下一步：FFmpeg／FFprobe（config.json 路径优先，其次 PATH；配置路径失效但 PATH 有则提示）、ComfyUI 桌面程序（`comfy_runtime.executable`）、Blender（`white_model_service.find_blender`）、Claude Desktop／Codex／Claude Code 命令行（`workflow_settings.find_program`，命令行条目指向图形程序给出 R1425 的说明）、API 模型密钥（`model_pool.key_of` 只判有无，不返回内容）。可选依赖缺失只是「提示」，FFmpeg 缺失与全部 API 密钥缺失才是「缺失」。

不启动任何程序、不联网、不写文件；各探测函数可注入。入口：设置 → 开发信息 → 「环境自检」，弹窗显示全文，状态栏显示汇总。

## 测试

- 新增 5 项（`test_environment_check`）＋ 1 项（设置页按钮）。Linux 副本（Python 3.12.13，非随附解释器）`test_environment_check` ＋ `test_pet_settings` 共 58 项全部通过。
- 架构目录 341 项：除 R1425 行号基线 2 项（已在 R1425 修正并复跑通过）外全部通过，新模块层级登记生效。
- 未运行：随附解释器冒烟与全量。1426−1420=6≥5，**安全全量欠账仍待 Windows 补跑**，本轮不冒充。

## 自审

仅改授权范围；未改用户配置与密钥；输出不含密钥；未引入依赖。
