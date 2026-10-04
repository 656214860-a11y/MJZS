# R1056：J15 路径辅助死代码清理

1. 本轮为结构治理轮（执行），不是功能轮；来源 R1036 J15／OPT-13、K4。
2. 删除前定向 203/203、40.0 秒，删除后 203/203、38.7 秒；默认冒烟 8/8、架构 309/309；70a25ad 固定检查点安全全量 3973/3973、388.9 秒，全部通过。
3. 人工队列 J15 已勾选、中央已 complete；project_status.md 正文欠账本轮未减少，不将死代码清理冒充用户体验或历史欠账收口。

## A. 范围与授权

用户授权直接操作优化队列；本轮仅复核并清理 idea_chat／white_model 两个候选，不领取 J16。使用 simplify 技能约束最小行为等价清理；不进行 UI 操作或 computer-use。

## B. 基线

起点 master 954e2cc；中央 next 分配 1056，R1036-J15 由 codex-j15 认领。改前工作树干净，WIP 分支 codex/wip-R1056。既有默认冒烟 8、架构 309；最近真实安全全量 R1053 检查点 c303259 为 3968/3968、382.203 秒，仅代表当时内容树。

## C. 引用证据

在起点 954e2cc，idea_chat.py:124 的 _numbered_path、white_model.py:71 的 _base_directory 各仅定义命中。对受控 Git 跟踪的 566 个 Python／pyw 源文件解析 AST，Name、Attribute、导入别名及精确字符串均没有消费者，解析错误 0。排除 private、episode、writing、配置、logs、skills 和备份目录，不读取用户数据。

11 个直接导入方为 app、desktop、local_previs、local_video、native_apps、white_model_ref、writing_api，以及 tests/test_idea_chat、test_previs、test_ui_edges、test_white_model_ref。复核相关调用和 ui_plugin_registry、stage_handler_registry、legacy_compat 注册边界，无候选的动态注册／反射调用。静态扫描不保证仓库外脚本不存在私有符号引用。

## D. 修改

删除两个私有函数及 white_model 中随之失去使用者的 pathlib.Path 导入；生产代码减少 20 行。只改两个生产模块，不删除测试或修改断言。保留 _BLENDER_CACHE、_WORKSPACE_CACHE、_BASE_CACHE、_DIR_CACHE 四个共享别名。

## E. 行为与路径

idea_chat.save_reply／save_manual_creative 仍接收 L3 发布器，stage_execution_service.publish_idea_creative 经 write_dir 定位当前剧本阶段。旧创意与聊天读取分支不变，不恢复旧路径新写入。white_model.shot_directory 仍注入上下文并委托 white_model_service；缓存失效、路径越界拒绝、旧记录读取均未修改。

## F. 差异审查

删除前后 AST 对比：排除两个指定函数和 white_model 的孤立 Path 导入后，两文件剩余 AST 完全相同；两文件内存 compile 通过，四个缓存别名与服务对象 identity 检查通过。没有新依赖、事件或路径权威。已有缓存重复查询／workspace 切换测试位于 tests/test_previs.py:203，创意发布及旧读测试位于 tests/test_idea_chat.py。

## G. 测试策略

按 K4 删除前后执行同一命令：随附 Python -B run_selftests.py -k idea_chat white_model stage_paths path_authority previs。保持所有测试文件原样，覆盖聊天、白模、旧读、新写路径与缓存。项目无单独 lint／类型检查配置；使用 AST 等价、diff --check、默认静态冒烟与架构门禁，不声称运行不存在的 lint/typecheck 命令。

## H. 验证记录

- 删除前定向：203/203，40.0 秒，0 红。
- 删除后定向：203/203，38.7 秒，0 红。
- 默认 smoke_test.py：8/8，0 失败。
- smoke_test.py --architecture：309/309，104.334 秒，0 失败，与改前历史实测 309 一致；本次在 WIP 分支执行，随后 master 全量仍须通过。
- 本轮 1056−1053=3，触发 run_selftests.py --all --safe：干净 master 检查点 70a25ad 实测 300 个测试文件、3973/3973、388.9 秒，0 红；包括 master 上的架构与轮次门禁。真实 common-dir 凭据：tree=67590ad058708133dbee5adc5c1614b39d9b0f29，round=1056，at=2026-10-05T02:35:13。未修改或伪造凭据。
- 全量后仅更新报告、状态与人工队列；最终 test_agents_md／test_round_baselines 15/15、0.347 秒，默认冒烟复验 8/8；不宣称最终文档树再次执行全量。

## I. 数据安全

不改配置、用户项目数据、密钥、private/、episode/、writing/、logs/；不清缓存、不提交云端请求。删除的是 Git 可恢复源码中的无调用函数，不执行用户文件删除。测试仅采用既有隔离夹具。

## J. 整改结果

两个候选已清理，全部适用门禁通过后勾选 J15／中央 complete。J16 及其余优化项不在本轮范围。状态正文中的旧待办事实留给 J18 整理，不擅自删除历史记录；继续推进前仍须按 AGENTS §2.5 复核五轮欠账减少要求。

## K. 测试迁移计划

无需迁移；现有测试文件、测试方法、断言原样保留。若任何回归显示遗漏消费者，恢复对应私有实现并重新验证，不弱化断言迁就清理。

## L. 提交与状态

代码及进行中报告已提交固定检查点 70a25ad（R1056: 保存路径辅助清理全量验证检查点），随后安全全量通过。最后仅提交报告／状态／人工队列三份文档；本轮总范围六文件。收尾提交以 Git 消息 `R1056: 完成路径辅助死代码清理验收` 唯一定位，最终回复提供提交号，不预造自引用哈希。diff --check 通过；N=1057、M=1056，满足 N=M+1。凭据形态扫描限定本轮差异中的常见 token／私钥模式，不构成完整安全证明；不 push。

## M. 自审

自审通过：仅两个生产模块、20 行无消费者代码／孤立导入删除；剩余 AST 和所有测试不变，兼容路径、缓存 identity 与路径越界防护有原有回归覆盖。定向、默认冒烟、独立架构和固定检查点安全全量均通过。无新功能、越界依赖或用户数据改动。使用 simplify 技能完成最小行为等价清理，未借机重排或格式化其他代码。
