# R682 功能轮——外部包 SKILL 的引擎适配提示

## 开头三问

1. **本轮功能还是整理轮？** 功能轮：为外部包 SKILL 总入口补充引擎适配提示，不改变注入或执行链路。
2. **Test run? all 3 baselines?** 已执行默认冒烟、`--affected skill_panel skill_registry` 与任务指定的 `skill_panel` 关联回归；架构门禁和全量安全自检按声明跳过。
3. **did project_status debt decrease?** 是；API 模型勾选外部包总入口时不再静默呈现为可完整展开。

**验证档位声明：**本轮涉及 2 个模块（`skill_panel.py`、`tests/test_skills.py`），按任务指定执行**默认冒烟 + `--affected skill_panel skill_registry` + `run_selftests.py -k skill_panel`**，跳过架构门禁与全量安全自检，理由：仅为单一面板增加只读元数据提示及回归，未触及启动路径、用户数据格式、L0 契约、删除路径或注册表扫描/解析。

## 改动

- `skill_panel.py`：增加 `external_package_api_hint()`，仅读取已注册 `Skill.meta` 中的 `skill_registry.IMPORTED_PACKAGE_FLAG`，并复用 `model_pool.desktop_engine(model_id)` 判定当前模型是否为桌面引擎；未新增目录扫描、注册表解析或模型判定规则。
- `skill_panel.py`：在 SKILL 勾选区与说明区之间增加独立提示行，沿用既有 `Muted.TLabel`、既有说明行的换行宽度和 `SPACING['xs']` 间距。页面加载、勾选变化、全选/取消、删除后、模型/厂商变更与模型池刷新均同步刷新该行。
- `tests/test_skills.py`：新增面板回归，断言外部包入口 + API 模型显示提示，切到 `chatgpt-desktop` 后提示消失，普通 SKILL + API 模型也不提示；测试直接检查实际标签文案。

## 边界核对

- 未改 `skill_registry.py`，没有改变扫描根、缓存键、外部包解析或注册顺序。
- 未改 `workflow_settings.skill_prompt`、`_one_skill_prompt` 或任何注入、执行、网络与进程调用。
- 提示只读取当前面板已勾选注册项的内存元数据；不读写项目配置、不触发文件扫描。
- 页面改动需重启应用生效。

## 验证原始输出片段

```text
python -B -m unittest tests.test_skills.PanelTests.test_imported_package_hint_only_appears_for_api_models
Ran 1 test in 0.240s
OK

python -B smoke_test.py
通过：8 项
失败：0 项

python -B smoke_test.py --affected skill_panel skill_registry
跑 1 个测试文件 / 18 路工作单元（串行）
共 128 条用例，57.7 秒；0 个文件有红
ALL TESTS PASSED
通过：9 项
失败：0 项

python -B run_selftests.py -k skill_panel
定向：忽略增量台账，执行 0 个匹配测试文件
跑 0 个测试文件 / 0 路工作单元（8 路并行）
共 0 条用例，0.0 秒；0 个文件有红
ALL TESTS PASSED
```

`-k skill_panel` 的筛选依据是测试文件名，当前回归文件名为既有的 `test_skills.py`，故该命令如实返回 0 条；任务指定的 `--affected skill_panel skill_registry` 已通过既有映射执行同一文件的 128 条用例，且新增的面板回归另已直接运行通过。未为让该筛选命中而越界修改自检运行器或新增重复测试文件。

## 三个基线数

- 默认冒烟：本轮 **8/8** 通过。
- 架构门禁：最近一次已验证为 R680 的 **102/102**；本轮按声明跳过。
- 全量回归：AGENTS.md 记录的基线为 **3,230** 条；本轮按声明跳过全量安全自检。

## 用户数据未改动确认

未修改任何用户项目、`skill_config.json`、全局配置、密钥或 SKILL 文件。

## 自审

是：仅改阶段配置 SKILL 面板的只读提示和对应测试；未修改注册扫描/解析、SKILL 注入、执行路径、用户配置或用户数据。
