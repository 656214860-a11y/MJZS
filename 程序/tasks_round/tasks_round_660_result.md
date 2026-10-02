# R660｜修复轮：裸 Desktop 的 IdeaChatController 兼容属性边界

本轮改动涉及 1 个模块（`desktop.py`），按分级规则执行默认冒烟 + `--affected hollmwood_ui_queue`，跳过架构门禁与全量，理由：仅修复单模块兼容属性在最小 UI 实例下的访问边界，未触及启动路径、用户数据格式、L0 契约或删除路径。

## 一、开头三问

1. 当前轮次与台账是否一致：一致；当前轮次为 660，最新结果为 R659。
2. 上一轮进行中未完成的任务是什么：R659 全量安全自检失败；其中 `test_hollmwood_ui_queue` 的裸 `Desktop` 控制器访问是本轮唯一处理项。
3. 下一轮该做什么：根据本轮结果推进台账；其他 R659 失败组保留在后续独立轮次处理。

## 二、改动文件清单

- `desktop.py`：为 `_idea_requesting` 兼容属性增加控制器尚未创建时的实例级回退状态；正常 UI 生命周期仍直接委托 `IdeaChatController`。
- `tasks_round/tasks_round_660_result.md`：记录本轮边界、验证及自审。

## 三、验证档位声明与原始输出片段

本轮改动涉及 1 个模块（`desktop.py`），按分级规则执行默认冒烟 + `--affected hollmwood_ui_queue`，跳过架构门禁与全量，理由：仅修复单模块兼容属性在最小 UI 实例下的访问边界，未触及启动路径、用户数据格式、L0 契约或删除路径。

默认冒烟命令：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项
```

定向门禁命令：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected hollmwood_ui_queue
共 2 条用例，0.4 秒；0 个文件有红
ALL TESTS PASSED
通过：9 项
失败：0 项
```

## 四、用户数据确认

未读取、写入、迁移或删除用户数据。

## J、后续

R659 其余失败组（模型凭据优先级、宠物 UI、技能注册表、字幕静态边界、页面入口）未在本轮处理，保留后续独立轮次。

## 自审

只处理 `_idea_requesting` 在裸 `Desktop` 实例中的控制器缺失边界；没有修改其他兼容属性或同类页面逻辑。
