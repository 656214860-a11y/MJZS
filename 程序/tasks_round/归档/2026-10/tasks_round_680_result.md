# R680 修复轮——阶段外部 SKILL 包重复显示

## 开头三问

1. **本轮功能还是整理轮？** 修复轮：修复阶段配置中一个外部 SKILL 包被“包内清单 + 包总入口”重复显示的问题。
2. **Test run? all 3 baselines?** 已执行默认冒烟、`--affected skill_registry` 与架构门禁；三项均通过。
3. **did project_status debt decrease?** 是；阶段外部包的“只登记总入口”契约已落实到常规 `.skill.md` 扫描路径。

**验证档位声明：**本轮改动涉及 2 个模块（`skill_registry.py`、`tests/test_skills.py`），且调整阶段目录扫描边界；按分级规则执行**默认冒烟 + `--affected skill_registry` + 架构门禁**，跳过全量安全自检，理由：未触及启动路径、L0 契约、用户数据格式或删除路径。

## 只读复现与根因

- 现场目录同时存在外部包根 `SKILL.md`（如 `短剧工业化流水线/SKILL.md`）与可被递归发现的包内清单；截图中的同名/近义两项由此形成。
- `skill_registry.py` 旧实现先用 `stage_dir.rglob('*' + SKILL_SUFFIX)` 把包内 `.skill.md` 登记为普通清单，随后 `_package_sources()` 又把该包根 `SKILL.md` 登记为总入口；同一外部包因此有两个来源。

## 修复改动

- `skill_registry.py`：新增 `_manifest_sources()`，在常规 `.skill.md` 扫描时跳过已识别的阶段外部包目录及其子目录；总入口仍只由 `_package_sources()` 注册。
- `tests/test_skills.py`：在外部包夹具加入包内 `.skill.md`，断言该清单不注册、包根总入口仍是唯一候选。
- `project_status.md`、本结果文件：R680 台账登记。未修改 `skills/` 内容、用户项目数据、`skill_config.json`、工作流配置或密钥。

## 回归断言

1. 同一外部包的根 `SKILL.md` 与包内 `.skill.md` 共存时，只显示包根总入口。
2. 外部包内嵌套 `SKILL.md` 不会单独成为阶段候选。
3. 阶段根目录的普通 `.skill.md` 仍会显示；新放入外部包无需重启即可发现总入口。

## 现场复核

修复后“剧本准备”阶段注册表为 8 项；`短剧工业化流水线`、`影视剧本写作技能`、`剧本锻造`、`短剧编剧搭子`各仅保留包根 `SKILL.md` 的总入口，不再有其包内清单重复项。

## 验证原始输出片段

```text
python -B -m unittest tests.test_skills.RegistryTests -q
Ran 14 tests in 0.670s
OK

python -B smoke_test.py
通过：8 项
失败：0 项

python -B smoke_test.py --affected skill_registry
跑 1 个测试文件 / 18 路工作单元（串行）
ALL TESTS PASSED
通过：9 项
失败：0 项

python -B smoke_test.py --architecture
Ran 102 tests in 25.456s
OK
✅ 架构治理测试：tests/architecture
```

## 用户数据未改动确认

未修改用户项目数据、`skill_config.json`、工作流调用设置、全局配置、密钥或任一 `skills/` 文件；只改程序注册表扫描代码和测试。

## J 后续

无。同类包将自动适用本次总入口去重规则，不需要逐包修复。

## 自审

是：只改 SKILL 注册扫描边界及其回归测试；未改扫描根、阶段配置 UI、业务逻辑或用户数据。
