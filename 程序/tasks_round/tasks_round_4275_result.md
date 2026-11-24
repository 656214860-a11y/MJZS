# R4275 REL-05：账号服务与外部地址——外部地址清单测试固定＋登录闸不可达提示与重试（修复轮，续做）
<!-- round-evidence: {"commit_base": "962927f0e", "credential_hits": 0, "evidence_sha256": "5f0601c59cb19022", "exit": 0, "failed": 0, "passed": 95, "round": 4275, "tests": "run_selftests.py -k http_boundary account_client login_gate doc_registry_migration"} -->

## 三问
- 轮次类型：§3.2 修复轮（REL-05 / 波次 W2 / 共享资源 account；续做卡）。
- 测试跑了吗、三个基线过了吗：跑了卡面三条验收命令，全部退出码 0（明细见下）；架构门禁 `smoke_test.py --architecture` 701 条全绿。默认冒烟 `smoke_test.py`（无参数）与全量 `run_selftests.py --all --safe` 未跑（卡面验收未要求）。
- 欠账少了吗：新增「外部地址清单未登记即红」与「登录闸三类不可达提示＋重试」两条守卫，无新增欠账。

## 范围与基线
- 基准版本：`cb33bcfebd3d3936f400b12fdd0af5d8d6c74533`；开工 `git log -1 --format=%h` 输出 `cb33bcfe`，`git rev-parse --abbrev-ref HEAD` 输出 `codex/rel-05`，`git status --porcelain` 与卡面续做现场 5 行逐行一致（中文路径为八进制转义，按文件名对照吻合）。
- 续做现场（上一位执行者未提交草稿，本轮全部保留并在其上补齐）：
  - 保留：`domain/account_client.py` 的不可达分类实现（`SERVICE_TIMEOUT`/`CERT_ERROR` 常量、`UNREACHABLE_MESSAGES` 三句人话提示、`SUPPORT_PLACEHOLDER` 占位、`_unreachable()` 分类、`request()` except 分支返回分类 `SystemError`）；`ui/desktop_login_gate.py` 的闸提示机制（`account_message.configure` 包装＋`_show/_hide/_arm` 系列）；`tests/test_login_gate.py` 的三失败原因提示用例；新建 `docs/process/外部依赖清单.md`（81 条登记）；`docs/records/工程文档登记表.md` 新增一行。
  - 修改及原因：
    1. `ui/desktop_login_gate.py`：删除 `from ui_widgets import SecondaryButton`（`desktop_login_gate` 与 `ui_widgets` 同为 L4 且 `('desktop_login_gate','ui_widgets')` 未登记进 `_layers.SAME_LAYER_EDGES`，`_layers.py` 已冻结不可改）；「重试」按钮改为 `type(self.account_use_code_button)(...)` 复用表单 SecondaryButton 类（不新增同层边、不退回裸 `ttk.Button` 以满足按钮边界门禁）。
    2. `ui/desktop_login_gate.py` `_show_gate_notice`：补「已建提示框被 pack_forget 后再次显示」分支的 `box.pack(...)` 重新置顶——原草稿在 hide→show 循环（如重试发送中→再次失败、切页签后再失败）会让提示框保持隐藏但 `account_message` 已是错误文案，提示不可见。
    3. `ui/desktop_login_gate.py` `_gate_notice_retry`：改为 `self.account_use_code_button.invoke()` 走「用验证码登录」同一发送路径（保留视图切换、按钮禁用与发送中提示），删除随之失效的 `_gate_notice_sent`；失败后提示仍由 `say()→configure` 包装自动重现。
    4. `tests/architecture/test_http_boundary.py`：把 `.agent-tmp/rel-05-old-drafts/test_external_endpoints.py` 的清单固定用例并入为新方法 `test_hardcoded_addresses_are_registered`（AST 扫 `production_runtime_files()` 的 `http(s)://` 字符串常量、排除文档串、按 `文件:行号` 对 `docs/process/外部依赖清单.md` 登记核对）；原有两条用例逐字未动；模块 docstring 补一句清单职责。
    5. `tests/test_login_gate.py`：新用例补「重试按钮 invoke 后 `send_code` 被再次调用」断言（`test_gate_shows_unreachable_prompts_with_retry`）。
    6. `tests/test_account_client.py`：新增 `test_unreachable_failures_have_distinct_codes_and_messages`，覆盖五种异常形态→三种 code→对应人话提示的映射与三句文案互不相同。
    7. `docs/process/外部依赖清单.md`：第 5 行测试文件名由草稿的 `test_external_endpoints.py` 改为实际并入处 `test_http_boundary.py`；R4252→R4275。
    8. `docs/records/工程文档登记表.md`：新文档行轮次号 R4252→R4275。
- 改动文件：`domain/account_client.py`、`ui/desktop_login_gate.py`、`tests/test_account_client.py`、`tests/test_login_gate.py`、`tests/architecture/test_http_boundary.py`、`docs/process/外部依赖清单.md`、`docs/records/工程文档登记表.md`、`tasks_round/tasks_round_4275_result.md`；`tasks_round/evidence/R4275.json` 由 `scripts\dev.py commit` 生成。
- 未触碰：`governance/structure.json`、`governance/structure-baseline.json`、`architecture.md`、`tests/architecture/_layers.py`（治理裁决要求冻结）；`.agent-tmp/` 下旧草稿只读未动，未复制回 `程序/tests`。

## 改动位置（文件:行号）
- `程序/domain/account_client.py:28-36`：`NETWORK`/`SERVICE_TIMEOUT`/`CERT_ERROR` 常量、`SUPPORT_PLACEHOLDER`、`UNREACHABLE_MESSAGES` 三句提示。
- `程序/domain/account_client.py:179-186`：`_unreachable(exc)` 分类（SSLCertVerificationError→cert_error；TimeoutError/'timed out'→service_timeout；其余→network）。
- `程序/domain/account_client.py` `request()` except 分支：出站异常返回带 `data['code']` 的分类 `SystemError`。
- `程序/ui/desktop_login_gate.py:75-96`：`_arm_gate_unreachable_notice`（包装 `account_message.configure`，文案命中三句提示时调 `_show_gate_notice`）。
- `程序/ui/desktop_login_gate.py:98-133`：`_show_gate_notice`/`_hide_gate_notice`/`_gate_notice_retry`（提示条＋「重试」按钮，复用 SecondaryButton 类）。
- `程序/tests/architecture/test_http_boundary.py:21-73,95-102`：清单登记解析与新增地址扫描 helpers＋`test_hardcoded_addresses_are_registered`。
- `程序/tests/test_login_gate.py:150-175`：三失败原因提示＋重试按钮＋重发断言。
- `程序/tests/test_account_client.py:362-380`：异常形态→code→提示映射用例。
- `程序/docs/process/外部依赖清单.md`：新建，81 条 `名称|文件:行号|地址|是否用户可改|失效时的表现` 登记。
- `程序/docs/records/工程文档登记表.md:108`：新文档登记行。

## 改前红
- 续做现场已有实现，未观察改前红（按接口契约第一条如实记录；禁止回退产品代码看红）。上一位执行者的旧结果草稿（`.agent-tmp/rel-05-old-drafts/tasks_round_4252_result.md`，不作为本次交付）记录过改前红：81 个未登记外部地址＋`AttributeError: no UNREACHABLE_MESSAGES`。
- 新增并入的 `test_hardcoded_addresses_are_registered` 首次运行即绿——清单 81 条与扫描结果一一对应，说明上一位执行者的登记已完整。

## 验证命令与结果
工作目录均为 `程序`；命令原样照抄卡面。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k account_client login_gate http_boundary`
   - 退出码：0。输出尾部：
     ```text
       architecture.test_http_boundary     3 条     4.5 秒
       test_account_client#1          9 条     0.2 秒
       test_account_client#5          9 条     0.2 秒
       test_account_client#4         14 条     1.1 秒
       test_account_client#2         16 条     1.3 秒
       test_account_client#3         12 条     1.4 秒
       test_login_gate#1             11 条    13.3 秒
       test_login_gate#2             14 条    15.2 秒
     共 88 条用例，366.3 秒；0 个文件有红
     ALL TESTS PASSED
     ```
   - 说明：执行前曾排队等待跨树 GUI 令牌约 5.5 分钟（队列第 2→第 1 位），非失败。
2. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`
   - 退出码：0。输出尾部：
     ```text
       architecture.test_design_coverage     8 条     1.0 秒
       architecture.test_agent_doc_budget    11 条     1.0 秒
       architecture.test_stage_doc_sections    10 条     1.0 秒
       architecture.test_requirement_traceability     5 条     1.5 秒
     共 34 条用例，2.5 秒；0 个文件有红
     ALL TESTS PASSED
     ```
3. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`
   - 退出码：0。输出尾部：
     ```text
     Ran 701 tests in 274.291s
     OK
     ✅ 架构治理测试：tests/architecture
     ```
   - 其中 `test_lr03_unregistered_same_layer_edge_is_red` 等同层边门禁全绿——`ui_widgets` 导入已移除，无未登记边。
4. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`
   - 退出码：0，输出 `4275`。

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4275: REL-05 修复" --tests account_client login_gate http_boundary <上述 8 个文件路径>`（提交哈希以完成报告为准；`tasks_round/evidence/R4275.json` 由提交命令生成）。

## 第二笔提交：出口门禁修复（合入接管会话，门禁类小修）
- 现象：上一次 `dev.py merge` 出口 CI 架构门禁红（702 条 1 红）：`test_hardcoded_addresses_are_registered` 报 `desktop.py:254 http://127.0.0.1:8189` 与 `domain/tts_api.py:16 https://api.openai.com/v1` 未登记。
- 根因：两条地址在 `docs/process/外部依赖清单.md` 里**早已登记**，但登记行号按旧基点 `c8b94924` 写的是 `desktop.py:242`、`domain/tts_api.py:15`；主干其后给 `desktop.py` 增加了 12 行、`domain/tts_api.py` 增加了 1 行，分支变基到主干后行号位移，门禁按「文件:行号」精确匹配判红。地址、用途、是否可配置均未变。
- 修复：只改 `docs/process/外部依赖清单.md` 两行的行号（`242→254`、`15→16`）；名称、地址、「是否用户可改＝是」、失效表现逐字未动。核对用途：`desktop.py:254` 是 `startup_settings(...)` 的 `defaults={'comfy_url': 'http://127.0.0.1:8189', ...}`，即桌面设置的本机 ComfyUI 默认地址，用户可在设置里改；`domain/tts_api.py:16` 是 `DEFAULT_URL`（`read_settings()` 的 `base_url` 默认值），用户可在配音设置里改。
- 未动：测试文件、断言、产品代码、`docs/records/工程文档登记表.md`、`governance/` 下任何结构文件（核对过，没有门禁按行数或哈希核对本清单；`tests/architecture/test_external_endpoints.py` 在仓库中不存在，该用例已并入 `test_http_boundary.py`）。
- 变基：车道 `git rebase master` 干净完成，无冲突；分支基于 master `755c7e9d0`。

## 未验证项
- 未观察改前红（续做现场已有实现，见上）。
- 未跑默认冒烟 `smoke_test.py`（无参数）、`--affected`、`--gate` 与全量 `--all --safe`；卡面验收只要求上述三条命令。
- 未做真实网络验证（卡面禁止联网）：三类不可达均以桩/构造异常验证；`SSLCertVerificationError` 在真实 TLS 握手中的触发路径未实测。
- 支持渠道为占位 `联系客服：[待用户提供联系渠道]`（`account_client.py:31`），卡面「拿不准」项待用户提供真实联系方式后替换。

## 卡外发现（只记录不修）
- `ui/desktop_account_page.py:240` 对续期失败按 `code != 'network'` 分支：新 code `service_timeout`/`cert_error` 会落到「显示状态文本」分支而非 network 提示，行为可接受但文案未单独区分；该文件不在本卡允许清单。
- 顶层 `程序/account_client.py` 为 `domain.account_client` 门面别名，本卡改动经门面自动生效，未单独验证门面导出（`run_selftests` IMPORT OK 已覆盖导入）。

## 被拒绝的命令
- `Get-ChildItem "程序\tasks_round" -Filter ...`（PowerShell 枚举结果文件）被拒一次；改用文件工具列目录完成同一取证目的，未重试。

## 仍留在车道里的未跟踪文件
- `.agent-tmp/`（旧草稿 `rel-05-old-drafts/` 等，已被 gitignore，不进提交）；提交后 `git status --porcelain` 预期仅剩 `.agent-tmp/` 开头行，原文见完成报告。
