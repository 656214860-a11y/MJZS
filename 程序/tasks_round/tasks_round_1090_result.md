# R1090：模型请求重定向认证边界（进行中）

- 类型：AGENTS.md §3.2 修复轮。来源：R1089 报告 J.1 / F1。
- 测试：新增失败回归已先红后绿，默认冒烟 8/8、受影响 9/9、定向 122/122；架构仍在执行，完整安全回归待执行，不能宣称三基线通过。
- 欠账：F1 已实现，未完成全部验收；F3、F4、F2 及后续全仓分批简化未完成。

## 根因与修复

普通请求和 SSE 请求使用 urllib 默认重定向处理器，301/302/303 可把认证头传到重定向目标。新增共用的禁止重定向 opener，两种传输都在发送后续请求前拒绝跳转；保留正常响应、错误结果形状和 TLS EOF 重试行为。无需读取真实密钥或联网。

范围：model_pool.py、tests/test_model_pool_redirects.py、tests/test_pet_llm.py。后者只迁移两处网络打桩位置，既有断言不变。拒绝策略包含同源跳转，配置的 API URL 应直接指向最终地址。

## 实跑证据

解释器：随附 Python，工作目录为隔离树程序目录，均使用 -B。

- `-m unittest discover -s tests -p test_model_pool_redirects.py`：修复前 2 项测试、18 个子场景失败，实际出现多次请求；修复后 2/2 通过，覆盖两种传输 × 5 种状态 × 3 种目标，另验证正常响应。
- `-m unittest discover -s tests -p test_pet_llm.py`：54/54 通过，原有 TLS 重试断言保留。
- `smoke_test.py`：8/8，通过。
- `run_selftests.py -k model_pool model_router pet_llm`：122/122，2.5 秒，正常退出 0。
- `smoke_test.py --affected model_pool`：9/9，正常退出 0。
- 首次未提权运行在保存公共 Git 目录缓存时陷入 tempfile 重试；限时堆栈明确定位到 save_cache/mkstemp。受阻进程已终止，使用必要权限重跑通过，未改测试执行器。

## 待执行与保护边界

等待架构最终结果，再做完整安全回归；本轮与最近全量 R1087 相差 3，不能跳过全量。之后更新报告、主树状态和接力文件，按最小清单提交。中央队列无本轮对应 ID，未认领其他事项。

主树用户预设 SHA256 仍为 E596C86C8D362FD6C6797FE9F9E19B4A7507D4F6ACE19BB91CE955EFF47E4651；未读取真实项目、未改用户配置、未运行真实应用、未调用 API。

提交：尚未提交。状态：进行中，不是 TASK_COMPLETE。
