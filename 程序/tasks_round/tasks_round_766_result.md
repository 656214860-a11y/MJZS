# R766 结果｜性能轮：启动路径探针与递归扫描收口

## 结论

以“启动至 `01 剧本准备` 可见壳”为边界，探针已把递归目录扫描降为 0；剧本、创意与阶段 SKILL 的发现改为与既有目录布局一致的有界枚举。首次选择路径的两个测量点均下降；当天自动续开的单次样本仍在 1.0 秒契约内但高于旧策略，故本轮不宣称整体启动更快，只以通过的契约和可重复的扫描计数为验收依据。

## 改动与根因

- `script_workspace_service.py`：`iter_script_documents()` 不再对 `writing` 执行 `rglob()`，仅枚举兼容的三层固定布局（旧创意目录、供应商／创意目录、供应商／模型／创意目录）。
- `idea_chat.py`：创意文档发现按同一固定布局读取直接 Markdown 与三类直接子目录，不再递归遍历整个 `writing` 树。
- `skill_registry.py`：阶段默认 SKILL 清单只读取阶段目录的直接 `.skill.md`；外部包仍经其根 `SKILL.md` 的既有入口加载，避免启动配置默认值递归扫描 SKILL 树。
- `tests/test_desktop_startup_perf.py`：固化首次事件循环、首次选择页、选择后入剧本准备、当天自动续开和递归扫描五个探针。递归扫描断言的边界是用户已进入剧本准备页的可见壳；自动宠物后续的后台生产不属于该启动指标。

## 同条件探针：改前／改后

临时项目、临时设置和同一解释器运行；“改前”在内存中恢复旧的三个递归发现函数，不修改工作树或用户项目。一次测量存在调度波动，数值不被解释为吞吐量结论。

| 指标 | 改前 | 改后 | 契约／结论 |
| --- | ---: | ---: | --- |
| 首次事件循环（首次选择） | 0.0592s | 0.0589s | ≤2.6s，通过 |
| 首次选择页可见 | 0.3999s | 0.3807s | ≤1.0s，通过 |
| 首次选择后进入剧本准备 | 0.4438s | 0.3885s | ≤1.0s，通过 |
| 当天自动续开进入剧本准备 | 0.5410s | 0.8152s | ≤1.0s，通过；单次样本变慢 0.2742s，保留为后续实机复测基线 |
| 启动至剧本准备的递归扫描 | 13 次 `rglob()`（旧实现探针） | 0 次 `rglob()`／0 次 `os.walk()` | 必须为 0，通过 |
| 已有项目加载显示 | 既有回归 | 既有回归 | `show_loaded_project` ≤0.2s（强于 1.0s 要求），通过 |
| 聊天首次非空文本 | 既有回归 | 既有回归 | ≤1.5s，通过 |

## 四类候选瓶颈核验

### `time.sleep`（14 处）

逐项复核后，14 处均不在桌面 Tk 主线程的启动路径：原子写重试、缩略图工作线程、剪贴板锁轮询、Comfy／模型／子进程就绪重试、资源批处理工作线程、并行任务轮询和独立维护命令。没有把正常的后台重试替换成新的轮询，避免扩大范围。

### 列表、建页与代次

项目选择与剧本页仍使用既有代次取消／延后建页机制；本轮探针覆盖“首次手选”和“当天自动续开”两条实际入口。未发现改名认领链令列表重建或旧代次结果重新生效的证据，故未作无依据重构。

### 改名认领扫描纪律

源代码复核确认：`projects.reconcile_missing()` 仅在登记表存在失效条目时调用，只对项目库执行一级 `iterdir()`，候选配置经 `file_cache.read_json()` 读取且不进入阶段子目录。实际登记表只读探针没有失效条目，因此本次启动不会触发认领扫描。

### 改名项目活路径实机只读核验

探针从登记表定位当前项目，不硬编码旧目录；全过程只读，未改写用户项目。为避免把用户路径或项目名称写入版本化结果，原始结构化输出仅脱敏项目标识：

```text
registry_rows=3
target_current_registry_matches=1
directory_exists=True
project_config_exists=True
episode_live_reference_count=2
episode_references_current_root=True
cloud_video_config_count=1
invalid_registry_entries=0
reconcile_state=none
```

这证明已登记的当前路径存在、项目 `config.json` 的两处活引用均指向当前根目录，并且当前状态无需触发认领。它不替代用户机器的完整冷启动交互复验，原有挂账继续保留。

## 验证

- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected desktop project_stages`：9/9，底层 19 条／0 红。
- `python run_selftests.py -k desktop_startup_perf --safe`：10 条／0 红。
- `python -m unittest tests.test_script_workspace_service -q`：14 条／0 红。
- `python smoke_test.py --architecture`：138/138，未低于基线。
- 完整安全全量：`766 - last_full_safe_all_round(765) = 1 < 3`，按规则未执行；`last_full_safe_all_round` 保持 R765。

## J. 整改路线

若用户现场仍观察到当天自动续开停在项目页，下一轮先采集同一启动会话的可见页、活动登记和 tick 状态，再针对可复现链处理；不得以本轮单次计时替代现场证据。自动宠物进入剧本页后的后台目录工作若造成可见卡顿，应另立性能任务，不能混入本轮启动路径指标。

## K. 测试迁移计划

启动路径时延与零递归约束留在 `tests/test_desktop_startup_perf.py`；剧本目录布局的兼容性留在 `tests/test_script_workspace_service.py`；阶段 SKILL 包／默认清单的边界继续留在注册表测试。所有新增探针使用临时目录，不访问真实用户项目。

## 提交状态

未提交；commit hash：无。

[TASK_COMPLETE]
