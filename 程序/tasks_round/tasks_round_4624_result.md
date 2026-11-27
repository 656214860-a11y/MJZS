# R4624 结果：C09 按测试类拆分 test_pet_ui.py 为 6 个域文件＋共享夹具模块
<!-- round-evidence: {"commit_base": "704373351", "credential_hits": 0, "evidence_sha256": "23b5decbd5d1246e", "exit": 0, "failed": 0, "passed": 127, "round": 4624, "tests": "run_selftests.py -k test_selftests test_skip_hygiene test_static_hygiene test_structure test_line_endings"} -->

## 类型与三问

- 轮次类型：结构治理轮（任务书 C09：将 7,800 行 / 645 条用例的 `tests/test_pet_ui.py` 按测试类拆分为多个文件，用例总数、测试逻辑与断言 100% 原样保留）。
- 测试与三基线：
  - 拆分前基线：`unittest` 发现 `test_pet_ui` 共 89 个测试类 + 10 个辅助类 + 1 个辅助函数，合计 645 条用例。
  - AST 逐字等价核对：100 个顶层类/函数在拆分后 7 个文件中一一对应，0 缺失、0 新增、0 AST 差异。
  - `run_selftests.py -k pet_ui`：退出码 0，命中 6 个文件 / 50 路工作单元，**645 条用例全通过**（73.8 秒含 30 秒等锁；0 红、0 跳过），前后用例数严格一致。
  - `smoke_test.py`：退出码 0（9/9 通过）。
  - `smoke_test.py --architecture`：退出码 0（**714/714 通过**，含 `test_skip_hygiene`、`test_static_hygiene`、`test_structure`、`test_module_size_ratchet`、`test_agents_md`、`test_round_baselines` 等全部架构门禁）。
  - `governance/check_structure.py --check --candidate ...`：退出码 0，新增违规 0 条（6 个测试文件名均对应既有 `ui/pet_ui*.py` 源码模块，自动满足 `STR006` 归属契约）。
  - 定向单测 `test_skip_hygiene`、`test_static_hygiene`、`test_structure`、`test_selftests`、`test_line_endings`：退出码 0（105/105 通过）。
  - 外部调用方兼容性：`tests/test_pet_ui.py` 继续导出 `PetTestCase`、`FakeDesktop`、`make_project`、`SequenceRand`，`test_pet_agent_error_wiring`、`test_pet_login_quiet`、`test_pet_popup_policy`、`test_sanhu_pointer_avatar_menu`、`test_ui_batch9_pet_accessibility`、`test_skills` 无需改动即可正常导入（其中前 3 个非延迟模块已实跑 23/23 通过）。
- 欠账变化：无新增欠账（`project_status.md` 按主干归属规则保持未改，由合并轮推进）。

## 拆分方案

| 文件 | 职责与对应模块 | 顶层定义 | 行数 | 用例数 |
| --- | --- | --- | --- | --- |
| `tests/pet_ui_test_support.py` | 共享夹具与替身（`make_project`、`_Event`、`_Point`、`_Wheel`、`SequenceRand`、`_Registry`、`FakeDesktop`、`PetTestCase`、`FakeWinreg`、`_Handle`） | 10 | 230 | 0 |
| `tests/test_pet_ui.py` | 核心生命周期、几何、接缝与桌面集成（对应 `ui/pet_ui.py`，并继续导出 `PetTestCase`/`FakeDesktop` 等供外部测试复用） | 11 | 1,196 | 81 |
| `tests/test_pet_ui_view.py` | 外观、姿态、猫爪、气泡排版与落点几何（对应 `ui/pet_ui_view.py`） | 21 | 1,227 | 102 |
| `tests/test_pet_ui_popup.py` | 云朵对话框、弹窗、置顶/前景与尺寸/关闭（对应 `ui/pet_ui_popup.py`） | 13 | 1,591 | 125 |
| `tests/test_pet_ui_voice.py` | 播报、通知、免打扰、停滞与失败语音提醒（对应 `ui/pet_ui_voice.py`） | 17 | 1,206 | 119 |
| `tests/test_pet_ui_stages.py` | 阶段推进、一键执行、批量派发、对话落地与自动启动（对应 `ui/pet_ui_stages.py`） | 16 | 1,325 | 123 |
| `tests/test_pet_ui_settings.py` | 模型池、默认档位、开机自启、菜单反馈、日报与项目记忆（对应 `ui/pet_ui_settings.py`） | 12 | 1,217 | 95 |
| 合计 | — | 100 | 7,992 | 645 |

## 清单同步

- `selftest_env.py`：`GUI_E2E_MODULES` 增补 5 个新拆分模块（`test_pet_ui_view`、`test_pet_ui_popup`、`test_pet_ui_voice`、`test_pet_ui_stages`、`test_pet_ui_settings`），确保 `--layer gui-e2e` 与 `--safe` 调度继续完整纳入并优先并行派发。
- `维护记录/skip台账.json`：仅将 `PetTestCase.setUp` 的文件路径由 `tests/test_pet_ui.py` 同步更新为 `tests/pet_ui_test_support.py`（其余 8 条接缝类 skip 仍保留在 `tests/test_pet_ui.py`）；总登记数与内容不变，`test_skip_hygiene` 双向核验通过。
