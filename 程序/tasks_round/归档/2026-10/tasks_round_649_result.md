# R649｜结构治理轮：首帧管理页面拆分

## 开工三问与验证档位

1. 本轮是结构治理轮：按用户指定顺序处理 `desktop.py` 的「首帧管理」页，唯一入口为 `Desktop.storyboard()`。
2. 该页直接调用/定义的页面上下文函数中，`Desktop.storyboard()` 位于 `desktop.py:5262-5602`，共 341 行；`frame_checks_apply()` 位于 `desktop.py:5603-5612`，共 10 行；`delete_keyframe()` 位于 `desktop.py:5613-5628`，共 16 行；`restore_keyframe()` 位于 `desktop.py:5629-5634`，共 6 行。按行数降序，唯一超过 200 行的是 `Desktop.storyboard()`。
3. 本轮拆分目标为最长函数 `Desktop.storyboard()`，起始行 5262；只迁移多分镜行归属、首帧路径解析和按来源分批选择。控件构造、事件绑定、页面重建、缩略图和状态文案仍属 UI 层，保持在 `desktop.py`；既有 `keyframe_import`、`keyframe_batch` 与 `keyframe_lifecycle_service` 的职责不重复迁移。

本轮改动涉及 6 个模块（`desktop.py` 首帧管理页函数、新建控制器、测试文件及 3 处 L3 边界登记），按分级规则执行默认冒烟 + 全量安全自检，跳过 `--affected` 与架构门禁，理由：新增 L3 控制器并同步架构契约，改动超过 4 个模块，未触及启动路径、用户数据格式、L0 契约或删除路径。

## 改动文件清单

- `keyframe_page_controller.py`：新增无 Tk 的 `KeyframePageController`，只保存多分镜行归属、首帧路径安全校验和按来源的批次选择。
- `desktop.py`：首帧管理页改为消费控制器；控件构造、事件绑定、页面刷新、缩略图和状态文案仍在 `Desktop.storyboard()`。
- `tests/test_keyframe_page_controller.py`：新增三条控制器回归。
- `tests/architecture/_layers.py`、`tests/architecture/test_migrated_ui_boundaries.py`、`architecture.md`：登记 L3 控制器的无 Tk、无项目数据写入边界。

未改动首帧导入／替换／删除／恢复生命周期、项目 JSON、用户媒体、启动路径或其它页面。

## 新增回归

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_keyframe_page_controller
Ran 3 tests in 0.019s
OK
```

回归覆盖多分镜行归属与首帧存在性、路径缺失的受控错误、选中行优先的按分镜批次选择，以及未知高亮行的稳定回退。

## 验证结果

默认冒烟：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项
```

全量安全自检（已按声明运行）：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B run_selftests.py --all --safe
完整原始日志（未取得汇总）：D:\漫剧制作助手\程序\维护记录\r649_safe_all.log
--safe（全量串行）：忽略增量台账，216 个测试文件全跑一遍
跑 216 个测试文件 / 567 路工作单元（串行）
日志在 architecture.test_path_authority 开始后被受限执行环境中止，未产生汇总行。
```

首次日志重定向因受限沙箱拒绝访问而未启动；获授权后重新启动的串行进程同样未能持续到汇总，且未生成重试日志或退出码。未执行 `--affected` 与架构门禁；二者均在验证前按本轮已声明的全量档位跳过，未事后补跑。

因此按任务硬判定：**[TASK_FAILED]**。原因是已声明的全量安全自检未取得汇总；原始日志路径已在上文保留，不能将本轮标记为验收完成。

## 用户数据确认

未以用户项目目录为目标执行写入命令，未修改 `skill_config.json`、项目 JSON、密钥、媒体或用户资产数据。唯一写入目标为维护记录中的自检原始日志。

## J｜后续

- 应在独立验证轮、具备可持续运行全量串行自检的环境中重跑 `run_selftests.py --all --safe`，从而取得 R649 的完整汇总；不得把该验证故障归为首帧功能失败。
- 其它首帧 UI 拆分边界不在本轮处理。

## 自审

- 只处理首帧管理页的一个无 Tk 状态边界；初步分镜页和其它页面未改。
- 没有改首帧生命周期服务、用户数据格式或同类问题。
- 已按声明执行默认冒烟和全量安全自检；未追加被声明跳过的档位。
