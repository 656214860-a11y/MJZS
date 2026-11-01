# R636 验证/基线轮（执行 R630 K-1.1）结果

## 验证档位声明（验证前）

本轮改动涉及 **1 个测试模块**（`tests/test_workflow.py`），不改生产代码、启动路径、用户数据格式、L0 契约或删除路径；按分级规则执行 **默认冒烟 + `--affected workflow`**，跳过 `--architecture` 和全量安全自检，理由是这是单一既有工作流测试模块的回归补齐。

## 轮末三问

- 本轮是功能轮还是整理轮？**验证/基线轮**：只补 R630 K-1.1 指定的自动化回归，不改变产品行为。
- 测试跑了吗？三个基线过了吗？已按声明运行默认冒烟及 `--affected workflow`，均通过；`--architecture` 和全量安全自检为预先声明跳过，并非本轮适用档位。
- `project_status.md` 的欠账少了吗？K-1.1 的回归缺口已收口；其余 R630 K 项及 R630 的其他候选未处理。

## 范围

来源：`tasks_round/tasks_round_630_result.md` 的 K-1.1。目标是覆盖 `stage_config.get`、`model_pool.pool`、`find_program` 的预期/非预期异常，验证“未安装”仍回退、意外异常不会静默改引擎，以及读取不写 `skill_config.json`。

## 改动文件清单与断言

- `tests/test_workflow.py`：仅新增/扩展 `DesktopModelPoolTests` 的 4 个边界断言；没有修改生产模块。
  - `stage_config.get()` 抛出非预期 `RuntimeError` 时，`workflow_settings.current()` 原样抛出，且 `skill_config.json` 字节不变。
  - `model_pool.pool()` 抛出非预期 `RuntimeError` 时，原样抛出，且配置字节不变。
  - `find_program()` 抛出预期的 `ValueError('not installed')` 时，GPT API 仍回退到 `qwen`/OpenAI API，且配置字节不变。
  - `find_program()` 抛出非预期 `RuntimeError` 时，原样抛出而非静默改走 API，且配置字节不变。

测试以 `tempfile.TemporaryDirectory()` 创建临时项目；所有 `skill_config.json` 仅存在于临时目录，退出上下文后自动删除。

## 验证

已执行、且只执行预先声明的档位：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected workflow
共 93 条用例，8.3 秒；0 个文件有红
ALL TESTS PASSED
✅ 门禁 run_selftests.py（定向：workflow）：12 秒 → 0 个文件有红
通过：9 项
失败：0 项
```

未执行 `--architecture`：单一测试模块的测试迁移，不涉及 2 个以上模块、路径/导入边界或异常实现变更。未执行全量安全自检：不涉及启动路径、用户数据格式、L0 契约、删除路径或 4 个以上模块。

## 用户数据未改动确认

- 未访问、未创建、未修改 `D:\漫剧下载\` 下任何项目文件。
- 未修改任何真实项目的 `skill_config.json`、工作流调用设置或密钥。
- 受影响门禁按自身设计刷新了开发维护台账 `维护记录\自检增量.json`；这不是用户项目数据，也不属于产品配置。

## J｜后续

- 本轮只覆盖 R630 K-1.1；其它工作流异常边界或 R630 K 的 3.1、3.2、4.1/4.2、6.1 均未处理。

## 自审

- 只执行 R630 K-1.1；仅改 `tests/test_workflow.py`，新增 R636 结果与台账同步。
- 未改生产代码、产品配置、用户项目数据，也未执行声明外验证档位。
