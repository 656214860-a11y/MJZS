# R815 结果：项目登记空壳启动崩溃修复

## 完成项

- `Projects.__init__()` 与 `refresh_registry()` 读取登记后，都会保留字典中的未知字段，并补齐缺失的 `active: None` 与非列表／缺失的 `projects: []`。
- 因而无 `projects.json` 且 `migrate_legacy=False` 的首帧路径不再把空字典交给桌面项目列表；不在 `desktop.py` 吞掉 `KeyError`，未改真实 `projects.json`，未新增 L3/L4 依赖。
- `tests/test_projects.py` 恢复空对象登记的初始化回归，并新增 `refresh_registry()` 遇到空对象时的同类回归。

## 同类问题复核

`projects.py` 内全部 `isinstance(..., dict)` 分支已逐条复核：

- 第 46 行：历史目录候选的 `config.json` 内容；只是传给候选比对，非项目登记，未要求 `active`／`projects`。
- 第 79、111、337 行：应用或项目 `config.json`；读取的是设置，不是项目登记，所需键由各调用方以 `get()` 定义。
- 第 88、96 行（本轮修复后）：唯一直接读取 `projects.json` 的分支；现已保留未知字段并补齐 `active`、`projects`。
- 第 100 行：L3 网关映射；该分支显式逐一验证所需可调用项，不是 JSON 结构信任。
- 第 137 行：资产清单 `assets.json`；后续按资产项迭代，不适用项目登记键。
- 第 175 行：重命名时的通用 JSON 变换前置检查；目标配置的必需键由各自 transform 决定，不能套用项目登记结构。
- 第 190 行：重命名项目内本地登记的单个项目条目；只在条目为字典时更新其 `path`，不是对整个登记容器的信任分支。

结论：没有其他需要补齐 `active`／`projects` 的项目登记 `dict` 信任分支。

## 实测

```text
> 临时空程序目录探针（migrate_legacy=False）
info = {'active': None, 'projects': []}
未抛出 KeyError

> python run_selftests.py -k desktop_startup_perf projects
15 条用例，0 个文件有红

> python smoke_test.py
通过：8 项
失败：0 项

> python smoke_test.py --architecture
Ran 207 tests
4 项既有红：test_layers×2、test_round_baselines、test_unification_ratchet
R815 引入红：0

> 本轮差异凭据形态扫描
credential_shape_matches=0
```

架构门禁的四项红均为任务书明确排除的 R814／门禁债；本轮未登记台账、未弱化断言以凑绿。完整安全全量仅作为验证范围，本修复轮未以其改变轮次类型。
