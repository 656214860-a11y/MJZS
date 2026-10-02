# 第 180 轮：全页面 SKILL 审计与配音重复收敛

## 审计结论

- 全部 12 个制作阶段共登记 55 个 SKILL；注册表字段与阶段映射均通过校验。
- 只有 `voice-multi-character` 与 `voice-tts-synthesis` 同时满足“同一输入、同一产物、同一合成／质检工具”且前者依赖后者，是会造成重复执行与重复付费的实质重复。
- 资产、首帧、剪辑、质检等其余共享工具的项是“总流程 + 单项复核／重试／导出”关系；不合并，以保留单独人工入口。
- `storyboard-asset-sync` 虽名称涉及资产，但它调用的是分镜定稿的漂移／一致性工具，并依赖定稿提示词；归属“分镜定稿”正确，未跨阶段迁移。

## 改动

- 保留 `voice-multi-character.skill.md` 作为历史兼容项，标记 `deprecated` 与 `replacedBy: voice-tts-synthesis`，没有删除用户既有配置可引用的文件。
- 注册表新增 `canonical_id()`；阶段配置读取旧 ID 时自动归一到主 SKILL，重复勾选只保留一次。
- 新项目默认配置与阶段配置面板隐藏已合并项；旧项目不需手工迁移，执行时同样只会进入主 SKILL。
- 增加旧 ID 迁移回归，并同步配置面板数量断言。

## 验证

- `python -m unittest test_skills.RegistryTests test_skills.StageConfigTests`：19 项通过。
- `python run_selftests.py --serial -k skills`：本轮相关的注册表／阶段配置断言通过；该全文件回归仍有既存的 4 类不稳定／缺工具失败（付费确认状态、失败重试清单、模型按钮状态、`script_contract` 两个工具未登记），与本轮配音别名改动无关。

## 后续风险

“同工具”不自动等于“同功能”。后续若要继续合并，必须先为每个候选项确认输入范围、是否覆盖已有产物、以及是否保留独立的手动复核入口；不能以删除 `.skill.md` 直接处理。
