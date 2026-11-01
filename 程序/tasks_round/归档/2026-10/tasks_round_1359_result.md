# R1359：O34 交付包可独立检查，剪映交接能力如实标注

类型：功能轮（§3.1；本项为「建议」→ 实现＋回归）。承接 R1267 清单 O34（O01—O33 已完成）。中央轮次 1359（在干净 master 工作树 `o07-fullsafe-master` 领取）。本轮非五轮全量欠账点，按 O06—O48 验证策略默认只跑定向＋关联＋架构＋默认冒烟。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k test_handoff_bundle test_handoff_service` 16/16（其中新用例 9 条）；关联 `-k test_copy_rules` 14/14＋`architecture.test_handoff_publication_boundary` 4/4（合计 34/34）、`-k test_ui_edges` 115/115、`-k stage_execution stage_completion final_viewer handoff delivery skill_tools engine_probe` 107/107；架构门禁 `--layer architecture --all` 312/312；默认冒烟 8/8；全 0 红。
- 欠账：O34 关闭，清单剩 O35—O48；1359 − 1356 = 3 < 5，且未命中 §5（未改启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表），本轮不跑全量；下一欠账点 1361。

## 目标（R1267 清单 O34）
- 依据：`handoff_service.py` 输出有序媒体、JSON 与说明，明确不是剪映原生草稿；交付导入/完成的缺口见 O02/O03。
- 建议：交付包列成片、字幕、音频、来源版本、技术 QC、人工结论、许可资料、摘要及缺项；增加离线包完整性校验；需要 NLE 可编辑时间线时单列格式适配功能，不改名冒充已有原生草稿。
- 验收：在另一目录解包仍能验证；缺视频/字幕、被改文件、漏镜头会失败；只交接媒体时界面如实写「素材交接包」。

## 实现（`handoff_service.py`，L2）
- 新增 `BUNDLE_MANIFEST_NAME='交接包清单.json'`／`MEDIA_PACKAGE_KIND='media'`／`MEDIA_PACKAGE_LABEL='素材交接包'`／`MEDIA_PACKAGE_NOTE`。
- `publish_bundle` 额外给出 `summary`（类型、标签、说明、镜头覆盖 `{included, expected, missing}`、是否带字幕、逐镜来源 `sources`＝镜头/文件/版本/验收/技术 QC/时长），随发布器一起交 L3。
- 新增 `build_bundle_manifest(summary, files, *, built_at=None)`：把事实与每个文件的大小＋sha256 汇成清单（清单不自列）。
- 新增纯函数 `verify_manifest(manifest, probe)`：按清单核对每个文件（在不在／大小／内容摘要），声明齐全却漏镜、声明带字幕却没有 `对白.srt` 都算缺陷；清单自己声明的缺项 `missing` 如实列出、不算失败（素材包允许缺镜）。全部只读、无 I/O。

## 实现（`stage_execution_service.py`，L3）
- `publish_handoff_bundle(..., summary=None)`：发布前把 `交接包清单.json`（含逐文件大小与 sha256、覆盖、来源版本、缺项）写进同一个原子成果包。
- 新增 `verify_handoff_bundle(folder)`：只读一个已解包目录——`file_cache.read_json` 读清单，`file_cache.file_digest` 流式核对每个文件，条目越界（`../`）或缺失一律报错；缺清单/坏清单如实返回原因。换目录解包也能验。

## 实现（`desktop.py`，L4）
- 后期页新增「校验交接包」按钮：选任意已解包目录 → 后台 `verify_handoff_bundle` → 状态栏报「校验通过（含声明缺镜）」或逐条缺陷。
- 页面说明补一句「素材交接包只给有序视频与字幕，不是剪映草稿，可用『校验交接包』离线核对」；交接包内 `导入剪映说明.txt` 原有「这是素材交接包，不是剪映草稿」保留，未改名冒充剪映原生草稿。

## 验证
- `tests/test_handoff_bundle.py`（新）9 条：清单记录文件（大小/sha256 与磁盘一致、清单不自列）＋覆盖＋来源版本；完整包离线校验通过并如实报声明缺镜；文件缺失／被改（同长度）／被截断（变长）三种都失败；清单条目越界（`../evil.txt` 即便真实存在也拒）；缺清单／坏清单报错；纯规则：声明齐全却漏镜失败、声明缺镜不算失败、声明含字幕却无 `对白.srt` 失败、空/坏清单失败。
- 更新 `tests/test_ui_edges.py` 三处「自动交接包目录内容」断言：新增 `交接包清单.json`（包内多一份离线清单，属有意契约变更；其余文件与行为断言未动）。

## 边界
- 清单只证明「文件与清单一致」与「覆盖声明自洽」，不证明模型内容正确，也不替代人工审核；素材包允许缺镜（`missing` 如实列出），只有「声明齐全却漏镜」才算失败。
- 成片、许可资料属交付（delivery）阶段，不在素材交接包内；本轮不新增 NLE（剪映）原生草稿格式适配，只如实标注「不是剪映草稿」。
- `verify_handoff_bundle` 返回普通 dict（只读诊断），不是 service_contract 结果；发布路径仍走 `publish_stage_*` 唯一发布器。
- 台账：`stage_execution_service.py` 新增代码使 3 处裸 `json.loads` 行号平移（1040→1044、1071→1075、1087→1091），已同步 `维护记录/架构统一基数.json` 第四项；未新增豁免／`skipTest`／顶层模块／L2 直写／动态导入；`desktop.py` 唯一 TODO 仍在 2753。
- 未实发模型请求、未重启应用、未真实点击界面（`test_ui_edges` 的 Tk 用例除外，已在主树通过）。主树 `desktop.py` 为 LF 与 `.gitattributes` 钉的 CRLF 不符属既有环境项（干净工作树 CRLF、`test_line_endings` 16/16 绿），与本轮无关。
- 未命中 §5：`handoff_service`（L2）、`stage_execution_service`（L3）、`desktop`（L4）均在分层表内。
