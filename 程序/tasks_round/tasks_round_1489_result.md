# R1489 修复轮：文案「您」规则对整包第三方 SKILL 放行

1. **本轮类型？** 修复轮（测试口径）。
2. **测试与基线？** `test_copy_rules` 通过；R1482 后重跑全量（5152 条）仅此 1 条红，其余全绿；本轮提交后再跑全量。**断言有意调整，见下。**
3. **是否欠账？** 无新增。

## 事实

R1481 把全流程 SKILL 包升级到 V7.4.20（嵌套仓库指针，别的轮次所为）。新版脚本（`gate_check.py`、`build_board_lite.py`、`check_package.py`、`compile_feed.py`、`sd_core.py`、`style-lock-ladder.py` 等）输出的文案含「你」，`test_copy_rules.SecondPersonTests.test_interface_copy_speaks_to_you_with_the_polite_pronoun` 因此红 13 处。该测试原先只对 `validate_prompt.py` 放行，其余 SKILL 脚本恰好没有「你」。

## 判断与改动（断言有意调整）

这些脚本属于整包引入的第三方 SKILL，随版本整体替换，文案不是本项目的界面文案，我们不改写它。逐文件登记白名单会让每次升级都追着补，所以新增 `VENDORED_SKILL_PACKAGE` 前缀放行整个 `skills/00全流程SKILL/AIGC创作全流程/`；项目自己的界面文案（程序根目录模块等）仍受「您」规则约束，`test_the_prompt_files_still_say_you` 与三虎第三人称检查未动。

## 提交

已提交，见 git log 标题 `R1489:`。
