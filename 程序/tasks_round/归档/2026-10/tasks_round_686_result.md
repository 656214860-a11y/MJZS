# R686 修复轮——阶段配置 SKILL 双源渲染去重与工作流路径保全

## 开头三问

1. **本轮功能还是整理轮？** 修复轮：只修复阶段配置面板将同一 SKILL 同时按注册表与工作流保存路径渲染为两个勾选框的问题。
2. **Test run? all 3 baselines?** 已执行。默认冒烟 8/8、受影响门禁 9/9、SKILL 关联回归 136 条均为 0 红。
3. **did project_status debt decrease?** 否；本轮未关闭“已知阻塞与待办”既有事项，待办数不变。本轮仅处理已确诊的面板显示与持久化保全缺陷。

**验证档位声明：**本轮改动涉及 1 个产品模块（`skill_panel.py`）及测试文件，按用户指定执行**默认冒烟 + 受影响模块门禁 + SKILL 关联回归**，跳过架构门禁与全量安全自检，理由：只改阶段配置面板内部的去重显示与既有工作流设置写回保全，未触及启动、契约、路径、删除或用户数据格式。

## 根因与复现证据

前两轮修复对象为注册表双登记（R680，已生效）；本轮根因为面板双源渲染，属不同缺陷。

- `skill_panel.py:833-840` 的 `build_flow_skill()` 按注册表 `self.skills` 创建阶段 SKILL 勾选框；注册表标签使用 `displayName`。
- `skill_panel.py:920-926` 的 `refresh_flow_checks()` 又把 `flow_skill_paths()` 从 `<项目>/工作流调用设置.json` 的 `flows.<flow>.profiles.<engine>.skills` 读取的每个有效路径创建流程勾选框；流程标签使用 `文件夹/SKILL.md`。
- 活动项目“摄像头3”（`D:\漫剧下载\项目\摄像头3_20260924`）的 `flows.writing.profiles.codex.skills` 保存了短剧工业化流水线、短剧编剧搭子、剧本锻造、影视剧本写作技能四个包根 `SKILL.md`。它们与 R680 后注册表的剧本阶段四项是同一文件，因此打开“01 剧本准备”会出现四对重复框。

## 修复改动

- `skill_panel.py`
  - 新增 `resolved_skill_path()` 与 `registered_skill_paths()`，统一用 `Path.resolve()` 比较注册表项与工作流保存项。
  - `add_flow_check()` 发现路径已由注册表渲染时不再创建第二个流程框，原有“显示名”排重仍保留；两个框均附带规范路径供回归检查。
  - `refresh_flow_checks()` 记录这类“隐藏注册表覆盖路径”；它们不再出现在流程框列表，但仍保留在内存保存集。
  - `save_flow_skill()` 将已勾选的流程框路径与隐藏覆盖路径合并后才调用既有 `set_flow_skills()`。保存前不刷新 BooleanVar，避免“取消”动作被旧设置重新勾回。
- `tests/test_skills.py`
  - 同一已注册且已保存的外部包 `SKILL.md` 在 `flow_skill_row` 中只有一个对应 resolve 路径的勾选框。
  - 保存时隐藏覆盖路径仍写回 `flows.writing.profiles.<engine>.skills`。
  - 未注册但有效的保存路径仍正常生成流程勾选框。
  - R680 的外部包注册表回归未改动；本次新增断言没有弱化或删除既有断言。

## 持久化与用户数据边界

- 未改 `skill_config.json` 的注册表框语义；它仍只由 `save()` 管理。
- 未改变 `工作流调用设置.json` 的格式、未迁移或清空任何用户保存项；隐藏仅指 UI 去重，工作流路径仍由既有 `set_flow_skills()` 原样持久化，供 CLI 引擎的 `skill_prompt` 消费。
- 未访问或改写用户项目数据、配置、密钥；测试仅使用临时目录构造项目与 SKILL 文件。
- 未修改 `skill_registry.py`、扫描根、扫描规则或缓存键。

## 验证原始输出片段

1. `python -B smoke_test.py`

   ```text
   通过：8 项
   失败：0 项
   冒烟测试通过，可以进入下一轮
   ```

2. `python -B smoke_test.py --affected skill_panel skill_registry workflow_settings`

   ```text
   增量台账已刷新：D:\漫剧制作助手\程序\维护记录\自检增量.json
   ALL TESTS PASSED
   门禁 run_selftests.py（定向：skill_panel、skill_registry、workflow_settings）：60 秒 → 0 个文件有红
   通过：9 项
   失败：0 项
   ```

3. `python -B run_selftests.py -k skill_panel skill`

   ```text
   共 136 条用例，20.3 秒；0 个文件有红
   ALL TESTS PASSED
   ```

三个基线数：默认冒烟 **8/0**；受影响门禁 **9/0**；SKILL 关联回归 **136/0**。

## J 后续与自审

- J 后续：本轮未发现需要扩大范围的同类面板双源渲染；注册表侧双登记仍由已生效的 R680 负责，不在本轮重复处理。
- 自审：只改 `skill_panel.py` 的流程框去重与保存路径保全，以及对应的 `tests/test_skills.py`；未夹带注册表、扫描、持久化格式、用户数据或其他页面改动。
- 页面改动需**重启应用**生效。验收建议：重启后打开“摄像头3”的“01 剧本准备”阶段配置，确认四对重复框消失、原勾选状态不变；再以 Codex 引擎发送，确认 `工作流调用设置.json` 中四条包根路径仍在。
