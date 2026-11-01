# R1343：O19 初稿和定稿采用增加差异与影响预览

类型：功能轮（§3.1；本项为「建议」，交付为实现＋测试）。承接 R1267 清单 O19（O01—O18 已完成；依赖 O18）。中央轮次 1343。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k adoption_impact storyboard file_cache row_targets workflow_context` 78/78；`tests.test_ui_edges.BatchContinuationTests.test_adopt_skips_adopted_without_confirm` 1/1（Tk）；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O19 关闭，清单剩 O20—O48；1343 − 1341 = 2 < 5，本轮不跑全量。

## 目标（R1267 清单 O19）
- 依据：`storyboard_catalog_service.py:147` 已有采用前整份验证，应在此基础上增强而非另建入口。
- 建议：采用前显示新增/删除/改动镜头，时长、对白、资产引用变化，以及将失效的首帧/视频；稳定镜头 ID，移动顺序不轻易换 ID。
- 验收：同一文件重排、删除镜头、仅改对白、替换资产分别生成准确影响清单；取消采用不改正式状态。依赖 O18。

## 实现
### 1）只读影响预览（`storyboard_catalog_service.adoption_impact`）
- 新增 `adoption_impact(context, paths)`：把候选分镜相对「同集已采用分镜」逐镜对比。基线按「同路径优先，否则同 `episode_id`」匹配；没有基线时全部镜头算新增。
- 逐镜用稳定镜头 ID 对比，输出 `added`／`removed`／`changed`（含具体字段 `duration`／`dialogue`／`assets`／`frame`／`video_prompt`／`title`）／`reordered`（顺序变化只报告、不换号）。
- 将失效媒体：删除或改动「首帧／资产／时长」的镜头，其已存在的首帧 PNG（`media_root(base)/shot['frame']`）列入 `frames`；其已生成过视频的镜头编号（项目 `data/state.json` 与 `cloud_video/*/data/state.json` 里 shots 非空的键）列入 `videos`。
- 汇总成一行中文 `summary`（`+n 镜／-n 镜／改 n 镜／重排 n 镜／n 个首帧将失效／n 段视频将失效`）。
- 全程只读：不改采用清单、不改资产、不删文件、不改镜头编号。

### 2）接线（不新建入口）
- L3 门面 `stage_execution_service.storyboard_adoption_impact(project, paths)` 注入项目上下文（追加在文件末尾，不移动既有 `json.loads` 行号）。
- L4 `storyboard_files.adoption_impact(project, paths)` 作为页面门面；「手动采用分镜」在 `check_adoptable` 之后、真正采用之前计算预览，把 `summary` 追加到状态栏（非阻塞、不弹窗，不影响无人值守 `adopt_pending` 路径）。
- 取消采用（不点采用／`storyboard_selection.remove`）不经过该预览写入，正式采用清单与文件都不变。

## 验证
- 新增 `tests/test_adoption_impact.py`（7 条）：同文件重排只报 `reordered`（added/removed/changed 为空且文件字节不变）；删除镜头 → removed=[SH001] 且首帧列入 frames、已生成视频列入 videos；仅改对白 → changed 字段为 `dialogue` 且无媒体失效；替换资产 → changed 含 `assets` 且首帧失效；改时长 → 首帧失效；无基线 → 全部 added（summary `+2 镜`）；预览对 ui_settings.json 与候选文件字节只读。
- 既有 Tk 用例 `test_adopt_skips_adopted_without_confirm` 仍绿：采用路径不弹窗、不重复采用、状态栏保留「新增采用 n 份／已采用 n 份分镜」。
- 既有 `check_adoptable` 采用前整份验证不变。

## 边界
- 预览只回答「与当前已采用分镜相比的变化」，不比较历史版本快照；同一路径内容变化也按同集基线对比（即使该路径已在采用清单里）。
- 视频失效以「项目／云端工作集任务状态里该镜头编号已有版本」为准，不解析具体视频文件路径（避免大目录扫描）。
- 未命中 §5 升级条件；未增删 `json.loads`（台账未平移）。
- 未实发模型请求、未重启应用、未真实点击界面（单个 Tk 用例除外，已在 Tk 下跑过）。

## 风险与边界
- 基线按 `episode_id` 匹配；同一集有多份已采用分镜时取第一个匹配，可能与用户期望的「上一版」不同。
- 首帧失效以 base 的 `frame` 指向的文件存在为准；用户手工挪动首帧文件会漏报。
- `reordered` 是逐位置比较，插入式重排会把其后所有镜头都算「重排」（语义正确，但计数偏大）。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿；不在本轮修复。

[TASK_COMPLETE] 初稿/定稿采用增加差异与影响预览：新增只读 `adoption_impact`（同集已采用分镜为基线，逐镜稳定 ID 对比 added/removed/changed/reordered，列出将失效的首帧 PNG 与已生成视频镜头），经 L3 `storyboard_adoption_impact` 与 L4 `storyboard_files.adoption_impact` 接线，在 `check_adoptable` 之后、采用之前把 summary 追加到状态栏（不弹窗、不改状态、不换号）；取消采用不改正式采用清单；新增 7 条预览用例，覆盖重排/删镜/改对白/换资产/改时长/无基线/只读，定向 78/78、Tk 采用用例 1/1、架构 312/312、默认冒烟 8/8，0 红；1343−1341<5 本轮不跑全量。
