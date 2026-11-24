# R4263 SANHU-FIX-1A：三虎切档只留一个入口（修复轮）
<!-- round-evidence: {"commit_base": "79fa309b", "credential_hits": 0, "evidence_sha256": "5adfb2ee3e89c804", "exit": 0, "failed": 0, "passed": 77, "round": 4263, "tests": "run_selftests.py -k sanhu_mode pet_settings"} -->

> 由合入接管会话代提交，原执行者中断。原执行者已在工作区完成全部改动与验证（见下文），提交因定向测试当时拿不到 GUI 令牌（证据 exit=2）被门禁拒绝；接管会话未改产品与测试代码，只重跑验证、补本句并提交合入。

## 三问
- 轮次类型：§3.2 修复轮（卡面 SANHU-FIX-1A，三虎只读审查 S-02：切档绕开 `set_paw_level` 这个唯一入口）。
- 测试跑了吗、三个基线过了吗：跑了卡面指定两条验收。定向 `run_selftests.py -k sanhu_mode pet_settings ui_batch7_settings_models pet_agent` 改前 3 条红、改后 189 条全绿退出码 0；`smoke_test.py --architecture` 700 条全绿退出码 0。默认冒烟与全量 `--all --safe` 未跑（卡面验收未要求）。
- 欠账少了吗：S-02 双入口缺陷闭环，切档只剩 `set_paw_level` 一个入口；无新增欠账。

## 范围与基线
- 基准版本：`79fa309b3237ab9a08534a3df0265eeb3fd7c5da`（开工三查：`git status --porcelain` 无输出、`git log -1 --format=%h` 输出 `79fa309b`、分支 `codex/sanhu-fix-rules`）。
- 任务：SANHU-FIX-1A / 波次 W2 / 已领号 R4263。
- 缺陷：`set_paw_level`（`ui/pet_ui_stages.py:817-822`）是唯一自动化入口——全自动同步开模式与全部开关、其余两档回手动关开关；但设置页「自动化等级」（`ui/pet_settings_ui.py` `level_page/apply`）与聊天一句话切档（`ui/pet_ui_stages.py` `run_plan` 的 `intent == 'level'` 分支）直调 `set_level`，只改等级不动模式与开关，会产生非法组合（例：手动模式 + 全自动等级 + 开关全关；自动模式 + 半自动等级 + 开关全开）。

## 改前红（退出码 1，3 条红 / 共 189 条）
命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k sanhu_mode pet_settings ui_batch7_settings_models pet_agent`（工作目录 `程序`，隐藏桌面）

```text
  test_sanhu_mode               17 条    11.3 秒  ✗ 2
  test_pet_settings#3           16 条    18.8 秒  ✗ 1
共 189 条用例，32.7 秒；2 个文件有红
```

红因原文（与缺陷一致）：
- `test_chat_level_switch_to_auto_takes_the_paw_entry`（test_sanhu_mode.py:98）：`AssertionError: 'manual' != 'auto'`——聊天切「全自动」只落了 level，模式没进 auto。
- `test_chat_level_switch_to_semi_releases_auto_mode_and_switches`（test_sanhu_mode.py:111）：`AssertionError: 'auto' != 'manual'`——全自动里聊天切「半自动」，模式停在 auto、开关未关（非法组合 自动+半自动+全开）。
- `test_picking_levels_only_reaches_the_three_legal_combinations`（test_pet_settings.py:695）：`AssertionError: Lists differ`——设置页点「全自动」实测得到 `('manual', 'auto', False)`，期望 `('auto', 'auto', True)`（非法组合 手动+全自动+全关）。

## 改动内容（文件:行号；产品只改两行，不增行不减行）
- `ui/pet_settings_ui.py:315`：`level_page/apply` 内 `pet.set_level(level)` → `pet.set_paw_level(level)`。
- `ui/pet_ui_stages.py:505`：`run_plan` 的 `intent == 'level'` 分支内 `self.set_level(target, at=at)` → `self.set_paw_level(target, at=at)`。
- `set_level`／`set_mode`／`set_paw_level`／`should_auto_run`／`start_level` 函数体未动。
- `tests/test_sanhu_mode.py`（+24）：`SanhuModeTests` 新增两条不建窗口用例——聊天切全自动须进 auto 模式并开全开关；全自动里聊天切半自动须退回 manual 并关全开关。
- `tests/test_pet_settings.py`（+19，含一行 `import infra.project_settings`）：`LevelPageTests` 新增一条隐藏桌面用例——设置页三档正、反向各切一遍，只允许三种合法组合（手动+只提醒+全关、手动+半自动+全关、自动+全自动+全开）。
- `tests/test_ui_batch7_settings_models.py`（+3）：`FakePet` 补 `set_paw_level` 转调方法（apply 改走后假宠物接口不齐）。
- 既有断言逐字未动。

两行 diff 原文：

```diff
@@ -312,7 +312,7 @@ def level_page(frame, pet, width=None):
     def apply():
         level = picked.get()
-        pet.set_level(level)
+        pet.set_paw_level(level)
@@ -502,7 +502,7 @@ class PetStagesMixin:
                 if target is None:
                     return ''
-                self.set_level(target, at=at)
+                self.set_paw_level(target, at=at)
```

## 验证命令与结果
Python 命令工作目录均为 `程序`，逐条单独执行。

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k sanhu_mode pet_settings ui_batch7_settings_models pet_agent`（改前）：退出码 1（3 条红，见上）。
2. `git diff --stat`（产品两文件）：各 1 行增、1 行减，共 `2 files changed, 2 insertions(+), 2 deletions(-)`。
3. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k sanhu_mode pet_settings ui_batch7_settings_models pet_agent`（改后）：退出码 0，尾部原文：
   ```text
   共 189 条用例，22.5 秒；0 个文件有红
   实际跳过 0 条用例：本机没有任何登记位被跳过
   ALL TESTS PASSED
   ```
4. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（改后）：退出码 0，尾部原文：
   ```text
   Ran 700 tests in 236.922s
   OK
   ✅ 架构治理测试：tests/architecture
   ```

## 提交
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4263: SANHU-FIX-1A 切档只留一个入口" ui/pet_settings_ui.py ui/pet_ui_stages.py tests/test_sanhu_mode.py tests/test_pet_settings.py tests/test_ui_batch7_settings_models.py tasks_round/tasks_round_4263_result.md --tests sanhu_mode pet_settings`（文件参数相对 `程序`，`--tests` 置于文件参数之后）。
- 提交被门禁拒绝（退出码 1），原文：
  ```text
  拒绝提交：R4263 证据不通过（scan hits=0, tests exit=2 failed=0）。凭据命中先移除；改了 .py 须用 --tests <模块关键词> 跑定向测试且全绿。
  ```
- 判断：`tasks_round/evidence/R4263.json` 记录定向命令 `run_selftests.py -k sanhu_mode pet_settings` exit=2；git common-dir 锁显示外车道进程（PID 76100，轮次 4264）持有 `full-safe-runner.lock` 与 `gui-selftest.lock`，定向轮按 60 秒封顶等不到 GUI 令牌，GUI 用例记 `GUI_DEFERRED` 未执行——环境性占用，非凭据命中、非断言红。待全量释放令牌后重跑同一提交命令即可。
- 工作树状态：上述 7 个文件停留在暂存区（未提交、未 push、未合入，分支仍在 `79fa309b`）。

## 未验证项 / 未核实
- 默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe` 未跑（卡面验收未要求）。
- 隐藏桌面运行日志里偶发 `invalid command name "...run" ("after" script)` 的 Tcl 噪音，来自窗口销毁后的遗留 after 回调，不计红；两次运行均有、与本改动无关（卡面只要求两条验收退出码）。
- `set_paw_level` 对未知档位的拒绝路径（`level not in PAW_LEVELS` 返回 None）沿用既有实现，本轮未新增断言。
- 未合入、未 push；合入由合并车道按正式流程处理。

## 被拒绝的命令（原文）
- `Get-ChildItem '程序\ui\pet_settings_ui.py','程序\ui\pet_ui_stages.py','程序\tests\test_sanhu_mode.py','程序\tests\test_pet_settings.py','程序\tests\test_ui_batch7_settings_models.py' | Select-Object FullName, Length`（开工取文件大小，未重试，改用文件工具直接读）。
- `git -c core.quotepath=false diff -- 程序/ui/pet_settings_ui.py 程序/ui/pet_ui_stages.py`（带配置参数的 diff；按规则重试一次裸 `git diff` 成功）。
