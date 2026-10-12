# R1355：O30 字幕估算轴与实际音频轴建立校准流程

类型：功能轮（§3.1；本项为「事实/建议」→ 实现＋回归，新增校准与校验，不改提交/发布判据）。承接 R1267 清单 O30（O01—O29 已完成）。中央轮次 1355。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k subtitle ui_edges skill handoff stage tts` 690/690；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O30 关闭，清单剩 O31—O48；1355 − 1351 = 4 < 5，且未命中 §5 升级条件，本轮不跑全量。上次绿全量 1351（tree c97c1336），下一欠账点 1356（O31 收口时补跑）。

## 目标（R1267 清单 O30）
- 依据：`subtitle_timing.py:35` 无明确时间时按镜头时长分配；界面已有「估算/草稿、需试听」提示。
- 建议：保留低成本估算，音频生成后增加按实际句长或对齐结果校准；保存字幕来源音频摘要和校准状态；对重叠、负数、非有限时间、越界明确报错。
- 验收：不同语速、停顿、插入静音、台词修改后不沿用错误时间；导出前列未校准句。SRT/ASS 多格式属于按需求扩展，不等于当前导出失败。

## 实现（`subtitle_timing.py`，L1）
- 抽出 `_shot_duration`／`_dialogue_rows`／`_clamp`，`timed_entries` 改为复用（行为不变：仍是**等分估算**）。
- 新增 `line_weight(text)`：按可见字符数（空白不计）计权重，至少 1。
- 新增 `calibrate_entries(episode, audio=None)` → `(entries, report)`：在每个镜头内按权重重排字幕轴——已标注时间的句子按作者给定、不重排；未标注的句子：给了真实音频秒数或 `(start, end)` 对齐区间就按真实值定位（计 `audio`），否则按句长权重分摊（仍计 `uncalibrated`）。真实音频合计超过镜头时长时整镜按比例压缩并记 `overflow`。`report` 含 `mode`（estimate／length／explicit／audio／mixed）、`calibrated`／`audio`／`uncalibrated`／`overflow`／`source`（条数、总秒数）与 `estimated`。
- 新增 `validate_entries(entries, total=None)`：非有限、负数、反向、重叠、越界一律 `ValueError` 明确报错（不静默修正）。
- 新增 `rows_from_entries(entries)`；`srt_rows(episode, audio=None)` 改为用校准轴渲染并先校验（返回仍为 `(rows, estimated)`）。

## 实现（`subtitle_export_service.py`，L2）
- `export_srt`：改用 `calibrate_entries`＋`validate_entries`，返回 `(target, report)`；成功后再把「字幕来源音频摘要＋校准状态」写成同目录 `字幕校准.json`（经同一注入发布器，失败只记 warning、不回滚 SRT）。
- `export_dialogue_script`：同样改用校准轴，返回 `(target, report)`。
- 新增 `pending_calibration(episode, audio=None)`：导出前列出仍未按音频校准的句子（只读）。
- 新增 `export_calibration(project_root, episode, *, publish, audio=None)`：写 `字幕校准.json`。

## 实现（`desktop.py`，L4）
- `subtitles()`／`dialogue_script()` 读取 `report` 后按状态提示：已按实际配音／作者标注校准就说清楚句数；仍是估算的就列出未校准句数与依据（句长／镜头时长）。`subtitle_rows()` 保持 `(rows, estimated)` 不变。

## 验证
- `tests/test_subtitle_calibration.py`（新）23 条：句长权重（空白不计、最少 1）；句长重排长句得更多时间；`audio` 秒数改成真实轴（mode=audio、estimated=False）；对齐区间取长度；缺音频句子列入 `uncalibrated`（mode=mixed）；音频超镜头记 overflow 且整镜压缩、不越界；已标注时间不重排（mode=explicit）；混合标注仍报错；改台词后不沿用旧时间；非字典空；`validate_entries` 对非有限／负数／反向／重叠／越界各自报错且正常轴通过；`srt_rows` 用校准轴；`pending_calibration` 列未校准句；`export_calibration` 写含 source 的 JSON；`export_srt` 同写 SRT＋校准 JSON；非法对齐被忽略回退、不产生坏时间。
- `tests/test_subtitle_export_service.py` 契约更新为 `(target, report)`（14 条保持通过）。
- 定向 `-k subtitle ui_edges skill handoff stage tts` 690/690；架构门禁 312/312（含 `test_subtitle_export_publication_boundary`）；默认冒烟 8/8；全 0 红。
- 台账：未新增裸 `json.loads`／L2 直写／未登记动态导入／顶层模块；未新增 `skipTest`；`desktop.py` 唯一 TODO 仍在 2753（本轮改动在 7200+ 行，未平移）。

## 边界
- 「实际音频轴」需要调用方给出每句真实秒数或对齐区间（`audio` 参数）；本轮未接自动取音频时长的探针（现有逐句配音清单不记时长、运行环境无 mp3 解码库），未给 `audio` 时退回**句长校准**并把这些句子记为「未校准」——是诚实标注，不是假装已对齐。
- 校准只重排时间、不改台词、不读盘；已标注作者时间的镜头不重排。
- 越界判定以全片总时长为准；重叠按全局时间轴相邻句判断。
- 未实发模型请求、未真实点击界面（导出页 Tk 用例经 `-k ui_edges` 渲染通过）；未改启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表。
