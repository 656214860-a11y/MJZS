# R4359 结果：REL-11B 隐私声明草案（只写文档，不改界面）
<!-- round-evidence: {"commit_base": "17d244985", "credential_hits": 0, "evidence_sha256": "cf0428da4c9a1dce", "exit": 0, "failed": 0, "passed": 23, "round": 4359, "tests": "run_selftests.py -k agent_doc_budget requirement_traceability doc_registry_migration"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（仅文档）。任务卡 REL-11B（波次 W2），车道 `.agents/worktrees/rel-11b`，分支 codex/rel-11b，基准 17d24498。缺陷：`docs/requirements/产品需求规格.md` §1.4「隐私协议要点」要求对外发布前须有正式文本，而隐私声明草案不存在。复现方式：先按卡面设计落地 `docs/process/隐私声明草案.md`（草案本体），不登记，跑定向命令，登记门禁 `test_all_current_documents_are_registered` 如期转红（新文档存在但未登记），随后登记一行转绿。
- （二）测试跑了吗、三个基线各是什么结果：定向——跑了。改产品（登记行）之前 `run_selftests.py -k agent_doc_budget requirement_traceability doc_registry_migration`：共 23 条用例、1 个文件有红，红 1 条（原文见「改前红」）；登记后同命令退出码 0：「共 23 条用例，1.2 秒；0 个文件有红」「ALL TESTS PASSED」。架构门禁——跑了：`smoke_test.py --architecture` 输出尾部「Ran 706 tests in 271.525s」「OK」「✅ 架构治理测试：tests/architecture」，退出码 0。默认冒烟和全量自测——没跑（卡面验收只写了上面两条命令）。
- （三）欠账少了吗：少了——需求规格 §1.4 要求的发布前隐私文本有了草案（待用户批准），并已在工程文档登记表登记，受 `test_doc_registry_migration` 双向核对保护。无新增债务。

## 改前红

新建 `docs/process/隐私声明草案.md` 之后、登记之前，在车道的 程序 目录下跑 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k agent_doc_budget requirement_traceability doc_registry_migration`，退出码 1：

```
定向：忽略增量台账，执行 3 个匹配测试文件
跑 3 个测试文件 / 3 路工作单元（8 路并行）
  architecture.test_doc_registry_migration     7 条     0.1 秒  ✗ 1
  architecture.test_agent_doc_budget    11 条     0.1 秒
  architecture.test_requirement_traceability     5 条     1.6 秒

共 23 条用例，2.3 秒；1 个文件有红

### architecture.test_doc_registry_migration（1 条红）

===== test_all_current_documents_are_registered (architecture.test_doc_registry_migration.DocRegistryMigrationTests.test_all_current_documents_are_registered) =====
AssertionError: Lists differ: ['存在但未登记：docs/process/隐私声明草案.md'] != []
```

红的原因与缺陷一致：发布要求的隐私声明文档落在 `docs/` 职责目录后必须登记，登记缺失即被门禁拦住。该遍输出末尾另有 `[SUSPECT_CONCURRENCY]` 提示（红项时有其他 PID 持有 GUI 令牌），登记后复跑同命令无红，判定为噪声。

## 改了哪些文件

- `docs/process/隐私声明草案.md`（新建）：文首标明「草案，待用户批准；批准前不放进关于页，不作为发布阻断项」；七节结构——本地保存不上传的数据清单、外发操作逐项表（每条标注在 `docs/process/外发内容清单.md` 的对应节）、密钥与日志脱敏口径（`infra/app_logging.redact`：凭据→`[已脱敏]`、邮箱→`[邮箱]`、用户目录→`~`、用户名→`[用户]`，依据 app_logging.py:53-76 与 log_maintenance.py:25 的 30 天保留）、关闭与删除方式、账号注销与年龄声明、中转站说明（当前无计量上报端点）、联系方式与主体留空待填。外发描述逐条对应清单的联网采风／模型请求／图像视频生成／本机 ComfyUI／账号服务／更新检查／实时 ASR／TTS／SKILL 包下载／离线模型下载／连通性探测／浏览器打开各节，未写清单之外的字段。
- `docs/records/工程文档登记表.md`：只在表尾加一行（:110）`docs/process/隐私声明草案.md | 全局 | 全局 | 权威 | R4359 | 用户、执行 agent`，性质按登记表定义取「权威」（该主题是唯一权威文档；草案待批状态写在文首标注里，登记表没有第三档性质）。
- `tasks_round/tasks_round_4359_result.md` 是本文件；`tasks_round/evidence/R4359.json` 由提交工具生成。

没有改任何 .py 与界面代码，没有改基线、台账、层级登记表，没有删除或放宽断言，没有新增跳过。草案不放进关于页、不接入界面（卡面明确批准前不接入，接入另立卡）。

## 命令与退出码

都在车道的 程序 目录下跑，`python.exe` 指 `..\..\..\..\运行环境\Python\python.exe`。

| 命令 | 结果 |
| --- | --- |
| python.exe -B run_selftests.py -k agent_doc_budget requirement_traceability doc_registry_migration（草案落盘、未登记） | 退出码 1：「共 23 条用例，2.3 秒；1 个文件有红」（1 条红，原文见上） |
| 同命令（登记行加入后） | 退出码 0：「共 23 条用例，1.2 秒；0 个文件有红」「实际跳过 0 条用例」「ALL TESTS PASSED」 |
| python.exe -B smoke_test.py --architecture | 退出码 0：「Ran 706 tests in 271.525s」「OK」「✅ 架构治理测试：tests/architecture」 |
| python.exe -B scripts\dev.py claim | 领到轮次 4359 |

## 未覆盖项

- 草案尚未经用户批准：联系方式与法律主体名称为占位符，由用户填写；批准前不放进关于页，不作为发布阻断项（卡面既定）。
- 未跑默认冒烟与全量自测（卡面验收只有上述两条命令）；未改 about 页与任何界面；未 push、未 merge、未合入。
- 草案表格为人工逐条对应清单编写，无自动化逐句核对（卡面测试用例注明「无代码」）；清单日后变更时按草案头部声明同步修订。

## 卡外发现的问题（只记录）

- `docs/process/外发内容清单.md` 与需求规格 §1.4 之外，仓库内未发现第二份面向用户的隐私文本；草案是唯一候选，批准后接入位置（关于页）另立卡处理。

## 提交

用 `scripts\dev.py commit` 提交，只提交上面列出的文件与 evidence。提交号见提交输出与本文件的 round-evidence 头。
