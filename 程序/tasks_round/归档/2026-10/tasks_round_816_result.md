# R816 结果：D 池规则承接第二阶段簇（03／06）

## 依据与范围

用户已拍板采用“按阶段定向注入 00 包”。本轮遵循 [SKILL规则承接映射草案](../维护记录/SKILL规则承接映射草案_20261002.md) 的 03／06 阶段簇：03 只承接调度与覆盖的风险预检；06 作为 D 锁的唯一放行点。

## 完成项

- `pipeline-storyboard-draft` 只引用 `blocking-and-staging` 的 Blocking notation／Blocking for AI video，以及 `cinematic-language` 的 Shot functions／Continuity geometry。每镜先写戏剧职责与可执行调度，段缝只报风险，不越权采用分镜或生成最终提示词。
- `pipeline-storyboard-final` 只引用镜头职责、提示词转换／单主运镜、镜间连续性／状态账本的章节。D 锁要求每段缝冻结 `in_state`、`out_state`、`cut_type`、`audio_bridge`、`owner`；缺失或冲突即退回，不发布采用分镜／提示词批次。
- 新增的架构断言确认上述章节锚点真实存在于本地 00 包，并防止 03 获得 D 锁放行权。两阶段均明确禁止全文、风格库与示例库注入；风格仍须由用户明确选择单一 reference。

## 实测

```text
> python -m unittest tests.architecture.test_skill_reference_injection
Ran 4 tests
OK

> python run_selftests.py -k skill_reference skills
144 条用例，0 个文件有红

> python -c "...skill_registry..."
count = 73
problems = []
storyboard = [pipeline-storyboard-draft, storyboard-camera-language,
              storyboard-duration-estimate, storyboard-pacing-check,
              storyboard-scene-breakdown, storyboard-shot-generation]
final = [pipeline-storyboard-final, storyboard-asset-sync,
         storyboard-consistency-lock, storyboard-final-validate,
         storyboard-prompt-render, storyboard-version-snapshot]

> python smoke_test.py
通过：8 项；失败：0 项
```

## 红线核对

- 未向 SKILL 注入 00 包全文，未默认注入风格／示例 reference。
- 统筹可替换、人工复核与调试途径未改动。
- D 锁没有提前到 03；03 预检和 06 放行的职责分离已由门禁覆盖。
