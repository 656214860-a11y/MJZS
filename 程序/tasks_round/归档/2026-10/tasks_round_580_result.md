# R580｜修复轮｜剧本准备页底部三列表恢复显示

## 本轮回答

1. 本轮是修复轮，不是整理轮。
2. 测试已运行：三列表精确 Tk 回归 1/1、默认冒烟 8/8、架构门禁 101/101 通过；完整 `--affected ui_edges` 另有 1 项失败，未扩大范围处理。
3. `project_status.md` 的结构债务未减少；本轮修复的是用户可见回归，既有 R568/P3-2、P0-3 阻塞项不变。

## 根因与复现

- 以含“项目设定／项目大纲／项目剧本”各一份文件的项目打开剧本准备页，`fill_script_list()` 首批插入后进入 `finish()` 的排序回调。
- `desktop.py:3651` 原调用 `Treeview.move(row.item_id, 'end')`，漏传 Tk 所需的 `parent` 参数；实际 Tk 回调报 `TypeError: Treeview.move() missing 1 required positional argument: 'index'`。
- 异常发生在 `set_script_box_visible(bool(live))` 之前，而加载开始时又先隐藏了 `script_box`，所以三列表及其列头持续不可见。问题并非 token 值或用户项目文件。

## 改动

| 文件 | 改动 |
| --- | --- |
| `desktop.py` | 修正 `Treeview.move(item, '', 'end')` 的 Tk 调用；扫描期间保留三列表列头，仅确认无文件时隐藏空表。 |
| `tests/test_ui_edges.py` | 为已有文件的剧本准备页补充三列表容器必须映射的回归断言。 |
| `project_status.md` | 登记 R580 结果并推进当前轮次。 |

## 验证

| 命令 | 结果 |
| --- | --- |
| `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_ui_edges.UiEdgeTests.test_the_writing_page_wraps_the_box_with_buttons` | 1/1 通过；不再输出 Tk 回调异常。 |
| `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py` | 8/8 通过。 |
| `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture` | 101/101 通过。 |
| `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --affected ui_edges` | 该扩大 UI 边界门禁发现 1 项失败；本轮精确回归通过，失败项未在未授权范围内改动，需另行诊断。 |

## 自审

通过。修改仅覆盖三列表渐进加载与其可见性回归；未触及 token、对话、项目文件读写或其他页面。已有文件、无文件收起空表的原有语义均保留。
