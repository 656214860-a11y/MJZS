# R1401：UI 路线图 §一 第 2 项（设计 token）desktop.py 内联间距改用 SPACING

类型：功能轮（§3.1，UI 统一入口／设计 token；**零视觉变更**）。中央轮次：1401。范围＝设计 token 迁移中可证明零视觉变更子集的一页：`desktop.py` 内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改从 token 取值。该模块自 line 30 已 `from ui_tokens import COLORS, FONTS, SPACING, SCRIPT_ACTION_WIDTH, SCRIPT_ACTION_PADDING`，**无需新增 import、行数不变**。

## 三个必答
- 本轮类型：功能轮（§3.1）——1 个生产模块 13 处内联间距字面量等值改用 token；不改业务逻辑、字体、颜色。
- 测试：默认冒烟 **8/8**；架构 **341/341**；**命中 §5**（`desktop.py` 属启动路径，且 1401−1396=5）→ 干净 master 全量 **4983/4983、558.1 秒、0 红**。
- 欠账：无（本轮已按 §5 跑全量）。

## 实现（等值提换，零视觉变更）
- 13 处内联标量 `padx/pady`（值∈{4,8,12,16}＝`SPACING` 既有档）改 `SPACING['xs'/'sm'/'md'/'lg']`：4→xs×2、8→sm×2、12→md×3、16→lg×6。
- 未新增 import（line 30 已含 `SPACING`）→ 行数 7498 不变、**无行号平移**、无需同步任何快照基线。
- 未动 hex：`desktop.py` 的 31 处内联色属旧调色板决策范围；其中 `#ffffff` 大小写等值会与 `test_idea_chat` 既有字面量断言（`cget('selectforeground')=='#ffffff'`）冲突，故一并留待调色板三选一。
- 保留不动：值非 token 的间距（1／2／3／5／6／18／22 等）与全部 tuple 间距。

## 验证
- 默认冒烟 `smoke_test.py`：**8/8、0 失败**。
- 架构 `smoke_test.py --architecture`：**341/341、0 红**（127.83 秒）。
- `test_token_boundary`：`desktop.py` 数字 `padx/pady` 计数 **40→27**（只减不增）。
- **全量（§5 必需）**：干净 master `o07-fullsafe-master`（reset→`a8a0803`）`run_selftests.py --all --safe` **4983/4983、558.1 秒、0 文件有红、ALL TESTS PASSED**；凭据 tree=`60d4e23d…`＝`a8a0803:程序`、round=1400（执行时最新已提交结果）、`last_full_safe_all_round` 1396→1400。

## 提交
- 内容：`a8a0803`（`desktop.py`）。
- 报告／状态／接力：本轮收尾提交。

## 复盘
- 已收口：`desktop.py` 可证明等价于 token 的 13 处间距（全站最大单文件 offender 的间距部分）。累计四轮已迁内联间距 71 处（R1396 13＋R1399 21＋R1400 24＋R1401 13）。
- **决策-free 子集基本耗尽**：全站内联标量 `padx/pady` 中仅剩 `agent/prompt_optimizer.py`（10 处，属 agent 层、须另评层级与 import）；全 0 值间距（`cell_hover.py`／`shared_video_controls.py`）不迁。
- 未做（理由）：hex（含 `desktop.py` 31 处）、103 处旧 `ui_theme` 调色板值、非 token 间距值、旧页面文字层级——全部需要用户先对设计 token 调色板决议（①改视觉／②零视觉补值／③暂不迁移）。本轮不擅自改视觉或引入大小写等值冲突。
- 下一轮候选：`agent/prompt_optimizer.py`（10）；或等调色板决议后统一推进 hex／旧色／文字层级。
