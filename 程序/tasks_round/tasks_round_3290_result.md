# R3290：历史语音设置超屏与继承 Tk 夹具分类阻断修复

- 轮次类型：§3.2 修复轮；只处理残留 SKILL 治理最终验收暴露的语音设置长表单及 Tk 测试分类，不扩散 UI。
- 测试与三个基线：先红后绿；默认冒烟8核心＋probe＝日志9/9，最终affected78/78，最终全部架构532/532、253.416秒、exit0。冻结源码完整安全全量8574条、688.7秒、实际skip5、唯一范围外表格UI失败，exit1；显式脏树诊断NO_RECEIPT，不是正式绿凭据。
- 欠账：本轮语音超屏与Tk分类两项阻断已修复；完整全量仍因历史表格同页重建滚动偏移失败，已交lead下一独立轮，不弱化断言。轮4真实删除／用户本人重装仍由用户执行，完整任务书交付与 master 合并由 lead 统筹。

## 授权、起点与范围

直接授权要求本子会话实际领号、改码、测试、独立提交；不合 master、不代用户重装。R3287 已提交 `ee67ca06ded7abc1fe743b3b17310425155cd2dc`，前轮 R3283=`d90358b7`、R3279=`9b620f1c`。

工作树 `dsh-6187d0c7-f35d`，分支 `codex/skill-residue-governance`，起点 HEAD=`ee67ca06`，开工 `git status --short` 空。已读 AGENTS、runbook §12/13/16、任务书全局决策及 R3279/R3283/R3287 结果。加载 diagnosing-bugs、minimal-diff-fix、ui-ux-pro-max、scoped-tests；采用项目现有 UI token 与 ScrollForm，不设计新框架。`dev.py claim` 实领 R3290；scope 与另外53条活跃分支无重叠，无对应队列任务不冒领。

## 先红与根因

1. `run_selftests.py -k model_manager_actions --gui --gui-wait 180` 经统一隐藏桌面运行器：9条、1红、12.2秒；`SpeechSettingsTests.test_fields_show_settings_and_missing_key` 原断言 `1061 not greater than or equal to 1227 : 不写死高度，表单不被裁掉`。原始 `logs/R3290_red_speech.log`。根因是裸 Card 包含完整长表单，屏幕高1080但请求高1227，无滚动入口。
2. 新行为测试 `test_inherited_tk_fixture_runs_in_gui_layer_and_pool` 先红：`assertTrue(gui_test_module('test_model_manager_actions'))` 得 False。`run_selftests.py -k test_selftests --serial` 66条、1红、6.6秒；`logs/R3290_red_classification.log`。根因是测试通过 Batch7Case 继承真 Tk fixture，直接 import 分类表漏识别，服务工作池会在可见桌面执行。

两个原始红日志附带并发 GUI 令牌提示，失败分别为确定性几何和纯分类布尔断言，不是并发竞态。开工已查全量 PID，别树的全量仍在运行；未杀进程、未抢锁。

## 最小修复与契约

先同步 REQ-S01-71 / DES-S01-71：长表单完整可达、恢复默认／保存／取消固定可见，键盘焦点自动滚入视口。复用 responsive_ui.ScrollForm，保留全部原字段与读写／下载逻辑；内容实测尺寸传给 canvas，窗口按屏幕余量计算。聚焦字段通过原生 FocusIn 自动滚入视口，不更改字段键盘绑定。原“窗口高≥全部内容高”改为对应滚动契约的真实 Tk 视口／scrollregion／滚动条／末尾字段滚达／Tab 焦点滚达／底部按钮可见几何断言；原宽度、保存／重置／校验断言保留，补取消不保存与下载开始／取消／完成回归。

selftest_discovery 使用显式 INHERITED_TK_TEST_MODULES 登记唯一漏检模块；不塞无用 tkinter import、不全依赖递归扫描。行为测试验证它进入 gui-short 与受控 Tk 工作池、排除 service 层。

首次修复回归100条只有新增取消测试1红：原宽度断言在插入新测试时被错误放到销毁窗之后，TclError；已将原断言移回原测试，未改产品逻辑。原始 `logs/R3290_targeted.log`。

## 验证与恢复检查点

每次 PowerShell 设置 PYTHONUTF8=1，解释器 `D:\漫剧制作助手\运行环境\Python\python.exe -B`；FFmpeg PATH前置随附目录，含Tk由统一隐藏桌面入口运行。

- 首次最终定向 job `pwsh-8f826db7d0404bad` 已结束exit2：89条服务测试通过，模型管理Tk未运行／不计通过，因为他树 PID49580 持有GUI令牌等满180秒。日志 `logs/R3290_targeted_final.log`。
- 首次冻结定向 job `pwsh-861bd37761974044` 已结束exit1：101条仅新增下载完成断言文案不符（实际为“离线语音包安装完成”）；已按既有文案修正新增断言，产品下载逻辑未改。`logs/R3290_targeted_frozen.log` 保留。修正后 job `pwsh-93627a55a9c74a85`：101/101、5.8秒、0skip、exit0；`logs/R3290_targeted_verified.log`。GUI等待采用既有1800秒上限，未绕过锁。
- 默认smoke job `pwsh-52919a194f7d47c7` 已采集exit0：8核心＋1probe，日志9通过0失败，`logs/R3290_smoke.log`。
- 首遍全架构 job `pwsh-c517fa0988e64a4d` 已采集exit1：532条仅1红，`open_speech_settings` 184行超过既有150行上限，`logs/R3290_architecture.log`。新增骨架／焦点／尺寸适配已提取同模块两个私有辅助函数，不抬基线、不改门禁；长度失败项复验2/2、2.7秒、exit0，`logs/R3290_function_size_verified.log`。
- 提取后最终affected job `pwsh-fb2045e8e3394d5f` 已采集exit0：3个全部消费者（model_manager_actions/selftests/selftests_gui_token），78/78、0skip，冒烟8核心＋probe＋affected门禁＝日志10通过0失败，`logs/R3290_affected_final.log`。首次提取前affected亦exit0，`logs/R3290_affected.log`。
- 最终全架构 job `pwsh-67449568ccbc496c` 已采集exit0：532/532、253.416秒，较前轮532不变、失败集合空，`logs/R3290_architecture_final.log`。
- 最终冻结SHA256：`ui/speech_settings_ui.py=858597cd5582e5c99d572fa6f3335d84869d50cba7e4c02da594af031ef5094d`、`selftest_discovery.py=1069ff5348b6883059908179198172c0e2358dce1227fc87a5b2f2321ec9f245`、`tests/test_model_manager_actions.py=7ed122404e1b4d2fad38b1d9c5f0985b183067e2389012fb7df04f15976985a1`、`tests/test_selftests.py=d745727f68da6e5439be71d8e72a05c22b454a539f00a2b0ac37d266d2b3e621`。
- 真实Tk几何probe经统一隐藏桌面、共享GUI令牌执行，job `pwsh-c6b649f3ce01469b` exit0，`logs/R3290_geometry.json`：1920×1080屏，窗口991×1016，视口950×943，表单950×1154，scrollregion=`0 0 950 1154`。600高窗口视口527高，滚到底yview=(0.5433,1.0)，末尾替换框y=456..550完全在视口43..570内，三按钮y=582..619且窗底631，未裁切；全部输入项焦点／Tab／滚轮行为由真Tk测试断言。临时probe脚本只放 `<git common-dir>/round-local-evidence/R3290`，不入生产扫描。
- 全量启动前进程与锁两次复核：别树全量已结束，共享full-safe锁不存在；启动脚本再次检查，存在任何全量PID／锁则直接中止，不抢锁。
- 完整 `run_selftests.py --all --safe --allow-dirty-diagnostic` 于最终源码／测试冻结且完整架构通过后启动，唯一job `pwsh-9d24aa35090143e4`、锁PID52496已完成采集exit1。728文件／984工作单元，8574条用例、688.7秒，实际skip5，无GUI_DEFERRED，唯一红 `test_ui_edges_tables.UiEdgeTablesTests.test_same_page_rebuild_keeps_scroll_offset`。UTF8日志 `logs/R3290_full_safe_diagnostic.log`，汇总3128行、skip3140–3145、失败3147–3156。`test_model_manager_actions` 12条13.1秒全绿，分类／词典／离线下载相关均绿。明确NO_RECEIPT，不写绿凭据／分层／增量台账。
- 全量期间没有任何生产源码或测试变更；结束后与冻结SHA256逐项核验一致。Tk stderr出现已有after销毁回调（check、_apply_idea_send_state、start_update_check、start_account_renewal）无新增单元失败，原始日志保留。
- 5个实际skip：test_aigc_lint两项与test_core一项因发行包未含受测bundled skill；test_desktop_tray类setUpClass与最小化循环两项因隐藏桌面无资源管理器任务栏。沿用登记原因，本轮未新增skip。
- 表格唯一红原始堆栈：`tests/test_ui_edges_tables.py:538 self.assertAlmostEqual(d.canvas.canvasy(0), before, delta=2)`；实际210.0、重建前246.0、差36.0。夹具在500–541行：TemporaryDirectory隔离项目、make_adopted_project，分镜24行每行长标题，真实Tk1000×660，show_catalog_page_ready(final)，滚到0.5，再同页重建，应保持像素偏移；换页再归零。本轮两生产文件仅speech_settings_ui表单局部和selftest_discovery测试分类，未改desktop／表格／滚动权威，未改共享ScrollForm；其无关UI由lead新独立轮裁定。
- 可复用最小模块命令（隐藏桌面自包装）：`python -B run_selftests.py -k ui_edges_tables --serial`，附随附解释器／PYTHONUTF8／FFmpeg PATH；本轮未启动该额外定向、不把猜测写成根因。lead已明确下一独立子会话修复，不混入本轮。
- 状态页已从 HEAD 原字节精确还原3278，SHA256=`94c8999da502352abfc65b6d43a4e6d56e873a98ab21ee17a97df5eabfdbfd1e`，`git diff --exit-code -- project_status.md` exit0，不暂存。新增行凭据预扫0命中，`logs/R3290_credentials_precheck.log`。
- 行尾验证16/16、0.9秒、exit0，`logs/R3290_line_endings.log`；已完成的PowerShell UTF16日志逐一原文字转UTF8，运行中日志不改写，后续用Out-File UTF8。
- 本树状态页已临时投影3291供架构 N=M+1；提交前从 HEAD 原字节恢复3278，不暂存。全量脏树仅使用显式 `--allow-dirty-diagnostic`，不写正式绿色收据；最近正式收据仍R3258（只读核验common-dir），正式干净全量由 lead 的最终master候选执行，禁止伪造凭据。

## 提交

lead已确认将本轮独立收为真实失败检查点：使用 `scripts/dev.py commit -m "R3290-FAIL: 修复语音设置滚动与Tk分类 REQ-S01-71 DES-S01-71" --tests ...`，统一入口相关测试必须绿、凭据扫描必须0命中。只暂存生产根因模块、对应测试、S01契约与本轮结果／自动证据。日志、状态页、用户配置不暂存。结果文件在提交前冻结；自身hash由lead接续补记或引用本结果所在提交，避免自引用额外提交。完整全量未绿、任务书未整体完成，不标 TASK_COMPLETE；下一独立轮先复现和修复表格滚动阻断，再冻结跑完整全量，正式干净master凭据由lead统筹。
