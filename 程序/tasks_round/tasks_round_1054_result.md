# R1054 结构治理轮（执行）：假凭据静态门禁边界审计

1. 结构治理轮（执行）；执行 `tasks_round/tasks_round_1036_result.md` J13／OPT-11，补 canary 并明确能力边界，不新增用户功能。
2. 定向密钥审计 6/6、5.586 秒，含新增 3 方法／30 个子场景；默认冒烟 8/8，架构 309/309。最近全量为 R1053，不冒充本轮全量。
3. J13 已由中央入口完成并勾选；不关闭安全审计的未支持路径，不改其他队列任务。

## A. 范围与认领

中央入口领取 1054。J13 尚未登记，第一次 claim 明确拒绝；使用 round_claim 的共享锁与权威读写入口登记该已授权条目后认领，owner=codex-j13，不手改工作树快照、不覆盖他人租约。先建立 codex/wip-R1054，再修改测试与关联文档。

## B. 扫描事实

`tests/architecture/_scan.py:10` 的 production_files 只枚举程序根目录 *.py，排除测试前缀及三个开发执行器，不递归 agent/ 等子包；它不读用户项目或密钥文件。`test_secret_sink_audit.py` 的 audit 按函数 AST 节点源码位置遍历，Assign／AnnAssign 的右值为已知 source 调用或引用 tainted 名称时，累加左值名称；sink 调用引用这些名称才命中。没有跨函数摘要、别名解析、控制流或清除污点逻辑；ast.walk 还会进入嵌套函数。

## C. 安全执行方法

新增 audit_snippet 使用 Path 协议替身提供假代码字符串，实际走 audit 的 ast.parse 分支；不 import／exec 假代码，不访问环境变量值、不调用取钥提供者或网络。只使用 FAKE_TEST_KEY 等变量名和公开占位文本；原三个断言完整保留。生产扫描仍经原 production_files，未缩窄扫描范围或增加豁免。

## D. 可检出路径与 canary

| 分组 | 子场景 | 精确断言 |
| --- | --- | --- |
| source × sink | model_secrets.load、model_pool.credential、pet_llm.credential、api_endpoints.configured_key、os.getenv、os.environ.get 六种来源 × logger.warning／json.dumps／client.chat 三类出口 | 18 个样本各命中唯一 file:line:kind，行号为 3 |
| 局部传播 | 普通赋值别名、带注解别名、f-string 后关键字参数、已取钥变量装入 list、装入 dict、return 中调用 prompt sink | 6 个样本各命中唯一第 4 行出口；return sink 不等于跨函数返回值传播 |
| 非污点／范围反例 | 普通字面量、非敏感环境变量名、仅 JSON 字段名含 token、无已知来源的函数参数、非 sink 的 transport.request、独立函数同名变量 | 6 个样本零命中；后两类范围反例不表示所有实际输入安全 |

正常 6/6 测试方法通过；其中新增三项包含上述 30 个子场景。内存故障注入依次将 is_source_call 恒 False、sink_kind 恒 None、names 恒空集合：对应新增测试产生 18／18／6 个失败且零执行错误，均成功检出。替身作用域退出即恢复，未改源代码制造故障。

## E. 漏检边界（假样本实测，非安全通过）

下列九项实际输出均为零命中；仅记录能力，不写“必须漏检”的测试，以免阻止后续增强。

| 场景 | 最小形态（取钥均为假代码，未执行） | 当前限制 |
| --- | --- | --- |
| 直接 source 入 sink | print(os.getenv('FAKE_TEST_SECRET')) | 没有赋值 tainted 名称 |
| 容器中直接取钥 | data={'x':os.getenv('FAKE_TEST_SECRET')}; print(data) | 只认整个右值是 source，不认嵌套 source |
| 跨函数返回 | read 返回 source；调用方 token=read(); print(token) | 无返回摘要 |
| 跨函数参数 | token=source；emit(token)；emit 内 print(value) | 无参数传播 |
| import 别名 | from os import getenv as read；token=read(...) | 无导入别名解析 |
| source 函数别名 | read=os.getenv；token=read(...) | 无可调用对象解析 |
| sink 别名 | emit=print；emit(token) | 无 sink 别名解析 |
| 环境变量关键字 | token=os.getenv(key='FAKE_TEST_SECRET'); print(token) | 只认第一个位置参数 |
| 容器追加 | data=[]; data.append(token); print(data) | 无方法副作用传播 |

该矩阵不是穷尽证明；模块级代码、子包、动态名称、复杂控制流等也不在已证明覆盖范围。

## F. 误报边界（假样本实测）

三项均命中 fake_secret_canary.py:4:log：取钥变量随后覆盖为公开字面量仍被标记；嵌套函数同名形参打印公开参数被外层 tainted 名称污染；字典私密字段与公开字段混装后只打印公开字段仍命中。扫描器是保守的名称集合，不做作用域／字段／覆盖分析。人工复核应根据真实数据流判断，不能删除断言或增加全局豁免来“清零”。

## G. 当前生产扫描

原生产无命中测试与冻结台账／判据一致性测试均通过，未出现新的生产命中证据；不据此宣称无真实泄露。未读取 `.env`、private/、配置/宠物/配置.json、episode/、writing/ 或用户目录。没有真实凭据验证或上传。

## H. 验证与基线

随附 Python，程序目录执行 `-B -m unittest tests.architecture.test_secret_sink_audit`：6/6、5.586 秒。默认 smoke_test.py 冒烟 8/8；smoke_test.py --architecture 实测 309/309、112.061 秒，失败集合为空，改前 306，新增 3 方法。run_selftests.py --layer architecture --all 独立实测 309/309、104 单元、35.886 秒，刷新架构分层基线；清除执行器顺带复制进文档的全量凭据字段，仅保留本轮 architecture 差异，common-dir 权威凭据未改。没有生产改动、启动／Tk／删除／层级表改动；1054−1053=1，未触发三轮全量周期，不重复上轮全量。未修改 AGENTS §5 的触发条件。

## I. 文件边界

最终文档／轮次复验：test_agents_md 与 test_round_baselines 共 15/15、0.314 秒；状态页 1055 = 最新报告 1054 + 1。

只改现有测试模块和本项关联的 AGENTS 入口说明、architecture、架构基线与轮次／队列文档；生产模块零修改，旧 canary 与扫描算法不变。禁止改用户配置、项目、密钥；没有删除或回收操作，没有 computer-use。架构测试清单仍是原文件集合。

## J. 整改结论与后续

本项完成标准是能力审计与 canary，不是实现完整污点分析。新增支持路径保护已落地；九类漏检、三类误报已明确。若后续出现真实安全候选，按判据单独修复；增强算法应先确定 source／sink／作用域契约，并用本矩阵对应样本先红后绿，不顺带更改生产取钥行为。本轮不推进 J14。

## K. 测试迁移计划

保留原三个方法，新增 source×sink、局部传播、反例三项；不移动测试、不删断言、不加 skip。后续能力扩展应将相关漏检探针变成正向检出 canary，并补误报反例；支持范围扩大必须重跑生产扫描、冻结台账一致性及完整架构门禁，不能只跑人工样本。原已支持的 30 个子场景需持续通过。

## L. 提交与回执

适用测试通过；凭据扫描针对本轮差异，仅检查常见 token／私钥形态，未命中，不构成完整泄露证明。仅 master 更新状态页，最小暂存限定本轮 7 个文件，不含用户数据或日志。收尾提交以 Git 唯一消息 `R1054: 明确密钥静态审计边界并补假凭据canary` 定位（提交自身哈希由最终回复提供，不预造自引用哈希）；不 push。

## M. 自审

任务未扩大为安全算法重写；新增断言可由三种故障注入证明有效，限制与成果分开陈述。writing-for-agents 技能促使入口只保留简短提示并指向本报告详细矩阵；无新 Agent 规则或第二套权威。适用门禁通过，中央 R1036-J13 已完成并勾选；曾以简称 J13 收口被入口拒绝，核对规范 id 后成功，无覆盖其他任务。
