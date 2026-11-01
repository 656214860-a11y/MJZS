# R519 修复轮：阶段 SKILL 同步与提示词渲染入口

1. 本轮是功能轮还是整理轮？修复轮。
2. 测试跑了吗？三个基线过了吗？已跑定向单测 23/23、受影响冒烟 9/9、默认冒烟 8/8；本轮未重跑架构门禁 92/92 或全量安全回归 3,230 条，二者仅保留既有已验证基线，不能视为本轮通过。
3. `project_status.md` 的欠账少了吗？本轮未改变台账欠账；距上次状态更新仅一轮，按每五轮更新协议不修改状态文件。

## 根因与复现

- 复现：进入“视频生成 → 线上生成”，点击“手动制作提示词”右侧的“阶段配置”。
- 根因：`desktop.py` 创建视频工作台时，把该按钮绑定为 `skill_panel.show(self, 'storyboard')`；同一动作的 Agent 工作流也以 `storyboard/初步分镜` 启动。实际 `storyboard-prompt-render.skill.md` 位于 `skills/06分镜定稿SKILL/`，应使用分镜定稿内的提示词渲染职责。

## 完成内容

- `skill_registry.py`：01—12 阶段目录成为 SKILL 归类依据；漏写 frontmatter `stage` 的阶段目录 SKILL 会自动归入对应阶段，目录与明确 frontmatter 不一致会报问题。
- `stage_config.py`：读取已有项目配置时移除不存在/已废弃项，并把已配置但落在错误阶段的有效 SKILL 迁到其目录归属阶段；不会重新勾选用户主动取消的有效 SKILL。
- `desktop.py`：提示词工作流改以 `final` / “提示词渲染阶段”启动；相邻“阶段配置”改打开 `final`，其中包含 `storyboard-prompt-render` 等分镜定稿 SKILL。
- `app.py`、`architecture.md`：同步职责说明；阶段配置面板通用逻辑未改。
- `tests/test_skills.py`、`tests/test_video_ui.py`：增加目录缺失 stage 的自动归类、配置迁移与工作台按钮阶段绑定回归。

## 验证

- `python -B -m unittest tests.test_skills.RegistryTests tests.test_skills.StageConfigTests tests.test_video_ui.VideoEntryTests.test_manual_prompt_stage_config_opens_prompt_render_stage -v`：23/23 通过。
- `python -B smoke_test.py --affected stage_config skill_registry app desktop`：9/9 通过；定向门禁无失败文件。
- `python -B smoke_test.py`：8/8 通过。

## 修复轮自审

- 通过：配置与页面均已使用同一 `final` 阶段，目录分类、失效清理和错阶段归位均有回归覆盖。
- 通过：仅修改注册、阶段配置、视频工作台入口、对应测试及架构说明；未写入用户作品数据、未更改 12 阶段契约或通用阶段配置面板。
- 通过：默认冒烟 8/8。
- 同类复核：本地与线上共用同一 `App` 工作台，因此两条入口均使用 `final` 回调；视频制作按钮仍保持既有 `video` 阶段，不受影响。
