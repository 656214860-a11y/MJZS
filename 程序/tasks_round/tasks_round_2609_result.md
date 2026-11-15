# R2609 结果：SWE-2 优化清单 T6 收尾——gitleaks 接入远端 CI＋历史扫描＋签名/SBOM 方案
<!-- round-evidence: {"commit_base": "e33a71c0", "credential_hits": 0, "evidence_sha256": "4f5044a00a6c1288", "exit": 0, "failed": 0, "passed": 7, "round": 2609, "tests": "run_selftests.py -k remote_pre_receive"} -->


> 写作中：服务器命令先列后执行（任务书 §0.4），执行结果后补。

1. 轮次类型：功能轮（安全加固；不改产品阶段行为）。

## 服务器执行命令清单（执行前列出）

```bash
# 1) gitleaks 二进制（v8.30.1，发布于 2026-03-21，>7 天）
mkdir -p /srv/git/ci/bin
curl -fsSL -o /tmp/gitleaks.tar.gz \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
tar -xzf /tmp/gitleaks.tar.gz -C /srv/git/ci/bin gitleaks
/srv/git/ci/bin/gitleaks version

# 2) 部署 .gitleaks.toml 副本与更新后的 pre-receive（含可选 gitleaks 步骤）
cp /srv/git/ci/.gitleaks.toml /srv/git/ci/.gitleaks.toml.bak 2>/dev/null || true
#   上传 程序/.gitleaks.toml → /srv/git/ci/.gitleaks.toml
#   上传 维护记录/基准脚本/remote_pre_receive.py → /srv/git/manju-assistant.git/hooks/pre-receive（chmod +x）

# 3) 沙箱红绿验证（/srv/git/ci/test.git）
git init --bare /srv/git/ci/test.git
cp /srv/git/manju-assistant.git/hooks/pre-receive /srv/git/ci/test.git/hooks/pre-receive
#   推干净提交（绿）、推放假密钥提交（红）、推 tests/ 内示例密钥（按 .gitleaks.toml 白名单放行）
rm -rf /srv/git/ci/test.git

# 4) 历史扫描（只出报告，真实泄漏立即停下通知用户）
/srv/git/ci/bin/gitleaks git /srv/git/manju-assistant.git \
  --config /srv/git/ci/.gitleaks.toml --redact \
  --report-format json --report-path /srv/git/ci/history-scan-20261115.json
```

## 执行记录

### 服务器部署（已执行，全部经由 ssh root@8.138.223.126）

- gitleaks 8.30.1 装至 `/srv/git/ci/bin/gitleaks`（`gitleaks version` 输出 8.30.1）。
- 旧钩子备份：`/srv/git/manju-assistant.git/hooks/pre-receive.bak-r2602`（命名沿首轮领号 R2602，后改领 R2609）。
- 新钩子部署至 `/srv/git/manju-assistant.git/hooks/pre-receive`，`chmod +x`，file 检查 UTF-8、LF 行尾（无 CRLF）。
- `.gitleaks.toml` 部署副本在 `/srv/git/ci/.gitleaks.toml`。

### 沙箱验证（/srv/git/ci/test.git，验证后已删）

| 场景 | 内容 | 结果 |
|---|---|---|
| A 干净提交 | 程序/t.py 普通 print | 绿，放行 |
| B 形态扫描命中 | 程序/leak.py 内 ghp_+36 位 | 红，`程序/leak.py:1:github-token` |
| D2 仅 gitleaks 命中 | 仓库根 leak_root.txt 内高熵 ghp_+36 位 | 红，`gitleaks:github-pat leak_root.txt:1` |
| E 白名单放行 | tools/tests/leak.py 同密钥 | 绿（gitleaks tests/ 白名单＋形态扫描只管 程序/） |

B 证明第 2 项形态扫描仍是硬门禁；D2 证明 gitleaks 补上了 `程序/` 前缀之外的盲区；
E 证明白名单不误伤。低熵假密钥（ghp_+36 个 b）被 gitleaks 自身熵阈值放行，属预期。

### 历史扫描

- 命令按上面清单第 4 步执行，报告写到 `/srv/git/ci/history-scan-20261115.json`（--redact，不落明文）。
- 首轮结果：3 条命中，全部为 `generic-api-key` 落在 `程序/说明/版本文件校验.json`
  （SHA-256 校验清单，64 位 hex 被通用规则误识）——误报，非真实凭据。
- 处置：`.gitleaks.toml` allowlist.paths 补 `说明/版本文件校验\.json`，重新部署并复扫。
- 复扫结果：**1785 个提交、32.28MB、no leaks found**。


## 三个基线与欠账

1. 轮次类型：功能轮（安全加固——远端钩子接 gitleaks＋历史扫描＋签名/SBOM 方案文档；不改产品阶段行为）。
2. 测试基线：`run_selftests.py -k remote_pre_receive` 7/7 绿；`-k silent_exception remote` 8/8 绿
   （静默异常棘轮不升）；`smoke_test.py` 8/8 绿。服务器侧沙箱红绿矩阵 5 场景全部符合预期。
3. 欠账：T6 清单项中 gitleaks CI 接入、历史扫描、SBOM/签名方案三项本轮落地；
   剩余 T7/T8/T9 未动，欠账继续下降。

## 涉及文件

- `维护记录/基准脚本/remote_pre_receive.py`：新增第 3 道可选 gitleaks 扫描
  （二进制缺失/自身故障不阻断，exit 1 命中才拒绝；配置优先取推送版
  `程序/.gitleaks.toml`，退回 `/srv/git/ci/.gitleaks.toml`；命中只报
  RuleID＋路径＋行号，不落明文）。
- `.gitleaks.toml`：allowlist 补校验清单误报路径。
- `tests/test_remote_pre_receive.py`：4 条行为测试（二进制缺失 no-op、
  干净扫描、命中报告、扫描器故障不阻断）。
- `docs/review/发布签名与SBOM方案_T6.md`：签名＋SBOM 方案（提案级，未宣称已实现）。
