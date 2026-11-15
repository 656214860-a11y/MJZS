# R2573 结果：SWE-2 T10 包化迁移方案（先出方案轮）

## 交付

- `docs/review/包化迁移方案_T10.md`：按层为主的包结构（contract/infra/domain/orchestrator/ui）、迁移规则（git mv+改 import、薄转发、同轮更新登记表）、七批前缀族顺序（account/project → contract 小模块 → writing → asset 族 → keyframe/storyboard → UI 族 → app.py 拆分）、前置 AST 依赖扫描器与待确认项（包名、__init__ 再导出）。

## 实测

- 顶层 `.py` 359 个（不含测试），按前缀聚类 top：ui(12/2952行)、pet_cloud(8/1185)、storyboard(8/2123)、asset(7/2723)、pet(7/5111)、skill(7/4228)、stage(7/3215)、model(6/2443)、pet_ui(6/4346)、writing(6/1908)。
- 族内跨层混合已确认（asset_* 横跨 L1–L4），方案要求先出跨层清单再搬。

## 验收

- 文档轮，不跑 smoke/selftest（AGENTS §5 文档轮口径）。方案获用户批准后按搬家轮逐批执行。
