# R631 修复轮结果：阶段配置异常不再被静默改为默认引擎

- 本轮是功能轮还是整理轮？**修复轮**。执行 R630 J 节第 1 项（1.1/5.1，P1），仅处理 `workflow_settings.current()` 吞掉配置/模型池异常的问题。
- 测试跑了吗？三个基线过了吗？**已跑。**目标回归修复后 85/85 通过；默认冒烟 8/8 通过；架构门禁 102/102 通过。全量安全自检执行完毕但有 18 个既有红文件，故全量基线未通过，详见“验证”。
- `project_status.md` 的欠账少了吗？**没有。**本轮只消除一个无提示失败路径；为满足轮次连续门禁，将台账从 630 待执行校正为 631 待执行。

## 来源与根因

来源为 R630 的 J-1：`tasks_round/tasks_round_630_result.md:15-35,119-121,185`。

`workflow_settings.py:356-377` 的 `current()` 把 `stage_config.get()`、`model_pool.pool()` 和本机桌面引擎选择包在 `except Exception: pass` 内。配置读取发生意外错误时，函数继续使用先前的默认 `engine`，用户既看不到错误，也不知道实际引擎已变成默认值。

正常的“本机桌面程序未安装”不依赖这个宽泛捕获：`_local_engine_for_selected_model()` 在 `workflow_settings.py:318-331` 已针对 `KeyError`、`ValueError` 返回空路由并走 API 回退。因此删除外层吞错不会改变正常回退。

## 修改

| 文件 | 改动 |
|---|---|
| `workflow_settings.py` | 移除 `current()` 的宽泛 `try/except Exception: pass`，令配置/模型池的意外异常传播到既有的受控错误边界。|
| `tests/test_workflow.py` | 新增 `test_unexpected_stage_config_error_is_not_silently_routed_to_default_engine`（约 692-701 行）：mock `stage_config.get()` 抛 `RuntimeError`，断言错误原样可见。|
| `project_status.md` | 仅将“当前轮次”从 630 待执行校正为 631 待执行，修复 R630 结果已经存在而台账未递增造成的架构门禁失败。|

未修改 UI、模型选择策略、用户项目数据、`skill_config.json` 或配置格式。

## 回归证据

修复前，仅注入该新测试而未改生产代码：

```text
FAIL: test_unexpected_stage_config_error_is_not_silently_routed_to_default_engine
AssertionError: RuntimeError not raised
Ran 1 test in 0.157s
FAILED (failures=1)
```

修复后，该测试断言：`stage_config.get()` 发生 `RuntimeError('stage config unavailable')` 时，`workflow_settings.current(project, 'writing')` 同样抛出该错误；它不再静默返回默认引擎。目标文件全量：85 条通过。

## 验证

| 命令 | 结果 |
|---|---|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_workflow` | 85 条，全部通过。|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py` | 默认 8 项，0 失败。|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected workflow` | 2 个匹配文件、91 条，0 失败。|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --architecture` | 102 条，全部通过。|
| `D:\漫剧制作助手\运行环境\Python\python.exe -B run_selftests.py --all --safe` | 3333 条、1091.4 秒；18 个文件有红，退出码 1。|

曾尝试 `smoke_test.py --affected workflow_settings`，该名称没有映射测试文件（0 个命中），定向门禁因此返回非零；没有为单一模块名补映射，避免越出本轮范围。改用现有的 `workflow` 映射后通过。

全量安全自检的红项不涉及本轮改动，且在全量日志中 `test_workflow#1` 至 `#13` 均通过；示例失败为：

- `test_copy_rules.SecondPersonTests.test_interface_copy_speaks_to_you_with_the_polite_pronoun`：技能目录中既有“你”字文案被全局文案规则检出。
- `test_static_names.StaticNameTests.test_every_module_defines_the_names_it_uses`：`storyboard_files.py：remove_selected 里用了没定义的 remove`。
- `test_token_saver.AnthropicCacheTests.test_the_connection_test_uses_the_anthropic_shape`：当前 Windows 环境不能读取/保存模型 API Key。

按本轮失败判定：**[TASK_FAILED]**。原因是要求的全量安全自检整体为红；没有把这些与 J-1 无关的模块顺手改入本轮。

## J 后续

R630 J 节的下一项为 3.1/8.1（剪辑扫描性能基线与回归覆盖）。应另立专项，先测量扫描调用链，不能与本轮的异常可见性修复混做。

## 自审

- 只改了 R630 J-1 的根因模块与一条对应回归；没有变更桌面引擎优先策略。
- 轮次台账校正是架构门禁要求的行政同步，不属于功能扩展。
- 未改用户项目数据、配置、密钥或 UI。
- 全量安全自检为红已如实登记，未声称本轮完全完成。
