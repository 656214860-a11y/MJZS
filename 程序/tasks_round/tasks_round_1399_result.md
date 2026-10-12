# R1399：UI 路线图 §一 第 2 项（设计 token）批量单页迁移（4 页，零视觉变更）

类型：功能轮（§3.1，UI 统一入口／设计 token）。中央轮次：1399（说明：本轮原领 1397，提交前中央号被并行轮推进到 1398，为避免与并行轮冲突改领 1399；1397／1398 未由本会话产生提交）。范围＝设计 token 迁移中**可证明零视觉变更**子集的第 2 批：`asset_detail.py`／`prompt_window.py`／`qwen_setup.py`／`seedream_settings.py` 四页内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改从 token 取值，另 1 处等值 `#ffffff → COLORS['background_card']`。

## 三个必答
- 本轮类型：功能轮（§3.1）——4 个生产页的内联视觉常量等值改用 token ＋ 各页 1 处 import；不改业务逻辑、阶段、路径、分层；不改字体；颜色仅做等值提换。
- 测试：定向 `tests.test_asset_detail`＋`test_asset_detail_service`＋`test_token_boundary` **50/50**；`tests.test_api`＋`test_copy_text`＋`test_seedream_direct` **70/70**；默认冒烟 **8/8**；架构 `--architecture` **341/341**（首次 2 红＝行号平移，同步基线后复验第 2 次全绿）。
- 欠账：**命中 §5 五轮规则**（1399−1394=5），已在干净 master 工作树 `o07-fullsafe-master`（reset→`4ed81e9`）跑 `run_selftests.py --all --safe`：**4983 条、609.6 秒、0 文件有红、ALL TESTS PASSED**；凭据 tree=`250b6384…`＝内容提交 `4ed81e9:程序`，`last_full_safe_all_round` 1394→1396。

## 实现（等值提换，零视觉变更）
- 21 处内联标量 `padx/pady`（值∈{4,8,12}＝`SPACING` 既有档）改 `SPACING['xs'/'sm'/'md']`：`asset_detail.py` 11、`seedream_settings.py` 4、`prompt_window.py` 3、`qwen_setup.py` 3。
- `asset_detail.py` 1 处 `bg='#ffffff'` → `bg=COLORS['background_card']`（#FFFFFF 等值；同处 `fg='#243247'` 非 token 值，留待调色板决议）。
- 4 页各新增 `from ui_tokens import SPACING`（`asset_detail.py` 另含 `COLORS`）——纯数据模块、无依赖、无环。
- 保留不动：值非 token 的间距（2／3／5／6／7／10／14／18／22 等）与全部 tuple 间距（棘轮不计）。

## 行号平移同步（各页插入 import 致后续行号 +1）
- `维护记录/TODO注释快照_20261003.json`：`asset_detail.py` `_board_block` 注释 353→354。
- `维护记录/架构统一基数.json`：第四项 `qwen_setup.py` 位点 48→49、170→171。

## 验证
- 定向：`tests.test_asset_detail`＋`test_asset_detail_service`＋`test_token_boundary` **50/50、OK**（68.77 秒）；`tests.test_api`＋`test_copy_text`＋`test_seedream_direct` **70/70、OK**。
- 架构首次 341 有 2 红（`test_todo_comment_snapshot` 行号 353/354；`test_unification_ratchet` 第四项 `qwen_setup.py:48`→未登记 49）；定向修绿 5/5 后复验架构 **341/341、0 红**（128.24 秒）——该项共 2 次。
- 默认冒烟 `smoke_test.py`：**8/8、0 失败**。
- 全量：干净 master `o07-fullsafe-master` `--all --safe` **4983/4983、609.6 秒、0 红、ALL TESTS PASSED**；凭据 tree=`250b6384…`、round=1396（执行时最新已提交结果）、`last_full_safe_all_round` 1394→1396。

## 提交
- 内容：`4ed81e9`（4 页＋两个行号基线）。
- 报告／状态／接力：`d6dd313`（本文件＋`project_status.md`＋`.agent-handoff/` 4 文件）。

## 复盘
- 已收口：四页可证明等价于 token 的内联间距／1 色全部迁移；`test_token_boundary` 对应计数下降（`asset_detail.py` 21→10、`prompt_window.py` 3→0、`qwen_setup.py` 9→6、`seedream_settings.py` 9→5；HEX `asset_detail.py` 21→20）。
- 未做（理由）：hex 颜色（全站仅 8 处等于现有 token）、103 处旧 `ui_theme` 调色板值、非 token 间距值、旧页面文字层级——均需用户对设计 token 调色板决议（①改视觉／②零视觉补值／③暂不迁移）后逐页推进；本轮不擅自改视觉。
- 下一轮候选：同法继续剩余页（`workflow_settings.py` 5、`native_assets.py` 3、`background_characters.py` 1 等），或等调色板决议后统一。
