# R650｜修复轮：初步分镜取消采用的未定义名称

## 开工三问与验证档位

1. 本轮是修复轮：只处理全量安全自检的 `test_static_names` 报告项——`storyboard_files.py` 的 `remove_selected()` 使用了未定义名称 `remove`。
2. 根因是模块已将 `storyboard_selection.remove` 导入别名为 `_remove`，但页面回调仍调用旧名称；该错误会在用户点击“手动取消采用”时触发 `NameError`。
3. 修复目标为 `storyboard_files.py:672-673` 的单一回调调用点；不改分镜选择服务、回收、其它页面或用户数据。

本轮改动涉及 1 个模块，按分级规则执行默认冒烟 + `--affected storyboard_files`，跳过架构门禁与全量，理由：单一名称绑定修复，未触及异常边界、路径、导入关系、启动路径、用户数据格式、L0 契约或删除路径。

## 验证结果

```text
python -B -m unittest tests.test_static_names
Ran 8 tests in 1.986s
OK

python -B smoke_test.py
通过：8 项
失败：0 项

python -B smoke_test.py --affected storyboard_files
定向筛选 storyboard_final_controller final_viewer file_cache；3 文件／5 单元，退出码 0
```

未修改用户项目数据。架构门禁与全量已按声明跳过。

## J｜后续

- R649 全量日志现已完成：3355 条、20 个失败文件；本轮解决其中 `test_static_names` 的 1 条，需在后续全量复跑确认总数。
- 其它失败项另立轮次。

## 自审

只处理了 `remove_selected()` 的未定义名称。

**[TASK_COMPLETE]**
