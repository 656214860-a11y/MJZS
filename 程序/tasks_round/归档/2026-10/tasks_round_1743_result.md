# R1743：契约轮——场景资产 resolution 跟随项目锁（RES）

## 三个必答问题

- **本轮类型**：功能轮（REQ-S05-03 契约修复，先改需求/设计再改代码与测试，符合 §2.7）。
- **测试跑了吗、三个基线过了吗**：
  - 定向 unittest：13 条 OK（`tests.test_req_s05_anchors` + `tests.architecture.test_requirement_traceability`）。
  - 默认冒烟 8/8：`--affected asset_contract` 内 8 项快速检查全 ✅。
  - 架构门禁：`--architecture` 374 条 OK，0 红。
  - 未跑全量安全回归（本轮为契约/文档+定向测试轮，非触发条件，未运行）。
- **欠账少了吗**：`维护记录/需求锚定基线.json` 的 `untested_done` 为空，本轮新增 REQ-S05-03 锚点测试，无新增欠账，基线无需变更。

## 改动

1. `asset_contract.py`
   - 新增 `resolve_resolution(workflow_lock=None, default='1920x1080')`：项目锁 `resolution` > 默认值，纯契约函数不读文件，与 `resolve_aspect_ratio` 同型。
   - `defaults('scene')` 的 `resolution` 由写死 `'1920x1080'` 改为 `resolve_resolution(workflow_lock, '1920x1080')`。
2. `tests/test_req_s05_anchors.py`
   - 新增 `import asset_contract`。
   - 新增 `test_req_s05_03_scene_resolution_uses_project_lock_then_default`（docstring 写 `REQ-S05-03`）：锁里有 `resolution` 用锁值、无锁/不传锁时 `1920x1080`；画幅锁优先也一并断言。
3. `docs/stages/S05_资产管理.md`
   - REQ-S05-03 由 🟡 改 ✅，删除句末「（REQ05 核对：…）」括注。
   - DES-S05-03 补 `asset_contract.resolve_resolution`：项目锁 > `1920x1080`。

## 先红输出（改实现前）

```
FAIL: test_req_s05_03_scene_resolution_uses_project_lock_then_default (...)
REQ-S05-03：场景画幅与分辨率默认 16:9／1920x1080，项目锁优先。
AssertionError: '1920x1080' != '1280x720'
- 1920x1080
+ 1280x720
 : 锁里有 resolution 时用锁值
Ran 1 test in 0.002s
FAILED (failures=1)
```

改实现后复跑：`Ran 1 test ... OK`。

## 实际计数

- `python -B -m unittest tests.test_req_s05_anchors tests.architecture.test_requirement_traceability`（PYTHONPATH `.;tests`）：**13 条 OK，EXITCODE=0**。
- `python -B tests/architecture/test_requirement_traceability.py --find REQ-S05-03`：定位到
  `tests/test_req_s05_anchors.py: ReqS05AnchorTests.test_req_s05_03_scene_resolution_uses_project_lock_then_default`，EXITCODE=0。
- `python -B smoke_test.py --affected asset_contract`：**通过 9 项、失败 0 项**；门禁 `run_selftests.py --serial -k ...` 共 96 条用例，74 秒，0 个文件有红，`ALL TESTS PASSED`，EXITCODE=0。
- `python -B smoke_test.py --architecture`：**374 条 OK，0 红**，EXITCODE=0。

## 需裁决事项

1. **`saved_preference` 是否也用于 resolution**：grep 调用方结论——`defaults()` 的 `saved_preference` 目前只有 `tests/test_aspect_ratio_priority.py` 传入画幅偏好字符串（如 `'1:1'`），生产调用方 `normalize()` 只走 `defaults(kind)` 不带参；全库无「分辨率偏好」概念。故 `resolution` 只按「项目锁 > 默认 `1920x1080`」，不消费 `saved_preference`，与需求原文一致。无待拍板项。
2. **GUI 令牌竞争（非代码失败）**：首次 `--affected asset_contract` 在 `test_asset_detail` 前等待跨树 GUI 令牌 900 秒超时（占用者 PID 22412，属另一车道进程）；该进程退出后复跑即通过。属环境串行竞争，非本轮改动引入，无需修复。
3. 本轮未执行任何 git 写命令、未领号、未提交、未改 `project_status.md`/`AGENTS.md`（任务书与 §4.2 约定）。

## 独立验收（Claude，主工作区）

- 来源：R1741 把 REQ-S05-03 降为 🟡（`asset_contract.defaults('scene')` 写死 resolution），本轮补实现。
- 先红证据见结果文件；主树 `unittest test_req_s05_anchors test_aspect_ratio_priority test_requirement_traceability` 16 条 OK；`run_selftests -k asset_contract aspect_ratio req_s05 asset_plan` 全绿；`smoke_test --architecture` OK。
- 验收红证：把 `resolve_resolution(...)` 改回写死 `'1920x1080'` → `test_req_s05_03_scene_resolution_uses_project_lock_then_default` FAIL，已还原。
- 裁决：`saved_preference` 不用于分辨率（全库无分辨率偏好概念），接受。
- 测试只新增、未改既有断言，断言未动。
