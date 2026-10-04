# R1034 修复轮：三虎聊天框被动画重排关闭

1. 本轮为修复轮，来源 R1033 J1/J2；用户要求直接修复，不录屏。
2. 默认冒烟 8/8；新增/相关动画点击测试 15/15；受影响 pet_ui、pet_cloud 门禁通过。架构与完整安全回归尚待收尾实测。
3. 已修根因，验收未完成前不宣称清偿；不扩展其他 UI 待办。

## 根因与最小修复
R1033 实机栈证明 step → _schedule → stop → Cloud.close，显示后约 15ms 即关闭。
pet_ui._schedule 改为仅调用 _cancel_animation_timer；stop 复用同一取消函数，但保留关闭云朵、取消单击和主窗置顶回调的退出清理。
仅修改 pet_ui.py 生产模块；不改阅读时长、焦点守卫、启动路径、配置与用户数据。

## 回归证据
先新增 tests/test_pet_ui.py 三项真实 Pet/Tk 接缝测试：连续动画帧保持聊天、连续帧保留单击 after、stop 仍关闭并清理且可重复。
改前 AnimationTests 9 项中 2 项失败，分别为 visible=False 与 pending click=None；改后 AnimationTests + PetClickTests 15/15。
初次 unittest 包形式调用因 tests/skip_reasons 不在搜索路径而失败；改用测试文件既有直接执行入口后完成上述红绿验证。
smoke_test.py --affected pet_ui pet_cloud：零红，约 102 秒；默认 smoke_test.py 8/8。
保留所有既有断言和测试，不迁移、不 skip。

## 自审与范围
同类路径复核：动画重排也不再误取消主窗置顶恢复任务；正常 stop 仍清除它。
无新增依赖、权威源或数据写入；无录屏、无临时诊断代码。
当前正在运行的旧桌面进程未热替换；新代码需重新启动应用生效。

## 提交与待验收
[TASK_FAILED] 仅作为干净受测检查点，完整安全验收尚未完成，不表示已出现完整回归失败。
待本轮真实全量与架构结果追加后收尾。提交哈希以 Git 回执为准。
