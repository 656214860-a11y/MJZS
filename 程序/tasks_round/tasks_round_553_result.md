# R553｜结构治理轮（子场景：执行）｜P1-3 剧本准备对话控制器

## 完成结论

- 已完成 R547 J 节 P1-3：剧本准备页对话的请求状态、发送节流、流式角色进度回调和附件注入已迁入无 Tk 的 `IdeaChatController`。
- `desktop.py` 仍创建并绑定所有 Tk 控件；它只注入项目根、输入文本、取消令牌、队列投递与 UI 回调。`idea_chat.py`、`idea_attachments.py` 的公开接口和内容/附件契约均未改动。
- 本轮生产改动为 2 个模块（`desktop.py`、`idea_chat_controller.py`），低于每轮最多 3 个模块限制；未增加用户功能。

## 改动文件

| 文件 | 改动 |
| --- | --- |
| `idea_chat_controller.py` | 新增 L3 无 Tk 控制器，拥有附件路径、输入提交拼装、0.3 秒节流、请求令牌/取消和已取消请求的进度丢弃。 |
| `desktop.py` | 保留控件绑定和 UI 更新；通过兼容属性注入控制器，将提交、API 回调、刷新重试、取消与关闭清理迁入统一状态。 |
| `tests/test_idea_chat_controller.py` | 新增无 Tk 回归，覆盖附件注入的可见标记、节流和取消后旧进度丢弃。 |
| `tests/architecture/_layers.py`、`architecture.md`、`PROJECT_MAP.md` | 将控制器登记为 L3，说明其不持有 Tk 控件及依赖边界。 |
| `project_status.md` | 登记 P1-3 完成并更新债务台账。 |

## 保持的边界

```
Desktop（Tk 控件绑定／队列／状态文案）
  └─ IdeaChatController（请求状态／节流／附件注入／进度回调）
       └─ idea_attachments、idea_chat（既有 L2 契约）
```

- 控制器不导入 Tk，也不持有任何控件；流式回调只通过桌面注入的队列投递函数返回主线程。
- 取消会置位既有取消事件、清除活动令牌；随后到达的旧角色进度不会再更新界面。
- 非直连模型的剧本 Agent 启动失败会撤销本次节流占位，保留原有“输入不丢失、可立即重试”语义。

## 验证

| 检查 | 结果 |
| --- | --- |
| `python tests/test_idea_chat_controller.py` | 3/3 通过 |
| `python smoke_test.py --affected idea_chat_controller` | 1 个测试文件、3 条通过 |
| `python smoke_test.py --affected desktop idea_chat` | 6 个匹配测试文件通过 |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --architecture` | 95/95 通过，无新增架构红点 |

## 债务台账与自检

- P1-3 已关闭；R182 可执行拆分债务由 **13 项减至 12 项**。
- P0-3 仍为 R550 已登记阻塞项，未扩大本轮范围。
- 自检：生产模块 2/3；新增服务已登记 L3；无 L3→L4 依赖；未修改 `idea_chat.py`、`idea_attachments.py` 的契约或页面最终布局。
