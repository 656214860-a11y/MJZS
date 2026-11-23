# R4109 结果：提示词优化的密钥改存本机加密存储
<!-- round-evidence: {"commit_base": "f624a5fc", "credential_hits": 0, "evidence_sha256": "188f03bd5edad6db", "exit": 0, "failed": 0, "passed": 22, "round": 4109, "tests": "run_selftests.py -k mcp_settings"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 W6-SEC-K3，车道 codex/sec-k3-optimizer-key；来源是推进窗口的密钥落点审查（SEC-KEYSINK）——「Prompt Optimizer MCP 设置」窗口的 API 密钥明文写进 private/prompt_optimizer.json，且交给优化子进程的数据包了整份设置。

（二）测试与三个基线：mcp_settings 点名实测 22 条全过（原有 10 条、新增 12 条），改产品代码之前那一遍红 12 条（全是新用例，旧 10 条过），退出码 1；架构门禁 smoke_test --architecture 实测 700 条、失败集合为空、退出码 0（第一遍曾因新注释含「暂时」红 1 条，改措辞后复验全过）；默认冒烟没单独跑；全量自测没跑。没有删除用例，没有改已有断言。

（三）欠账：设置文件明文存密钥这一条消掉——顶层、profiles、model_profiles 里的 api_key 全部写空串；交给桥子进程的数据从整份设置缩到六项。未新增欠账；如实说明里列了两处需要验收窗口留意的既成事实。

## 改了哪些文件

- agent/prompt_optimizer.py：import 行加 hashlib，新增 `import infra.model_secrets`；HOME 之后新增 8 个模块级函数 `key_name_for/_secret_root/stored_key/_migrate_plain_keys/load_config/forget_key_if_unused/ready_config/bridge_payload`；settings() 改七处（读设置改走 load_config、api_key 格回填走 stored_key、新增内部函数 show()、select_provider 三处回填与 choose_model 回填改走 show()、delete_model 结尾追加 forget_key_if_unused、commit 改为密钥先入加密存储再 remember 一份 api_key='' 的记录）；start() 改三处（读设置改走 ready_config()、删掉重复的 missing 计算、data 改走 bridge_payload() 六项）。work()/receive()/_optimizer_home()/HOME/界面控件与界面文字未动。
- tests/test_mcp_settings.py：新增 `import infra.model_secrets`、模块级 `use_fake_protector()`（换可逆假加密）、SettingsCase.setUp 挂假加密；新增 KeyAtRestTests 6 条（保存不落明文、开窗自动迁移、留空沿用、新地址无密钥被拒、删除最后模型清密钥、删除在用地址保留密钥）与 KeyStoreTests 6 条（密钥名规则、迁移抹文件、已有密钥不覆盖、存不进留原文、ready_config 缺项、bridge_payload 只六项）。
- 本结果文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| git -c core.quotepath=false status --porcelain | 无输出，退出码 0 |
| git log -1 --format=%h | f624a5fc，退出码 0 |
| run_selftests.py -k mcp_settings（改产品代码前） | 退出码 1；22 条中 12 条红（全部新用例）、10 条过 |
| git -c core.quotepath=false diff --stat | 恰好 2 个文件，退出码 0 |
| run_selftests.py -k mcp_settings（改后） | 退出码 0；22 条全过，ALL TESTS PASSED |
| smoke_test.py --architecture（第一遍） | 退出码 1；700 条中 1 条红（TODO 注释快照：新注释含「暂时」） |
| run_selftests.py -k mcp_settings（改注释后复验） | 退出码 0；22 条全过 |
| smoke_test.py --architecture（第二遍） | 退出码 0；700 条全过，OK |
| scripts\dev.py claim | 领到 4109，退出码 0 |

## 如实说明

- 点「MCP 优化」时密钥仍经标准输入的 JSON 交给桥子进程（只在内存和管道里，不落盘），这是桥调用模型必需的；agent/optimizer_mcp_bridge.py 未改。
- 设置窗口的密钥格照旧回填显示（用户要求的行为保留：选回保存过的接口，密钥格回填该地址在本机存的密钥）。
- 密钥按接口地址存，同一个地址下的多个模型共用一把（原来每条模型记录在文件里各存一份明文）；密钥名 OPTIMIZER_<主机>_<地址 sha256 前 8 位>_KEY 不写进设置文件。
- 本机加密存储用不了时保存设置会报错（ValueError/OSError 走原有 notify 通道），不再退回明文；老文件里迁不走的明文原样留着，下次读设置再试，开始优化时由 ready_config() 兜底使用。
- 密钥读取经 stored_key() 和 ready_config()；这两个读取口没有登记进密钥流向审计（tests/architecture/test_secret_sink_audit.py 的 SOURCE_CALLS 未含它们），所以 start() 里把密钥交给桥的那一处 json.dumps 不会被审计记成命中——这一点请验收窗口亲自读并决定要不要登记。
- start() 整条链路没有自动测试（原来也没有），本轮只测到 ready_config() 和 bridge_payload()。
- 没有同步文档：仓库文档里没有提到这个设置文件。
- 和卡面参考代码不一样的地方：一处。load_config() 里 OSError 兜底那行注释，参考写法含「暂时」二字，命中 TODO 注释快照门禁 MARKERS（第一次架构门禁因此红）；按门禁只允许改本轮代码的规则，把「文件暂时写不了」改为「文件写不进去」，语义与行为不变，复验 700 条全过。除此之外与参考代码一致；契约里引用的行号与原文逐一对得上，未做其他对齐调整。

## 未覆盖项

- 没有在真实的 Windows DPAPI 加密上跑：用例用 use_fake_protector() 换成了可逆的假加密，只验证密钥去向，不验证系统加密本身。
- 没有用真实的老设置文件验证迁移，只用临时目录里的种子文件验证。
- start() 的界面流程（子进程启动、结果回填）没有测试。
- 全量自测没跑；默认冒烟没单独跑。
