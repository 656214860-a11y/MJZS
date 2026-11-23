# R4144 结果：手动导入资产图片按内容验真（改名成 .png/.jpg 的文本文件不再被登记进资产库）
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "443ab40bd567b398", "exit": 0, "failed": 0, "passed": 17, "round": 4144, "tests": "run_selftests.py -k asset_image_import asset_detail_service"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮。任务卡 W7-FIX-AUD-US03-IMGCHECK（波次 W2），审查发现 AUD-US03 D3：`domain/asset_batch_service.py` 的 `import_asset_image` 只查文件后缀不验内容，改名成 .png/.jpg 的文本文件导入成功；SG-01 的 `_has_imported_image`（`orchestrator/stage_parallel.py:716-726`）只查登记表指向的文件存在且非空，门禁放行但资产图不可用。同型缺陷在 `domain/asset_detail_service.py` 的 `_source`（正典板视角与状态变体缩略图两条手动绑定路径）也存在，一并修复。车道目录 fix-aud-us03-imgcheck，分支 codex/fix-aud-us03-imgcheck，基准 3383684c。验收窗口提示对照 `asset_batch_service.py` 旧 `:55-62`（`register_image` 的 PNG 内容校验）核实——缺陷属实。
- （二）测试跑了吗、三个基线各是什么结果：定向——跑了。`run_selftests.py -k asset_image_import asset_detail_service`：改产品之前 17 条用例里 2 个测试方法红（新加的拒收用例，失败原因与缺陷一致，见「改前红」）；改后同一条命令「共 17 条用例，0 个文件有红」「ALL TESTS PASSED」，退出码 0。条数对账：改前 13 条（导入 3＋详情 9＋架构边界 1），新增 4 条（导入 2＋详情 2），改后 17 条。架构门禁——`smoke_test.py --architecture` 整套跑过：「Ran 700 tests in 258.495s」「OK」，退出码 0。中途第一遍红过 2 条（LR-03 同层依赖边），处置见「与任务书不同的地方」第一条，改法调整后第二遍全绿。默认冒烟和全量自测——没跑（卡面只允许定向命令与 `--architecture`）。
- （三）欠账少了吗：少了一条——两条手动导入路径现在按内容验真，非图片文件在写盘前被拒。新增一条要如实记的欠账：三个不在本卡允许文件清单内的既有用例以「非图片字节」作导入源，产品收紧后它们会在全量自检里红（名单与原因见「未覆盖项」），需要后续轮次把它们的夹具换成真图片字节。

## 缺陷复现方式

改产品之前先写测试：`import_asset_image` 与 `bind_canonical_view`/`bind_variant_thumbnail` 各喂「后缀合法但内容是文本／截断头」的文件。改前代码只查 `source.suffix.lower() in ('.png','.jpg','.jpeg','.webp')`（旧 `asset_batch_service.py:114-116`）与「存在且非空」（`asset_detail_service._source` 旧 `:52-55`），于是导入成功、登记表写入 `image` 指针，SG-01 的 `_has_imported_image` 只见文件存在且非空而放行——门禁过、图不可用，正是 AUD-US03 D3 描述的链路。

## 改前红

改产品代码之前（两个产品文件都还是原样），在 程序 目录下跑 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k asset_image_import asset_detail_service`，退出码 1。共 17 条用例，2 个文件有红；红的全部集中在本轮新加的两个拒收用例（每个文件各 7 条红＝6 个失败子用例＋循环后 1 条收尾断言），失败原因与缺陷一致。输出尾部原文：

```
IMPORT OK: all modules imported
定向：忽略增量台账，执行 3 个匹配测试文件
跑 3 个测试文件 / 3 路工作单元（8 路并行）
  architecture.test_asset_image_import_boundary     1 条     0.1 秒
  test_asset_image_import_service     5 条     4.3 秒  ✗ 7
  test_asset_detail_service     11 条     5.1 秒  ✗ 7

共 17 条用例，5.8 秒；2 个文件有红
最慢 3 路工作单元：
  test_asset_detail_service     5.1 秒 / 11 条
  test_asset_image_import_service    4.3 秒 / 5 条
  architecture.test_asset_image_import_boundary    0.1 秒 / 1 条
实际跳过 0 条用例：本机没有任何登记位被跳过

### test_asset_image_import_service（7 条红）

test_import_rejects_non_image_content_with_image_suffix (name='fake.png'/'fake.jpg'/'fake.jpeg'/'fake.webp'):
    AssertionError: ValueError not raised
test_import_rejects_non_image_content_with_image_suffix (name='broken.png'):
    ValueError: 原图目录已有同名文件：...\CHAR_001.png。请先移走该文件后再导入。
    （断言正则 '图片内容无效' 不匹配，子用例仍红；broken.jpg 同型——前序 fake 子用例已把 CHAR_001.jpg 发进原图目录，撞上同名分支）
循环结束后 assets.json 已被改写，收尾 assertEqual 断言失败，方法中止。

### test_asset_detail_service（7 条红）

test_non_image_content_returns_user_error_without_publication（file × bind_canonical_view/bind_variant_thumbnail 共 6 个子用例）:
    AssertionError: ServiceResult(ok=True, reason='', recoverable=False, data=WindowsPath('.../正典板/CHAR_001_front.jpg')) is not an instance of <class 'contract.service_contract.UserError'>
（fake.png 两个子用例同型；其逐字输出被运行器截断未留存）
循环结束后索引文件已被改写，收尾 assertEqual(old_index) 断言失败，方法中止。
```

（上引输出中的临时目录绝对路径按报告规则以 `...` 省略，其余为逐字原文。）

`test_import_rejects_non_image_content_with_image_suffix`（6 个子用例）：文本改名 .png/.jpg/.jpeg/.webp 导入成功（`ValueError not raised`），坏 PNG／坏 JPEG 撞上前序子用例留下的同名文件被同名分支拦截——两类失败都以「导入放行了非图片」为根。`test_non_image_content_returns_user_error_without_publication`（3 个文件 × 2 条绑定路径＝6 个子用例）：非图片内容经 `bind_canonical_view`／`bind_variant_thumbnail` 全部返回 `ServiceResult(ok=True)` 并发布落盘——同型缺陷复现。其余 15 条（含两个「真图被收」新用例与全部既有用例）改前即绿：真图本来就能过后缀检查，新夹具只是把它换成了内容真实的图片。

## 改了哪些文件

- `domain/asset_batch_service.py`：新增模块私有 `_image_content_ok(path)`（`:102-125`）——按内容验真：PNG 要求 ≥33 字节＋`\x89PNG\r\n\x1a\n` 签名＋`IHDR` 在 12-16 字节＋`IEND` 在末段（与 `register_image` 旧 `:57-61` 同一严度）；JPEG 要求 `\xff\xd8` 开头＋`\xff\xd9` 结尾；WEBP 要求 `RIFF`＋`WEBP`。只读头 16 字节与尾 8 字节，不把整图读进内存。`import_asset_image` 在后缀检查之后（`:143-144`）加一句拒收：内容不符抛 `ValueError('图片内容无效，请选择完整的 PNG、JPG 或 WebP 图片')`，发生在任何写盘／改名之前。
- `domain/asset_detail_service.py`：新增同名私有 `_image_content_ok(path)`（`:50-73`，与上一处逐字相同的判定）；`_source` 在后缀检查之后（`:82-83`）加同样的拒收，抛 `_BindingInputError`，经 `_binding_result` 变成 `UserError` 返回，发生在复制与索引更新之前。
- `tests/test_asset_image_import_service.py`：夹具从 `b'new image'` 换成 `tests.image_fixtures.png()` 生成的真 PNG（`SOURCE_PNG`，`:11`、`:26`），原有「内容逐字节一致」断言同步改为对 `SOURCE_PNG`（`:36`），断言强度不变；新增 `test_import_rejects_non_image_content_with_image_suffix`（`:61`，文本改名四种后缀＋PNG 只有签名＋JPEG 无 EOI，共 6 个子用例，断言拒收、登记表不变、`assets/` 目录不产生、源文件保留）与 `test_import_accepts_real_jpeg_and_webp`（`:81`，PIL 现造真 JPEG/WEBP 各一，断言落盘字节一致、登记表指针正确、覆盖 scenes/props 两个类别目录）。
- `tests/test_asset_detail_service.py`：夹具从 `b'png-data'` 换成同一 `png()` 真 PNG（`:12`、`:24`），两处字节断言同步（`:31`、`:65`）；新增 `test_non_image_content_returns_user_error_without_publication`（`:113`，文本 .png、JPEG SOI 无 EOI、RIFF/WAVE 改名 .webp，各过 `bind_canonical_view` 与 `bind_variant_thumbnail`，断言 `UserError`、索引不变、正典板无文件）与 `test_real_jpeg_content_is_accepted`（`:131`，PIL 真 JPEG 被收、文件名与字节正确）。
- `tasks_round/tasks_round_4144_result.md` 是本文件；`tasks_round/evidence/R4144.json` 由提交工具生成。

没有改基线、棘轮登记值、跳过登记；没有动 `orchestrator/stage_parallel.py` 的 SG-01（卡面把它列为受害方而非修改对象——入口收紧后坏图进不了库）；没有新建产品模块；没有改允许范围以外的文件。

## 与任务书不同的地方

- 验证器在两个产品文件里各放了一份逐字相同的私有 `_image_content_ok`，没有做成单点共用。原因：第一版写成 `asset_detail_service` 顶层 `from domain.asset_batch_service import image_content_ok`，架构门禁 `test_layer_relations`（LR-03 同层依赖边）判红——`('asset_detail_service','asset_batch_service')` 不在 `_layers.SAME_LAYER_EDGES` 登记基线里（实测 5 > 基线 4），而 `tests/architecture/_layers.py` 不在本卡允许修改的文件里，登记新边无门。反向同样未登记。域内既有可复用宿主（`asset_plan`/`asset_context`/`asset_reference_prompts`）也都不在允许清单。两份十几行的魔数判定是受约束下的最小合规写法；判定口径注释里已写明与 `asset_reference_images.image_bytes` 一致，后续若要收敛可在登记轮把它下沉到公共模块。
- 两个测试文件的既有夹具从「任意字节」换成了内容真实的 PNG/JPEG。按 AGENTS.md §2.4 这是有意契约变更的同步：导入契约从「后缀合法」收紧为「后缀合法且内容是对应格式的完整图片」，夹具必须跟上契约才能继续测原有行为（复制逐字节一致、登记、改名、回滚）；断言本身没有删改弱化，只把期望值换成新夹具字节。
- 拒收文案用「图片内容无效，请选择完整的 PNG、JPG 或 WebP 图片」，与既有后缀拒收文案「请选择 PNG、JPG、JPEG 或 WEBP 图片」同句式；`asset_detail_service` 侧经 `_BindingInputError`→`UserError` 走用户可见错误通道，`import_asset_image` 侧抛 `ValueError` 与该函数既有拒收方式一致。
- 校验口径取「魔数＋首尾结构」（PNG 的 IHDR/IEND、JPEG 的 EOI、WEBP 的 RIFF/WEBP），没有上 PIL 解码：与 `register_image`（只认 PNG）和 `asset_reference_images.image_bytes`（参考图导入）的既有严度一致，且不需要新依赖；Pillow 本就在白名单内，仅测试夹具用它现造真 JPEG/WEBP。

## 改后命令输出尾部原文

定向（改后第二遍，退出码 0）：

```
跑 3 个测试文件 / 3 路工作单元（8 路并行）
  architecture.test_asset_image_import_boundary     1 条     0.1 秒
  test_asset_image_import_service     5 条     1.4 秒
  test_asset_detail_service     11 条     3.0 秒

共 17 条用例，3.8 秒；0 个文件有红
...
ALL TESTS PASSED
```

架构门禁（改后第二遍，退出码 0）：

```
----------------------------------------------------------------------
Ran 700 tests in 258.495s

OK
✅ 架构治理测试：tests/architecture
```

第一遍架构门禁（共用导入写法时）退出码 1，尾部原文：

```
FAIL: test_compliance_ledger_matches_measured_violations ...
AssertionError: Lists differ: ['LR-03 同层依赖登记方向且禁止互相依赖：实测 5 > 基线 4'] != []
FAIL: test_lr03_unregistered_same_layer_edge_is_red ...
AssertionError: Lists differ: [('asset_detail_service', 'asset_batch_service')] != []
Ran 700 tests in 279.017s
FAILED (failures=2)
```

## 命令与退出码

都在车道的 程序 目录下跑，python.exe 指 `..\..\..\..\运行环境\Python\python.exe -B`。

| 命令 | 结果 |
| --- | --- |
| git -c core.quotepath=false status --porcelain | 无输出（干净） |
| git log -1 --format=%h | 3383684c |
| git rev-parse --abbrev-ref HEAD | codex/fix-aud-us03-imgcheck |
| python.exe -B run_selftests.py -k asset_image_import asset_detail_service（改产品之前） | 退出码 1，17 条用例 2 个文件有红（见「改前红」） |
| python.exe -B run_selftests.py -k asset_image_import asset_detail_service（改产品之后） | 退出码 0，「共 17 条用例」「0 个文件有红」「ALL TESTS PASSED」 |
| python.exe -B smoke_test.py --architecture（第一遍，共用导入写法） | 退出码 1，LR-03 同层边 2 条红 |
| python.exe -B smoke_test.py --architecture（改为两处私有副本之后） | 退出码 0，「Ran 700 tests」「OK」 |
| python.exe -B scripts\dev.py claim | 领到轮次 4144 |

## 未覆盖项

- 未跑默认冒烟、未跑全量自测（卡面禁止卡外命令）；未在真实界面上点过导入对话框。
- **范围外连带影响（如实记录）**：以下三个既有用例以「非图片字节」作导入源，不在本卡允许修改的文件里，本卡无法同步夹具。产品收紧后它们在全量自检中会红，需要后续轮次把夹具换成 `tests.image_fixtures.png()` 一类的真图片字节（各只差一行 `write_bytes`）：
  - `tests/test_uow_write_paths.py` `AssetBatchTransactionTests.test_import_asset_image_cancel_restores_image_and_registry`（`:76` 写 `b'new image'`）
  - `tests/test_uow_write_paths.py` `AssetDetailTransactionTests.test_bind_cancel_restores_image_and_index`（`:110` 写 `b'png-data'`）
  - `tests/test_latent_defects_r1853.py` `AssetBindingReplaceRetryTests.test_transient_sharing_violation_is_retried`（`:153` 写 `b'png-data'`）
  这三条测的是事务回滚语义，与图片校验无关；它们红的原因是导入在更早的输入校验处被拒、到不了被测的取消点，不是回滚逻辑被破坏。
- SG-01 的 `_has_imported_image` 本身仍只查「存在且非空」，没有顺手加内容校验：卡面把它列为受害方描述，验收窗口只点名导入侧；存量已入库的坏图仍需靠重新导入覆盖，门禁侧是否加固留给后续卡。
- `stage_animatic_gateways.import_animatic_references`（`:46`）同样只查后缀不验内容，属范围外同型点，只记录未改。
- 校验是「魔数＋首尾结构」，不是完整解码：结构合法但像素数据损坏的极端文件仍可能通过（与 `image_bytes` 既有口径一致）；要解码级把关需另起一轮评估。

## 提交

用 `scripts\dev.py commit` 提交，只提交上面列出的文件。提交号不写在本文件里，见完成报告。
