# R4325 结果：修复 AssetPagesMixin 删图确认文案在替身宿主上的 AttributeError（FIX-ASSET-DELETE-CONFIRM）
<!-- round-evidence: {"commit_base": "3cc271764", "credential_hits": 0, "evidence_sha256": "24f560bcdf05becd", "exit": 0, "failed": 0, "passed": 86, "round": 4325, "tests": "run_selftests.py -k asset_page_services asset_batch_window asset_detail asset_impact"} -->

## 三问
- 轮次类型：修复轮（§3.2）。卡 FIX-ASSET-DELETE-CONFIRM：R4251/R4276 S05-USAGE 引入的主干回归，test_asset_page_services 两条红灯。
- 测试和三个基线：定向命令 `run_selftests.py -k asset_page_services asset_batch_window asset_detail asset_impact` 改前 2 红、改后 86 条全绿（退出码 0）；`smoke_test.py --architecture` 702 条全过（退出码 0）；默认冒烟 8/8 本轮未运行（卡面验收未列）。
- 欠账：主干复验红灯的回归已闭环，欠账减少，未新增欠账。

## 缺陷复现
- 复现命令（程序 目录下原样执行）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k asset_page_services asset_batch_window asset_detail asset_impact`
- 改前红 2 条，失败原因与卡面一致（退出码 1）：
  - `test_delete_image_redraws_the_assets_page`：`AttributeError: 'types.SimpleNamespace' object has no attribute '_delete_image_confirm_text'`，抛在 `ui/desktop_asset_pages.py:529` 的 `self._delete_image_confirm_text(aid,image)`。
  - `test_batch_delete_redraws_the_assets_page_once`：`AttributeError: 'types.SimpleNamespace' object has no attribute '_batch_delete_images_confirm_text'`，抛在 `ui/desktop_asset_pages.py:553` 的 `self._batch_delete_images_confirm_text(targets,shown,how)`。
- 根因：测试用 SimpleNamespace 替身宿主以 unbound 方式调 Mixin 方法，宿主实例上没有这两个私有方法属性；同函数内 `asset_write_base`（:534）早已按 `AssetPagesMixin.asset_write_base(self)` 兼容写法调用，这两个调用点漏改。

## 改动
- `ui/desktop_asset_pages.py:528-532`：`delete_asset_image` 确认文案改为 `fn=getattr(self,'_delete_image_confirm_text',None)`，`callable(fn)` 时用实例方法，否则回退 `AssetPagesMixin._delete_image_confirm_text(self,aid,image)`；ask=False 路径不算文案的逻辑不变。
- `ui/desktop_asset_pages.py:553-555`：`delete_asset_images` 同法回退 `AssetPagesMixin._batch_delete_images_confirm_text(self,targets,shown,how)`。
- `tests/test_asset_page_services.py:90-92`、`:104-106`：两个既有用例各追加 3 行断言——confirm 收到的文案非空且包含 `'CHAR_001'`；原有断言逐字保留未弱化。
- 行为边界：真 Desktop 宿主与 AssetPagesMixin 子类实例（含子类覆写）仍走实例方法分支，只有替身宿主走 Mixin 绑定回退；`_delete_image_confirm_text`/`_batch_delete_images_confirm_text` 内部对 `self.root` 的访问本就有 `try/except Exception` 兜底（:486-492、:500-511），SimpleNamespace 无 `root` 时安全落纯文案。

## 核对（命令输出尾部原文）
- `run_selftests.py -k asset_page_services asset_batch_window asset_detail asset_impact`，退出码 0：
  ```
  共 86 条用例，235.3 秒；0 个文件有红
  最慢 8 路工作单元：
    test_asset_detail#2          48.4 秒 / 16 条
    test_asset_detail#1          48.2 秒 / 14 条
    test_asset_detail#3          31.6 秒 / 10 条
    test_asset_batch_window      20.9 秒 / 9 条
    test_asset_detail_service     3.1 秒 / 11 条
    test_asset_impact             0.2 秒 / 16 条
    test_asset_page_services      0.1 秒 / 8 条
    architecture.test_asset_detail_binding_boundary    0.0 秒 / 2 条
  实际跳过 0 条用例：本机没有任何登记位被跳过
  增量台账已刷新：…\.git\selftest-incremental.json
  最近 5 轮自检中位基线：21.5 秒

  ALL TESTS PASSED
  ```
- `smoke_test.py --architecture`，退出码 0：
  ```
  ----------------------------------------------------------------------
  Ran 702 tests in 284.602s

  ✅ 架构治理测试：tests/architecture
  OK
  ```

## 未验证
- 默认冒烟 8/8 未运行；全量 `run_selftests.py --all --safe` 未运行（卡面验收未列，定向与架构门禁已覆盖改动面）。
- 真 Desktop 交互弹窗未人工点验；实例方法分支由 `test_asset_batch_window.py` 的 `DeleteConfirmCopyTests`（真子类宿主）覆盖，9 条全绿。
