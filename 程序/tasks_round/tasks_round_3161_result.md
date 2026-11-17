# R3161 结果（修复：白模身份回归——STAGES 移除后遗留的导入）

- 轮次类型：修复轮（分支 `codex/wip-R3161`）。

## 三问

1. **本轮属于 §3 哪种类型？** 修复轮（修 P0「重复阶段映射收敛」遗留的一处导入回归）。
2. **测试跑了吗、三个基线过了吗？** 定向跑了：`test_white_model_identity` 由红转绿（12 条 0 红）。本轮未跑冒烟与架构，合并轮 CI 覆盖。
3. **欠账少了吗？** 少 1 项：`test_white_model_identity` 的 `ImportError: cannot import name 'STAGES' from 'contract.project_stages'` 回归已闭。

## 根因与修法

`R3093（P0，Q15）` 删除了 `contract/project_stages.STAGES` 字典（重复阶段映射收敛，改由 `stage_dirs()` 派生），但漏改了 `domain/white_model_service._reroot()` 里的一处 `from contract.project_stages import STAGES; names = set(STAGES.values())`。该函数只在项目改名／移动后重定位分镜时触发，因此冒烟与架构门禁都没覆盖到，直到全量 `test_white_model_identity` 才暴露。

修法：改用等价的 `stage_dirs()`（返回同样的阶段目录名元组），语义不变。

> 更正上一轮（R3152 结果文件）的判断：`test_white_model_identity` **是本任务书引入的回归**，不是他车道既有红。上一轮只看到失败点落在 `white_model_shot_directory`，未深挖到导入层；本轮在干净 master 复现时暴露了真正的 `ImportError`。

## 改动

| 文件 | 改动 |
| --- | --- |
| `domain/white_model_service.py` | `_reroot()` 内 `from contract.project_stages import STAGES` → `from contract.project_stages import stage_dirs`；`set(STAGES.values())` → `set(stage_dirs())` |

## 验证

- `run_selftests.py -k test_white_model_identity` → **12 条 0 红**。
