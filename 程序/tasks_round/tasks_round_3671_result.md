# R3671 结果文件 — L1 任务书轮 I15：资源感知（infra/resources.py，L1-Q12／L1-H6）
<!-- round-evidence: {"commit_base": "5433b45a", "credential_hits": 0, "evidence_sha256": "00fb55da4b355557", "exit": 0, "failed": 0, "passed": 28, "round": 3671, "tests": "run_selftests.py -k resources stdlib_closure startup_budget"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.7 性能／资源轮（任务书明定：准入实测＋新增模块）。依赖准入实测 psutil 与 nvidia-ml-py（均达标 L1-H6 四阈值）；新增 L1 `infra/resources.py`（`snapshot()`／`ensure_free()`／429 限额学习三件套）＋`tests/test_resources.py`（14 条）；生产锁六包→八包，白名单文档补 R3671 准入实测表。
2. **测试跑了吗、基线过了吗？** 跑了。任务书定向命令 `run_selftests.py -k resources dependency_whitelist stdlib_closure startup_budget` **43 条，唯一红为 `test_site_packages_whitelist` 环境红**（pydantic 五包跨分支污染，R3564 起同录，与本轮零因果）；`smoke_test.py` 默认冒烟 **9/9 绿**；`smoke_test.py --architecture` 见「验证汇总」；覆盖率两基线真实重测同步。详见「验证汇总」。
3. **欠账少了吗？** 是。FL-12「资源快照字段」由「只有 diagnostic_capture 一处磁盘读数」→ `infra/resources.py` 提供内存、磁盘空间与读写、网络计数、可选显存五类字段＋写前磁盘闸门原语＋外部限额学习原语；LR-08 实测缺口中「磁盘空间守卫不存在」一项由 `ensure_free` 原语落地（接线属地基 C2 车道，见「遗留与接线」）。

## 领号说明

- R3671 由本工作树经 `维护记录/基准脚本/round_claim.py next` 领得（输出含已知 GBK 解码噪声，登记成功，`round-claims.json` 可查）。

## I15-1 依赖准入记录（L1-H6 四阈值实测）

| 包 | 锁定版本 | 许可证 | Windows wheel | 冷导入实测 | 体积增量 | 维护状态 |
| --- | --- | --- | --- | --- | --- | --- |
| psutil | 7.2.2 | BSD-3-Clause | cp314 win_amd64 wheel 可用 | ≈21–22 ms（≤50 ms） | 隔离安装 ≈895 KB（≤5 MB） | 活跃维护，GitHub psutil/psutil |
| nvidia-ml-py | 13.615.71 | BSD | 纯 Python（pynvml.py），无原生扩展 | ≈30.8 ms | 隔离安装 ≈703 KB | NVIDIA 官方维护仓库 |

- 冷导入在隔离 site-packages 上以随附解释器（Python 3.14 系）实测；体积为解包后目录实测，非估算。
- 两包均**惰性导入**：`infra/resources.py` 顶层零第三方 import，`tests/test_resources.py::LazyImportTests` 在干净子进程断言 `import infra.resources` 后 `psutil`/`pynvml` 均不在 `sys.modules`（I15-4）。
- 准入记录同步写入 `维护记录/依赖白名单.md`「R3671 依赖准入实测」节与变更记录。
- `requirements.txt` 追加 `psutil==7.2.2`、`nvidia-ml-py==13.615.71`（发行名锁版；pynvml 为导入名，`test_stdlib_closure._requirements_imports` 已登记别名 `nvidia_ml_py→pynvml`）。
- 执行模型自决：**准入**（不走 ctypes 退路，无需「再造轮子」说明）。

## 交付物

### `infra/resources.py`（L1，213 行）

- **`snapshot(path=None)`**：返回 `{collected_at, memory, disk, disk_io, network, vram}`。
  - `memory`：total/available/used/percent（psutil.virtual_memory）；
  - `disk`：path 所在卷 total/used/free（stdlib `shutil.disk_usage`，目标不存在时向上找既有祖先，默认程序目录）；
  - `disk_io`：read/write count 与 bytes（psutil.disk_io_counters）；
  - `network`：bytes/packets sent/recv（psutil.net_io_counters）；
  - `vram`：total/used/free MB（pynvml，见 I15-2）。
  - 任何采集失败该字段为 `'unavailable'`，不抛异常；psutil 缺失时 memory/disk_io/network 降级、disk 仍可用。
- **`ensure_free(path, nbytes)`**（I15-3）：写前磁盘空间原语；不足抛 `contract.infra_errors.StorageError`（`E-IO-WRITE`，兼容 `except OSError`），`detail={'required_bytes','available_bytes','probe'}`；充足返回 `shutil.disk_usage` 结果。地基 C2 磁盘闸门由地基车道接线（任务书「车道」行明定）。
- **外部限额学习**：`note_rate_limited(host, retry_after)`——Retry-After>0 推导 `rpm=max(1, 60/秒)`；裸 429 把当前学习值减半（起点 60、下限 1）；同主机 TTL 600s 内取更保守值、不同主机独立、主机名大小写归一。`effective_rpm(host, configured)`＝min(配置 rpm，学习 rpm)，两侧皆无返回 None。`learned_rpm(host)` 供诊断查看。`api_endpoints` 消费接线属后续轮（本轮范围只含 resources.py 与测试）。
- **线程安全**：限额表 `threading.Lock` 保护；快照为只读采集无共享态。
- **分层**：只 import `contract.infra_errors`（L0）与标准库；无同层边，无 `SAME_LAYER_EDGES` 新增。

### `tests/test_resources.py`（14 条）

- SnapshotTests 5 条：字段形状、disk 跟随 path、vram 永不抛、pynvml 导入失败→'unavailable'（I15-2）、psutil 缺失降级；
- EnsureFreeTests 3 条：小额通过、不存在嵌套路径通过、超额→StorageError E-IO-WRITE＋detail 字节数（I15-3）；
- RateLearningTests 5 条：Retry-After 推导、与配置 rpm 取小、裸 429 减半、TTL 过期、主机隔离；
- LazyImportTests 1 条：子进程断言模块导入不拉 psutil/pynvml（I15-4）。

### 门禁与登记同步

- `tests/architecture/_layers.py`：`resources` 登记 L1（R741 顶层模块表）。
- `tests/architecture/test_dependency_whitelist.py`：生产锁断言六包→八包（契约有意变更：I15 准入两包）。
- `tests/test_stdlib_closure.py`：发行名→导入名别名补 `nvidia_ml_py→pynvml`；**顺带修复 `_defines` 解析盲区**——`from x import (\n A,\n B)` 跨行括号导出（如 `concurrent.futures.__init__` 再导出 `Future`/`wait`）原正则无法识别，导致 I10/I11 引入的 `from concurrent.futures import Future, wait` 在闭包中误报 missing（潜在欠账，本轮定向命令首跑暴露）；新增 `(?s)` 括号导入模式后 13 条全绿。
- `architecture.md`：新增 R3671 段＋L1 模块表补 `resources`。
- `PROJECT_MAP.md`：「成本与运行保障」行补 `infra/resources.py`。
- `维护记录/依赖白名单.md`：八包口径、两包用途行、R3671 准入实测表、变更记录。
- 覆盖率基线：`覆盖率基线.json` targets 11→12（+`tests.test_resources`）；`分支覆盖率基线.json` targets 追加同名；分支下限表补 `resources.py` 实测值。
- 任务书 I15-1~4 勾选；`project_status.md` 轮次头同步。

## 验证汇总

| 检查 | 结果 |
| --- | --- |
| `run_selftests.py -k resources dependency_whitelist stdlib_closure startup_budget`（任务书指定） | 43 条；唯一红 `test_site_packages_whitelist`＝purelib pydantic 五包污染（annotated-types/pydantic/pydantic-core/typing-extensions/typing-inspection），R3564 起同录的共享环境欠账，与本轮零因果；本轮相关 42 条全绿 |
| `smoke_test.py`（默认冒烟） | 9/9 绿 |
| `smoke_test.py --architecture` | 560 条 6 红→修复后复验：4 项系覆盖率基线重测在途竞态（行基线已重写 665/85、分支基线重测完成后复跑转绿）、1 项 `test_no_new_silent_exception_handlers`（resources.py `except Exception: pass` 已改为外层统一降级，棘轮 4/4 绿）、1 项 `test_site_packages_whitelist` 环境红（pydantic 五包污染，同 R3564/R3610 归因零因果） |
| `tests/test_resources.py` 直跑 | 14/14 绿 |
| 行覆盖率基线重测 | 665 模块／85 覆盖／12 组目标全绿；`infra/resources.py` 行覆盖 83.8%（109/130） |
| 分支覆盖率基线重测＋下限 | 97 模块／2909 决策点／1622 覆盖（重测终值）；`resources.py` 20 点 8 覆盖 40.0%，下限登记 40.0 |

### 本轮产生的契约变更（如实记录）

- 生产锁 6→8 包：`test_dependency_whitelist` 断言同步；`test_stdlib_closure` 别名表同步。
- `test_stdlib_closure._defines` 增加跨行括号导入识别：测试解析器缺陷修复，断言语义不变（仍要求符号真实可解析）。

### 遗留与接线（不属本轮范围，如实记录）

- `ensure_free` 的调用方接线属地基车道 C2（任务书「车道」行明定）；`note_rate_limited`/`effective_rpm` 的 `api_endpoints` 消费接线属后续轮。
- `snapshot()` 当前无产品内调用方（FL-12 交付的是原语；I21/I22 自适应并发与预加载才是消费方，任务书依赖表 I15→I21/I22）。
- pydantic 环境污染红项维持原状（不修改共享 runtime）。

## 三基线

- 默认冒烟：9/9 绿。
- 架构门禁：本轮新增模块＋登记表变更，已跑 `--architecture` 全量，终态与历史环境红对比见上表。
- 全量回归：以 `.git/full-safe-receipts.json` 真实凭据为准；本轮非 master 提交点触发轮。

<!-- evidence 回填于提交时 -->
</content>
</invoke>','file_path':'D:\漫剧制作助手\.agents\worktrees\devin-l1-enterprise\程序\tasks_round\tasks_round_3671_result.md