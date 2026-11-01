# R1310：结构治理轮（执行）——剧本启发式判断拆成 idea_script_heuristic

类型：结构治理轮（执行子场景，拆职责、不加功能）。中央轮次 1310。来源为用户直接指定的执行条目"拆分 5：剧本启发式判断"。

## 三个必答
1. 本轮属于 §3 哪种类型？——§3.3 结构治理轮，执行子场景。
2. 测试跑了吗？三个基线过了吗？——跑了。定向 169/169、0 个文件有红；默认冒烟 8/8 加门禁 1 项＝通过 9、失败 0；架构门禁 312/312。全量未跑（纯 L2 搬迁，无五轮差、无升级项）。
3. project_status.md 的欠账少了吗？——未新增欠账，也未清偿既有欠账。

## 实现
- 新增 L2 `程序/idea_script_heuristic.py`：`SCRIPT_MARKS`、`SCRIPT_MIN`、`looks_like_script()` 原值原语义搬移；判定门槛（300 字 ＋ 至少两个剧本要素）与提示注释不变，纯文本判断，不读文件、不发网络、不碰 Tk。
- `程序/idea_chat.py` 删除这三处定义，改为 `from idea_script_heuristic import looks_like_script` 静态重导出，界面与既有测试仍可走 `idea_chat.looks_like_script`。
- `程序/desktop.py` 的 `update_script_download_button()` 与 `download_script()` 改从新模块导入 `looks_like_script`，调用方式（参数、返回值用法、报错文案）未动。
- 新增 L2 模块登记：`tests/architecture/_layers.py`；`architecture.md` 的 L2 模块表与"维护边界"新增 R1310 条目。

## 范围与调用方核验
- 生产调用方核验：`rg "looks_like_script|SCRIPT_MARKS|SCRIPT_MIN"` 命中生产侧仅 `desktop.py`（2 处）；`SCRIPT_MARKS`／`SCRIPT_MIN` 无其他消费者，只被 `looks_like_script` 内部使用。与用户"唯一调用方 desktop.py"的口径一致。
- 测试侧 `tests/test_idea_chat.py` 有 4 条断言经 `idea_chat.looks_like_script` 调用；按用户要求断言未动，因此保留 `idea_chat` 静态重导出。
- 生产模块改动 3 个（`idea_chat`、新增 `idea_script_heuristic`、`desktop`），符合 §3.3"每次最多改 3 个模块"。另有分层登记、架构文档与门禁台账更新。

## 门禁台账同步（架构门禁要求，非功能改动）
- `维护记录/架构统一基数.json` 第一项：新增 L2 模块必须登记范围记录，`idea_script_heuristic` 加入 `exempt_items`（与 `idea_chat` 同组，纯文本判断、零数据读写），`exempt_count` 35→36。
- `维护记录/TODO注释快照_20261003.json`：`desktop.py` 因新增 2 行 import，快照中 `desktop.py:2748`（`_tick_async_result` 的既有说明性注释）行号顺移为 2750；仅更新行号，注释文本与处置结论未动。核对方式为按注释原文在当前文件重新定位，唯一命中后才改写。

## 验证
- 定向：`smoke_test.py --affected idea_chat idea_script_heuristic desktop` → 9 个匹配测试文件、169 条用例、85.2 秒、0 个文件有红；默认冒烟 8/8 加门禁 1 项，合计通过 9、失败 0。
- 架构门禁：`smoke_test.py --architecture` → 312/312 OK（含分层登记、无环依赖、L2 范围记录、注释快照、统一棘轮）。
- 首次架构门禁曾红 2 项（L2 范围记录缺登记、注释快照行号未同步），按上述台账同步后复验转绿；两项均为本轮新增模块／新增行的必然联动，不是放宽断言。
- 未跑全量：改动属 L2 纯搬迁，本轮无"轮次号 − last_full_safe_all_round ≥ 5"，也无启动路径、Tk 控件生命周期、删除语义、`_layers.py` 之外的层级表改动，按 §5 不触发全量。

## 自审（§4.2）

## 收尾提交
- 已提交；轮次类型：结构治理轮。提交首行：`R1310: 轮次类型：结构治理轮——剧本启发式判断拆成 idea_script_heuristic`。
- 提交后 HEAD 的 commit hash 记录在 `project_status.md` 的 R1310 条目；工作树因预提交门禁（只有 master 可提交 `project_status.md`）不把状态页并入本提交。
1. 验收：新模块落地、命名体现职责、L2 同层、`idea_chat` 删除定义并保留必要 re-export、`desktop` 只改 import 来源、断言未动、定向与门禁按 §5 全绿——均达成。
2. 范围：生产模块 3 个，未超上限；未改其他函数、未改用户数据。
3. 验证：定向与架构门禁为本轮实测绿；全量未跑并已注明，未冒用历史凭据。
4. 新问题：新模块仅依赖标准库，位于 L2 且不 import 更高层，无反向依赖、无环；`idea_chat` 对新模块为单向依赖。两处入口（`idea_chat.looks_like_script` 与 `idea_script_heuristic.looks_like_script`）为迁移期兼容而保留，已在架构文档记录。
