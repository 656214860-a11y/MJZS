# R615｜修复轮：移除剧本准备 `/` SKILL 补全

- **本轮是功能轮还是整理轮？** 功能轮中的修复轮。
- **测试跑了吗？三个基线过了吗？** 默认 `smoke_test.py` 为 8/8；`python -B -c "import desktop"` 通过。未重跑架构门禁和全量回归。
- **`project_status.md` 的欠账少了吗？** 是；移除了会触发卡死风险、且用户明确不再需要的 `/` 补全功能及其专属测试。

## 修改

- `desktop.py`：删除 `idea_skill_commands`、异步候选读取、菜单渲染、插入命令等全部 `/` SKILL 补全实现；移除输入框的 `<KeyRelease>` 补全绑定。普通文本输入和既有 `@` 创意附件引用菜单不变。
- `tests/test_idea_chat.py`：删除两条仅覆盖已移除补全功能的测试。

## 验证

```text
IMPORT OK
SLASH_COMPLETION_REFERENCES=0
smoke_test.py: 8/8 passed
```

## 自审

未改 SKILL 注册表、阶段配置、UI 布局、用户数据或发送链路；未保留 `/` 菜单的后台线程、缓存或事件绑定。
