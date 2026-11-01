# R769 结果｜UI 统一入口第一批第 1 项：弹窗

**轮次类型：** 功能轮  
**状态：** 已验收  
**提交：** 未提交；未执行 `git add`、`git commit` 或 `git push`，commit hash：无。

## 交付

- `ui_widgets` 新增 `BaseDialog`、`FormDialog`、`ConfirmDialog`：统一标题／内容／操作区、模态 grab、transient、Esc 关闭、首个可交互控件焦点、销毁时释放 grab，以及危险确认按钮样式。
- 仅将 `desktop.py` 的“填写创作信息”迁入 `FormDialog`；字段采集、统筹锁与保存发送语义保持不变。
- 弹窗视觉值进入 `ui_tokens.py` 与 `design_tokens.md`；`ui_components.md` 写明组件选用规则，禁止业务页新增裸 `tk.Toplevel` 对话框。
- 新增架构边界门禁与组件回归：历史裸 `Toplevel` 数量仅允许下降，且“填写创作信息”必须使用 `FormDialog`。其余历史 `Toplevel`／`messagebox` 留待后续独立迁移轮。

## 验证

| 检查 | 结果 |
|---|---|
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --affected desktop ui_widgets` | 9/9 通过 |
| `python run_selftests.py -k ui_widgets desktop_idea_chat agents_md --safe` | 12 条／0 红 |
| `python smoke_test.py --architecture` | 139/139 通过（基线 138→139） |
| `python run_selftests.py --all --safe` | 3,504 条，829.3 秒，0 个文件有红 |

本轮改动 Tk 模态与 Esc 事件绑定，按 §5 已执行完整安全全量；`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 已推进为 769。

## 后续

第一批下一项为表格统一。路线图 `维护记录/UI统一入口路线图_v1.md` 不记录逐项进度，状态仅记入 `project_status.md`。
