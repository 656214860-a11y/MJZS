# R1429 结果：项目用量总览（路线图 C，只读汇总，不新增写入路径）

- 轮次类型：§3.3 功能轮（小）。范围：新增 `usage_overview.py`（L2，只读）、`pet_settings_ui.py`（「设置 → 预算」加「用量总览」按钮）、`tests/test_usage_overview.py`、`tests/test_pet_settings.py` 1 项、`tests/architecture/_layers.py`、`维护记录/架构统一基数.json`（登记豁免项，计数 40→41）、路线图。工作位置：独立工作树分支 `codex/r1429-usage`（主目录另一任务有未提交改动）。

## 核查结论（与原路线图不同）

原以为"账本只在内存"。核查后：`pet_llm.RequestLedger` 自带 `save/load`（`工作流任务/宠物/请求台账.json`），但没有任何生产调用方写它；而**每次模型调用已经落盘一条脱敏事件**（`model_diagnostics/*.json`：模型、阶段、成败、token 用量，不含正文），剧本、四角色、三虎调用都写。所以用量数据其实已持久，缺的是汇总视图。本轮因此不在调用路径上新增写入，避免重复记账与改动调用流程。

## 内容

- `usage_overview.summarize(project, budget=None)`：读取 `项目/model_diagnostics` 与 `项目/logs/**/model_diagnostics` 的事件，汇总合计、按模型、按阶段、按天；输入／输出／缓存命中 token 分列；没有用量字段的调用记为「未上报用量」，不当 0；损坏文件跳过并计数；请求台账有内容时另列各类（秒数、生图、次数）各自的已结算／预留／未知，不折算金额。
- 「设置 → 预算 → 用量总览」：当前项目汇总弹窗，附预算已用／额度；未打开项目时提示。

## 仍未覆盖

视频秒数、生图、配音的**逐笔**用量：目前只有预算计数器（每项目图片／视频张数）和未被使用的 `RequestLedger`。要做逐笔，需要在视频提交／下载、生图、TTS 的成功点补写 `RequestLedger`（涉及 `engine`／`cloud_video_service`／`tts_api` 等调用路径），属于单独一轮，未做。

## 测试

- 新增 2 项＋设置页 1 项。Linux 副本（Python 3.12.13，非随附解释器）：`test_usage_overview`＋`test_pet_settings`＋`test_environment_check` 共 61 项通过；架构目录 341 项通过（过程中发现局部变量名 `requests` 被覆盖率审计 26 误判为 `requests.get`，已改名）。
- 未运行：随附解释器冒烟、全量（1429−1420=9≥5，欠账待 Windows 补跑）、真实项目上的实机汇总（本机无含事件的项目样本）。

## 自审

只读；不改调用路径；输出不含正文或密钥（测试断言事件里的正文不外泄）。
