# R846 结果｜UI 修复与关闭路径兼容

## 范围

- 修复阶段配置面板中注册 SKILL 入口均名为 `SKILL.md` 时，勾选标签退化为通用名称的问题；现使用注册表的用户可见名称。
- 修复 Windows ttk 主题下表单弹窗动作区锁定高度可能裁切按钮文字的问题；动作区保留 token 间距并允许按按钮请求高度扩展。
- 关闭路径兼容尚未完整初始化的最小桌面替身，缺失的后台生命周期登记器不再导致关闭崩溃。
- 同步登记 UI 入口路线图和缺陷／架构路线文档中的既有事实；R845 架构基线校正随本次收尾提交。

## 验证

- `run_selftests.py -k skills ui_widgets_dialogs desktop_close --safe`：147 条，0 个失败文件。
- `smoke_test.py`：8/8 通过。
- `git diff --check`：通过。

## 提交

- 本报告创建后，R845／R846 已验证的改动将以独立提交落库；不包含工作树中未核验的 `workspace_maintenance.py` 与其层级登记改动。

`[TASK_COMPLETE]`：UI 可见性、注册 SKILL 标签与最小关闭路径兼容已修复；未弱化既有断言。
