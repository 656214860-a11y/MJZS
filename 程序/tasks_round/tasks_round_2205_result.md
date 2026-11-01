# R2205 结果：初步分镜选 API 模型时直连调用（功能轮）

## 做了什么
- 文档先行：S03 文档新增 REQ-S03-53、DES-S03-52，修订 DES-S03-18，模块表与测试锚定表补行。
- 新增 `storyboard_direct_api.py`（L3）：一集一次请求，发完整结构剧本（不截 4000 字）、S03 SKILL、规则；修订时带原 JSON。`ensure_request_context` 超限抛错不静默截断；chat 线路流式，`max_tokens=32768`，超时 600 秒，截断（finish_reason）报错。
- 校验用 `validate_episode`；不合格带错误清单重试一次，仍不合格不落盘并报原因；合格经 `stage_publication.publish_stage_bundle` 发布（JSON + 分镜文档/*.md，修订时备份旧稿并回收超过 2 份的历史）。
- 新增 `desktop_storyboard_direct.py`（L4）：后台线程、每集完成播报、全部失败且三虎自动时发 `stage.failed`。
- 分流点唯一：`_FlowAgentLaunch.build()`（手动按钮与三虎 _start_storyboard 都经此），仅 `stage=='storyboard'`、engine=qwen、所选模型在模型池且非 Desktop 时直连；其他阶段与 Qwen 代码不动。
- 强制停止：`workflow_process_registry` 新增 register/forget/cancel_project_requests，`workflow_engines.terminate` 顺带取消直连请求；停止后不落盘。
- 重构：`workflow_tasks` 抽出 `storyboard_batch_plan`、`storyboard_direct_rules`（原函数行为不变）；`WritingRequestAdapter` 加 `stage` 参数（默认 script）。
- 门禁登记：_layers.py、architecture.md、架构统一基数.json（json.loads 豁免）、覆盖率基线.json（重测，8 组目标）、runbook §11 数字同步（333/283）。

## §7.3 三问
- 唯一入口：分流只在 `_FlowAgentLaunch.build()`；发布只走 `publish_stage_bundle`；停止只走 `workflow_engines.terminate`。
- 无新增第二入口，Qwen 路径未删。
- 不碰数据边界；未调用真实 API（测试全用假适配器）。

## 红灯输出（实现前）
```
IMPORT OK: all modules imported
定向：忽略增量台账，执行 1 个匹配测试文件
跑 1 个测试文件 / 1 路工作单元（8 路并行）
  test_storyboard_direct_api     6 条     0.3 秒  ✗ 6

共 6 条用例，0.9 秒；1 个文件有红
最慢 1 路工作单元：
  test_storyboard_direct_api    0.3 秒 / 6 条
实际跳过 0 条用例：本机没有任何登记位被跳过

### test_storyboard_direct_api（6 条红）

===== test_req_s03_53_direct_model_only_for_pool_models (test_storyboard_direct_api.DirectApiTests.test_req_s03_53_direct_model_only_for_pool_models) =====
Traceback (most recent call last):
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 64, in test_req_s03_53_direct_model_only_for_pool_models
    import storyboard_direct_api as api
ModuleNotFoundError: No module named 'storyboard_direct_api'

===== test_req_s03_53_invalid_json_retries_once_then_writes_nothing (test_storyboard_direct_api.DirectApiTests.test_req_s03_53_invalid_json_retries_once_then_writes_nothing) =====
Traceback (most recent call last):
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 95, in test_req_s03_53_invalid_json_retries_once_then_writes_nothing
    results = self.run_batch(adapter)
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 55, in run_batch
    import storyboard_direct_api as api
ModuleNotFoundError: No module named 'storyboard_direct_api'

===== test_req_s03_53_manual_and_auto_share_one_executor (test_storyboard_direct_api.DirectApiTests.test_req_s03_53_manual_and_auto_share_one_executor) =====
Traceback (most recent call last):
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 116, in test_req_s03_53_manual_and_auto_share_one_executor
    patch('storyboard_direct_api.direct_model', return_value=('deepseek-v4-pro', {'name': 'x'})), \
    ~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\漫剧制作助手\运行环境\Python\Lib\unittest\mock.py", line 1487, in __enter__
    self.target = self.getter()
                  ~~~~~~~~~~~^^
  File "D:\漫剧制作助手\运行环境\Python\Lib\pkgutil.py", line 458, in resolve_name
    mod = importlib.import_module(modname)
  File "D:\漫剧制作助手\运行环境\Python\Lib\importlib\__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1406, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1379, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1343, in _find_and_load_unlocked
ModuleNotFoundError: No module named 'storyboard_direct_api'

===== test_req_s03_53_retry_can_recover (test_storyboard_direct_api.DirectApiTests.test_req_s03_53_retry_can_recover) =====
Traceback (most recent call last):
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 106, in test_req_s03_53_retry_can_recover
    self.assertTrue(self.run_batch(adapter)[0]['ok'])
                    ~~~~~~~~~~~~~~^^^^^^^^^
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 55, in run_batch
    import storyboard_direct_api as api
ModuleNotFoundError: No module named 'storyboard_direct_api'

===== test_req_s03_53_stop_interrupts_request_and_writes_nothing (test_storyboard_direct_api.DirectApiTests.test_req_s03_53_stop_interrupts_request_and_writes_nothing) =====
Traceback (most recent call last):
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 133, in test_req_s03_53_stop_interrupts_request_and_writes_nothing
    import storyboard_direct_api as api
ModuleNotFoundError: No module named 'storyboard_direct_api'

===== test_req_s03_53_valid_json_is_published_without_qwen (test_storyboard_direct_api.DirectApiTests.test_req_s03_53_valid_json_is_published_without_qwen) =====
Traceback (most recent call last):
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 77, in test_req_s03_53_valid_json_is_published_without_qwen
    results = self.run_batch(adapter)
  File "D:\漫剧制作助手\.claude\worktrees\quizzical-gagarin-b1854b\程序\tests\test_storyboard_direct_api.py", line 55, in run_batch
    import storyboard_direct_api as api
ModuleNotFoundError: No module named 'storyboard_direct_api'

[SUSPECT_CONCURRENCY] 红项发生时有其他 PID 持有 GUI 令牌；建议串行复跑。
```

## 测试
- test_storyboard_direct_api（6 例）+ flow_agent 相关：绿。
- 断言未动：既有测试未改。
- `smoke_test.py --architecture`：仅 3 项红，均与本轮无关——基准历史.json 缺失、screenplay-gate-engine.md 缺失（工作树缺少未入库文件）；覆盖率口径一项已通过 runbook 同步修复。
- `smoke_test.py --affected`：test_master_skill 红为工作树缺 skills 子仓内容（补齐后绿）；test_ui_edges 一例并发令牌下偶红，串行复跑绿。
- 未做：真实 API 联调；非 chat 线路无法在请求中途中断（停止后丢弃结果不落盘）；分镜 JSON 未加 schema_version。
