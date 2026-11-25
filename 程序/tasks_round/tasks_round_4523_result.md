# R4523 制作工作台、阶段文件与分镜预演
<!-- round-evidence: {"commit_base": "f2220e56e", "credential_hits": 0, "evidence_sha256": "35a72a6d6f7a97e9", "exit": 0, "failed": 0, "passed": 232, "round": 4523, "tests": "run_selftests.py -k test_animatic_page test_stage_reply_area test_board_assets_buttons test_media_page_buttons test_asset_detail test_ui_edges_tables test_ui_edges_pages"} -->

## 三问

本轮修复制作界面的主题、交互、布局和首帧绘制。阶段图标控制文件筛选，13 个阶段均可回看，资产清单仅由资产管理图标切换。布局实测覆盖常规窗口、缩窗、左右两侧发起滚动，13 对图标中心均重合。

控制端在真实 Windows Tk 窗口逐页检查日间→夜间→日间，比较可见控件及文本标签颜色；用 H.264/AAC 样片检查分镜预演页内播放、暂停与离页释放。针对性自动用例覆盖设置按需加载、聊天浮层、右侧文件、配色、阶段操作菜单和分镜时间线。最终机器凭据见本文件头部。

后续维护时应保留底部输入框的发送动作、阶段文件及其右键菜单、锁定前置条件。验证使用隔离项目和本地样片，没有发起计费生成任务。系统文件选择器仍由 Windows 绘制。
