# R560｜结构治理轮（子场景：执行）

## 来源与执行项

- 来源：`tasks_round/tasks_round_547_result.md` J 节。
- 执行：P1-7——为已迁移的 desktop／分镜／资产边界补静态架构门禁，禁止服务导入 Tk、禁止 view 直连进程/网络，并冻结允许的适配器入口。

## 完成结果

- 新增 `tests/architecture/test_migrated_ui_boundaries.py` 三项 AST 门禁：五个迁移控制器不可导入 `tkinter`；三个 UI 视图不可直接调用浏览器、socket、子进程或系统启动 API；`platform_tools`／`native_apps` 的允许导入入口为显式白名单。
- `desktop.py` 的短 TCP 端口探测及浏览器打开、`asset_batch.py` 的 Midjourney 浏览器打开改经 L1 `platform_tools`；`platform_tools.tcp_listener()` 保持原有短连接、不发 HTTP 请求的语义。
- 分镜视图没有直接进程/网络调用，现由同一门禁冻结；不改用户数据、阶段状态机、服务契约或页面功能。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `platform_tools.py` | 新增短 TCP 探测适配器。 |
| `desktop.py` | 以已登记平台适配器取代直接浏览器与 socket 调用。 |
| `asset_batch.py` | 以已登记平台适配器取代直接浏览器调用。 |
| `tests/architecture/test_migrated_ui_boundaries.py` | 新增三项静态边界回归。 |
| `AGENTS.md`、`architecture.md`、`project_status.md` | 同步门禁、基线和债务状态。 |

应用代码仅改动 3 个模块，符合本轮上限。

## 验证

- `python -B -m unittest tests.architecture.test_migrated_ui_boundaries`：3/3 通过。
- `python -B smoke_test.py`：默认冒烟 8/8 通过。
- `python -B smoke_test.py --architecture`：架构门禁 98/98 通过。

## 债务状态与自审

- P1-7 已完成；R182 可执行拆分债务由 9 项减至 8 项。P0-3 的既有二进制发布／分层阻塞不变。
- 通过：未改分层或对外契约，未新增功能；应用代码改动数为 3；无新增架构红点。
