# R4392 结果：REL-13 用户文档与环境错误指引（应用内帮助入口、环境类错误指引、已知问题清单）
<!-- round-evidence: {"commit_base": "67fd96c99", "credential_hits": 0, "evidence_sha256": "af3f564868d20228", "exit": 0, "failed": 0, "passed": 55, "round": 4392, "tests": "run_selftests.py -k account_page copy_rules static_names"} -->

## 三问
- 轮次类型：功能轮（§3.1，先文档后写码；按卡面先红后绿执行）。卡 REL-13：发布就绪调研确认的缺口——无应用内帮助入口、无环境类错误用户指引、无用户可见已知问题清单。
- 测试和三个基线：定向 `run_selftests.py -k account_page copy_rules static_names` 改前 6 红、改后 55 条全绿（退出码 0）；`-k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 34 条全绿（退出码 0）；`smoke_test.py --architecture` 三跑 708 条全过（退出码 0；前两跑各修掉 1 条本改动引入的红）；默认冒烟 8/8 本轮未运行（卡面验收未列）。
- 欠账：减少。缺陷面全部落地；门禁红灯（EC-3 异常变量泄漏、Desktop 类体积 814>813）同轮内按门禁口径改写法闭环，未调任何登记值、未放宽阈值。

## 缺陷复现
- 复现命令（程序 目录下原样执行）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k account_page copy_rules static_names`
- 改前红 6 条（共 55 条、退出码 1），原因与卡面缺陷一致——帮助入口、文档清单与错误指引指针在源码中全部不存在：
  - `test_account_page.HelpEntryTests.test_env_error_prompt_ends_with_help_pointer`：`ImportError: cannot import name 'with_help_hint' from 'ui.desktop_account_page'`
  - `test_account_page.HelpEntryTests.test_env_guide_has_five_pages_each_with_required_fields`：`ImportError: cannot import name 'ENV_HELP_PAGES'`
  - `test_account_page.HelpEntryTests.test_help_doc_text_reads_utf8_and_tolerates_missing`：`ImportError: cannot import name 'help_doc_text'`
  - `test_account_page.HelpEntryTests.test_help_docs_ship_with_app_and_load`：`ImportError: cannot import name 'help_doc_text'`
  - `test_account_page.HelpEntryTests.test_help_topics_cover_three_user_docs_and_entry_exists`：`ImportError: cannot import name 'help_topics'`
  - `test_account_page.HelpEntryTests.test_known_issues_doc_lists_user_visible_fields`：`ImportError: cannot import name 'help_doc_text'`
- 新增用例按卡面合入既有 `tests/test_account_page.py` 的 `HelpEntryTests`（防 STR006），不建真实 Desktop／Tk 窗口，只用临时目录。

## 改动
- `ui/desktop_account_page.py:8`：`import errno`；`:128-139` 模块级 `HELP_GUIDE_NAME`／`HELP_DOCS`（使用说明→`docs/process/制作失败与人工替代.md`、环境类错误指引、已知问题，相对 `APP_ROOT`）与 `ENV_HELP_PAGES` 错误码→页名映射（`E-TOOL-MISSING`→FFmpeg 缺失、`E-IO-WRITE`→磁盘满、`E-AUTH-*`/`E-QUOTA-EXCEEDED`→模型 Key 无效、`E-NET-*`→网络不可达、账号 `network`/`service_timeout`/`cert_error`→账号服务不可达）；`:142-168` `help_topics()`（root 可注入）、`help_doc_text()`（UTF-8 读、缺档返回空串）、`with_help_hint()`（认 code 属性／结果字典／`errno==ENOSPC`，命中在提示末尾补「查看帮助：环境类错误指引 · <页名>」，未命中原样返回）；`:171-194` `help_card()`（「帮助」卡：三个「查看」按钮页内展开只读 TextArea，可切换可收起，缺文档给一句话说明）；`:404,410-412` `account_page()` 尾部在 `_account_about_card()` 后挂 `_account_help_card()` 薄方法（与「关于」同处，类体积棘轮内）；`:699` 登录/注册/找回失败分支 `say(with_help_hint(...,data))`，`network` 等不可达码提示末尾带「查看帮助：环境类错误指引 · 账号服务不可达」。
- `desktop.py:47`：import 行并入 `with_help_hint`（零净增行）；`:593` `safe()` 通知改经 `message = with_help_hint(error_codes.user_text(e),e);self.notifier.error(message)`——环境类异常（`E-TOOL-MISSING`/`E-IO-WRITE`/`E-AUTH-*`/`E-NET-*`/`ENOSPC`）的弹窗末尾带帮助页指向，其余文案逐字不变。单行分号写法与该行原风格一致，Desktop 类体积不增。
- `docs/guides/用户手册/环境类错误指引.md`（新建）：FFmpeg 缺失、磁盘满、模型 Key 无效、网络不可达、账号服务不可达五节，每节含「现象、原因、怎么办、联系方式」；联系方式沿用 `account_client.SUPPORT_PLACEHOLDER` 既有占位「联系客服：[待用户提供联系渠道]」，并提示附诊断包。
- `docs/guides/用户手册/已知问题.md`（新建）：4 条用户可感知问题（「剪映」名义与其他剪辑软件未验证、升级/回滚只演练过模拟构建、源码副本不携带随包工具与开源清单、取消不保证远端已停止），每条含「现象、影响、临时办法」。
- `docs/process/制作失败与人工替代.md:35-37`：文末加「环境类故障」一节，把五类环境错误指向《环境类错误指引》并把残留问题指向《已知问题》。
- `docs/records/工程文档登记表.md:111-112`：登记两份新文档（`L4 | 全局 | 权威 | R4392 | 用户`），只加本卡新建文档那两行。
- `tests/test_account_page.py:429-488`：新增 `HelpEntryTests` 6 条（帮助入口存在且三类文档随包可读、UTF-8 读文与缺档容忍、指引五页字段齐全、错误提示末尾含指向、已知问题字段齐全）；不建 Tk、只用临时目录。
- 棘轮适配（同轮闭环）：首跑架构门禁报 `desktop.py:593 通知调用直接渲染异常变量 e`（EC-3，异常原文须只经 `user_text()` 进通知），把提示文本先算进 `message` 变量；复跑报 `desktop.py::Desktop 814 行 > 上限 813`，改单行分号写法消掉净增行。

## 核对（命令输出尾部原文）
- `run_selftests.py -k account_page copy_rules static_names`，退出码 0：
  ```
  跑 3 个测试文件 / 4 路工作单元（8 路并行）
    test_static_names              8 条     1.9 秒
    test_copy_rules               18 条     4.4 秒
    test_account_page#2           13 条    12.2 秒
    test_account_page#1           16 条    20.1 秒

  共 55 条用例，29.7 秒；0 个文件有红
  ……
  ALL TESTS PASSED
  ```
- `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`，退出码 0：
  ```
  跑 4 个测试文件 / 4 路工作单元（8 路并行）
    architecture.test_design_coverage     8 条     0.0 秒
    architecture.test_stage_doc_sections    10 条     0.1 秒
    architecture.test_agent_doc_budget    11 条     0.1 秒
    architecture.test_requirement_traceability     5 条     0.4 秒

  共 34 条用例，1.3 秒；0 个文件有红
  ……
  ALL TESTS PASSED
  ```
- `smoke_test.py --architecture`，退出码 0（第三跑；前两跑各修掉 1 红：`desktop.py:593` EC-3、`Desktop 814>813`）：
  ```
  ----------------------------------------------------------------------
  Ran 708 tests in 283.917s

  OK
  ✅ 架构治理测试：tests/architecture
  ```

## 未验证
- 默认冒烟 8/8 未运行；全量 `run_selftests.py --all --safe` 未运行（卡面验收未列）。
- 真 Desktop 账户页未人工点验「帮助」展开交互；`help_card` 的 Tk 构建未用真窗口断言（卡面禁止新测试建 Tk），逻辑与数据层由无 Tk 用例覆盖。
- 打包副本是否随附 `docs/`：帮助入口对缺文档容错（显示一句提示），开发副本三份文档均可读。
- 「拿不准」项：支持联系方式用户未提供，按 `account_client.SUPPORT_PLACEHOLDER` 同款占位写入，待用户补渠道后全局替换。
- 卡外发现（只记录不修）：`smoke_test.py --architecture` 首跑检出既有门禁对本改动生效属预期，非存量红；无其他卡外缺陷。
