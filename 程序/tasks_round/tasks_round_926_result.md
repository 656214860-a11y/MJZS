# R926 UI 统一入口：快捷键命令审计

- 递归扫描业务 Python：直接 `bind` 的 Ctrl／Command 快捷键均禁止，必须经 `ShortcutRegistry`。
- 保留并检查现有的三个命令快捷键登记点：视频提示词全选、聊天记录复制／编辑、分镜文件表全选。
- Alt/F4 下拉展开、Return/Escape 输入与弹窗关闭等控件原生局部交互不属于跨页面命令快捷键，继续由控件处理。

验证：

- `python -m unittest tests.architecture.test_shortcut_registry_boundary`：3 条通过。
- `python smoke_test.py`：8 项通过、0 失败。
