# R3232 标准库验收契约跟随已批准完整运行时
<!-- round-evidence: {"commit_base": "62656555", "credential_hits": 0, "evidence_sha256": "abbb48e534292d93", "exit": 0, "failed": 0, "passed": 10, "round": 3232, "tests": "run_selftests.py -k test_stdlib_closure"} -->

## 三问

1. 类型：验收契约同步轮，仅测试；依据主线R3199/R3211/R3221已批准的完整Python3.14.7及谨慎白名单依赖策略，不更改用户运行时。
2. 测试：`test_stdlib_closure` 10条/2.584秒/OK。之前R3226自动全量在当前3.14完整运行时出现两条旧裁剪策略失败；无产品缺失import，不能继续把58个历史裁剪模块重新从用户运行时删除。
3. 欠账：消除旧“盘上必须没有58模块”与已批准完整运行时的矛盾；没有跳过任何测试、没有把缺失import放行。

## 契约更正

- 原缺失子包测试依赖tkinter.colorchooser/multiprocessing.pool在旧裁剪环境不存在。现改为TemporaryDirectory真实最小包：父包必须解析、缺失子模块必须返回None，坏样本检验更直接，不依赖版本偶然缺件。
- 原58项清单保留历史计数和源码新增依赖约束；磁盘裁剪断言替换为当前完整随包必需标准库完整性断言（Tk/json/ssl/urllib/zip/sqlite/multiprocessing等）。启动真实import闭包无缺项、只Blender宿主可缺的两道强断言保持。
- 不删除标准库、不安装任何新库、不改依赖白名单、不扩大HOST_ONLY。

## 后续

与文案迁包修复一并合入后跟踪最终全量。R3226自动全量另报test_perf_batch_queue，需读取测量并复验。任务书仍待最终全量和任务完成文件，不虚报完成。
