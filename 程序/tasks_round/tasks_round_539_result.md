# R539 性能/资源轮结果

日期：2026-09-29  
范围：仅 `skill_registry.py`、其注册表回归测试与状态/结果台账。

## 根因与修复

R538 的真实启动堆栈确认，自动打开项目期间，主线程经
`stage_config.synchronize()` → `Registry.canonical_id()` → `_fresh()` 进入
`skill_registry.py:363 Registry.files()`；旧实现每一次查询均 `rglob` 整棵
`skills/` 目录，文件级指纹缓存无法节省这次遍历。

本轮在 `skill_registry.py:358-390` 增加目录级内存缓存：

- `_directory_mtime_ns` 是 `skills/` 根目录的 `st_mtime_ns` 缓存键；每次查询只做一次根目录 `stat`。
- `_file_records` 保存已排序的 `(路径, 文件 mtime, 文件大小)`；`files()` 和 `fingerprint()` 直接从它构造结果，不再再次 `rglob` 或逐文件 `stat`。
- 根目录 mtime 改变（或首次缓存为空）才递归扫描并重建清单；`scan()` 随后继续复用原有 `_skills`、解析、校验及公开查询接口。

因此首次进程内扫描仍会建立一次清单；稳定目录下的后续 `getAll()` / `getById()` / `canonical_id()` 不再重复全树遍历。未改 SKILL 文件格式、注册表外部接口或其他业务模块。

## 覆盖与耗时

新增 `tests/test_skills.py:183-204`：先完成首次扫描，再拦截 `Path.rglob`；连续 `getById()` 与 `getAll()` 必须不调用递归扫描。既有热加载测试仍覆盖根目录新增文件后的失效重建。

同一项目内置 Python、`time.perf_counter()` 单进程实测（67 个 SKILL）：

| 情况 | 修改前 | 修改后 |
| --- | ---: | ---: |
| 首次 `getAll()`（建表） | 0.081 s | 0.046 s |
| 紧接一次稳定 `getAll()` | 0.019 s | 0.001 s |

首次扫描按设计仍需一次目录遍历；主要收益是启动调用链中随后所有注册表查询不再反复扫描。

真实 GUI 命令 `python -X faulthandler` 设置 10 秒超时后，超时栈仅为
`tkinter.__init__.py:1613 mainloop` → `desktop_launcher.py:17 launch` →
`app.py:1404`，已不含 `skill_registry.rglob`，即首个已定位的 10 秒启动卡点已消失。

## 验证

- 注册表定向回归：2/2 通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：94/94 通过（状态轮次台账更新后复跑）。
- `python smoke_test.py --affected skill_registry`：筛选键未匹配任何测试文件，实际执行 0 条并按门禁规则失败；这是当前筛选映射缺口，未把该假阳性写作通过，也未改用户限制之外的 `smoke_test.py`。

## 风险与后续

缓存失效依据是用户指定的根目录 mtime：常规在根目录增删 SKILL 会自动失效；若直接修改既有深层子目录中的文件而文件系统不传播根目录 mtime，可调用既有 `scan(force=True)` 立即刷新。用户侧仍应重启现有应用实例后复验截图中的白屏；本轮仅证明 R538 已捕获的注册表扫描卡点已移除。
