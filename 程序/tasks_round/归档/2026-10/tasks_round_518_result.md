# R518 结构治理轮：全流程 SKILL 阶段拆分

- 本轮是结构治理轮（子场景：执行）；来源为用户指定的 `skills/00全流程SKILL` 阶段拆分任务。
- 测试已跑：SKILL 注册/阶段配置定向 20/20、架构门禁 92/92、默认冒烟 8/8；全量安全回归非本轮所需，既有后台运行不作为本轮验收。
- `project_status.md` 的既有风险欠账未新增也未减少；本轮完成的是 SKILL 组织与依赖契约治理项。

## 变更

- 从 `00全流程SKILL` 的全流程资料抽出 12 个阶段专属注册 SKILL；原始导入资料保持不动，避免破坏其参考包。
- `skill_registry.Registry.files()` 已递归扫描 `skills/**/*.skill.md`，故未改 `skill_registry.py`；未改阶段配置面板逻辑。
- 更新注册契约回归，验证新增的子目录文件、12 阶段覆盖与 `dependsOn` 图；同步将实际架构门禁基线登记为 92/92。

## 拆出的 SKILL 文件

1. `skills/01 剧本准备SKILL/pipeline-script-preparation.skill.md`
2. `skills/02 剧本整理SKILL/pipeline-script-structure.skill.md`
3. `skills/03初步分镜SKILL/pipeline-storyboard-draft.skill.md`
4. `skills/04资产管理SKILL/pipeline-assets.skill.md`
5. `skills/05连贯性SKILL/pipeline-continuity.skill.md`
6. `skills/06分镜定稿SKILL/pipeline-storyboard-final.skill.md`
7. `skills/07首帧管理SKILL/pipeline-keyframe.skill.md`
8. `skills/08白模预演SKILL/pipeline-previs.skill.md`
9. `skills/09视频生成SKILL/pipeline-video-generation.skill.md`
10. `skills/10配音字幕SKILL/pipeline-audio-subtitle.skill.md`
11. `skills/11后期剪辑SKILL/pipeline-editing.skill.md`
12. `skills/12质检交付SKILL/pipeline-delivery.skill.md`

## dependsOn 链

`pipeline-script-preparation` → `pipeline-script-structure` → `pipeline-storyboard-draft` → `pipeline-assets` → `pipeline-continuity` → `pipeline-storyboard-final` → `pipeline-keyframe` → `pipeline-previs` → `pipeline-video-generation` → `pipeline-audio-subtitle` → `pipeline-editing` → `pipeline-delivery`。

其中 `pipeline-editing` 还显式依赖 `pipeline-video-generation`，确保视频产物与配音字幕产物同时就绪后才进入剪辑。

## 验证与自审

- `python -B -m unittest tests.test_skills.RegistryTests tests.test_skills.StageConfigTests -v`：20/20 通过。
- `python -B smoke_test.py --architecture`：92/92 通过。
- `python -B smoke_test.py`：8/8 通过。
- 自审：未改用户项目数据、`skill_registry.py` 或阶段配置面板；阶段顺序仍以 `pet_bus.STAGES` 为唯一来源；新增文件均经递归注册校验且无问题。
