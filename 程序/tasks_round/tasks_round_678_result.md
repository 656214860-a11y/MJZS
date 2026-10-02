# R678 功能轮结果：阶段 SKILL 包总入口导入适配

## 开头三问

1. 当前轮次与台账是否一致：一致。开始时台账为 R678 待执行、最新结果为 R677；本报告完成后台账已推进为 R679 待执行，满足 `679 = 678 + 1`。
2. 上一轮进行中未完成的任务是什么：R677 已完成“被引用的已勾选 SKILL 允许用户确认后删除”；本轮承接用户提出的外部 SKILL 包注册问题。
3. 下一轮该做什么：请重启应用并打开“阶段配置 → 剧本准备”，确认现在显示外部包总入口；以后将新包放入对应阶段目录的 `<包名>/SKILL.md`（或使用既有 `<名称>.skill.md`）后，重新打开该页即可扫描到。

## 验证档位声明

本轮改动涉及 3 个模块（`skill_registry.py`、`tests/test_skills.py`、`architecture.md`），按分级规则执行默认冒烟 + `--affected skill_registry` + 架构门禁，跳过全量，理由：仅扩展阶段配置打开后的注册表懒扫描及其测试/说明，未触及启动路径、L0 契约、用户数据格式或删除路径。

## 改动与入口规则

- `skill_registry.py`
  - 保留既有 `skills/**/*.skill.md` 的严格 frontmatter 与文件名校验。
  - 在已经打开阶段配置、由面板显式调用 `Registry.scan(force=True)` 时，额外检查各 `01`—`12` 阶段目录的**一层**子目录：根部有 `SKILL.md` 的外部包登记为一个总入口；没有 `SKILL.md` 但有根部 `README_ZH.md`/`README.md` 的集合包同样登记一个总入口。
  - 外部包不展开其内部子目录；不足的外部 frontmatter 由注册器补齐为只读、无工具、无模型绑定的安全元数据。常规 `.skill.md` 契约不变。
  - 缓存键增加阶段下一层目录的 mtime，因此后续新放入 `<包名>/SKILL.md` 后，重新打开阶段配置即可被发现；该行为未进入应用启动路径。
- `tests/test_skills.py`
  - 新增回归：外部包只出现一个入口、内部 `SKILL.md` 不展开、后放入的新包自动被发现。
  - 更新两个旧的固定数量断言为与注册表“当前非弃用项”一致的断言；这是注册源契约扩展所需的测试同步，未弱化 UI/阶段配置必须完整显示注册项的断言。
- `architecture.md`
  - 记录“常规 `.skill.md` 递归发现 + 外部包一层总入口、显式懒扫描”的注册边界。

## 本机发现结果

`01 剧本准备SKILL` 的五个外部包现均以单个入口注册：`短剧编剧搭子`、`screenplay-production-line`、`script-forging`、`screenplay-writer`、`编剧技能集`。另发现 `08白模预演SKILL/create-blender-story-video/SKILL.md` 也符合相同约定，故全注册表实际由 67 增至 73；剧本准备阶段为 8 项，白模预演为 7 项。

## 验证输出摘录

```text
python -B -m unittest tests.test_skills.RegistryTests
Ran 13 tests in 0.451s
OK

python -B smoke_test.py
通过：8 项
失败：0 项

python -B smoke_test.py --affected skill_registry
跑 1 个测试文件 / 18 路工作单元（串行）
ALL TESTS PASSED
✅ 门禁 run_selftests.py（定向：skill_registry）：41 秒 → 0 个文件有红
通过：9 项
失败：0 项

python -B smoke_test.py --architecture
Ran 102 tests in 24.335s
OK
✅ 架构治理测试：tests/architecture
```

首次定向门禁暴露两处旧固定数量断言（阶段面板与阶段默认项）；按新的“注册表为唯一入口”契约改为核对当前非弃用注册项后，已完整重跑并通过上述门禁。

## 用户数据未改动确认

未修改用户项目、`skill_config.json`、工作流调用设置、外部 SKILL 正文或密钥；新增测试仅使用临时目录。

## J 后续

仅有嵌套子 `SKILL.md`、但包根既无 `SKILL.md` 也无 README 的目录会继续被忽略，以免把任意资料目录误注册。若需要支持另一种外部包规范，应另立一轮明确其入口文件与元数据边界。

## 自审

只修改注册总入口适配、对应回归和架构说明；没有改扫描根、用户配置、删除逻辑或启动路径。新增逻辑只在阶段配置显式打开后的扫描中运行，未引入越界依赖。
