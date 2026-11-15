# R2813 结果：修复 test_ui_edges_pages 异步解析时序脆弱（合并前置）
<!-- round-evidence: {"commit_base": "d659fbe9", "credential_hits": 0, "evidence_sha256": "d5e0d1daface081a", "exit": 0, "failed": 0, "passed": 40, "round": 2813, "tests": "run_selftests.py -k test_ui_edges_pages"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   修复轮（§3.2）。剧本准备车队合入 master 前跑 --affected 时暴露的存量测试缺陷，
   在干净 master（2ded4464）上单独复跑同样失败，与本车道改动无关。
   根因：show_conversation 的模型键改为异步解析后（R1949/R2318），第二次
   show(0) 会取消尚未到期的 resume 定时器；构建期 win.update() 若不足 50ms
   则缓存永不就绪，视图停在示例气泡——重载环境靠内部耗时凑满 50ms 才侥幸绿，
   轻载即确定性红（后台全量该条曾侥幸过）。

2. **测试跑了吗、三个基线过了吗？**
   - 修复前干净 master 复跑：同断言同位置红（已取证）。
   - 修复后：unittest 直跑该用例 OK；--affected 八模块门禁 9/9 全绿（371 秒）。
   - 断言逐字未动，仅在断言前按 test_idea_history_first_paint 既有泵法补
     事件循环等待（至多 5 秒），使异步渲染落地——fixture 对齐，未弱化契约。
   - 全量 --all --safe：未跑（合并轮前由 local_ci 门禁把关；全量欠账按
     凭据制度另计）。

3. **project_status.md 的欠账少了吗？**
   未新增；消除一条会随负载随机拦截各车道 --affected/全量的存量 flake。

## 改动

- tests/test_ui_edges_pages.py：断言前加泵循环（win.update + time.sleep(.01)，
  至多 5 秒），断言与用例意图不变。
