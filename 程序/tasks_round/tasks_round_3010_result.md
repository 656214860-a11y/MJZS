# R3010 结果：修复轮——语音输入中文乱码（离线 ASR 引擎与 MCP 服务 stdio 未固定 UTF-8）
<!-- round-evidence: {"commit_base": "5efaee2e", "credential_hits": 0, "evidence_sha256": "9bd8cb33ad6000db", "exit": 0, "failed": 0, "passed": 68, "round": 3010, "tests": "run_selftests.py -k offline_asr voice_mcp"} -->

## 三问

1. **轮次类型**：修复轮（§3.2）。起因：用户实机反馈「语音输入输入时出现乱码」，补充「中文显示乱码，英文显示正常」——ASCII 双向兼容、中文必坏，是子进程 stdio 编码不匹配的典型特征。
2. **测试跑了吗、三个基线过了吗**：跑了。新增 2 条真实子进程回归（改前红、改后绿）；`run_selftests.py -k offline_asr voice_mcp voice_dict voice_ai shared_input_voice dialog_voice_input` 7 文件 100 条 0 红；`smoke_test.py --affected voice_engine voice_mcp` 9/9；默认冒烟 8/8。
3. **欠账少了吗**：是。两处 stdio 协议端点补齐 UTF-8 固定，此前中文 Windows 下中文转写/日志/热词/错误提示全部经 GBK→UTF-8 错配变乱码；`data/` 运行数据区不产生源码欠账。

## 根因（改前失败证据）

主程序经 `platform_tools.launch_text_process` 以 `encoding='utf-8'` 拉起引擎子进程；但子进程解释器（`data/voice_asr_venv` Python 3.12.11）在管道下 `sys.stdout/stdin/stderr.encoding` 均为 `gbk`（cp936，中文 Windows 区域设置默认值），未做任何重配。后果双向：

- 引擎 `emit_message` 以 `ensure_ascii=False` 写中文句子/日志 → GBK 字节 → 主程序按 UTF-8 `errors='replace'` 解码 → 中文变 `ʶ��Ự�ѿ�ʼ` 类乱码，英文因 ASCII 兼容不受影响（与用户现象一致）。
- 主程序回写 `hotword` 等中文命令 → UTF-8 字节 → 引擎 stdin 按 GBK 解码 → 热词乱码。
- `agent/voice_mcp_server.py` 同构缺陷：MCP stdio 规范按 UTF-8，中文识别结果/错误同样乱码。

实测：venv Python `sys.stdout.encoding == 'gbk'`；真实链路复现 `{"type":"log","message":"ʶ��Ự�ѿ�ʼ"}`（应为「识别会话已开始」）。注意 `运行环境\Python` 为 3.15 UTF-8 模式默认，测试解释器天然不暴露此 bug，故回归用 `PYTHONIOENCODING=gbk` 强制子进程复现生产编码。

## 本轮交付

| 文件 | 改动 |
|---|---|
| `voice_engine/offline_asr_server.py` | 新增 `_configure_stdio()`：`main()` 首行把 stdin/stdout/stderr `reconfigure` 为 UTF-8（`errors='replace'`，无 `reconfigure` 的替身流跳过、失败不阻塞）；引擎脚本保持零主运行时依赖，未引入共享 helper |
| `agent/voice_mcp_server.py` | 同构 `_configure_stdio()`，`main()` 首行调用；MCP 服务同样是独立子进程入口 |
| `tests/test_offline_asr_engine.py` | `StdioEncodingTests.test_engine_stdout_emits_utf8_chinese`：真实子进程跑桩驱动（`FunAsrBackend.load` 打桩），`PYTHONUTF8=0`+`PYTHONIOENCODING=gbk` 复现中文 Windows 默认编码，断言「识别会话已开始」与 `done` 事件以 UTF-8 透传 |
| `tests/test_voice_mcp.py` | `StdioEncodingTests.test_server_stdout_emits_utf8_chinese`：同环境变量拉起真实 `voice_mcp_server.py`，坏 JSON 请求断言「请求不是有效 JSON」UTF-8 透传 |

## 验证证据

- 改前红：两条新测试失败输出 `实际：['ʶ��Ự�ѿ�ʼ']` 与 `'��������Ч JSON'`（与用户乱码一致）。
- 改后绿：`python -B -m unittest tests.test_offline_asr_engine.StdioEncodingTests tests.test_voice_mcp.StdioEncodingTests` 2/2 通过。
- 生产链路实测：venv Python 3.12.11（GBK 默认）跑修复后引擎，`launch_text_process` 读出 `{"type":"log","message":"识别会话已开始"}` 正常 UTF-8，`start`（含中文 hotword）→`stop`→`done` 全通。
- `python -B run_selftests.py -k offline_asr voice_mcp voice_dict voice_ai shared_input_voice dialog_voice_input`：7 个测试文件 100 条用例 0 红（含 GUI 相关 `test_dialog_voice_input`/`test_shared_input_voice`）。
- `python -B smoke_test.py --affected voice_engine voice_mcp`：9/9 通过（定向门禁 49 条用例 0 红）。
- `python -B smoke_test.py`：8/8 通过。

## 边界与说明

- 修复只钉 stdio 编码，不改协议内容；`errors='replace'` 与客户端解码侧对称，坏字节不崩进程。
- 两个服务脚本各自内联 `_configure_stdio()`：`offline_asr_server` 有「不 import 主运行时模块」隔离约束，`voice_mcp_server` 面向外部 agent 独立拉起，共享 helper 反而扩大依赖面，重复 8 行是有意取舍。
- 云端后端（`RealtimeSession` WebSocket/HTTP）与 `voice_ai`/词典均为进程内或 HTTP JSON，不经此边界，无同类问题。
- 修复轮不改阶段行为，REQ/DES 文档（§2.7）不适用；`project_status.md` 轮次头由合并轮在 master 同步。
