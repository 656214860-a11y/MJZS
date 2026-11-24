# R4342 结果：REL-10 许可证与披露（关于块、随包 NOTICE、FFmpeg 构建类型披露、逐包许可证表）
<!-- round-evidence: {"commit_base": "7cbe112c5", "credential_hits": 0, "evidence_sha256": "04a0ef770b47e05f", "exit": 0, "failed": 0, "passed": 28, "round": 4342, "tests": "run_selftests.py -k sbom distribution_build"} -->

## 三问
- 轮次类型：修复轮（§3.2）。卡 REL-10：发布就绪调研确认的许可证/披露缺口——无应用内关于/开源许可入口、随包 ffmpeg/ 无 NOTICE 且未写构建类型、THIRD_PARTY_NOTICES.txt 无 GPL 披露、依赖白名单缺 6 包逐包表、docs/specs/03 的「LICENSE/NOTICE」说法与实际不符。
- 测试和三个基线：定向 `run_selftests.py -k sbom distribution_build` 改前 4 红、改后 28 条全绿（退出码 0）；`-k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` 34 条全绿（退出码 0）；`smoke_test.py --architecture` 首跑 5 红（新增 UI 代码触发棘轮，改写法后）702 条全过（退出码 0）；默认冒烟 8/8 本轮未运行（卡面验收未列）。
- 欠账：减少。缺陷面全部落地，未新增欠账；首跑棘轮红灯在同一轮内按门禁口径改写法闭环，未调任何登记值。

## 缺陷复现
- 复现命令（程序 目录下原样执行）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k sbom distribution_build`
- 改前红 4 条（退出码 1），原因与卡面缺陷一致：
  - `test_sbom.BundledNoticeTests.test_bundled_ffmpeg_notice_carries_gpl_disclosure`：`AssertionError: False is not true : 随包 ffmpeg/ 下缺 NOTICE.txt`
  - `test_sbom.BundledNoticeTests.test_missing_bundled_notice_fails_distribution_verify`：`FileNotFoundError: [WinError 2] 系统找不到指定的文件。: '…\\out\\运行环境\\ffmpeg\\NOTICE.txt'`（构建物根本不产出 NOTICE，unlink 复现缺失场景时即抛）
  - `test_sbom.AboutPageTests.test_about_page_block_lists_version_build_and_license_entry`：`ImportError: cannot import name 'about_info' from 'ui.desktop_account_page'`
  - `test_sbom.AboutPageTests.test_about_page_license_entry_survives_missing_bundle`：同上 `ImportError: cannot import name 'about_info'`
- 另 2 条新用例落地即绿（`missing THIRD_PARTY_NOTICES.txt → verify 失败`、`NOASSERTION → release_blockers`）——REL-02 既有门禁已覆盖，非本卡缺陷。

## 改动
- `scripts/sbom.py:26-28`：新增 `_GPL`/`_BUILD` 正则与 `FFMPEG_UPSTREAM` 源码获取链接；`:123-144` `_build_type()` 从版本串抽 `essentials_build`、`gpl_tool_homes()` 按 `release:path` 把 GPL 工具归组到 `运行环境/<目录>`；`:146-161` `gpl_notice()` 生成目录级 NOTICE（许可证、构建类型、构建来源、源码获取方式）；`:202-205` THIRD_PARTY_NOTICES.txt 增「GPL 组件披露」段；`:214-224` `write()` 逐目录落 `NOTICE.txt`，返回值扩为全部写入路径的 tuple。
- `scripts/distribution_build.py:266-274`：`verify()` 用 `gpl_tool_homes()` 计算 `missing_notices`，`supply_chain` 检查新增该键且 `ok` 要求其为空。
- `ui/desktop_account_page.py:21-22,26,28-29`：新增 `VERSION`、`file_cache.read_json`、`TEXT_ROWS`、`TextArea` 导入；`:73-75` 模块级 `NOTICES_NAME`/`DIGEST_NAME`/`APP_ROOT`；`:78-93` `about_info()`（版本、构建提交、随包许可全文，无 Tk 依赖）；`:96-104` `about_lines()`；`:107-124` `about_card()`（Card＋展示行＋「查看开源许可」按钮页内展开只读 TextArea，不弹模态）；`:333-337` `account_page()` 尾部挂 `_account_about_card()` 薄方法调模块级构建（类体积棘轮上限 600 行）。
- `tests/test_sbom.py:68-104`：`FFMPEG_TOOL`/`NOTICE_MANIFEST`/`_notice_source()` 构建夹具；`:105-161` `BundledNoticeTests` 4 条（NOTICE 存在且含 GPL+essentials+ffmpeg.org；缺 NOTICE → verify 红 `missing_notices`；缺 THIRD_PARTY_NOTICES → verify 红；NOASSERTION → release_blockers）；`:163-193` `AboutPageTests` 2 条（about_info/about_lines/_account_about_card 存在且含版本/构建/许可入口；缺包存活）；并 `import distribution_build`。
- `维护记录/依赖白名单.md`：新增「生产包逐包许可证登记」表，8 个生产包（requests、urllib3、certifi、charset-normalizer、idna、Pillow、psutil、nvidia-ml-py）逐包许可证与来源，与 `sbom.py` `PYPI` 表同一份事实。
- `docs/specs/03_安装签名与分发.md`：§2.2 目录树补 `运行环境\ffmpeg\ … + NOTICE.txt`；§4 SBOM 格式行写明 `THIRD_PARTY_NOTICES.txt`（含 GPL 组件披露）。
- 棘轮适配（同轮闭环）：`except Exception: pass` → 顶层直接 import VERSION（无兜底需要）；裸 `json.loads` → `file_cache.read_json`＋窄 `except (OSError, ValueError)`；`height=10` → `TEXT_ROWS['xl']`；`font=FONTS['heading_2']` 标题 Label → 纯 `ttk.Label`；UI 构建移出 `AccountPageMixin` 保类体积上限。

## 核对（命令输出尾部原文）
- `run_selftests.py -k sbom distribution_build`，退出码 0：
  ```
  跑 2 个测试文件 / 2 路工作单元（8 路并行）
    test_sbom                      9 条     0.6 秒
    test_distribution_build       19 条     2.0 秒

  共 28 条用例，2.7 秒；0 个文件有红
  ……
  ALL TESTS PASSED
  ```
- `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`，退出码 0：
  ```
  共 34 条用例，1.2 秒；0 个文件有红
  ……
  ALL TESTS PASSED
  ```
- `smoke_test.py --architecture`，退出码 0（复跑；首跑 5 红为新增代码棘轮违规，已改写法）：
  ```
  ----------------------------------------------------------------------
  Ran 702 tests in 257.943s

  OK
  ✅ 架构治理测试：tests/architecture
  ```

## 未验证
- 默认冒烟 8/8 未运行；全量 `run_selftests.py --all --safe` 未运行（卡面验收未列）。
- 真 Desktop 账户页未人工点验；「查看开源许可」展开为页内 TextArea，逻辑与数据层由 `AboutPageTests` 无 Tk 覆盖。
- `about_info` 的构建提交取自 `分发清单.json` 的 `commit` 字段，由分发构建器产出；开发副本无此文件时显示「开发副本」。
