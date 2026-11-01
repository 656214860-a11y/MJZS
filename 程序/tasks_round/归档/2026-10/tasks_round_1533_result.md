# R1533 模型厂商保留与后台安装路径搜寻

- 类型：§3.2 修复轮。
- 测试：专项 38 项通过，追加手动路径与关闭回归 1 项通过；受影响模块检查通过（0 文件失败）、默认冒烟 8 项通过。架构 345 项中 344 通过，1 项为继承状态页轮次头 1528 未跟上既有 R1528 报告；分支禁止修改共享状态，合入 master 后补记并定向复验。
- 欠账：解决用户报告的 Provider 丢失和搜寻无反馈；不将既有全量结果冒充本轮结果。
- 分支：codex/model-manager-modes；原领取 R1530，中央编号被并行任务推进后按正式入口重新领取 R1533。

## 根因与修复

1. 本地调用内部仍需 provider=desktop；增加独立 provider_label 持久化厂商名，表格分组、下拉候选与记录回填使用该名称。API 的既有厂商推断保留。
2. 安装定位在后台线程执行，主线程显示“正在搜寻…”并禁用重复按钮，结束后恢复。异常显示到提示区；通过 BackgroundTaskLifecycle 隔离取消后的结果，切换记录/方式、浏览与关闭取消等待，手填路径不被覆盖。
3. 支持 Google Gemini 4 Argon 这类版本和代号名称，补查 Google/Gemini 安装目录；仍检查实际文件存在，不执行候选程序。

## 实测

捆绑 Python：D:/漫剧制作助手/运行环境/Python/python.exe。

- 修改前回归复现 Gemini 代号路径未找到及意外异常直接逃逸到调用方；Provider 根因从保存与回填链路确认。
- `python -m unittest tests.test_pet_ui.ModelPoolTests tests.test_claude_program_detection`：38 项通过。
- `python -m unittest tests.test_pet_ui.ModelPoolTests.test_search_preserves_manual_path_and_can_close_while_running`：1 项通过。首次测试误用不存在的测试夹具 root 属性，改用测试 Tk 主窗口后通过。
- `python smoke_test.py --affected model_pool workflow_settings pet_models_ui`：0 文件失败，冒烟汇总 9 项通过。
- `python smoke_test.py`：8 项通过。
- `python smoke_test.py --architecture`：345 项，唯一失败 `test_round_number_continuous`，1528 != 1529；待 master 合并补记后闭环。不重复整套架构扫描。
- `git diff --check` 通过；凭据扫描对本轮非空差异检查 sk-/AKIA/私钥头形态，无命中。
- 专项仍打印既有 pet_cloud.py:2099 的已忽略 TclError；测试无失败。

## 自审与交付

业务修复与定向验证通过；共享状态编号验收待合入后完成，当前为可恢复检查点，不标记任务完成。未修改真实配置、密钥或项目数据。搜寻覆盖注册表、商店记录与常见目录，不声称穷举所有自定义磁盘目录；无对应桌面程序时显示未找到并允许浏览。

本报告随源码提交；提交号可用 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_1533_result.md` 查询。未推送。
