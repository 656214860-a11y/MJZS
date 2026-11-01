# R622 结构治理轮（执行）：收口预设来源并移除个人删除入口

## 来源、编号与 AGENTS.md 第 7 节三问

- 子场景：**执行**；来源：[R620 报告 J 节路线 2](D:/漫剧制作助手/程序/tasks_round/tasks_round_620_result.md)。执行项仅为“移除个人预设探测 + 移除现有删除功能”。
- 编号：R621 已存在，故按连续编号使用 R622；`project_status.md` 仍标 R619，是既有台账滞后，本轮未修改它。
- 本轮是功能轮还是整理轮？**结构治理轮（执行）。**
- 测试跑了吗？三个基线过了吗？默认冒烟通过 8/8；架构门禁 100/101，唯一失败为既有台账编号不连续（R619 对最新 R621），非本轮引入；全量安全回归 3326 条结束，18 个既有文件有红，结果见验证节。
- `project_status.md` 的欠账少了吗？**没有更新台账；本轮移除了 Codex 依赖与对应僵尸删除入口。**

## 改动文件与摘要

1. [workflow_settings.py](D:/漫剧制作助手/程序/workflow_settings.py:61)
   - 删除 `_home_skill()`；`preset_skill()` 始终返回 `_bundled_skill()`。
   - 保留 `_preset_paths()` 签名，但缓存固定为内置预设 `(folder, bundled_path)`，不再读取 `CODEX_HOME`。
   - `preset_folder()` 只匹配内置路径。
2. [skill_panel.py](D:/漫剧制作助手/程序/skill_panel.py:162)
   - 删除 `personal_skills_root()`、`is_personal_skill_file()`、`delete_checked_personal_skills()`、删除按钮和 `recycle_paths` 导入。
   - 保留全选、取消、新增手选 SKILL 等原有职责；未实现任何新删除能力。
3. [tests/test_core.py](D:/漫剧制作助手/程序/tests/test_core.py:821)
   - 缓存契约改为内置路径缓存；断言 `CODEX_HOME` 不改变缓存对象或 `preset_skill()` 返回来源。
4. [tests/test_skills.py](D:/漫剧制作助手/程序/tests/test_skills.py:1176)
   - 移除个人删除功能测试，替换为“无删除按钮”和“`flow_skill_choices()` 在 mock `CODEX_HOME` 下只返回程序 `skills` 路径”的断言；未弱化其他 SKILL 选择/注册表断言。

## R614 缓存修复有效性

当前 [skill_registry.py](D:/漫剧制作助手/程序/skill_registry.py:366) 的 `_file_cache_key()` 返回：

```text
(root.stat().st_mtime_ns,
 ((一级目录绝对路径, 一级目录.stat().st_mtime_ns), ...))
```

真实目录同进程探针原始摘要（临时 `zz_probe_622.skill.md` 已删除）：

```text
before_has_probe=False
after_has_probe=True
deleted_has_probe=False
01 剧本准备SKILL mtime_ns:
1790679892659674300 -> 1790679987564704700 -> 1790680065390125700
```

结论：新增和删除均改变一级目录键，并在不重启同一 `Registry` 实例时反映到 `files()`。**R614 修复仍有效，本轮未触碰 `skill_registry.py`。**

## 手工启动观察

用 `D:\漫剧制作助手\运行环境\Python\python.exe app.py` 成功启动，进程窗口标题为“漫剧制作助手 · V0.7”。本执行环境的原生 UI 自动化枚举未暴露该窗口，故无法在自动化会话中完成“进入剧本准备 → 阶段配置”的点击观察；应用随后已结束，未留下进程。

代码与定向 Tk 回归提供等价可重复证据：固定预设候选调用 `preset_skill()`，其现已只返回程序 `skills`；面板不再构造删除按钮。此限制如实记录，不能替代人工视觉验收。

## 用户数据确认

未读取后写入、未修改下列用户数据：

- `D:\漫剧下载\项目\摄像头3_20260924\skill_config.json`
- `D:\漫剧下载\项目\摄像头3_20260924\工作流任务\工作流调用设置.json`

历史 `.codex` 路径保留原样；本轮只改变新候选来源，不迁移或清理已有选择。

## 验证

- `python smoke_test.py`：**通过，8/8**。
- `python smoke_test.py --architecture`：**100/101**；`test_round_number_continuous` 失败原文为 `AssertionError: 619 != 622`。失败原因是状态台账仍为 619、而已有 R621；本轮未修改 `project_status.md`，也未引入该问题。
- 定向回归：`ValidateProfileTests` 两项 + `PanelTests` 两项，**4/4 通过**。
- `run_selftests.py --all --safe`：原始汇总为 **3326 条用例、895.6 秒、18 个文件有红**。与本轮直接相关的 `test_skills` 两条既有红为候选顺序多出 `pipeline-audio-subtitle`、工具表缺 18 项；定向运行的本轮四条断言均通过，且上述失败不涉及预设路径、`.codex` 来源或删除按钮。其余典型既有红包括 `storyboard_files.py` 的未定义 `remove`、模型密钥 DPAPI 保护、宠物 UI 色值/字号等，均不在本轮改动文件或职责范围。

  原始汇总行：`共 3326 条用例，895.6 秒；18 个文件有红`。

## J. 后续：新删除功能的设计输入（本轮未实现）

1. 作用域应为程序 `skills/` 下全部 `.skill.md`，不得设置“内置不可删”。
2. 回收位置不得位于 `skills/` 之下；候选包括程序根的 `工作流任务/回收站`、用户项目回收位置或其它扫描树外位置。下一轮应先比较恢复语义与权限边界。
3. 删除必须经 `storage_maintenance.recycle_paths()` 并保留恢复清单。
4. 需与后续“用户手动新增 SKILL”共同设计，形成导入—删除的可恢复闭环。

## 自审

- 只修改了指定的两项职责及其必要测试；未改 `skill_registry.py`、UI 布局、用户配置或用户项目数据。
- 不保留 `.codex` 路径 shim/re-export；静态搜索确认旧个人删除符号和 `recycle_paths` 导入均不存在。
- 本轮新增能力为零；删除功能完全移除，后续设计未在本轮实现。
