# R1066：修复轮——资产详情图片键盘入口与焦点

1. 来源 R1052 J1；按用户授权逐项执行，本项完成前未启动下一项。
2. 定向 40/40、受影响检查 9/9、冒烟 8/8；检查点 e7f65b3 安全全量 3991 条、0 个文件失败，336.8 秒。
3. 收口图片键盘入口、预览关闭和重建焦点缺口；不宣称 Busy 或整个 OPT-07 完成。

## A. 范围

生产仅 asset_detail.py；既有 test_asset_detail.py 新增 3 项测试；维护快照仅同步一条注释行号。无用户配置、数据或密钥改动。

## B. 认领

起点 master 4ff7702，工作树干净。分配 1066，认领 R1066-ASSET-KEYBOARD，owner=codex-sequential。超过 50 行前切 codex/wip-R1066；状态仅在 master 提交，不抢占其他租约。

## C. 失败先行

旧实现运行新增 3 项测试，6 failures：三处图片按钮缺失、两种关闭场景初始焦点错误、重建焦点丢失。首次手工命令受测试 cwd 变化影响，改为绝对导入路径后取得真实红灯，不将调用错误算产品缺陷。

## D. 根因与修复

图片 Label 只有鼠标绑定；换用现有 SecondaryButton，Tab 可达，Space 沿用原生行为，Enter 显式调用。变体标题创建时捕获，避免指向末条变体。

无 chrome 预览不会自动聚焦；关闭按钮原来直接 destroy。现在窗口自身收到 FocusIn 时聚焦关闭按钮，按钮/Escape 统一经 BaseDialog.close，关闭后恢复存活原控件焦点。after_idle 初版仍被 Windows 激活时序覆盖，测试保持红灯后改为 FocusIn；生产不使用 focus_force。

页面重建后焦点交给返回资产管理按钮；不添加后台任务或另一套生命周期。

## E. 回归覆盖

新增 test_image_actions_are_keyboard_buttons、test_zoom_focus_and_both_close_routes、test_reload_restores_focus_to_detail_navigation。真实 Tk 和临时项目覆盖 Tab 顺序、Enter/Space、变体标题、Escape/按钮关闭及锁定重建焦点。原断言、用例、skip 不变。

## F. 验证

程序目录、随附 Python、-B：run_selftests.py --safe -k asset_detail 为 40/40（32.3 秒）；smoke_test.py --affected asset_detail 为 9/9；默认 smoke_test.py 为 8/8；test_todo_comment_snapshot 为 2/2；run_selftests.py --all --safe 为 3991 条、0 个文件失败（336.8 秒）。全量含既有架构用例；本轮非跨层/结构治理，不重复独立架构命令。

## G. 全量失败与凭据

首次全量因维护快照仍登记注释 asset_detail.py:345、实际已到 :358 失败。只更新 TODO注释快照_20261003.json 的行号，不改断言或分类；新检查点重跑通过。

真实凭据 tree=8a93b15524b47c306b12ecb1cf5d2228327dcb12、seconds=336.78、at=2026-10-05T05:34:12、round=1065（执行时最新落盘报告号）。实际为 R1066 的 e7f65b3 检查点验证；不手改凭据，不将报告回填后的树冒称已全量验证。

## H. 边界

不读真实 episode/、writing/、private/ 或配置，不操作日志和密钥，不删除文件；测试夹具由既有机制管理。阶段、路径、Busy 策略不变。

## I. 自审与限制

UI 技能用于键盘可达和焦点恢复，复用桌面组件，不套移动端尺寸规范。未做真实项目视觉验收。一个生产模块，无跨层依赖。流程先快进 master 后完成全量，不冒称合并前已验收；后续触发同类门禁时先在分支固定检查点验证再合并。

## J. 整改路线

R1052 J1 完成；下一项 R1052 J2，先复核状态覆盖和重新生成部分失败。J3 仍以实测阻塞为前提。其他条件任务不自动解禁。

## K. 测试迁移计划

零迁移、零删除，保留新增 3 项回归。后台成功/失败/取消/迟到结果测试仅在实际引入后台任务时追加，不虚构已覆盖。

## L. 收尾

代码 a4e8023，快照校正 e7f65b3。关闭中央认领，状态头 1067=1066+1，人工队列登记。收尾执行文档/轮次校验、凭据形态扫描、diff 检查并显式暂存提交，不 push；最终哈希以 R1066 收尾 Git 回执为准。

## M. 回滚

需要撤销时依次 git revert e7f65b3、a4e8023，保留审计历史，不重置用户更改。

收尾实测：文档与 round-claim 合计 23/23；初次误用 tests.architecture.test_round_claim 路径导致导入错误，改为实际 tests.test_round_claim 后通过。状态/报告静态检查 1067=1066+1，中央认领已 completed；未修改历史报告。
