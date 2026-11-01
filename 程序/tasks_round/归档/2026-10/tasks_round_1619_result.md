# R1619 拆分 stage_execution_service.py，并修掉 R1608 引入的 save_bytes 回归（Q9 第二批）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第三批 Q9；Q9 第 2 个模块）。同一文件内顺带修复一处**既有回归**（见下）。
- 测试：定向单元 8 个模块（原先红的 5 个 + `test_local_video_settings_service`／`test_asset_detail`／`test_stage_wiring`）全部 exit=0；另外 10 个原本全量红的模块单跑 exit=0；架构门禁首跑 353/354，唯一失败项是"R1618 欠一次完整安全全量"的**账簿项**（须由 post-commit 后台全量写凭据）；默认冒烟 0 失败。
- 欠账：本轮改源码＋新增模块，`project_status.md` 全量欠账计数 +1，未清。

## ⚠ 本轮发现的既有回归（master 全量是红的，不是本轮引入）

后台自动全量的落盘结果 `.git/auto-full-safe-result.json`（head `a0aa441`＝R1618，finished 2026-10-17T00:31:51）显示 **returncode 1、22 个模块红**；`logs/auto_full_safe.log` 末尾给出根因：

```
return {'publish_json': save, 'publish_bytes': save_bytes,
                                           ^^^^^^^^^^
NameError: name 'save_bytes' is not defined
```

**根因**：`2eb8393 R1608` 为了给 `collect_download_inbox` 换成流式 `save_file(target, source)`，把 5 处 `from agent.core import save, save_bytes` 机械改成 `save, save_file`，其中 **4 处函数体里仍在用 `save_bytes`、且根本没用 `save_file`**：
`local_video_settings_gateway`、`asset_plan_gateway`、`tts_gateway`、`storyboard_gateway`。R1608 只跑了架构门禁＋冒烟，没跑单元／全量，因此没被发现；此后 R1609–R1618 也都没跑全量，回归一直挂在主干上。

**修复**（各一行，恢复 R1608 之前的导入；`save_file` 仅 `collect_download_inbox` 真用，其余 4 处去掉）：

| 函数 | 现在 |
| --- | --- |
| `local_video_settings_gateway` | `from agent.core import save, save_bytes` |
| `asset_plan_gateway` | `from agent.core import save, save_bytes, save_text` |
| `tts_gateway` | `from agent.core import save, save_bytes` |
| `storyboard_gateway` | `from agent.core import save, save_bytes`（`save_bytes_new` 保留） |

**修复验证**（逐模块单跑，75 秒超时）：全量红名单里 18 个模块已 exit=0——`test_stage_copy_on_write`、`test_assets`、`test_asset_detail_service`、`test_asset_resume`、`test_core`、`test_local_video_settings_service`、`test_asset_detail`、`test_stage_wiring`、`test_request_recording`、`test_static_names`、`test_asset_gating`、`test_workflow`、`test_page_cache`、`test_timers`、`test_final_page_loading`、`test_final_viewer`、`test_storyboard_page_loading`、`test_desktop_compact_layout`。剩 4 个（`test_manual_gate`、`test_perf_baseline`、`test_row_targets`、`test_ui_edges`）在本会话 50 秒内不结束，日志停在 `pet_cloud.py:2099 已忽略 TclError: invalid command name ...` 的 Tk `after` 回调噪声上——与本轮改动无关的**会话级 GUI 限制**（同一限制下 `test_idea_chat`／`test_idea_inline_brief` 在含本轮改动之前的工作树里同样超时）。这 4 个模块另需一次真实全量来定性。

**结论口径**：本轮不能声明"全量已恢复绿"。能声明的是"已定位并修复唯一的确定性根因，且 18/22 红模块单跑转绿"。完整全量以 post-commit 后台跑出的凭据为准。

## 拆分

| 文件 | 行数 | 说明 |
| --- | --- | --- |
| `stage_execution_service.py` | 1677 → **1405** | 保留其余 L3 编排与网关 |
| `stage_publication.py` | 新增 **127** | "校验→原子发布→索引更新"发布契约、中断事务恢复、`projects` 网关 |
| `stage_write_preparation_service.py` | 新增 **129** | 首次修改前复制历史成果、旧编号路径重定位 |
| `stage_download_inbox_service.py` | 新增 **83** | 下载收件箱登记与收回 |

- 三个新模块登记为 **L3**（`_layers.py`）并写入 `architecture.md` §3 L3 行；`test_module_size_ratchet` 中 `stage_execution_service.py` 的 1700 上限**删除**（现 1405 行）。
- 拆出的 15 个顶层名按原名转发，`git show HEAD:…` 对照旧文件顶层名 163 个，缺失 0；`publish_stage_text` 等仍是同一函数对象（`is` 相等）。
- 三个新模块互相不依赖，也不反向依赖 `stage_execution_service`（否则成环，`test_no_circular_import` 会拦），这是选块的硬约束：只搬"不依赖本模块其它函数"的叶子块。

## 诚实边界

- 本轮只拆了 1 个模块；`pet_cloud.py` 2137、`desktop.py` 2259、`skill_panel.py` 1886 仍超限，`print` → `app_logging` 未动。
- 后台全量凭据落在**提交后的树**上；本轮工作树（未提交）与凭据树不同，故门禁首跑出现"欠一次全量"。这不是代码问题，但也不能拿它当"全量已通过"。
- "18/22 单跑转绿"是**逐模块**结果，不等于组合跑或全量跑绿；组合跑在本会话里被 4 个 GUI 模块拖住。

## 下一项

Q9 第 3 批（拆 `skill_panel.py` 或 `pet_cloud.py`），随后 `print` → `app_logging`。