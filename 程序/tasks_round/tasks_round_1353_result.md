# R1353：O28 本地/云端任务统一可恢复状态与错误分类

类型：功能轮（§3.1；本项为「建议/验证」→ 实现＋回归，只做只读翻译与展示，不改提交/重投判据）。承接 R1267 清单 O28（O01—O27 已完成）。中央轮次 1353。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k video_task_status integration video ui_edges` 332/332；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O28 关闭，清单剩 O29—O48；1353 − 1351 = 2 < 5 且未命中 §5 升级条件（非启动路径／非 Tk 控件生命周期销毁重建／非删除语义／非层级登记表），本轮不跑全量。上次绿全量 1351（tree c97c1336），下一欠账点 1356。

## 目标（R1267 清单 O28）
- 依据：`engine.py:239` 已存 `local_request`／任务回执，下载中断可续取且不重生成；本地流程另有适配。
- 建议：统一提交中、结果不确定、排队、生成中、下载失败、技术不合格、待审核、已采用；错误区分鉴权、限额、模型协议、内容拒绝、网络和本机磁盘；显示下一步是查询、补配置还是显式重做。
- 验收：断网、超时、关窗重启、查询失败、下载失败、远端成功本机未落盘均不盲目重投；真实服务验收需另行受控执行。

## 实现（`video_progress.py`，L4）
- 新增只读 `task_status(version)`：一条版本只翻出一个统一状态码——`submitting`／`unknown`／`queued`／`running`／`downloading`／`download_failed`／`qc_failed`／`review_pending`／`adopted`／`failed`／`rejected`／`missing_file`。已下载版本再按 `file`／`qc_pass`／`review` 细分缺文件、技术不合格、待审核、已采用。
- 新增 `status_label`／`status_next`／`status_detail`：每个状态都有中文名与「下一步」（查询／补配置／显式重做／人工验收／无需操作）。
- 新增 `error_kind(text)`／`ERROR_LABELS`／`ERROR_NEXT`：只归七类——鉴权／限额／模型协议／内容拒绝／网络／本机磁盘／未分类；本机磁盘标记先判，其余复用 `pet_agent.classify`（纯规则、不联网），认不出明确给「未分类」。`status_detail` 对失败/不确定态再带上错误分类与可行动作。
- 现有 `display`／`summary`／`snapshot` 语义不变（`display` 仍按原 `LABELS`，避免影响进度条口径）。

## 实现（`engine.py`，L3）
- `poll` 取回失败分支记 `v['download_error']='下载中断；任务已成功，再次查询可续取，不会重新生成'` 并 `save`，仍抛同一条 `RuntimeError`；状态保留 `succeeded`，再查询即续取，不重新生成、不追加版本、不重投。

## 实现（`app.py`／`desktop.py`，L4）
- `app.py` 视频页镜头状态行（`update_progress` 兜底分支）改用 `status_detail(v)`：显示统一状态名＋下一步，失败/拒绝再显示错误分类与动作。
- `desktop.py` 交付页逐镜行在未采用的镜头上追加「下一步 X」（已采用镜头不追加，避免噪音）。

## 验证
- `tests/test_video_task_status.py`（新）13 条：原始状态映射；已下载按 QC/验收细分；下载失败独立态；八态中文名与下一步全覆盖；`status_detail` 带错误分类与动作；错误七分类（含本机磁盘优先、空串返回空）；不盲目重投（未完成/不确定态一律拦截，仅失败/拒绝/需修改可重提）；关窗重启后状态与 `local_request` 仍在磁盘。
- `tests/test_integration.py` 新增 `DownloadResumeTests`：第一次取回失败后只保留一个版本、状态仍 `succeeded`、`download_error` 已记、`charged` 保留；再次 `poll` 续取成功且仍只有一个版本（远端任务没被重发）。
- 定向 `-k video_task_status integration video ui_edges` 332/332；架构门禁 312/312；默认冒烟 8/8；全 0 红。
- 台账：未新增 `json.loads`／L2 直写／未登记动态导入／顶层模块；架构各棘轮全绿。`video_progress`（L4）复用 `pet_agent`（L4）为同层依赖，不越层。

## 边界
- 统一状态与错误分类是只读翻译：是否允许提交/查询/重做仍由 `video_task_state.submission_block_reason` 与 `engine`/`local_video` 的既有判据决定，本轮未改这些判据。
- 本地 ComfyUI 的取回失败当前与「质检未完成」共用同一条失败分支（`local_video` 未单独区分下载错误）；本轮只给云端 `engine.poll` 补 `download_error`，本地侧的下载/质检区分留待后续。
- 错误分类是启发式：命中不了供应商特异文案时明确给「未分类」，不伪造类别；`pet_agent.classify` 的 `server` 归入「网络」。
- 未命中 §5 升级条件（非启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表；`video_progress`／`engine`／`app`／`desktop` 均已在层级登记表内）。
- 未实发模型请求、未重启、未真实手动点击界面（视频页/交付页 Tk 用例已在 `-k ui_edges` 中渲染通过）。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿。

[TASK_COMPLETE] O28 本地/云端任务统一可恢复状态与错误分类：`video_progress` 新增 `task_status`／`status_label`／`status_next`／`status_detail`／`error_kind`（八态＋失败/拒绝/缺文件、七类错误、每态「下一步」），`engine.poll` 记 `download_error`（取回失败保留 succeeded、再查询续取不重生成），视频页与交付页显示统一状态与下一步；新增 13 条用例＋1 条下载续取集成用例，定向 332/332、架构 312/312、默认冒烟 8/8，0 红；1353−1351=2<5 且未命中 §5，本轮不跑全量。
