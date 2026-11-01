# R1694 功能轮（源码轮）：「采风」入口上线——Search／Fetch 在应用里真正可点

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（源码轮）。把已在 R1691 落地的 Search／Fetch 能力接到**用户能点的入口**上：剧本准备页新增「采风」按钮，填对标剧名（或留空按简报题材找方向）→ 写采风请求 → 后台跑 `recon.card` → 落《对标情报卡》。按 §2.7 先补 `docs/`（REQ-S01-46／47、DES-S01-43）再写代码。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；受影响冒烟 **9/9**；`tests/test_recon_service.py` **38/38**（新增 9 条：请求读写／目标优先级、入口五种情形、结果汇报三态）；真机端到端 1 次（见 C）。架构门禁结果见 D 节。
3. **project_status.md 的欠账少了吗？** 没有减少；本轮改源码（含一个 L4 页面），全量欠账 **1/8**（上一轮由修好的后台通道清零），未命中 §5 的升级条件。

## A 为什么还要做这一轮

R1691 把能力落在了「工具 + 服务」层，R1692 用真机修了缺陷，但**③ 对标爆款没有给用户填对标对象的入口**：`recon.card` 只能从调用方上下文或手写 `input/recon_request.json` 拿到剧名。也就是说接口通了、链路通了，但用户在应用里点不到。本轮补的就是这一步。

考虑过的两条路：

- **加成制作锁**（`script_contract.PRODUCTION_LOCK_DEFINITIONS` 加 `recon_target`）：会同时改 `总控.json` 的锁清单（指纹一变触发全 stage 自动同步）、`test_script_contract_production_locks` 的 11 项断言，属于契约层连锁改动，收益与风险不匹配 → **放弃**。
- **页面入口 + 请求文件**：只动 L4 一个方法组 + L2 两个读写函数，不碰 L0 契约、不碰总控指纹 → **采用**。

## B 改动

- **L2 `recon_service`**：新增 `REQUEST_NAME`／`request_path()`／`save_request()`／`load_request()`——采风请求的**唯一读写口**（`save_request` 走 `agent.core.save` 原子发布）。
- **L4 `desktop_writing_page.WritingPageMixin`**：
  - `collect_recon()`：查素材来源 → 不是③④就用通知说明并停（不弹错误框）→ `askstring` 问剧名（留空＝④按简报题材）→ `save_request()` → `self.async_(work, self.recon_done, label='采集对标情报')`。页面**不联网、不写卡片**；`ToolNeedsInput` 在 `work()` 内转成 `{'needs': …}`，不变成异常弹窗。
  - `recon_done()`：状态栏汇报「N 个来源、还有没查到的几条、机检待处理几条」，并指路卡片位置。
  - 页脚新增 `self.recon_button`（`SecondaryButton`，`side='right'`，走 `SCRIPT_ACTION_WIDTH`／`SPACING` 令牌，无魔法数字）。
- **`skill_tools._recon_request()`** 改为委托 `recon_service.load_request()`，去掉页面侧与工具侧的两份读取逻辑（一个动作一个入口）。
- **文档**：REQ-S01-46（③④ 有采风入口、后台执行、跳过与缺对象不阻断）、REQ-S01-47（请求只有一处表达）；DES-S01-43。

## C 真机端到端（页面入口 → 联网 → 落盘）

用 `WritingPageMixin.collect_recon` 的真实代码路径跑了一次（假页面只替掉 Tk 与状态栏）：

```
状态栏: 正在采集公开情报（联网检索，约十几秒）…
请求文件: 01剧本准备\input\recon_request.json {'material_source': '对标爆款', 'name': '短剧 都市情感', 'question': '这部剧怎么成的'}
排队任务: [('采集对标情报',)]
工具返回: {'ok': True, 'sources': 19, 'problems': [], 'skipped': None, 'needs': None}
完成后状态栏: 采风完成：19 个来源，还有没查到的 1 条；卡片在 01剧本准备/input/recon_card.json
卡片: 01剧本准备\input\recon_card.json | sources = 19 | schema = 1
人读版存在: True
样例来源: [('T1', '弃他如风'), ('T2', '朝花夕拾'), ('T2', '霸总不再一掷千金…')]
```

即：入口 → 请求 → 后台 → 联网 → 卡片（JSON＋MD）→ 状态栏全部打通，`problems=[]` 表示机检干净。

## D 验证

| 项 | 结果 |
| --- | --- |
| 默认冒烟 | **8/8** |
| 受影响冒烟（`recon_service skill_tools`） | **9/9** |
| `tests/test_recon_service.py` | **38/38** |
| `tests/test_ui_writing_recon.py`（新增，真窗口构建） | **1/1**：页脚确有 `采风` 按钮、文案对、非禁用、与质检那组同栏；两处 `skipTest` 已按 `PLATFORM_TKINTER` 登记进 `维护记录/skip台账.json`（ordinal 1／2，`test_skip_hygiene` 通过） |
| 架构门禁 | **368/368**（首跑 3 红：①`第三项` 判 `save_request` 裸写正式路径 → 改成与 `save_card()` 同一的注入写法；②轮次连续性（结果 1694 已存在、轮次头仍 1694）→ 置 1695；③`test_function_size_ratchet`：`writing` 556 行 > 上限 554 → 把页脚「质检／采风」四个按钮抽成 `build_script_quality_buttons()`，`writing` 回到 553 行，上限未调大） |
| 真机端到端 | 1 次，19 个来源、0 机检问题、JSON＋MD 均落盘 |
| 真机 GUI 探针（真实 `Desktop` 窗口） | `recon_button 存在=True／文案=采风／已布局=True／可点=True`；页脚实测顺序：`发送、阶段配置、中断、刷新、删除、下载文件、添加剧本、剧本目录、查看质检报告、质检目录、采风` |

### 首跑三红都不是「把断言改掉」

- **第三项棘轮**：`recon_service.save_request()` 原来直接调 `core.save(...)`，被扫成「L2 未注入发布器写正式路径」。按项目自己的写法改成 `(save or core.save)(target, …)`（与同文件 `save_card()` 一致），保留注入点、不留裸写回退——**没有登记豁免、没有抬 pending 基数**。
- **函数行数棘轮**：`writing()` 只许下降，我加按钮让它 554→556。没有调上限，而是把页脚右侧四个按钮（质检报告／质检目录／采风）抽成 `build_script_quality_buttons()`：`writing()` 553 行，创建顺序与原来逐字一致（截图外的顺序语义有注释钉住）。
- **轮次连续性**：本轮结果文件出现后状态页轮次头要 +1，属 §7 收尾动作。

## E 未验证／边界

- **按钮已在真窗口里构建验证**（`tests/test_ui_writing_recon.py` 构建真实 `Desktop` 并断言存在／文案／非禁用／同栏），但**没有在运行中的应用实例上用鼠标点过**：本轮没重启用户正在跑的助手，也没做截图目视。
- 页脚靠右那组由「添加剧本／剧本目录／查看质检报告／质检目录」变成再加一个「采风」，窄窗口下这排按钮是否换行未目视确认。
- 采风仍是**手动触发**：没有做成「选了③④就自动跑」。自动跑会带来不可预期的联网与计费，先保持用户显式点击。
- ④ 的方向词仍取自简报「故事题材」；简报没填时会提示「需要先给出对标对象」，不瞎猜。
- 未做 S3（平台规格／模型版本巡检），口径与 R1691 一致。

## 提交

（见收尾提交。）
