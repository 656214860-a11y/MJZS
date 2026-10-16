# R1630 阶段门禁端到端覆盖补齐与运行期链路断言（阶段4 T2＋T3）

- 本轮类型：§3.10 验证/基线轮（测试与探针资产；不改产品行为）。
- 测试：定向 `tests.test_stage_gate_e2e_probe` 5/5；默认冒烟 8/8；架构门禁 356/356（本轮实测）。
- 欠账：只改 `tests/` 与 `维护记录/基准脚本/`，按 §5 口径不计源码轮。

## 交付

1. `维护记录/基准脚本/探针_阶段门禁端到端.py`
   - 门禁清单改为**驱动 `stage_parallel.GATES`**（此前硬编码 SG-01..SG-05，漏了 SG-A／SG-B）；空项目循环与执行循环都按权威清单走，将来新增门禁会自动进入探针。
   - 补 SG-A／SG-B 的真实证据：SG-A 用已采用分镜＋`ui_settings.adopted_storyboards`；SG-B 写真实 `animatic_manifest.json`（`file_cache.file_digest` 校验源版本与成果摘要、三项人工确认、镜头图）。
   - 结果新增 `gates`／`chain`／`missing_gates`：门禁链必须首尾相接，未跑到的门禁写入 findings。
2. `tests/test_stage_gate_e2e_probe.py`
   - 空项目用例改为记录**两类门禁语义**：SG-A／SG-B 是“必须有上游成果”的入口闸（`entry_ok=False`、`started=True`），SG-01..05 是“上游没做就别拦”（`entry_ok=True`、`started=False`），两类都断言，防语义漂移。
   - 执行清单断言扩到 7 条。
   - 新增 `test_gate_chain_is_complete_and_contiguous`：全部门禁跑到真实证据（`executed == GATE_IDS`）、`missing_gates` 为空、链首 `from=storyboard`、链尾 `to=video`、相邻门禁 `to == from`。

## 关键发现

- **补上的真实覆盖缺口**：改造前探针只跑 SG-01..05，`stage_parallel.GATES` 里的 SG-A／SG-B 没有任何真实证据级断言（只有 `tests/test_stage_parallel.py` 的单元级与 `tests/architecture/test_pipeline_stage_io_contract.py` 的静态契约）。现在 7 条门禁全部由真实临时项目证据驱动，并随权威清单自动跟进。
- **两类门禁语义不对称（记录，不作为缺陷）**：空项目下 SG-A／SG-B 返回 `entry_ok=False, started=True`（按“必须已有采用稿”判定），SG-01..05 返回 `entry_ok=True, started=False`（“上游没做就别拦”）。两者都符合各自 `condition`，已钉进用例。

## 未做

- 视频→配音字幕→剪辑→质检交付这一段**没有阶段门禁**（`stage_parallel.GATES` 到此为止）；本轮未新增门禁、未改产品代码，该段仍只有完成证据与分段用例（T2 剩余项）。
- 未跑全量；未联网；未实机。

## 自审（§4.2）

1. 满足验收标准：是（T2＝探针覆盖全部 7 条门禁；T3＝运行期链路连续性断言）。
2. 范围外文件：无（1 个探针脚本＋1 个测试文件）。
3. 验证：定向 5/5、默认冒烟 8/8、架构门禁 356/356 为本轮实测。
4. 新引入问题：无。

## 提交

master 提交（hash 见 `git log --grep="R1630"`）。