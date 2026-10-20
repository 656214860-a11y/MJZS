# R1767：修复轮——修复 R1764 误回退 R1763 的 engine.py 改动（三方合并恢复）

1. 本轮类型：§3.2 修复轮。R1764（C3 自动验收统一）提交流程事故的恢复——把被误回退的 R1763 engine.py 改动经三方合并恢复。

2. 测试跑了吗、三个基线过了吗：
   - 受影响 5 文件 67 用例 OK：tests.test_edit_adoption、tests.test_integration、tests.test_req_s12_anchors、tests.test_req_s10_anchors、tests.test_editing_scope
   - 默认冒烟 8/8 通过
   - 架构门禁 375 项，1 红＝test_full_safe_all_is_required_after_eight_source_rounds（既有「欠一次完整安全全量」，不阻断，post-commit 后台补跑）
   - 完整安全全量：未跑（按流程由 post-commit 后台自动补跑）

3. project_status.md 的欠账少了吗：本轮改源码 engine.py，按源码轮 +1；全量欠账由后台补跑清账。

## 根因
R1764 提交时 commit_batch.sh 的 LANE 拷贝把 lane_c3（基线 R1762 d9eca8f3）的整份 engine.py 拷回主树，覆盖了并行提交 R1763（1b3fcf5c）的改动。证据：master engine.py 的 EDIT_MANIFEST_SCHEMA 3→0；git diff 1b3fcf5c 14bd64c9 删 75 行。

## 修复
git merge-file 三方合并（base=d9eca8f3/R1762，ours=1b3fcf5c/R1763，theirs=14bd64c9/R1764）。1 处冲突：ours 新增 edit_clips／out_relative／shot_input_assets 函数块，theirs 同处新增 auto_review_ready，两块都保留（去掉冲突标记，两函数块间空两行）。

## 校验
- 字节级抽取无损（三份 blob 的 git sha1 比对一致）。
- 合并结果：EDIT_MANIFEST_SCHEMA×3、auto_review_ready×2、edit_clips×3、out_relative×4、shot_input_assets×2。
- git diff 14bd64c9 -- engine.py 仅含 R1763 内容（11 处删除均为 R1763 对基线代码的正常改写，如 register_edit_bundle 重写、publish_edit_lists 改用 edit_clips）；无冲突标记残留；ast.parse 语法通过。

## 防再发
commit_batch.sh 的 LANE 拷贝加守卫：对每个要拷的文件 f，若 git diff --quiet <车道HEAD> HEAD -- f 不成立（车道基线之后 master 上该文件又被改过）则中止，提示「车道基线落后，先三方合并」。

## 独立验收（advisor，主树真实环境直接运行）

- 范围：仅 engine.py（三方合并恢复）＋ commit_batch.sh 守卫（工作流任务/，gitignored 工具，不入库）。
- 根因证据：master engine.py EDIT_MANIFEST_SCHEMA 3→0、git diff 1b3fcf5c 14bd64c9 删 75 行。
- 合并校验：EDIT_MANIFEST_SCHEMA×3、auto_review_ready×2、edit_clips×3、out_relative×4、shot_input_assets×2；git diff 14bd64c9 -- engine.py 仅 R1763 内容；无冲突标记残留；字节级抽取与 blob sha 一致。
- 测试：5 文件 67 用例 OK；smoke_test.py 8/8；smoke_test.py --architecture 375 项，1 红为既有「欠一次完整安全全量」（不阻断，post-commit 后台补跑）。
- 已知：完整安全全量未跑（按流程后台补跑）；这笔是 R1764 提交事故，如实说明。
