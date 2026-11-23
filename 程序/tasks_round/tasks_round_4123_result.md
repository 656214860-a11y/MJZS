# R4123 结果：提示词优化的老明文密钥没有接口地址时原样留着，不再被抹掉（SEC-K3 复核更正）
<!-- round-evidence: {"commit_base": "ffa744c3", "credential_hits": 0, "evidence_sha256": "4edd086da35c8a99", "exit": 0, "failed": 0, "passed": 23, "round": 4123, "tests": "run_selftests.py -k mcp_settings"} -->

## 开头三问

（一）本轮类型：更正轮（R4109 的补丁）。任务卡 C-SEC-K3-FIX（队列 23 号）；独立审查（Cursor 队列 20 号卡，结论不通过，不通过项 K3）发现「有密钥、没有接口地址」的条目会被抹掉而没有存进加密存储。车道 `codex/sec-k3-optimizer-key`，基准 `ffa744c3`。

（二）测试与三个基线：`mcp_settings` 改前 23 条里 1 条红（新用例），改后 23 条全过，退出码 0。静态检查 `Ran 47 tests in 40.892s`、`OK`，退出码 0。默认冒烟与全量自测没跑；架构门禁整套没跑（卡面只点名静态子集）。

（三）欠账：K3「无地址明文被抹丢」这一条在代码上修掉了。没有地址的明文会一直留在设置文件里，直到用户在设置窗口里重新保存；这次没有给用户加提示。

## 改了哪些文件

- `agent/prompt_optimizer.py`：`_migrate_plain_keys` 文档字符串补一句「没有接口地址的那一份没处可存，原样留着」；末尾循环改成先算 `base`，仅当 `api_key` 有值且 `base` 非空且不在 `failed` 时才抹空。
- `tests/test_mcp_settings.py`：在 `KeyStoreTests` 里新增 `test_a_plain_key_without_an_address_stays_in_the_file`——顶层空地址、空白地址 profile、无 base_url 的 model_profiles 明文须留在文件；有地址的那一份照常搬走。
- 本结果文件。

改前循环原文：

```python
    for holder in holders:
        if holder.get('api_key') and str(holder.get('base_url') or '').strip().rstrip('/') not in failed:
            holder['api_key']='';changed=True
    return changed
```

改后：

```python
    for holder in holders:
        base=str(holder.get('base_url') or '').strip().rstrip('/')
        if holder.get('api_key') and base and base not in failed:holder['api_key']='';changed=True    # 没有地址的明文没处可存，原样留着
    return changed
```

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `git status --porcelain` / `git log -1` | 干净；`ffa744c3 R4109: …` |
| `run_selftests.py -k mcp_settings`（改产品前） | 退出码 1；共 23 条，1 个文件有红。红用例：`test_a_plain_key_without_an_address_stays_in_the_file`，`AssertionError: 'sk-top' not found in '… "api_key": "" …'` |
| 同上（改产品后） | 退出码 0；共 23 条用例，0 个文件有红；`ALL TESTS PASSED` |
| 卡面点名静态检查（9 个模块） | 退出码 0；`Ran 47 tests in 40.892s`；`OK` |
| `scripts\dev.py claim` | 领到 4123 |

## 如实说明

- 没有地址的明文会一直留在设置文件里，直到用户在设置窗口里重新保存；这次没有给用户加提示。
- 正常在设置窗口里保存的数据都带地址，这种「有密钥、无地址」条目只会出现在手改过或损坏的文件里。
- 没有在真实窗口里试；没有跑全量；设置窗口保存时怎么处理这种没有地址的条目，这次没有读、没有改。

## 未覆盖项

- 未在真实界面验证；未跑默认冒烟与全量自测；未跑整套架构门禁（仅卡面点名的静态子集）。
- 设置窗口对无地址明文条目的保存路径未读未改。
