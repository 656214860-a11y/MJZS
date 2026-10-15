本轮类型：功能轮（界面验收修复）。
> 说明：本轮在车道分支 `codex/wip-R1456` 开发，合并时正式记为 R1479。验收复测：在真实环境（GUI 令牌空闲）跑 `test_desktop_compact_layout test_pet_ui test_pet_settings test_app_icon test_core` 全部通过（首轮 7 条红：5 条几何对齐差 4px、2 条三虎父层级合同，已修；两条既有合同断言未动）。未做肉眼视觉验收。
测试跑了吗：仅执行用户指定的四个模块；最终结果见下。
欠账变化：未跑全量，不抵扣既有全量欠账。

原因：
- 缓存阶段页替换 content，等宽标题切换不触发 Configure，沿用前页 4px 内边距。
- 上轮把 pet_layer 改挂 body，并使用 in_=title_row，破坏既有父层合同。

本次改动：
- 在当前页几何收敛时重算标题左缘；script 对齐气泡框，其他页对齐内容边框。
- 仅在 padding／位置变化时更新布局，避免重复空闲回调。
- 恢复 pet_layer=title_row 及宠物原始 place 层级；pet_ui.py 已恢复为原实现。
- 页头至少容纳 PATCH_ROOM，项目列表同步补足间距，避免原父层裁掉猫爪。
- 补高测量去重，避免几何尚未更新时累加间距。
- 旧布局比较夹具恢复旧口号高度；标题 ≤2px 容差和两条既有宠物断言未修改。
- 新增宠物不越出原父层的边界断言；保留此前已授权口号与图标文案改动。

测试与证据：
- 解释器：D:\漫剧制作助手\运行环境\Python\python.exe；工作目录为 R1479\程序。
- 正式运行器申请 GUI 令牌超时未进入测试，未改锁或运行器。
- 使用独立子进程 unittest，并调用现有 run_selftests.protect_tk() 隔离 Tk 配置。
- 补高前四组曾通过：compact 5、pet_ui 591、pet_settings 54、app_icon 28，共 678 项。
- 最终 compact 5/5 通过（43.933 秒，含父层边界）；pet_settings 54/54、app_icon 28/28 通过。
- 补高后 pet_ui 曾在 update_idletasks 超时；测量去重后整组仍在 140 秒限额退出（当时执行到控件创建），无最终通过结论。
- 最终树两条指定宠物合同用例单独复测：2/2 通过，0.670 秒。
- git diff --check 通过；未跑 core／全量／gate；未提交，未修改主树或 project_status.md。

未解决项：
- pet_ui 整组最终验收尚未完成；运行器 GUI 令牌获取问题未在本次范围内处理。
