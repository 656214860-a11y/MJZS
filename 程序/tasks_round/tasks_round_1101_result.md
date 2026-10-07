# R1101 简报编辑区与追问输入分离

- 类型：功能轮；生产逻辑仅改 desktop.py，既有门禁与附件提取保持不变。
- 实跑：最终定向/UI 360/360、独立架构 308/308、受影响冒烟 9/9、默认冒烟 8/8；全量未运行。架构基线 308，无增减。
- 欠账：本轮有 Tk 控件与事件绑定变化，需在干净 master 完成安全全量，不借用 R1100 凭据。

## 实现与边界

聊天记录上方新增独立 TextArea 和“创作简报：直接修改示例内容”可见标签。模板初始为次级灰，可就地修改；必填标记和字段染色迁到上方。下方追问初始为空，保留输入提示、附件入口和发送快捷键；空聊天不再展示软件示例气泡。

发送沿用原流程，只将输入换成“上方简报 + 两个换行 + 非空追问”。门禁仍从同一 prepared attachments 获取字段；不另建附件提取路径，不改变手填/附件优先规则。成功后上方复位灰色模板、下方清空；启动失败保留两框。两个未发送草稿按项目保留在内存，翻页不丢失，明确清空的上方框不被模板覆盖。

idea_chat.py、script_contract.py、skill_panel.py、默认创意示例.md 未修改。其他文件仅为三个指定测试文件、既有 TODO 注释行号快照、执行器基线与轮次/交接文档。

## 测试迁移

- test_the_example_is_never_sent：示例移到上方编辑框、下方为空；拦截、未落盘断言保留，增加不启动断言。
- 原软件示例气泡整条复制用例迁为上方编辑框原生选择复制；只移除已删除气泡的命中要求，仍断言完整复制和无示例气泡。
- test_idea_inline_brief.py 预填/必填标记/上方填写断言迁至新控件；附件补齐、逐项缺失拦截保留。新增上下合并文本精确提交、启动失败保留、翻页保留（含清空）测试。
- test_ui_edges.py 的模板位置、灰色、编辑、历史示例不回填、追问初始值按新契约迁移；其余行为断言不动。
- SendMessageTests.say 测试助手显式清空上方后填下方，以保持既有单输入行为断言原样；另加“上方示例 + 下方补齐”真实发送用例。无测试删除，不弱化保留功能断言。

## 实跑与未运行

内置 Python 带 -B，在隔离工作树运行，原始日志只留系统 TEMP。

| 命令 | 当前结果 | 日志 |
| --- | --- | --- |
| run_selftests.py -k idea_inline_brief（实现前） | 新控件/读取方法缺失，新增回归失败 | R1101-red.log |
| run_selftests.py -k idea brief workflow（首轮） | 244/244，56.9 秒 | R1101-targeted.log |
| run_selftests.py -k idea brief workflow ui_edges | 360/360，178.0 秒 | R1101-target-final.log |
| run_selftests.py --layer architecture | 增量仅 5/5，不冒称全架构 | R1101-architecture.log |
| run_selftests.py --layer architecture --all | 308/308，24.7 秒 | R1101-architecture-all.log |
| smoke_test.py --affected idea_chat workflow | 9/9 | R1101-smoke-affected.log |
| smoke_test.py | 8/8 | R1101-smoke-default.log |
| run_selftests.py --all --safe | 未运行 | R1101-full-safe.log |

首次直接 unittest 未设置项目测试导入路径，因 skip_reasons 导入失败退出；随后改用仓库执行器得到真实失败先行证据，不把导入错误视作功能验证。

未重启真实应用，未人工视觉验收，未调用真实模型，未读取真实创作项目；界面与发送由临时项目 Tk 测试验证。用户未提交预设和未跟踪资料不纳入提交。

## 收尾

中央领取 R1101，无对应队列 ID，不认领历史无关事项。采用 ui-ux-pro-max 的可见标签与语义颜色规则、scoped-tests 的受影响验证顺序；tech-writer 用于实跑证据和未运行边界留痕。

凭据扫描：新增源码/测试的常见 API key、AWS、GitHub token、私钥头形态零命中；git diff --check 通过。队列 validate 0 errors、1 条历史租约警告，未修改他人租约。自审确认三个禁止改动的生产模块均无差异；无新增反向依赖，必填/未落盘断言保留，仅按新契约迁移已删除的示例气泡行为。

完整安全回归待收尾。尚未提交；本文件为进行中检查点，不标 TASK_COMPLETE。
