# R614｜修复轮：Registry 一级阶段目录缓存键

## 开工与前置确认

- **本轮是功能轮还是整理轮？** 功能轮中的修复轮：只修 SKILL 注册表热刷新根因。
- **测试跑了吗？三个基线过了吗？** 已跑。默认 `smoke_test.py` 为 8/8；架构门禁在更新本轮台账前仅因轮次连续性（613 != 614）失败，台账推进后需复跑确认；`tests/test_skills.py` 118 条中仍有 2 条既存独立失败，故三个基线不能写作全部通过。
- **`project_status.md` 的欠账少了吗？** 本轮消除了“阶段目录内 SKILL 增删不刷新”的根因和覆盖缺口；两条既存 `skill_registry` 关联基线未在本轮越界修改，登记于 J。

R613 的缓存原始值复核：缓存键此前仅为 `self.root.stat().st_mtime_ns`；每次 `files()`、`fingerprint()`、`_fresh()` 查询都会重新对**根目录** `stat()`，不是仅首次 `Registry()` 计算。键不变即复用 `_file_records`，不再 `rglob()`；`_DEFAULTS` 只是进程内 `str(root) -> Registry` 单例映射，无落盘缓存文件、TTL 或哈希。

### 根目录重命名矛盾的直接证据

以下使用项目内置解释器在 `%TEMP%` 模拟同一 NTFS 操作；目录自身的 mtime 在 rename / rename-back 中保持不变。因此用户在没有查询发生的两次重命名之间改回 `skills/` 后，旧实现再次看到的是相同根目录 mtime，合理地错误复用旧清单，不是“根目录 mtime 一定会变化”。

```text
before=1790674382687697400 renamed=1790674382687697400 restored=1790674382687697400 equal_before_restored=True
```

本轮不改单例：它不是永久文件清单缓存；同一实例每次查询本就会 stat。修复为一级阶段目录变更可使该单例缓存失效。

## 修改文件与改动摘要

- `skill_registry.py`
  - 新增 `Registry._file_cache_key()`；键为 `(skills 根目录 mtime_ns, ((一级目录绝对路径, mtime_ns), ...))`，路径排序稳定。
  - `_refresh_file_cache()` 仅在这个键不同才 `rglob('*.skill.md')`；未变化时仍仅对根与一级目录 stat，不递归扫描。
  - 保存 `_child_directory_mtimes`、`_directory_cache_key` 供诊断与缓存比较；无配置格式、注册规则或 UI 改动。
- `tests/test_skills.py`
  - `RegistryTests.test_hot_reload_tracks_add_and_delete_inside_stage_directory`：真实创建临时 `skills/01 剧本准备SKILL/`，断言初始空、新增后文件/对象出现、删除后消失，并断言每次 `fingerprint()` 变化。

## 新回归：先红后绿

修复前命令：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' -m unittest tests.test_skills.RegistryTests.test_hot_reload_tracks_add_and_delete_inside_stage_directory
```

修复前原始失败：

```text
FAIL: test_hot_reload_tracks_add_and_delete_inside_stage_directory
File "D:\漫剧制作助手\程序\tests\test_skills.py", line 195
AssertionError: WindowsPath('.../skills/01 剧本准备SKILL/probe-stage-file.skill.md') not found in []
Ran 1 test in 0.009s
FAILED (failures=1)
```

修复后同命令原始结果：

```text
.
Ran 1 test in 0.019s
OK
```

断言覆盖：初始 `files()==[]`；新增合法文件后 `files()` 包含路径、`fingerprint()` 与 `_directory_cache_key` 均不同、`getAll()` 包含 id；删除后 `files()` 不含路径、指纹与缓存键再次不同、`getAll()` 不含 id。

## 修复前后 Registry 对照实验（无 UI）

复现命令（临时脚本在 `%TEMP%`，finally 删除临时树）：

```powershell
$env:PYTHONPATH = 'D:\漫剧制作助手\程序'
& 'D:\漫剧制作助手\运行环境\Python\python.exe' 'C:\Users\LAIBIAO\AppData\Local\Temp\r614_registry_probe.py'
```

### 修复前原始输出

```text
B1 files= []
B1 root_mtime_ns= 1790674458565650500
B1 cached_root_mtime_ns= 1790674458565650500
B1 fingerprint= ()
B3 files= []
B3 root_mtime_ns= 1790674458565650500
B3 cached_root_mtime_ns= 1790674458565650500
B3 fingerprint= ()
B4 files= []
B4 root_mtime_ns= 1790674458565650500
B4 cached_root_mtime_ns= 1790674458565650500
B4 fingerprint= ()
B5 files= []
B5 root_mtime_ns= 1790674458565650500
B5 cached_root_mtime_ns= 1790674458565650500
B5 fingerprint= ()
```

### 修复后原始输出

```text
B1 files= []
B1 root_mtime_ns= 1790674546894206100
B1 cached_root_mtime_ns= 1790674546894206100
B1 cached_child_mtimes= (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL', 1790674546894206100),)
B1 cache_key= (1790674546894206100, (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL', 1790674546894206100),))
B1 fingerprint= ()
B3 files= ['zz_probe_610.skill.md']
B3 root_mtime_ns= 1790674546894206100
B3 cached_root_mtime_ns= 1790674546894206100
B3 cached_child_mtimes= (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL', 1790674546896204500),)
B3 cache_key= (1790674546894206100, (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL', 1790674546896204500),))
B3 fingerprint= (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL\\zz_probe_610.skill.md', 1790674546, 299),)
B4 files= []
B4 root_mtime_ns= 1790674546894206100
B4 cached_root_mtime_ns= 1790674546894206100
B4 cached_child_mtimes= (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL', 1790674546898213700),)
B4 cache_key= (1790674546894206100, (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL', 1790674546898213700),))
B4 fingerprint= ()
B5 files= []
B5 root_mtime_ns= 1790674546894206100
B5 cached_root_mtime_ns= 1790674546894206100
B5 cached_child_mtimes= (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL', 1790674546898213700),)
B5 cache_key= (1790674546894206100, (('C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\r614_registry_probe_u0v75wbc\\skills\\01 剧本准备SKILL', 1790674546898213700),))
B5 fingerprint= ()
```

结论：根 mtime 在 B1/B3/B4 未变，而子目录 mtime 在创建、删除均改变；新键因此重建清单。`B5` 也证明不重启解释器的新 `Registry()` 看见删除后的状态。

## 验证

- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`（更新台账前）：101 条中 1 条失败，仅 `test_round_number_continuous`，原文 `AssertionError: 613 != 614`；这是结果文件已新增而台账尚未前进的轮次守卫，不是 Registry 失败。台账推进至 R615 后复跑：101/101 通过。
- `python -m unittest tests.test_skills`：118 条，2 条失败；新回归通过。

`python smoke_test.py --affected skill_registry` 逐条失败判定：

1. `tests.test_skills.PanelTests.test_the_skill_boxes_follow_the_flow_order`：
   `AssertionError: ... 'subtitle-format-export', 'pipeline-audio-subtitle'] != ... 'subtitle-format-export']`。分类 **b：既存独立失败**。它是 `skill_panel` 音频面板列表期望未包含已登记 pipeline SKILL；本轮未改 `skill_panel`、阶段注册规则或排序。
2. `tests.test_skills.ToolTests.test_every_tool_in_the_registry_is_known`（`tests/test_skills.py:535`）：
   `AssertionError: Lists differ: ['asset.plan', ... 'delivery.package'] != []`（18 个缺失 tool id）。分类 **b：既存独立失败**。它要求扩充 `skill_tools` 注册表，非本轮缓存键根因；本轮未改该模块。

两项均不属于“本轮修复后应转绿”的 a 类；R605/R606 已登记的历史门禁失败仍如实保留。

## J｜后续

- 处理 `PanelTests.test_the_skill_boxes_follow_the_flow_order` 的过期音频面板契约或产品排序，影响面：`skill_panel.py` 与该专项测试；须独立核定 pipeline SKILL 是否应显示。
- 补齐或裁定 18 个 `skill_tools` 映射，影响面：`skill_tools.py`、工具注册规格与 `ToolTests`；不得与 Registry 缓存修复混改。

## 自审

- 只改了根因模块 `skill_registry.py` 与其既有测试文件 `tests/test_skills.py`；未改 `/` 补全、UI 布局、`skill_config.json` 格式、SKILL 注册规则或用户数据。
- 未引入第三方或越界依赖；一级目录 `stat` 替代每次递归 `rglob`，保留 R539 的性能边界。
- 临时对照脚本只在 `%TEMP%`，探针目录由 `finally` 删除；本轮未修改任何用户项目数据。
