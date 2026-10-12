# R1396：UI 路线图 §一 第 2 项（设计 token）单页迁移——参考图页内联间距改用 token

类型：功能轮（§3.1，UI 统一入口／设计 token；**零视觉变更**）。中央轮次：1396。范围＝`维护记录/UI统一入口路线图_v1.md` §一 第 2 项「设计 token」剩余迁移缺口中的**单页、可证明零视觉变更**子集：把 `asset_reference_images.py` 中数值恰等于 `ui_tokens.SPACING` 的 13 处内联 `padx/pady` 改从 token 取值。其余非 token 值（10／6／5）与双调色板统一仍待用户对「设计 token 调色板」三选一（改视觉／零视觉补值／暂不迁移）后再逐页推进，不在本轮擅动。

## 三个必答
- 本轮类型：功能轮（§3.1）——只改 `asset_reference_images.py` 一个生产模块的内联间距字面量与一处 import；不改业务逻辑、阶段、路径与分层，也不改任何颜色／字体。
- 测试：定向 `tests.test_reference_images`＋`tests.architecture.test_token_boundary` **26/26**；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **341/341**。
- 欠账：`1396−1394=2<5` 且未命中 §5 升级条件（非启动器路径／非 Tk 控件生命周期／非删除语义／非层级登记表）→ **不跑全量**（最近绿全量 R1395 `tree=886cfd07…`）。

## 依据（为何零视觉变更、且与调色板决议无关）
- `ui_tokens.SPACING = {none:0, xs:4, sm:8, md:12, lg:16, xl:24, '2xl':32}`；`padx=12 → SPACING['md']`、`padx=4／pady=4 → SPACING['xs']` 取值完全相等，渲染不变。
- 间距与调色板无关（不随 `ui_tokens`／`ui_theme` 选色变化），故本页迁移与「调色板三选一」互不冲突：无论选①改视觉／②零视觉补值／③暂不迁移都成立。
- 未触碰颜色：`asset_reference_images.py` 无内联 hex（`test_token_boundary` 的 HEX 基线不含此文件）。

## 实现
- `asset_reference_images.py`：新增 `from ui_tokens import SPACING`（纯数据模块、无依赖、无环；`ui_widgets` 已传递引入，不新增启动图节点）。
- 13 处内联间距改 token：`padx=12`×11 → `SPACING['md']`；`padx=4`×1／`pady=4`×1 → `SPACING['xs']`。
- 保留不动：值非 token 的 5 处（`pady=10`×2、`pady=6`×2、`pady=5`×1）与全部 tuple 间距（棘轮不计）——待间距补齐／调色板决议后另批。

## 验证
- 定向：`tests.test_reference_images`＋`tests.architecture.test_token_boundary` **26/26、OK**（3.744 秒）。
- `test_token_boundary` 棘轮：`asset_reference_images.py` 数字 `padx/pady` 计数 **18→5**（只减不增，无需改基线，符合门禁注释「迁移后可直接下调或删除基线」）。
- 默认冒烟：**8/8、0 失败**。架构：**341/341、0 红**（140.95 秒；数量不变）。
- 全量：**不跑**（见「三个必答」）。

## 提交
- 内容：`ac01f9f`（`asset_reference_images.py`）。
- 报告／状态／接力：`d5aeffc`（本文件＋`project_status.md`＋`.agent-handoff/` 4 文件）。

## 复盘
- 已收口：参考图页内联间距中可证明等价于 token 的 13 处全部迁移，棘轮计数 18→5。
- 未做（理由）：hex 颜色（仅 8 处等于现有 token）、103 处旧调色板值、非 token 间距值、旧页面文字层级——均需用户对设计 token 调色板决议后逐页推进；本轮不擅自改视觉。
- 下一轮候选：同法继续 100% 可判定的单页（如 `prompt_window.py` 3/3、`native_assets.py` 3/9），或等用户决议后统一调色板。
