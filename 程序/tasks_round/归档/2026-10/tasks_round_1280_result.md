# R1280：Claude 剧本重新创作会话与读取范围优化

- 类型：§3.2 修复轮，中央唯一入口领取 R1280。
- 验证：定向 133/133，默认冒烟 8/8；架构 311 条首次 1 失败，唯一失败是本轮 desktop.py 注释后移一行，同步快照 2661→2662 后原失败文件 2/2。没有修改断言或增加豁免。未重新跑全量；主目录正式历史凭据为 R1279，不代表本次树全量通过。
- 欠账：本轮 Claude 重新创作复用历史会话的问题已处理；未处理其他优化队列。主目录并行 R1281 已登记，轮次头保留最新结果加一，不回退到 1281。

## 原因与改动

原逻辑对同阶段、同配置始终提交给已有 CLI；窗口关闭后仍 --resume 旧会话。“重新输出项目设定”因此继续承载旧对话。项目接续提示还要求读取全部既有分集，导致历史工具输出反复进入上下文。

现在明确的“重新创作／重新生成／重新输出（阶段名）”首行整句命令新建 Claude CLI 会话；普通确认、继续及修改请求保留会话。已有自有窗口只在可提交的空闲状态发送 /exit，确认退出后释放槽位；忙碌、草稿或退出超时则报告失败，不强杀、不启动重复请求。新会话使用完整任务书，正常续接保留 --resume。范围限定 writing 的 Claude Code CLI，API 和其他引擎调度不变。

Agent 任务书限制读取当前阶段相关采用成果与本次附件，禁止默认遍历各模型对话、旧任务书和 responses；分集先看索引，正文按需读取。读取限制属于模型指令，不是文件系统访问隔离，不能承诺模型绝不额外读取。

## 验证记录

解释器：D:\漫剧制作助手\运行环境\Python\python.exe。隔离工作树 preparation-response-save。

1. 新增回归先红：5 个测试，1 failure、13 errors（含子测试），证明旧代码缺少会话重启与读取范围行为；实现后 5/5，扩展后 9/9。
2. `-B run_selftests.py -k claude_writing_session workflow script_agent_delivery_assembly idea_semantic_brief`：133 条，9 文件／16 单元，6.3 秒，ALL TESTS PASSED，无跳过报告。
3. `-B smoke_test.py`：8/8。
4. `-B smoke_test.py --architecture`：311 条，112.347 秒，1 failure（test_keyword_comments_match_the_reviewed_snapshot）；仅校正本轮引起的 desktop.py 行号。
5. `-B -m unittest tests.architecture.test_todo_comment_snapshot`：2/2，1.766 秒。
6. `git diff --check` 无空白错误。测试使用模拟进程，未调用付费 API、未启动真实 Claude、未重启用户应用。

自审：新会话退出与槽位申请顺序有测试；普通会话续接、其他阶段绑定、忙碌与超时保护均覆盖。无新增阶段状态结构、依赖倒置、用户文件删除、Tk 生命周期改动。未实测真实耗时或 token 降幅；当前运行中的旧 CLI 不会自动加载修改。

截图中的 /clear 是排队输入，尚未执行；需先 Esc 中止当前生成，返回输入状态后执行清理。重启助手加载本轮代码后再发送明确重新创作命令。提交定位以 Git 的 R1280 提交为准。
