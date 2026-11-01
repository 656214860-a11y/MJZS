# R685 功能轮——HOLLMWOOD 四角色模式开关 + 关闭态自动落盘

## 开头三问

1. **本轮功能还是整理轮？** 功能轮：新增项目级四角色协作开关，并为关闭态补齐通用 API 直发与受控自动发布。
2. **Test run? all 3 baselines?** 已执行。默认冒烟 9/9 通过；受影响门禁 163 条、关联回归 27 条均为 0 红；全量安全自检 3377 条中 2 个文件有红，故本轮为 `[TASK_FAILED]`。
3. **did project_status debt decrease?** 否；本轮未关闭“已知阻塞与待办”中的既有条目，待办数保持 4 条；全量失败原因已如实留档，未扩大本轮修复范围。

**验证档位声明：**本轮改动涉及 4 个产品模块（`stage_config.py`、`writing_api.py`、`desktop.py`、`skill_panel.py`）及测试文件，按分级规则执行**默认冒烟 + 受影响模块门禁 + 全量安全自检**，跳过单模块与架构门禁，理由：改动达到 4 个模块且涉及剧本原稿自动发布路径；全量安全自检原始日志将写入 `维护记录/r685_safe_all.log`。

## 实施内容

- `stage_config.py`：新增 `HOLLMWOOD_ENABLED = 'hollmwood_enabled'`，纳入四角色字段读取与 `put()` 保存；`hollmwood_enabled(project, stage='script')` 在旧项目缺键时返回 `True`，保持原有四角色默认行为。
- `writing_api.py`：只有“简报存在且开关开启”才进入 `_hollmwood_reply()`；关闭时，通用 API task 仍包含完整 `<brief_complete>` 块。新增 `SCRIPT_RAW_AUTO_SAVE_MIN_CHARS = 800`，正文通过既有自然剧本闸门、长度达标后仅经 `_write_script_raw()` 自动发布；同文（`strip()` 后相同）不重复写入。成功或幂等命中均返回 `script_raw_path` 与本次 `hollmwood_enabled=False`。
- `desktop.py`：根据本次响应的模式显示“`四角色剧本已保存：script_raw.md`”或“`剧本已自动保存：script_raw.md`”；关闭态不伪造角色完成事件。
- `skill_panel.py`：HOLLMWOOD 行增加“`四角色协作`”复选框并复用现有保存入口；说明文案为“关闭后为所选 SKILL 单次直发；正文通过自然剧本闸门且达到最小长度时自动保存剧本原稿，否则仍可手动下载保存。”间距使用既有 `ui_tokens.SPACING`。
- `tests/test_stage_config_hollmwood.py`、`tests/test_writing_api.py`、`tests/test_skills.py`：覆盖旧项目默认开启与持久化、关闭态绕过四角色且携带简报、自动落盘的通过/闸门拒绝/过短/同文幂等、桌面文案及面板复选框保存。

### 自动发布边界

`_write_script_raw()` 仍是 `script_raw.md` 的唯一写入者；未改 `require_natural_script()`，未改 `hollmwood_roles.py`。自动发布与开启态使用同一原稿覆盖语义，但仅触及该唯一目标文件，不会触及用户其他原稿。闸门拒绝、正文过短时静默不写，手动下载路径保持不变。

页面改动需**重启应用**后显示四角色协作开关。

## 验证原始输出片段

1. `python -B smoke_test.py`

   ```text
   通过：9 项
   失败：0 项
   冒烟测试通过，可以进入下一轮
   ```

2. `python -B smoke_test.py --affected stage_config writing_api desktop skill_panel`

   ```text
   共 163 条用例，89.2 秒；0 个文件有红
   ALL TESTS PASSED
   通过：9 项
   失败：0 项
   ```

3. `python -B run_selftests.py -k writing_api stage_config skill_panel`

   ```text
   共 27 条用例，14.0 秒；0 个文件有红
   ALL TESTS PASSED
   ```

4. `python -B run_selftests.py --all --safe`（完整原始日志：`维护记录/r685_safe_all.log`）

   ```text
   共 3377 条用例，931.6 秒；2 个文件有红
   ### test_script_contract（1 条红）
   ### test_token_saver（1 条红）
   ```

全量失败均不属于本轮文件或功能：前者的 SKILL 审计期望清单落后于已存在的外部包/总入口；后者在当前 Windows 用户环境无法保护临时 API key。按声明档位任一失败即失败的规则，本轮结论为 **[TASK_FAILED]**，不以局部通过替代全量结论。

## 用户数据确认与自审

- 未修改用户项目数据、用户配置或密钥；测试仅在临时目录构造项目。
- 只改开关、关闭态通用请求/受控落盘、对应桌面提示与面板配置入口；未夹带扫描、角色执行器或自然剧本闸门改动。
- 三个基线数：默认冒烟 **9/0**；用户指定关联回归 **27/0**；全量安全自检 **3377 条/2 红**。
