# R1402：UI 路线图 §一 第 2 项（设计 token）agent/prompt_optimizer.py 内联间距改用 SPACING

类型：功能轮（§3.1，UI 统一入口／设计 token；**零视觉变更**）。中央轮次：1402。范围＝设计 token 迁移中可证明零视觉变更子集的**最后一处**：`agent/prompt_optimizer.py`（承载设置页 Tk UI，非启动路径）内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改从 token 取值。

## 三个必答
- 本轮类型：功能轮（§3.1）——1 个生产模块 10 处内联间距字面量等值改用 token ＋1 处 import；不改业务逻辑、字体、颜色。
- 测试：定向 `test_unification_ratchet`＋`test_token_boundary` **8/8**、`test_todo_comment_snapshot`＋`test_coverage_audit_ratchet` 同批（行号同步后全绿）；默认冒烟 **8/8**；架构 `--architecture` **341/341**。
- 欠账：`1402−1400=2<5` 且未命中 §5（`prompt_optimizer` 非启动路径）→ **不跑全量**（最近绿全量 R1401 `tree=60d4e23d…`）。

## 实现（等值提换，零视觉变更）
- 10 处内联标量 `padx/pady`（值∈{8,12}）改 `SPACING['sm'/'md']`：12→md×8、8→sm×2。
- 新增 `from ui_tokens import SPACING`（纯数据模块、无依赖、无环；该模块承载设置页 Tk UI，非启动路径）。
- 保留不动：值非 token 的间距（5／10／18）与全部 tuple 间距。
- **行号平移同步**（插入 import → 后续行 +1）：`维护记录/架构统一基数.json` 第四项 `agent/prompt_optimizer.py` 175→176；覆盖率审计21 位点 173→174。

## 验证
- 定向：`test_unification_ratchet`＋`test_token_boundary` **8/8、OK**（6.78 秒）；同批 `test_todo_comment_snapshot`＋`test_coverage_audit_ratchet` 行号同步后全绿（首轮 1 红＝第四项未登记 176，同步后复验绿）。
- 默认冒烟 `smoke_test.py`：**8/8、0 失败**。
- 架构 `smoke_test.py --architecture`：**341/341、0 红**（136.41 秒）。
- `test_token_boundary`：`agent/prompt_optimizer.py` 数字 padding **16→6**。
- 全量：**不跑**（见「三个必答」）。

## 提交
- 内容：`8274dee`（`agent/prompt_optimizer.py`＋`维护记录/架构统一基数.json`）。
- 报告／状态／接力：本轮收尾提交。

## 复盘
- 已收口：**设计 token 的「决策-free 子集」（值恰等于现有 token 的内联间距）至此**全部迁完**——五轮累计 81 处（R1396 13＋R1399 21＋R1400 24＋R1401 13＋R1402 10）；全站内联标量 `padx/pady` 只剩非 token 值（2／3／5／6／10／14／18／22 等）与 0 值间距。
- **明确边界**：再往前推进设计 token **必须先有调色板决议**——hex（含 `desktop.py` 31 处）、103 处旧 `ui_theme` 调色板值、非 token 间距值、旧页面文字层级，全部依赖「①以 `ui_tokens` 为准改视觉／②零视觉把旧值补进 `ui_tokens`／③暂不迁移」三选一。
- 未做（理由）：`desktop.py` 的 hex 有意不迁——等值提换会把小写 `#ffffff` 变成大写 `#FFFFFF`，与 `test_idea_chat` 既有 `cget(...)=='#ffffff'` 断言冲突；正确做法是随调色板决议统一处理（含大小写口径）。
