# R4410 结果：S04-SKETCH-BACKENDS 分镜预演可插拔草图生成器接口（REQ-S04-78~79）
<!-- round-evidence: {"commit_base": "6abcede44", "credential_hits": 0, "evidence_sha256": "08a13f701cc06b0d", "exit": 0, "failed": 0, "passed": 18, "round": 4410, "tests": "run_selftests.py -k animatic_sketch_backends"} -->

- 轮次类型（§3）：3.1 功能轮（新增 L2 模块 `domain/animatic_sketch_backends.py`）。
- 测试跑了吗：跑了定向与架构门禁，均绿；三个基线——默认冒烟本轮未跑（工作树未合入 master，验收按任务书两条命令）；架构门禁 708 条全绿；定向 18 条全绿；覆盖率基线已用工具机械刷新（133/685）。
- 欠账少了吗：零新增同层 L2 边、零新增外发点（ComfyUI 客户端改由编排层注入，不新增登记项）；参数棘轮未抬高。

## 缺陷复现方式（先红）

镜头草图生成写死在 `domain/animatic_service.py:80-103`（`local_sketch`/`_collect_sketch`），没有可插拔分流接口：无 `animatic_sketch_backend` 设置分流与默认 `comfy_local` 后端登记、无付费后端「默认关闭须显式开启」门禁、无每镜导入替换图校验入口（REQ-S04-10 口径）。REQ-S04-78/79 与 DES-S04-22（docs/stages/S04_分镜预演.md，现为 ⬜，本卡禁止改该文件，未翻 ✅）要求的能力整体缺失。

改前跑 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_sketch_backends`，红 1 个文件共 1 条（原文摘要）：

```
### test_animatic_sketch_backends（1 条红）

===== test_animatic_sketch_backends (unittest.loader._FailedTest.test_animatic_sketch_backends) =====
ImportError: Failed to import test module: test_animatic_sketch_backends
Traceback (most recent call last):
  File "D:\漫剧制作助手\运行环境\Python\Lib\unittest\loader.py", line 141, in loadTestsFromName
    module = __import__(module_name)
  File "…\程序\tests\test_animatic_sketch_backends.py", line 7, in <module>
    from domain import animatic_sketch_backends as backends
ImportError: cannot import name 'animatic_sketch_backends' from 'domain' (…\程序\domain\__init__.py)
```

红的原因即卡面缺陷：`domain.animatic_sketch_backends` 不存在，可插拔接口缺失。

## 改动位置（文件:行号）

- `domain/animatic_sketch_backends.py`（新建，1-101）：纯 L2、零同层与零下行 import（客户端注入式）。`DEFAULT_BACKEND='comfy_local'`；`ALLOWED_IMAGE_SUFFIXES`/`MAX_IMAGE_BYTES`（REQ-S04-10 口径）；`BACKENDS` 登记表与 `register`/`unregister`/`list_backends`（按名排序只读副本）；`create(settings)` 按 `animatic_sketch_backend` 分流，未登记报「未知的草图生成后端：…」，paid=True 且 `animatic_allow_paid_sketch is not True` 报「付费草图后端默认关闭…」且 factory 零调用；`comfy_local_render` 保留草图前缀、固定 seed（缺省 1）、超时报「不自动重复提交」、`ComfyGenerationFailed`/`ComfySubmissionUncertain` 原样上抛；`validate_imported_sketch` 校验存在/后缀/0<大小≤20MB 返回（小写后缀, 字节）。
- `tests/test_animatic_sketch_backends.py`（新建）：18 条，覆盖卡面全部边界例子（缺省分流、空 references=[] 构图提交、付费门禁缺省/False/'true'/1 拒绝且 factory 零调用、未知后端中文错、超时不重投仅 1 次提交、两类 Comfy 异常原样上抛、替换图 0字节/>20MB/非法后缀/不存在拒绝与 PNG/WebP/JPG/大写后缀/恰好20MB 放行、settings 注入客户端与缺注入报错）。
- `tests/architecture/_layers.py:156-158`：`_register(2, "animatic_sketch_backends")`。
- `维护记录/架构统一基数.json`：第一项 `entity_paths` 加 `"animatic_sketch_backends": "domain/animatic_sketch_backends.py"`，`exempt_items` 加 `"animatic_sketch_backends"`，`exempt_count` 58→59。
- `维护记录/覆盖率基线.json`：scripts/coverage_report.py 原 15 目标机械刷新（tests_ok=true，133/685）。
- `runbook.md` §11：模块数 684→685、未触达 551→552、19.5%→19.4%（181、183、186 行）。

## 签名与卡面接口契约的一处偏差及理由

卡面 `comfy_local_render(..., *, client=None)` 沿用 `animatic_service.local_sketch`（domain/animatic_service.py:83）的「缺省自行 `Comfy(url)`」语义。REL-11 门禁 `test_outbound_registry_covers_every_outbound_point`（tests/architecture/test_http_boundary.py:208）把任何 `Comfy` 名 Load 引用计为外发点、须在 `docs/process/外发内容清单.md` 登记——该文件不在本卡允许修改清单，首次架构门禁即红 1 条（`{'domain/animatic_sketch_backends.py': ['comfy_local_render x1 @L45']}`）。收拢方式：`client=None` 签名原样保留，客户端改由编排层注入——优先 `client` 参数、其次 `settings['comfy_client']`，两者都缺时报中文错「缺少本地 ComfyUI 客户端：请由编排层注入…」。本模块零外发点、零下行 import；`comfy_client` 注入点由后续 S04-TIMELINE-LOCK 装配（animatic_service 既有 Comfy 构造已登记在外发内容清单 L69-70）。

## 验收命令输出尾部（原文）

命令一 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_sketch_backends`（目录 程序，退出码 0）：

```
跑 1 个测试文件 / 1 路工作单元（8 路并行）
  test_animatic_sketch_backends    18 条     0.1 秒

共 18 条用例，0.7 秒；0 个文件有红
最慢 1 路工作单元：
  test_animatic_sketch_backends    0.1 秒 / 18 条
实际跳过 0 条用例：本机没有任何登记位被跳过

ALL TESTS PASSED
```

命令二 `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（目录 程序，退出码 0）：

```
----------------------------------------------------------------------
Ran 708 tests in 225.579s

OK
✅ 架构治理测试：tests/architecture
```

覆盖率刷新 `..\..\..\..\运行环境\Python\python.exe -B scripts\coverage_report.py <原15目标> --json 维护记录/覆盖率基线.json`：退出码 0，尾部 `模块被覆盖：133/685；目标用例：全通过`。

## 没有验证的地方

- 未连真实 ComfyUI：客户端注入路径只经假客户端验证（构图前缀/固定 seed/超时不重投/异常透传），真实提交与取回未验证。
- L3 消费方（`animatic_service.build_bundle` 改走 `create()` 分流、`settings['comfy_client']` 注入、stage_animatic_gateways 导入替换入口）由后续 S04-TIMELINE-LOCK 装配，本轮未接线。
- 未跑默认冒烟与全量 `--all --safe`（非本卡验收项）。

## 卡外发现（只记录，不顺手修）

- `docs/stages/S04_分镜预演.md` 已含 REQ-S04-78/79 与 DES-S04-22（现为 ⬜）；本卡禁止改该文件，未翻 ✅。
- `domain/animatic_service.py:80-103` 的 `local_sketch`/`prepare_reference` 各自构造 `Comfy(...)`（外发点已登记在外发内容清单 L69-70）；后续装配轮可把 client 透传给 `comfy_local_render`，草图路径即与本接口汇合。
