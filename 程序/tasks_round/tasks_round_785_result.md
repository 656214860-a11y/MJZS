# R785｜UI 统一入口第三批第 12 项：图标首迁（已验收）

## 范围

新增 L4 `ui_icons.IconLoader`，作为页面图标的共享构建、尺寸规格与按 Tk 宿主缓存入口。仅迁移 `video_navigation.show_back()` 的“返回生成方式”箭头；未迁移主题内部复选框图元、其他历史页面图标或任何用户项目数据。

## 验收

- 图标缓存与缩放单元测试、首迁边界和层级定向：7 条／0 红。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected video_navigation ui_icons`：9/9；定向 6 条／0 红。
- `python smoke_test.py --architecture`：151/151，不低于 R784 的 150/150。
- `python run_selftests.py --all --safe`：627 工作单元／0 红／871.373 秒。成功后增量台账于 2026-10-02 11:04:15 写入；该命令仅在无红时才写入该台账。

## 基线与收尾

层级表改动触发完整安全全量；`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 已从 784 推进至 785，架构基线为 151/151。未执行 git add、commit 或 push。

建议 commit message：`feat(ui): add shared icon loader for video navigation`
