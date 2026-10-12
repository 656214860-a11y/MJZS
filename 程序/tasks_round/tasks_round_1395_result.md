# R1395：出站 HTTP 收口到 platform_tools.open_https（覆盖率审计26 清零）

类型：修复轮（§3.2，2026-10-13）。中央轮次：1395。范围＝R1393 递归口径新暴露的 4 条 agent 真候选中「网络传输」2 条（覆盖率审计26）。

## 三个必答
- 本轮类型：修复轮（§3.2）——`platform_tools` 新增唯一出站 HTTP 入口 `open_https`，`agent/core.py` 的 `request()`／`download()` 改经它；同步台账与判据。
- 测试：定向 `test_coverage_audit_ratchet`＋`test_unification_ratchet` **7/7**；默认冒烟 **8/8**；架构 **341/341**；**全量 `run_selftests.py --all --safe` 4983 条、602.9 秒、0 红**（命中 §5 五轮规则 1395−1390=5）。
- 欠账：本轮已清（全量收口）；`last_full_safe_all_round` 由 1390 刷新为 1394（凭据 tree `886cfd07…`＝`d93993e:程序`）。

## 语义裁定（为什么收口而非豁免）
- 两处调用点均为应用自身资产 I/O，非模型路由：`asset_reference_search.fetch_bytes()` 经 `request(url, raw=True)` 下载参考图；`engine.py` 经 `download(url, dest)` 下载云端生成视频。
- `download()` 依赖 `agent.core` 的原子发布权威（`temporary_path`／`replace`）——按审计 20「绕过 `agent.core` 的 L3 `replace_file` 覆写即违规」，它不能外移，只能把**出站调用**收口到宿主适配层。
- 故与 R1394（进程→`run_process`）、R832（探测→`probe_http_endpoint`）同法：在 `platform_tools` 增设唯一出站 HTTP 入口 `open_https`，调用方保留各自错误分类与发布语义。

## 实现
- `platform_tools.py`：新增 `open_https(url, *, timeout=60, data=None, headers=None)`（惰性 `import urllib.request`；返回已打开响应，读取/分类留给调用方）。与 `run_process` 同属宿主适配层。
- `agent/core.py` `request()`：`urllib.request.urlopen(urllib.request.Request(...))` → `platform_tools.open_https(...)`；保留 `urllib.error` 异常分类与密钥脱敏文案。
- `agent/core.py` `download()`：`urllib.request.urlopen(url, timeout=120)` → `platform_tools.open_https(url, timeout=120)`；HTTPS 强制、`geturl()` 重定向校验、1GB 上限、空文件校验、原子发布均不变。

## 台账与判据同步
- `维护记录/架构统一基数.json`：`覆盖率审计26` 两条 disposition `pending`→`migrated`（reason 以 `R1395：` 开头），`count` 2→0（`baseline_pending` 2 不动）。
- `维护记录/覆盖率审计判据_20261001.md`：第 26 项真候选 2→0，并改写第 26 项说明。

## 验证
- 定向：**7/7、OK**（33.8 秒）。默认冒烟：**8/8**。架构：**341/341、0 红**（140.3 秒）。
- 运行期：本地 HTTP 服务下 `agent.core.request('http://127.0.0.1:…/x')` → `{'ok': True, 'path': '/x'}`；`platform_tools.open_https` 可调用。
- 全量（§5 五轮必需）：干净 master 工作树 `o07-fullsafe-master`（`git reset --hard master`→`d93993e`）`run_selftests.py --all --safe` **4983 条、602.9 秒、0 文件有红、ALL TESTS PASSED**；`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 **均无阈值抖动**（无需 O48 多数复测）。凭据 tree=`886cfd07…`＝`d93993e:程序`，`last_full_safe_all_round` 1390→1394。

## 提交
- 内容：`d93993e`（`platform_tools.py`＋`agent/core.py`＋`维护记录/架构统一基数.json`＋`维护记录/覆盖率审计判据_20261001.md`）。
- 报告／状态／接力：本轮收尾提交。

## 复盘
- 已收口：覆盖率审计 21／26 真候选全部归 0；R1393 暴露的 4 条 agent 真候选全部裁定完毕。
- 未做（理由）：`probe_http_endpoint` 仍保留自有的 `urlopen`（访问闸门语义），未与 `open_https` 合并，避免改动其既有错误分类；如后续统一可另轮处理。
- 新增待办：无（secret sink 第 27 项仍待评估是否递归化）。
