# R1100 附档补齐内联简报门禁

- 类型：修复轮，仅增量修复 R1099 的附件采集，不重做界面。
- 实跑：定向 241/241、独立架构 308/308（历史基线 308，无增减）、受影响 smoke 9/9、默认 smoke 8/8。完整安全全量尚待执行，当前为检查点，不是完成。
- 欠账：本轮到达 R1097 后第三轮，须取得 master 实跑全量凭据；未提前宣称清账。

## 改动与证据

`inline_required_missing` 接受可选附件字段；有效手填或非空附件任一满足，保留必填顺序。桌面复用同一 prepared attachments 的服务默认值，普通别名与制作锁定义同源归一化；篇幅仅拆出明确集数/单集时长，不猜缺省时长。

接收简报时仅在提取输入中过滤未改示例占位值，合入附件 brief_texts；手填优先，空锁回落附件。附件正文不写入本地 Agent submission、原始简报、聊天展示或提示词；模板原文另存及 API 边界不变。

新增 6 项测试：附件 OR 门禁、篇幅拆分、占位值与手填优先、锁别名及空锁回落、真实临时附件+未改示例直接启动、缺时长继续拦截。既有断言零删除零弱化，未删除功能或其测试。失败先行日志出现 4 个新增回归失败，修复后定向全部通过。

生产模块只改 idea_chat.py、desktop.py；测试只改 tests/test_idea_inline_brief.py。TODO 快照仅跟随已有注释行号；测试分层基线由执行器更新。报告/状态/接力是规则要求的收尾元数据。

## 实跑命令

均在隔离工作树使用项目随附 Python，带 -B；原始输出在系统 TEMP，不纳入仓库。

| 命令 | 本轮结果 | 日志 |
| --- | --- | --- |
| run_selftests.py -k idea brief workflow | 241/241，77.3 秒 | R1100-target-final.log |
| run_selftests.py --layer architecture --all | 308/308 | R1100-architecture-final.log |
| smoke_test.py --affected idea_chat workflow | 9/9 | R1100-smoke-affected.log |
| smoke_test.py | 8/8 | R1100-smoke-default.log |
| run_selftests.py --all --safe | 待执行 | R1100-full-safe.log |

## 未运行与边界

未重启真实应用、未人工视觉验收、未发起真实模型请求；工作流启动由桌面桩验证。未读取真实创作项目；测试使用临时项目。用户未提交预设与未跟踪清理资料保持原样，不纳入提交。

## 收尾

中央领取 R1100，无对应队列 ID；状态下一轮 1101。检查点待提交、全量未完成，暂不标 TASK_COMPLETE。不推送远端。
