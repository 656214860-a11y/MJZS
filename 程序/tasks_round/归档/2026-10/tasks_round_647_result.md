# R647｜验证/基线轮：剪映开始菜单兜底扫描非阻塞回归

## 开工三问与验证档位

1. 本轮是验证/基线轮：执行 `tasks_round/tasks_round_630_result.md` 候选 8.1，只复核“开始菜单兜底扫描不占住 Tk 主线程”的回归。
2. 现有实现已满足候选：`Desktop.launch_editor()` 在 `desktop.py:5979-5992` 仅将 `find_editor_shortcut` 交给 `async_()`；递归 `glob('**/*剪映专业版*.lnk')` 只在后台工作函数 `desktop.py:5969-5978`。
3. 既有专项位于 `tests/test_ui_edges.py:5281-5340`，覆盖点击只入队、快捷方式匹配规则和未找到后的受控错误；本轮不重复添加同义测试。

本轮改动涉及 0 个生产或测试模块，按分级规则执行默认冒烟 + `--affected desktop`，跳过架构门禁与全量，理由：仅复核单一既有 `desktop` 后台调度契约，未触及路径、导入、启动路径、用户数据格式、L0 契约或删除路径。

## 改动文件清单

- 未修改生产代码、测试、配置或用户项目数据；候选 8.1 的实现和回归已在此前轮次落地。
- 新增本结果文件，并将轮次台账接续至 R648。

## 验证结果

专项回归：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_ui_edges.EditorStartMenuScanTests
Ran 3 tests in 0.009s
OK
```

默认冒烟：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项
```

定向门禁：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected desktop
共 7 条用例，2.4 秒；0 个文件有红
ALL TESTS PASSED
通过：9 项
失败：0 项
```

未执行架构门禁和全量安全自检；它们均在验证前按本轮零代码改动、单模块既有调度复核的档位声明跳过。

## 用户数据确认

未以用户项目目录为目标执行写入命令，未修改 `skill_config.json`、项目 JSON、密钥、媒体或用户资产数据。定向门禁尝试刷新开发用增量台账时受环境权限阻止，不影响 7 条用例均通过的结果。

## J｜后续

- 候选 8.1 已有可执行回归，无需重复添加；若未来改变 `launch_editor()` 的排队语义，应在该专项中同步维护。
- 其它开始菜单扫描或外部程序发现路径不是本轮范围，需另立轮次。

## 自审

- 仅复核了 R630 候选 8.1。
- 未改写扫描实现、未引入同类修复，也未碰触其它候选。
- 已按验证前声明执行默认与 `desktop` 定向档位，并未追加被跳过的档位。

**[TASK_COMPLETE]**
