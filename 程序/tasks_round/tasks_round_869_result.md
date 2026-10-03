# R869 协作治理轮：共享轮次分配器

## 目标

落实队列 `P1-round-allocator`，让并行 Git 工作树领取连续且唯一的结果轮次号。

## 实现

- `维护记录/基准脚本/round_claim.py` 通过 Git common-dir 中的排他锁保护计数器；临时文件写入后用原子替换提交新号码。
- 新轮次取结果目录已有最大号与持久计数器的较大值再加一，避免分支目录不一致时回退或复用号码。
- `AGENTS.md` 规定每轮开工先运行领取命令，并在收尾校验项目状态轮次与最新结果文件连续。
- `tests/test_round_claim.py` 覆盖已有结果起点、持久计数和 8 线程并发唯一连续性。

## 验收

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_round_claim`：3 条／0 红。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8 项／0 红。

## 备注

- R868 的完整安全全量仍有独立性能临界失败，未将其作为本轮或共享基线的全绿凭据。
