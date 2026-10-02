# R681 功能轮——剧本准备过程文档输出契约

## 开头三问

1. **本轮功能还是整理轮？** 功能轮：扩展剧本准备阶段的输出契约，使所选 SKILL 的过程文档有受限的合法落点。
2. **Test run? all 3 baselines?** 已执行默认冒烟、指定受影响模块门禁和 `workflow` 关联回归；全量安全自检未在本轮声明范围内执行。
3. **did project_status debt decrease?** 是；外部 SKILL 的大纲、节点表和审查报告不再与“剧本正文禁止结构化”被混为同一类输出。

**验证档位声明：**本轮涉及 2 个模块（`workflow_settings.py`、`tests/test_core.py`），但契约会被 `writing_api`、`workflow_engines`、`workflow_tasks` 直接拼接；按任务指定执行**默认冒烟 + `--affected workflow_settings writing_api workflow_engines workflow_tasks` + `run_selftests.py -k workflow`**，跳过架构门禁与全量安全自检，理由：未触及导入关系、启动路径、落盘实现、用户数据格式、L0 契约或删除路径。

## 改动

- `workflow_settings.py`：保留自然语言剧本原稿的唯一阶段交付；将禁止范围明确限定为**剧本正文**中的结构化剧本、档案、字段表、JSON/YAML、镜头/分镜表、首帧/视频提示词和资产清单。
- `workflow_settings.py`：新增许可——所选 SKILL 的分集大纲、情节节点表、节奏/逻辑/合规审查报告、确认清单等人读 Markdown 可写到本阶段目录的相对 `docs/` 子目录；它们不是阶段交付，不能并入原稿或替代 02 的结构化剧本。
- `workflow_settings.py`：明确五类 manifest JSON 仍由 `script_contract.PRODUCERS` 的归属生产者产出，本阶段对话不生成；结尾改为只返回剧本正文与 SKILL 要求的确认清单。
- `tests/test_core.py`：新增契约守护，逐项断言唯一交付、正文禁区、02 归属、`docs/` 过程文档许可、manifest 归属及最终返回边界。

## 边界核对

- 全局检索 `stage_output_contract` / `_STAGE_OUTPUT_CONTRACTS`：调用点仍是 `writing_api.py`、`workflow_engines.py`、`workflow_tasks.py`；调用方式未改，均继续原样拼接 `stage_output_contract('writing')`。
- 未改 `script_contract.py` 的 `natural_script_violations`、`require_natural_script`、`save_natural_script`。
- 未改 `hollmwood_roles.py`、`writing_api.py`，没有新增路径拼接或硬编码绝对路径。
- 本次改测试因契约变更，断言未弱化：新增断言覆盖原稿唯一性和结构化正文禁区，并增加过程文档的精确许可边界。

## 验证原始输出片段

```text
python -B -m unittest tests.test_core.WorkflowSettingsTests -q
Ran 3 tests in 0.001s
OK

python smoke_test.py
通过：8 项
失败：0 项

python smoke_test.py --affected workflow_settings writing_api workflow_engines workflow_tasks
跑 1 个测试文件 / 3 路工作单元（串行）
共 21 条用例，15.8 秒；0 个文件有红
ALL TESTS PASSED
通过：9 项
失败：0 项

python run_selftests.py -k workflow
跑 2 个测试文件 / 14 路工作单元（8 路并行）
共 93 条用例，13.1 秒；0 个文件有红
ALL TESTS PASSED
```

## 三个基线数

- 默认冒烟：本轮 **8/8** 通过。
- 架构门禁：最近一次已验证为 R680 的 **102/102**；本轮按声明跳过。
- 全量回归：AGENTS.md 记录的基线为 **3,230** 条；本轮按声明跳过全量安全自检。

## 用户数据未改动确认

未修改任何用户项目、`skill_config.json`、全局配置、密钥或 SKILL 文件。

## 自审

是：只改契约文本和守护它的测试；未新增越界依赖，未改变落盘闸门、调用链或路径实现。
