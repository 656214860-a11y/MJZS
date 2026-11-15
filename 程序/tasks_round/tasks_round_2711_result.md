# R2711 结果：待采用稿按段落选择采用（REQ-S01-88）
<!-- round-evidence: {"commit_base": "ce9eb77f", "credential_hits": 0, "evidence_sha256": "6a8aa4ee1c878296", "exit": 0, "failed": 0, "passed": 16, "round": 2711, "tests": "run_selftests.py -k test_writing_unconfirm"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1，文档先行）。任务源：盘点文档优化项 3——「部分采用」，
   只采用某几段而非整份文件。分支 `codex/wip-R2711`（R2686–R2710 为
   中央计数器空号/他车道）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **9/9** 通过；`smoke_test.py --affected writing_unconfirm
     stage_execution_service desktop_writing_page` 自检门禁 **0 个文件有红**
     （423 秒；含 1 条登记位 skip `test_stage_profile_wrong_preset_rejected`，
     为发行包 bundled skill 实机复验登记项，与本轮无关）。
   - 先红后绿：4 条新用例在实现前全部 `ImportError: cannot import name
     'apply_partial_adoption'`，实现后 `test_writing_unconfirm` 16/16 绿。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账。盘点队列剩最后一项：规则 1（三阶段草稿并行编辑）。

## 实现（REQ-S01-88）

- **L2 `writing_unconfirm`**：
  - `adoption_sections(text)`：分段唯一口径——markdown 标题（`#{1,6} `）
    分段、标题前导文自成一段；无标题按空行分段。返回 `{title, text}`。
  - `apply_partial_adoption(project, stage, path, keep, publish=)`：所选
    段落重写文件；台账命中的记录（按 `stage`+相对 `path` 定位）写
    `partial_adoption={'kept':[…],'total':n}`。**已确认稿被截写等同取消
    该阶段确认**——同 `unconfirm` 口径截断其后记录，
    `_save_preparation_state_guarded` 的确认基线收窄自动撤销自然稿
    采用；待确认草稿只写标记与文件，指纹按既有待确认重绑口径装载时
    更新；文件未登记台账时只做截写；全选返回 `changed=False` 不落盘。
- **L3 `stage_execution_service.apply_partial_adoption`**：注入
  `publish_stage_text`，与 confirm/unconfirm 同构。
- **L4 `desktop_writing_page`**：阶段文件右键新增「按段落采用…」，
  `BaseDialog`＋逐项 `ttk.Checkbutton`（Canvas 滚动）列出段落标题，
  「采用所选」经 L3 编排落盘后刷新列表并提示审阅定稿。

## 先红后绿证据

```
4 条新用例（confirmed 截写/待确认截写/全选 no-op/分段口径）
  ImportError: cannot import name 'apply_partial_adoption'   ← 实现前
  test_writing_unconfirm 16/16 全绿                          ← 实现后
```

## 设计取舍

- 部分采用落在「截写文件＋台账标记」，sha256 绑定契约不变——用户看到的
  就是定稿内容本身，不存在「确认的是文件、生效的是子集」的双层状态。
- 截写已确认稿自动解除确认而非拦截：与「取消已确认」同口径，下游阶段
  记录一并截断，文件本体不删，可经「设为定稿」重新登记。

## 未覆盖

- 勾选列表只显示段首标题行（60 字截断），不内嵌段落全文预览——
  预览可走「历史快照／对比」或打开文件。
