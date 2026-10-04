# R975：阶段工作区初始化结果契约

独立分支，不写主树。stage_workspace_service 四个入口返回统一结果，成功 data 保留原 Path 或元组形状；目录创建 OSError 记录后返回 SystemError。desktop 六处调用检查 ok 后再使用数据。生产模块两个。

采用方、既有服务测试和音频调用测试已同步。

## 验证

- 定向 21 条通过，1.257 秒；四入口 mkdir 错误、编程异常传播、六调用结果检查和解包顺序均已覆盖。
- 冒烟 8/8 通过。
- 架构 280 条，92.532 秒，唯一失败 tests/architecture/test_round_baselines.py:33，963 != 976；不弱化断言，不写主树状态。
- 默认增量：3590 条用例，344.3 秒，5 个文件失败（6 条红）：architecture.test_round_baselines（963 != 976）、test_baseline_history（过滤输出未保留具体异常）、test_asset_gating（31 != 24，首帧首批渐进加载行数）、test_script_contract（剧本 SKILL 清单差异）、test_skills（两条 71 != 73）。退出码 1，不能视为通过。
- 本次改测试因契约变更，同步更新成功结果解包与调用 mock，保留原业务断言并增加失败分支覆盖。
- [TASK_FAILED]：定向与冒烟通过，但架构和默认增量未通过；本轮未提交，不宣告完成。新增失败须进一步定位，不能未经复现即归为环境问题。

## 增量失败窄化复核

- 单独运行 tests.test_baseline_history 与 tests.test_asset_gating.AssetPageContentTests.test_only_the_visible_rows_decode_a_picture：6 条，2.836 秒，1 个错误。
- 基线历史错误已定位 tests/test_baseline_history.py:100：本工作树缺少 `维护记录/基准历史.json`，FileNotFoundError。
- 首帧首批加载用例本次单独运行通过；并行增量中的 31 != 24 尚未稳定复现，不能宣告已修复，也未修改该用例或产品代码。

## 提交记录

- 已提交：`66a7cab`，`R975-FAIL: 统一阶段工作区初始化结果并记录回归失败`。仅独立分支 8 个列明文件，未合并 master。
- 提交前检查暂存清单及新增行凭据形态，未命中；测试失败状态不变。本节为提交后的追记。
