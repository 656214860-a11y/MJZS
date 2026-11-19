# R3752 结果：L1 任务书轮 I22 —— L4 试点二：预测性预加载
<!-- round-evidence: {"commit_base": "bfd577f8", "credential_hits": 0, "evidence_sha256": "4c33b70684c607d2", "exit": 0, "failed": 0, "passed": 44, "round": 3752, "tests": "run_selftests.py -k test_autotune_prefetch test_asset_thumbs"} -->

## 三问

- 轮型：§3.7 性能／资源轮（L1 任务书轮 I22）。
- 测试：任务书定向 `run_selftests.py -k autotune_prefetch asset_thumbs startup_budget desktop_startup_perf`＋默认冒烟＋架构门禁（结果见下「验证」）。
- 欠账：新增 `infra/prefetch.py` 已登记行/分支覆盖基线与下限表（实测 90.0% 行、80.0% 分支）；无新欠账。

## 变更

- `infra/prefetch.py`（新，L1）：预测性预加载唯一闸门。
  - `schedule(fn, *, snapshot=None, active=None, label='prefetch')`：三闸——关闭开关 `data/autotune_disable_prefetch.flag`、可用内存占比 < 10%（`resources.snapshot()`，`'unavailable'` 不阻断）、`active()` 用户活跃探针；过后 `executors.submit('io')` 低优先级执行，`QuotaError` 静默放弃（可再生优化，失败无损失）。
  - `warm_files(paths, *, reader=None)`：预取任务体——显式清单逐文件读入 `file_cache`／系统页缓存；`.json` 走 `read_json`、其余 `read_text(errors='replace')`；单文件失败跳过继续；不递归不造路径（规则 33），路径由调用方给。
- `ui/asset_thumbs.py`（接入点，一处）：`prefetch_media` 登记封面任务后把本批源文件投 `prefetch.schedule(warm_files)`——worker/ffmpeg 与下次翻页读命中页缓存；`master`/Tk 一律不进后台。
- `tests/test_autotune_prefetch.py`（新，9 条）：三闸各门独立断言（I22-2 注入资源快照）、io 池与 label 断言、QuotaError 降级、warm 计数与缺失跳过、暖层零磁盘读（`Path.read_bytes` spy）、reader 注入（下一阶段模板/SKILL 文件同机制）。
- `tests/architecture/_layers.py`：L1 登记 `prefetch`；同层边 prefetch→executors/file_cache/resources。
- `维护记录/覆盖率基线.json`：673 模块 / 91 覆盖（新增 infra/prefetch.py 45/50 = 90.0%）。
- `维护记录/分支覆盖率基线.json`：103 模块 / 2996 决策点（新增 prefetch.py 10 点 8 覆盖 = 80.0%）；`分支覆盖率下限.json` 登记 80.0。
- `architecture.md`／`PROJECT_MAP.md`／`runbook.md §11`：登记与口径数字同步。

## I22 验收对照

- **I22-1**：接入点在面板打开／导入完成的既有调用点（窗口可交互之后），warm_files 只接显式路径清单、零递归扫描；`test_startup_budget`／规则 33 守卫随定向命令验证。
- **I22-2**：`snapshot` 注入低内存→不调度、`active`→不调度、flag 文件→停用、`'unavailable'` 不阻断——4 条闸门面断言全绿。
- **I22-3**（取证 A5）：40 个阶段 JSON 文件，`file_cache.read_json` 冷读 441.2ms → 预热后二次读 7.03ms/轮（**63×**）；file_cache 层命中零磁盘读（spy 断言）。改善显著，默认启用；回滚放 `data/autotune_disable_prefetch.flag`。

## 验证

- 定向：`tests.test_autotune_prefetch` 9/9 绿（unittest 直跑）。
- 任务书命令 `run_selftests.py -k autotune_prefetch asset_thumbs startup_budget desktop_startup_perf`：62 条 0 红（隐藏桌面）。首轮曾 1 红——`test_prefetch_media_only_queues_media_files`：io 池 warm 任务在临时目录清理时持有 clip.mp4（WinError 32，真实竞态）；§2.4 同步测试对 `_prefetch.schedule` 打 spy（原断言不动，新增调度断言），复跑全绿。
- 默认冒烟：9/9 绿。
- 架构门禁：573 条 1 红——`test_site_packages_whitelist`（共享运行环境被其他车道装入未注册 pydantic 系 5 包，R3564/R3696 同录环境性分裂，与本改动零因果）；test_layers、coverage_baseline、branch_coverage_floor 全绿。
- 全量：分支欠账累计未达 8 源码轮阈值，不触发；master 合并轮按既有机制后台补跑。

## 提交

- （提交后回填）
