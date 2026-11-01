# R1431 结果：下载收回、启动白屏、统一调色板、钩子 LF 与本地 CI

- 轮次类型：缺陷修复＋用户授权的视觉统一与工程项（路线图 G）。工作位置：主目录 master；`file_cache.py` 为另一任务未提交改动，未纳入本轮。
- 用户授权：剧本准备下载文件自动覆盖；全项目排查「切换调用方式即失效」；按统一样式表调整视觉；修启动白屏；CI 平台由代理决定（本地）；全自动遇 Claude Desktop 只提示不拦截；代理自动跑本地 CI。

## 内容

1. 剧本准备「刷新」从下载文件夹收回同项目、同 Provider 的设定／大纲／角色卡／剧本（`idea_chat.import_downloaded_documents`，L3 `import_downloaded_creatives`，L1 `platform_tools.downloads_directory`）；任务书补交付文件名要求。
2. 通用下载收件箱（新 L2 `download_inbox`，L3 `register_download_inbox`／`collect_download_inbox`）：Claude Desktop 派发时登记任务书目标路径，桌面每 5 秒按同名、派发后下载、比现有文件新收回；全阶段适用。
3. 白模自动制作遇 Claude Desktop 提前报错；三虎全自动派发 Claude Desktop 后状态栏＋非阻塞提示手动发送。
4. 启动白屏：剧本准备整页在启动画面后建完才揭开（`启动漫剧制作助手.pyw`、`desktop.py`）。
5. 统一调色板：`ui_tokens.COLORS` 新增 27 个派生色；`ui_theme` 与 6 个业务页内联 hex 清零，颜色门禁基线下调；两处测试断言改按 token。
6. Git hooks 安装统一写 LF，`.gitattributes` 锁定；`test_git_hooks` 在非 Windows 用 PATH 上的 sh。
7. 本地 CI：`本地CI.cmd`／`ci_unattended.cmd`／`ci_targets.cmd` ＋ `scripts/local_ci.py`；自检与 CI 设 `DRAMA_SUPPRESS_MODAL=1`，通知分发器不弹阻塞系统框（被用例替换的 messagebox 仍可断言）。

## 测试

- Linux：新增 `test_download_inbox` 5 项、`test_idea_download_import` 7 项、`test_git_hooks` 7 项通过；架构相关门禁（分层、循环依赖、统一化台账、JSON、token、服务返回范围）通过。
- Windows 随附解释器（代理经本地 CI 自动运行）：默认冒烟 8/8；定向 `test_service_return_contract`、`test_edit_export`、`test_environment_check`、`test_integration`、`test_stdlib_closure` 通过。
- 未完成：安全全量需干净工作树，提交后补跑；`test_round_baselines` 的 R1430 全量欠账待该次全量清偿。
