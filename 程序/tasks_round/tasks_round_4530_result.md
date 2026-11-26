# R4530 启动器与项目列表交付
<!-- round-evidence: {"commit_base": "ee8b5e2e6", "credential_hits": 0, "evidence_sha256": "e69cc44fb57ed97f", "exit": 0, "failed": 0, "passed": 88, "round": 4530, "tests": "run_selftests.py -k test_desktop_startup_perf test_launcher_imports test_startup_selfcheck"} -->

## 三问

根目录正式启动器移除动画创建、进度回调与跟踪，主界面就绪后直接显示。项目卡片按实际项目行数收缩，长列表保留滚动。

验证启动器入口与真实窗口选择路径，复核日夜样式继承与列表布局。正式凭据记录在本文件头部。

关闭独立动画窗口带来的遮盖与额外加载路径。首帧诊断继续由应用的启动自检和桌面绘制指标记录。
