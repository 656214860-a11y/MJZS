# R1970 按钮一致性审计 + 规则落地（功能轮，第一步）

## 审计结论
按钮高度基本统一（37px）；宽度（clam 隐含最小 11 字符 vs `width=0` vs `width=N` 三种并存）、间距（xs/sm 混用）、compact（`fit_sidebar` 字面量且按下态内边距不同步）不统一。详细清单见会话调研，后续轮 B/C 收敛页面。

## 本轮改动
- `ui_tokens.py`：新增 `BUTTON_MIN_WIDTH`、`BUTTON_GAP`、`BUTTON_GAP_TIGHT`、`NAV_*` 内边距令牌。
- `ui_widgets._configure_button`：显式 `width=-BUTTON_MIN_WIDTH`（数值与原隐含值相同，外观不变）。
- `ui_rounded.py`：新增 `pressed_padding`、`set_button_padding`；`fit_sidebar` 改用，紧凑切换时按下态同步（修复按下回弹）。
- `design_tokens.md` 同步；新测试 `tests/test_button_consistency.py`（3 条）。

## 验证
button_consistency/ui_style_engine/button_boundary/token_boundary/desktop_compact/responsive_layout/ui_widgets 共 74 条全绿；architecture 406 条仅余历史红（agents_md、skill_reference_injection、round_baselines）；module_size_ratchet 因 ui_widgets 超 1500 行已把新函数移入 ui_rounded 解决。断言未动。未跑 --all --safe，未真实窗口目测。
未提交状态见提交信息。
