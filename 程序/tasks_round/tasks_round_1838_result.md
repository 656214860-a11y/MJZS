# R1838 结果（修复轮）：提交后的后台全量改在隐藏桌面跑，不再弹窗

## 现象
post-commit 钩子派生 scripts/auto_full_safe.py 跑 run_selftests.py --all --safe；NO_WINDOW 只藏控制台，测试建的 Tk 窗口照常弹到用户屏幕、抢焦点。两棵树每次提交都会触发。

## 改动
- scripts/auto_full_safe.py：仓库根有 工作流任务/gui_hidden.py 时，全量经它在隐藏桌面运行，输出写 logs/auto_full_safe.run.log 后并入 auto_full_safe.log（红模块解析照旧读该日志）；没有则退回原直接运行。退出码不变。

## 验证
- 隐藏桌面运行 run_selftests.py -k auto_full：ALL TESTS PASSED。断言未动。
- 未跑全量（下次提交后的后台全量即为实地验证）。
