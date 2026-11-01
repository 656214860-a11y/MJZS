# R1836 结果：local_previs.show 改写成类（整理轮，附带一处可见差异）

- 改动：`show` 用 c2c 改写成 `_LocalPrevisWindow`（17 个共享名、20 个方法），函数从 252 行降到薄壳；`OVERSIZE_CAPS` 删除该条。
- 可见差异（如实说明）：HEAD 上，环境说明那一行的 `StringVar` 只被 `refresh_environment` 这个闭包引用，而这个闭包只在建页时调用一次，`show` 返回后就被回收，所以“成果目录／Blender”这一行在页面上一直是空的。改写后变量挂在实例上，这一行会正常显示，符合原注释“给一行只读检查结果”的本意。新增 `test_environment_line_survives` 专门断言这一点，它在 HEAD 原文上是红的。
- 差分测试先行：`tests/test_local_previs_page_equivalence.py`，旧实现取 HEAD 原文内嵌，替换到同一个真 Desktop 的白模预演页上做通用探测（安全按钮、镜头列表选中／全选／取消），离开再回来再探测一遍；等布局稳定 1 秒后再拍快照。为了把上面那处差异隔离开，`environment_summary` 统一置空，并抹掉 PY_VAR 序号和空 var 项。“强制停止制作”会弹模态确认框，所以跳过。旧实现自比为绿。
- 变异检验：按钮文字“制作记录”改一字，差分测试变红，已还原。
- 验证（本轮运行，隐藏桌面）：差分测试 2 项、test_previs*（123 项）通过；`run_selftests.py --architecture` 通过。
- 断言未动。
