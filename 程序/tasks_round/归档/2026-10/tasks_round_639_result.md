# R639 修复结果复核轮（执行 R630 候选 1.1）结果

## 验证档位声明（验证前）

本轮目标涉及 **1 个模块**（`workflow_settings.py`），当前源码与 R636 回归已满足候选 1.1 的修复契约，故不重复修改生产或测试资产；按分级规则执行 **默认冒烟 + `--affected workflow`**，跳过 `--architecture` 和全量安全自检，理由是仅复核单一工作流模块的异常边界，未触及路径、导入关系、启动、用户数据格式、L0 或删除路径。

## 轮末三问

- 本轮是功能轮还是整理轮？**修复结果复核轮**：只验证 R630 候选 1.1 已具备的修复行为，不引入新功能。
- 测试跑了吗？三个基线过了吗？已运行声明内的默认冒烟与 workflow 定向门禁，均通过；`--architecture` 与全量安全自检为预先声明跳过，故不把它们冒充为本轮基线结果。
- `project_status.md` 的欠账少了吗？候选 1.1 的实现与回归已确认闭环；R630 的其它候选不受影响。

## 范围与当前事实

R630 候选 1.1 指向 `workflow_settings.current()` 曾可能静默吞掉配置、模型池和本机程序探测的异常。本轮复核当前源码：`current()` 直接调用 `stage_config.get()`、`model_pool.pool()` 和 `_local_engine_for_selected_model()`；其中 `_local_engine_for_selected_model()` 只把预期的 `KeyError`、`ValueError` 视为可回退，本机探测的其它异常会继续上抛。`current()` 本体没有包住这些调用的 `except Exception: pass`。

R636 已在 `tests/test_workflow.py` 的 `DesktopModelPoolTests` 留下四条对应回归：配置读取异常、模型池异常、本机探测的预期未安装回退、以及非预期探测异常原样暴露；均断言临时项目的 `skill_config.json` 字节不变。本轮不重复增加同义测试，也不修改产品代码。

## 修改文件清单

- `tasks_round/tasks_round_639_result.md`：本结果与验证记录。
- `project_status.md`：轮次台账同步（验证后写入）。

生产 `.py`、测试、产品配置、用户项目数据均不修改。

## 验证

已执行、且只执行验证档位声明中的命令：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected workflow
跑 2 个匹配测试文件 / 14 路工作单元（串行）
ALL TESTS PASSED
✅ 门禁 run_selftests.py（定向：workflow）：9 秒 → 0 个文件有红
通过：9 项
失败：0 项
```

未执行 `--architecture`：未改 2 个以上模块，也不触及异常实现、路径或导入关系。未执行全量安全自检：未触及启动、用户数据格式、L0、删除路径，且未改 4 个以上模块。没有在已声明跳过后补跑其它档位。

## 用户数据未改动确认

- 未访问、未创建、未修改 `D:\漫剧下载\` 下任何项目文件。
- 未修改任何真实项目的 `skill_config.json`、工作流调用设置或密钥。

## J｜后续

- 本轮没有发现候选 1.1 之外、且有证据需要同轮修复的异常吞没问题；`workflow_settings.py` 其它异常处理不在本轮范围。

## 自审

- 只处理 R630 候选 1.1 的修复结果复核；未顺手改同类代码。
- 声明档位内项目均通过；本轮未修改任何生产 `.py`、测试、产品配置或用户项目数据。
