# R1344：O20 保留 Animatic 强校验，并降低大媒体重复读取成本

类型：功能轮（§3.1；本项为「事实/建议」，本轮交付为实现＋回归＋实测）。承接 R1267 清单 O20（O01—O19 已完成）。中央轮次 1344。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k animatic file_cache` 41/41；锚定 `-k animatic_timeline stage_completion previs` 117/117；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O20 关闭，清单剩 O21—O48；1344 − 1341 = 3 < 5，且未命中 §5 升级条件（非启动路径／Tk 控件生命周期／删除语义／`_layers.py`），本轮不跑全量。

## 目标（R1267 清单 O20）
- 依据：`animatic_service.py:174` 已检查源摘要、成果摘要、镜头图与三项人工确认；`:183`/`:192` 原用 `read_bytes()` 整份读媒体再算 sha256。
- 建议：把此清单机制作为后段参考；摘要采用流式读取／受控缓存；界面继续显示草图／参考图、临时音频与正式媒体的区别；三项确认必须继续由用户产生。
- 验收：大项目内存有界；源／文件变化使确认失效；模型不得代签；性能收益需实测，不能仅凭文件大断言已卡顿。

## 实现
### 1）流式受控摘要（`file_cache.file_digest`）
- 新增 `file_digest(path)`：按 1 MiB 分块喂 `hashlib.sha256`，从不把整份文件读进内存；结果按 `(st_mtime_ns, st_size)` 缓存，未改动的大文件不重复计算；文件不可读时清掉该键并抛出。
- `clear()` 与 `invalidate(path)` 同步清理新缓存 `_DIGEST_CACHE`，与既有 `_CACHE`／`_TEXT_CACHE`／`_BYTES_CACHE` 同生命周期。

### 2）Animatic 强校验改用流式摘要（`animatic_service.evidence`）
- `evidence()` 对「源分镜」与「全体成果文件」的两处摘要比较，由 `digest(path.read_bytes())`（整份读入内存）改为 `file_cache.file_digest(path)`（分块流式）。
- 摘要算法与结果不变（仍是 sha256 十六进制），校验语义、错误文案、三项确认判据与「schema 变化 → 确认失效」全部保持原样；`digest()`／`validate_bundle`／`build_bundle` 未改。

### 3）强校验与「不得代签」保持不变（核对，未改）
- 发布前 `validate_bundle` 仍要求 `confirmed == {rhythm:False, duration:False, dialogue_sync:False}`——生成器发布时不得预置已确认；写 `confirmed=True` 的唯一路径仍是 L3 `stage_execution_service.confirm_animatic`，只由桌面「确认预演（SG-B）」的三个用户勾选框触发，模型／技能工具无写入入口。
- 页面文案继续区分「共享参考图／参考草图」「临时音频／临时 TTS」与「正式资产仍在线上生成」（`desktop.py` 的 animatic_page，本轮未改）。

## 验证
- 新增 `tests/test_file_cache.py::FileDigestTests` 2 条：`file_digest` 与 `hashlib.sha256(整份)` 结果一致，且第二次命中不再打开文件；文件内容变化后摘要刷新、`invalidate()` 后重算。
- 新增 `tests/test_animatic_service.py` 1 条：`build_bundle` ＋确认后，对 `.mp4`/`.wav`/`.png` 的 `Path.read_bytes` 打补丁使其抛错、并清空缓存，`evidence(root)` 仍返回 `(True, '')` → 证明成果校验不再整份读媒体。
- 既有强校验用例（源变化／成果变化／三项未确认 → 不就绪）不变，全部通过。

## 实测（性能收益）
- 在 64 MiB 媒体文件上对比（`tracemalloc` 峰值 + `time.perf_counter`，同一台机、同一文件）：
  - 旧法 `read_bytes()+sha256`：耗时 114.0 ms，峰值内存 64.1 MiB（≈整份文件）。
  - 新法 `file_digest` 冷算：耗时 118.7 ms，峰值内存 2.1 MiB（≈1 MiB 块 + 摘要对象）。
  - 新法 `file_digest` 命中（文件未改动）：耗时 0.211 ms，峰值 0.002 MiB。
- 结论：单次冷算耗时与旧法基本相当（都受 I/O 限制），但峰值内存从「随文件线性增长」降为「有界（≈2 MiB）」；同文件重复校验（页面重排、轮询、SG-B 复验）从「每次整份读＋算」降为一次缓存命中（本例约 540×）。收益为实测，不是「文件大所以卡」的推断。

## 台账
- 在 `file_cache.py` 中段插入 `_DIGEST_CACHE` 与 `file_digest` 使两处裸 `json.loads` 行号平移：`53→54`、`112→140`；已同步 `维护记录/架构统一基数.json` 第四项对应两条 `exempt` 登记，`-k unification_ratchet` 与架构 312/312 复验通过。
- 未改 `desktop.py`／`stage_execution_service.py`／`writing_api.py`，TODO 注释快照与其余台账未平移。

## 边界
- 摘要缓存按 `(mtime_ns, size)` 判定是否复用；同大小且 mtime 被刻意保留的替换文件不会被判失效——技术内容校验仍以 `file_digest` 冷算结果与 manifest 内 sha256 为准，缓存只复用「文件确未变」的重复查询。
- 仅把校验方式改为流式并加缓存，未改变 Animatic 阶段契约（SG-A/SG-B、13 阶段顺序、旧编号目录只读兼容、发布失败回滚均未触碰），故不触发 §5 全量升级条件。
- 未实发模型请求、未重启应用、未真实点击界面。

## 风险与边界
- 进程内内存缓存，仅在同进程内复用；崩溃或重启后需重新冷算一次（正确但不省）。
- 单次冷算收益有限（仍是全文件 sha256）；本项的确定收益是「峰值内存有界」与「未改动不重复算」，不是「校验变快很多」。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿；不在本轮修复。

[TASK_COMPLETE] 保留 Animatic 强校验并降低大媒体重复读取成本：新增 `file_cache.file_digest`（1 MiB 分块流式 sha256 + (mtime_ns,size) 缓存，clear/invalidate 同步清理），`animatic_service.evidence` 源分镜与全体成果改用流式摘要、不再 read_bytes 整份读媒体；三项人工确认与发布前「不得代签」（validate_bundle 要求 confirmed 全 False，写 True 只经桌面用户勾选）保持不变；实测 64 MiB 文件峰值内存 64.1→2.1 MiB、重复校验 114ms→0.21ms；台账第四项 file_cache.py 两处 json.loads 行号平移（53→54、112→140）已同步；新增 3 条用例（file_cache 2＋animatic 1），定向 41/41、锚定 117/117、架构 312/312、默认冒烟 8/8，0 红；1344−1341=3<5 且未命中 §5，本轮不跑全量。
