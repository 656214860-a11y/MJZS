# R566｜结构治理轮（子场景：执行）

## 来源与范围

- 来源：`tasks_round/tasks_round_547_result.md` J 节 P2-5——建立跨阶段模型请求的并发槽与排队／取消策略，并让 UI 显示等待而不在主线程阻塞。
- 应用代码只改动 `workflow_process_registry.py`、`workflow_engines.py`、`desktop.py` 三个模块；未改并发配置、分层、模型调用契约、阶段状态机或用户项目数据，未增加产品功能。

## 完成结果

- `workflow_process_registry` 在保留既有“立即预留／满额报错”接口的同时，增加非阻塞申请、领取和取消：满额请求只生成内存票据，不占用线程；释放运行槽位后，最早可运行的票据可被领取。项目停止会一次撤销该项目尚未启动的票据。
- `workflow_engines` 继续唯一地把阶段名映射到既有 `stage_parallel` 的全局／阶段上限；新增的申请／领取薄入口不复制配置。`terminate()` 在终止已登记进程前撤销本项目等待项。`launch_interactive()` 接受内部已领取槽位，旧调用不传该参数时仍按原路径预留。
- `Desktop.open_flow_agent()` 在主线程申请槽位：立即可用则异步启动；满额则用 200ms Tk `after` 轮询领取，状态栏显示“模型请求排队中（第 N 位）”。领取成功后仍经既有后台线程启动；关闭窗口时不再继续轮询，随后既有停止路径取消票据。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `workflow_process_registry.py` | 增加线程安全的排队票据、领取与按项目取消。 |
| `workflow_engines.py` | 增加阶段级排队薄入口、停止时取消，并支持内部注入已领取槽位。 |
| `desktop.py` | 在既有交互式 Agent 启动前加入非阻塞队列轮询和状态提示。 |
| `tests/test_workflow_process_registry.py` | 覆盖释放后领取及项目停止取消，原有容量拒绝回归仍保留。 |
| `project_status.md` | 更新本轮、债务计数与完成摘要。 |

## 验证

- `python run_selftests.py --serial -k workflow_process_registry`：5/5 通过。
- `python smoke_test.py --affected workflow desktop`：9 项通过、0 项失败；受影响门禁包含 `test_workflow_process_registry`，其 5 条通过。
- `python smoke_test.py`：默认冒烟 8/8 通过。
- `python smoke_test.py --architecture`：98/98 通过，无新增红点。

## 债务状态与自审

- P2-5 完成；R182 拆分债务由 4 项减至 3 项。剩余为 P0-3（既有二进制成果发布／分层阻塞）、P3-1、P3-2。
- 队列仅保存项目标识、阶段、容量与内部票据，不保存提示词、模型回复、文件内容或密钥；所有 Tk 状态更新和 `after` 调度都在 UI 线程，进程创建仍由既有 `async_` 工作线程执行。
