# R1342：O18 来源账本从「仍在」升级为「仍是这个版本」

类型：功能轮（§3.1；本项为「事实」，交付为实现＋测试）。承接 R1267 清单 O18（O01—O17 已完成）。中央轮次 1342。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k artifact_lineage file_cache storyboard script_structure script_contract` 136/136、架构门禁 312/312、默认冒烟 8/8，全 0 红。
- 欠账：O18 关闭，清单剩 O19—O48；1342 − 1341 = 1 < 5，本轮不跑全量（五轮全量欠账留到下次收口轮）。

## 目标（R1267 清单 O18）
- 证据：`artifact_lineage.py:28` 已保存 `source_sha256`，但 `:38` 的 `source_available` 只检查存在和非空；并非所有下游都统一检查版本。
- 建议：保留 available 语义，新增 current/stale/unknown；多输入成果记录分镜、资产、台词、模型配置等依赖。修改上游后展示受影响成果，不自动删除或覆盖用户成品。
- 验收：源同路径内容变更能标过期；改无关文件不失效；无账本旧项目可显式采用；覆盖结构、分镜、首帧、白模、音频、剪辑。

## 实现
### 1）账本同时回答「源仍在」与「源仍是这一版」（`artifact_lineage.py`）
- 新增状态常量 `CURRENT/STALE/MISSING/UNKNOWN` 与 `check(root, artifact)`：逐来源比对登记摘要，返回整体 status 与逐来源明细（role／path／status／recorded_sha256）。
- 新增 `source_status(root, artifact)`（只取整体状态）。源同路径内容变化 → `stale`；源被删 → `missing`；无账本／无该成果记录 → `unknown`。
- `source_available` 语义保留（源存在且非空为 True、缺失为 False、无账本为 None），改为基于 `check()` 派生：**内容变了仍可用，只标过期，不隐藏**。
- available 与 version 分开：`stale` 不触发下游隐藏，只有 `missing` 才隐藏孤立成果（既有隐藏用例语义未变）。

### 2）多输入成果与显式采用
- `record(root, artifact, source=None, artifact_type='', *, sources=None)`：`source` 兼容旧的单来源调用；`sources` 接受 `{角色: 路径}` 或 `[(角色, 路径), ...]`，用于分镜／资产／台词／模型配置等多输入成果；每个来源都在登记时留下内容摘要。
- 旧账本（只写 `source`/`source_sha256`）仍可读；同成果重记覆盖旧记录。
- 新增 `adopt(...)`：无账本旧项目显式采用（把现有成果与当前来源登记为一致），不自动为任何历史文件补账。
- 新增 `affected(root, source=None)`：只读遍历项目内账本，列出已过期／来源缺失的成果；给定 source 时只看依赖它的成果；不删除、不覆盖、不修复任何成品。

### 3）受影响成果在目录可见
- `storyboard_catalog_service.catalog`：定稿来源过期（stale）时标题追加 `· 来源已变更`，仍照常显示；来源缺失（missing）仍隐藏（与过期分开判断）。
- 剧本目录（kind=='script'）当前结构稿来源过期时标题追加 `· 原稿已变更`。

## 验证
- 新增 `tests/test_artifact_lineage.py`（10 条）：同路径内容变更标 stale 但仍 available、恢复原内容回 current；改无关文件不失效；删源标 missing 且 unavailable；无账本 UNKNOWN 且 available None；旧单来源账本可读；多来源逐角色状态（改台词 → 台词 stale、其余 current，整体 stale）；同成果重记覆盖旧来源；`affected` 只列非 current 且按 source 过滤；`adopt` 显式采用后 current；结构／分镜／首帧／白模／音频／剪辑六类都能登记并检出过期。
- `tests/test_file_cache.py` 增 1 条：定稿来源内容变更后仍在目录显示且标题含「来源已变更」。
- 既有血缘／隐藏用例（`test_lineaged_final_is_hidden_when_its_structured_script_is_deleted`、`test_structure_output_is_hidden_when_its_recorded_natural_script_is_deleted`）保持绿，证明 available 语义未退化。

## 边界
- 未改 `script_contract.py`／`storyboard_final.py` 的登记调用点，仅扩展账本 API 与目录展示；未增删 `json.loads`（未动 `架构统一基数.json` 台账）。
- 未命中 §5 升级条件（未动启动路径／Tk 控件生命周期／删除语义／层级登记表）。
- `affected` 只读；不自动删除、不覆盖用户成品、不为历史文件补账。

## 风险与边界
- 内容摘要按文件字节计算，改文件名／路径视为「新来源」（旧登记会成为 missing），符合「同路径」验收口径。
- `affected` 需遍历项目内 `产物来源关系.json`；大项目首次遍历有成本，只读且不写盘。
- 无账本旧项目状态恒为 UNKNOWN，需要用户／上层显式 `adopt`，程序不猜测。
- 未实发模型请求、未重启应用、未真实点击界面。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 把模型池 `claude-desktop` label 存成「Claude Desktop」，令 `test_workflow::test_stage_model_selects_the_matching_desktop_agent` 在主树红；干净工作树无此文件、`test_workflow` 108/108 绿，故不影响本轮结论，也不在本轮修复。

[TASK_COMPLETE] 来源账本从「仍在」升级为「仍是这个版本」：`artifact_lineage` 新增 `check`/`source_status`（current/stale/missing/unknown，逐来源明细）与多来源 `record(sources=...)`（分镜/资产/台词/模型配置等角色）及只读 `affected` 影响清单与显式 `adopt`；`source_available` 语义保留但改为派生（内容变只标过期、不隐藏、不改写用户成品，仅 missing 才隐藏）；剧本/分镜目录对过期项显示「原稿已变更／来源已变更」；新增账本 10 条＋目录回归 1 条，覆盖结构/分镜/首帧/白模/音频/剪辑六类，定向 136/136、架构 312/312、默认冒烟 8/8，0 红；1342−1341<5 本轮不跑全量。
