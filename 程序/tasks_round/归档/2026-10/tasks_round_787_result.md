# R787｜UI 统一入口第三批第 14 项：文案与复制（已验收）

## 改动

- 复用既有 `prompt_window.copy_text()` 作为唯一文本复制入口：接入 `clipboard_lock`，剪贴板暂时占用与 Tk 写入失败均返回可展示原因。
- `clipboard_lock` 支持同线程可重入，避免调用方已持锁时再次复制等待超时；跨进程互斥不变。
- 剧本聊天的选中文字、软件示例和整条消息复制全部改为委托入口；失败不再静默。
- `copy_preview()` 仅用于状态栏，掩盖疑似 API key／secret／token／password；复制到系统剪贴板的原文不改变。
- 新增复制入口边界门禁与单元回归；更新组件使用契约与 AGENTS 清单。

## 验证

- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop prompt_window clipboard_lock`：9/9；21 条／0 红。
- 复制入口、锁与 AGENTS／基线边界定向：19 条／0 红；`run_selftests.py --serial -k idea_chat --safe` 亦通过。
- `python smoke_test.py --architecture`：153/153，不低于 R786 的 152/152。

## 分档与提交

本轮未触及 Tk 生命周期／事件绑定、启动路径、删除语义或层级登记表；R787−R785=2，按 AGENTS.md §5 不触发完整安全全量。未执行 git add、commit 或 push。

建议 commit message：`feat(ui): centralize copy feedback and clipboard safety`
