# R814B 结果：SKILL 定向注入（功能轮）

## 完成项

- 剧本准备与剧本整理阶段只按需链接 00 包中与计划门控、镜头职责有关的具体章节；没有注入 00 包全文、风格库或示例库。
- 情绪曲线改为承接源规则的 12 节拍 0～10 模型：第 9 节拍为不低于 9.5 的最高峰，至少两次波峰达 9.0；移除与来源冲突的“相邻场次不得跳两级”替代规则。
- 模型、画幅与交付形态仍在剧本准备阶段先锁定；阶段文件未收紧统筹可替换性，也未封堵调试途径。
- 新增架构门禁 `test_skill_reference_injection.py`，固定三份阶段 SKILL 的授权 reference 章节，拒绝全文注入，并验证情绪曲线不回退旧规则。
- `test_skills.py` 的逐阶段注册数断言改为显式表，保留 12 阶段完整性检查。

## 实测

```text
> python run_selftests.py -k skill_reference skills
142 条用例，0 个文件有红

> python -c "...skill_registry..."
count = 73
problems = []
script = [pipeline-script-preparation, screenplay-production-line, screenplay-writer,
          script-emotion-curve, script-forging, 短剧编剧搭子, 编剧技能集]
video = [pipeline-video-generation, video-batch-submit, video-multi-model-route,
         video-quality-check, video-retry]
edit = [edit-auto-compose, edit-bgm-sfx, edit-multi-format-export,
        edit-preview-generate, edit-transition-library, pipeline-editing,
        video-audio-sync-precheck]

> python smoke_test.py
通过：8 项；失败：0 项

> python -m unittest tests.architecture.test_unification_ratchet
Ran 3 tests
OK（两处裸读随 R814C 冻结后不在 R814B 工作树中）
```

## B-3／B-4 在途归属

- `agent/prompt_optimizer.py:173` 的裸 JSON 读取随同 `BaseDialog`／`dispatch_notification` 迁移而出现于未提交的 L4 通知统一改动；不属于 R814B。已冻结为 `stash@{0}`（补件）。
- `qwen_setup.py:47` 同属 L4 通知统一主体，已冻结为 `stash@{1}`。两项均未登记到架构统一基数，也没有扩大白名单；待 R814C UI 轮以 `file_cache` 或合法发布器路径逐项处置。
- R814C 先后以两个连续 stash 冻结，故原 DataTable B1 半成品已顺延为 `stash@{2}`；任务队列保留原登记文本，实际索引以本节为准。
