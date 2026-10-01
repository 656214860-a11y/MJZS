# CRUD 与路径审计报告（2026-09-26）

## 范围与方法

静态扫描程序根的 Python 业务模块，检查 `write_text`、`write_bytes`、原子替换、`unlink`、`rmtree`、`rename` 及阶段路径调用；再以定向单元测试验证已修复链路。未读取或修改任何用户项目内容。

## 关键调用链

| 业务 | 入口 | 写入/删除边界 | 当前状态 |
| --- | --- | --- | --- |
| 剧本准备 | `desktop.py` → `writing_api.reply()` → HOLLMWOOD | `project_stages.writing()`；旧 `writing/brief_complete.json` 只读兼容 | 已修复 |
| 剧本结构 | `script_contract.py` / `stage_exec.py` | 原子替换结构剧本 | 已有原子写入 |
| 初步分镜 | `storyboard_selection` → `storyboard_files` | 当前 `03初步分镜`；旧 `storyboard` 只读兼容 | 已修复签名与媒体根 |
| 分镜定稿 | `storyboard_final` → `storyboard_lifecycle` | 原稿备份至回收站后退役 | 已修复当前阶段目录 |
| 资产参考图 | `asset_reference_images` / `asset_batch` | 解绑与重复中间图进回收站 | 已修复 |
| 自动维护 | `desktop` 关闭 → `storage_maintenance` | 历史和过期输出进回收站 | 已修复 |
| 配音／后期／交付 | `desktop.py` / `app.py` / `engine.py` | `project_stages.audio()`、`subtitles()`、`editing()`、`delivery()`、`exports()` | 已收口当前新写入 |

## 统一路径规则

1. 新写入只认 `project_stages.py` 的当前阶段目录。
2. 旧 `writing/`、`storyboard/` 仅在明确的历史读取分支中兼容；不得创建新副本。
3. 用户可见成果删除默认进入 `<项目>/工作流任务/回收站/自动维护_时间戳/`，批次中有 `恢复位置.json`。
4. 临时缓存、缩略图、失败任务台账可按其模块生命周期清理；不得冒充用户成果。
5. 所有项目路径必须拒绝项目外、软链接与联接点目标。

## 已确认问题与复现

| 编号 | 问题 | 复现方式 | 处理 |
| --- | --- | --- | --- |
| P1-01 | HOLLMWOOD 原稿写旧 `writing/` | 新项目发送完整简报后查看输出 | 改写 `01剧本准备`，旧简报只读兼容 |
| P1-02 | 剧本列表显示新目录但删除校验旧目录 | 选择当前阶段剧本后删除 | 校验统一为 `project_stages.writing()` |
| P1-03 | 自动采用签名扫描旧 `storyboard/` | 新 JSON 写入 `03初步分镜` 后切全自动 | 签名与媒体根改为当前阶段 |
| P0-01 | 关闭应用自动维护永久删除历史 | 关闭后检查历史目录 | 改为回收并记录恢复位置 |
| P1-04 | 参考图解绑直接删除受管图片 | 解绑不共享参考图 | 改为回收，共享引用不动 |
| P1-05 | 定稿仅退役旧目录原稿 | 当前目录分镜完成定稿 | 当前/旧目录均识别并备份 |
| P1-06 | 旧阶段归位会创建第二套顶层目录 | 执行 `adopt_legacy()` 后检查项目根 | 旧标识改为只读别名，链接一律落到当前编号阶段 |
| P1-07 | 分镜自动去重直接删除相同工作稿 | 同一集写入两份相同分镜 JSON 后触发维护 | 规范副本保留，重复项移入回收站并写恢复清单 |
| P1-08 | 自动交接包更新直接覆盖上一自动包 | 自动交接包第二次生成 | 上一包与中断暂存包均先移入回收站，再替换 |
| P1-09 | 资产导入同目录重名时直接删除原图 | 在项目资产目录选中非规范名称图片并导入同一资产 ID | 成功导入后通过项目回收站保存原图；回收失败则保留 |
| P1-10 | 文档与契约检查仍以旧目录名为权威 | 查看项目地图或执行 `merge_problems()` | 项目地图改为 12 个当前阶段；兼容键先解析为当前目录 |
| P2-01 | 参考图软删除提示误称“找不回来” | 资产页删除已绑定参考图 | 提示和状态改为“移入回收站，可恢复” |
| P1-11 | 资产图片删除后只进历史版本，没有用户恢复入口 | 资产页删除登记图片后尝试恢复 | 增加“恢复删除资产”；仅恢复该 ID 最新历史图片，目标已存在时拒绝覆盖 |
| P1-12 | 分镜定稿后工作 JSON 复制备份再永久删除 | 当前 `03初步分镜` 原稿定稿成功 | 退役动作统一改为 `recycle_paths()`；回收失败则保留原稿 |
| P1-13 | 配音、后期、交付仍会新建旧英文顶层目录 | 生成配音、打开后期或自动粗剪 | 新写入统一为 `10配音与字幕`、`11后期剪辑`、`12质检交付/导出成片` |
| P1-14 | 自动标记、创意/参考脚本扫描和导入入口仍硬编码旧目录 | 自动粗剪、自动交接、导入 JSON、扫描创意脚本 | 均改为通过 `project_stages` 取得当前阶段目录；旧路径不再是新写入落点 |
| P1-15 | 项目接续上下文漏读历史剧本/分镜，且新资产目录未注入 | 打开仅含旧目录的项目，或用当前资产目录执行后续工作流 | 目录清单只读兼容旧路径；资产清单当前路径优先、旧路径回退 |

## 剩余风险与建议

- `stage_layout.py` 与 `project_stages.py` 仍并存，但 `stage_layout.paths()` 已把旧内部标识解析为当前编号阶段，避免产生第二套目录。后续可逐项将模块改为直接调用 `project_stages`，不宜一次性重写。
- `smoke_test.py` 的默认 `ROUND=10` 与状态记录轮次不一致，属于测试台账问题；建议下一轮按现有 `ROUND_CHECKS` 机制补登记本轮路径/回收检查后再更新默认轮次。
- `asset_resume.clear()`、缩略图和失败任务状态删除的是可再生缓存；仍应在模块文档中明确其缓存性质。
- `恢复删除资产` 只恢复资产目录内最近一份历史图；通用回收站中的资产仍需后续提供批次浏览/恢复界面。
- 历史项目的 `audio/`、`subtitles/`、`editing/`、`delivery/`、`exports/` 仍只读保留，尚未进行不可逆自动迁移；新写入不会再创建它们。
- 少数 UI 测试夹具仍直接构造旧 `episode/storyboard` 工作集，因此会被当前工作集校验主动拦截；应另开测试迁移任务，不能将该测试债务误判为用户项目数据故障。

## 根目录旧 Python 文件审计

未执行盲删。`stage_exec.py`、`background_characters.py`、`reference_wall.py` 分别由桌面页以动态导入调用；`engine_probe.py` 由默认 smoke 检查和专用回归使用；`previs_progress.py`、`blender_previs_template.py` 由白模预演链路读取；`app_shortcut.py` 是安装/快捷方式维护入口；`clipboard_lock.py`、`hash_backend.py`、`selftest_sandbox.py` 是现有测试或安全自检支撑。当前候选均仍有调用证据，因此本轮没有安全可删除的程序根 Python 文件。

## 本次验证

- 路径与剧本 API、自动采用：22/22 通过。
- 存储、资产参考图、资产批处理：87/87 通过。
- 定稿阶段兼容：5/5 通过。
- 默认 `smoke_test.py`：8/8 通过。
- 阶段布局、门禁、连贯性：58/58 通过。
- 分镜自动去重（旧/当前阶段路径及回收清单）：2/2 通过。
- 核心、阶段、门禁、连贯性与分镜回归组合：158/158 通过。
- 自动交接包路径：`py_compile` 通过，默认 `smoke_test.py` 8/8 通过。
- Round 131：剧本契约与阶段布局 62/62 通过；`smoke_test.py --affected desktop stage_layout script_contract` 9/9、默认 `smoke_test.py` 8/8 通过。
- 参考图提示修正：`desktop.py` 编译通过，默认 `smoke_test.py` 8/8 通过；定向 `--affected desktop` 无匹配测试文件，已记录为测试覆盖缺口。
- 资产历史恢复：`tests.test_asset_restore` 2/2 通过（恢复最新历史图、拒绝覆盖现有资产）；默认 `smoke_test.py` 8/8 通过。
- 分镜定稿退役：`tests.test_workflow.StoryboardLifecyclePathTests` 1/1 通过（当前阶段原稿进入统一回收站并保留恢复清单）；默认 `smoke_test.py` 8/8 通过。
- 阶段路径收口：`tests.test_project_stages` 1/1 通过（配音、字幕、后期、交付和导出均落在编号阶段）；编译 `app.py`、`desktop.py`、`engine.py`、`project_stages.py` 通过，默认 `smoke_test.py` 8/8 通过。
- 受影响模块门禁：修复 `tests/test_engine_probe.py` 将 `tests/` 当作程序根的路径错误后，23/23 通过；`smoke_test.py --affected app desktop engine project_stages` 9/9 通过，定向自检 88/88 通过。
- 二次路径核验：`tests.test_idea_chat` 56/56 通过；自动标记、导入入口、创意历史和参考脚本扫描均不再硬编码旧阶段目录；默认 `smoke_test.py` 8/8 通过。
- 工作流上下文兼容：`tests.test_context` 14/14 通过，当前资产目录优先、旧剧本/分镜仅读取兼容；默认 `smoke_test.py` 8/8 通过。
