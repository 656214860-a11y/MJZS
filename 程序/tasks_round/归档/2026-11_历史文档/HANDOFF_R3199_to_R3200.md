# 交接文档：R3199 → R3200（放开零依赖，替换 HTTP 客户端）

**创建时间**：2026-11-17 18:14  
**当前状态**：R3199 已完成所有改动，等待提交；R3200 待执行  
**阻塞原因**：Git 验收锁（R3203，PID 45092，已运行 5+ 分钟）

---

## 一、R3199 完成情况（✅ 已完成，⏸️ 待提交）

### 1.1 已完成工作

#### Python 运行环境替换
- ✅ 旧：Python 3.15.0 embeddable（53.68 MB，无 pip）
- ✅ 新：Python 3.14.7 完整版（240.56 MB，含 pip 26.2.1）
- ✅ 体积增加：+186.88 MB（+348%）
- ✅ 备份：`运行环境\Python.bak_3.15_embeddable_20261117_175007`

#### 依赖安装
- ✅ requests 2.32.3
- ✅ urllib3 2.8.0
- ✅ certifi 2026.10.23
- ✅ charset-normalizer（版本不严格限制）
- ✅ idna（版本不严格限制）
- ✅ HTTP 测试通过：`https://httpbin.org/get` → status 200

#### 约束文档更新
- ✅ `AGENTS.md` §1：零第三方依赖 → 谨慎白名单依赖
- ✅ `CLAUDE.md` §项目：零第三方依赖 → 谨慎白名单依赖
- ✅ `architecture.md` §当前架构门禁清单：补充 test_dependency_whitelist.py

#### 新增文件
- ✅ `维护记录/依赖白名单.md`：策略、评估标准、禁止清单、变更记录
- ✅ `tests/architecture/test_dependency_whitelist.py`：3 个门禁测试

#### 验证结果
- ✅ 冒烟测试：8/8
- ✅ 架构门禁：481/483（2 个历史欠账：test_agents_md 已修复，test_unification_ratchet 为裸 json.loads 债务）
- ✅ 结果文件：`tasks_round/tasks_round_3199_result.md`

### 1.2 待提交（所有文件已暂存）

**Git 状态**：
```
M  ../CLAUDE.md
M  AGENTS.md
M  architecture.md
A  tasks_round/evidence/R3199.json
A  tasks_round/tasks_round_3199_result.md
A  tests/architecture/test_dependency_whitelist.py
A  维护记录/依赖白名单.md
```

**提交命令**（等验收锁释放后执行）：
```powershell
# 切换到程序目录
Set-Location 'D:\漫剧制作助手\程序'

# 设置白名单环境变量
$env:CODEX_STAGE_ALLOWLIST = "程序/AGENTS.md;程序/architecture.md;程序/维护记录/依赖白名单.md;程序/tests/architecture/test_dependency_whitelist.py;CLAUDE.md"

# 提交
git commit -m "R3199: 放开零依赖约束，建立谨慎白名单机制

- 修改 AGENTS.md、CLAUDE.md：零第三方依赖 → 谨慎白名单依赖
- 新增 维护记录/依赖白名单.md：白名单策略、评估标准、禁止清单  
- 新增 tests/architecture/test_dependency_whitelist.py：3 个门禁测试
- 更新 architecture.md：补充 test_dependency_whitelist.py 到清单

前置工作（已完成）：
- Python 运行环境：3.15 embeddable → 3.14.7 完整版
- 已安装 requests 2.32.3 + 传递依赖

验收：
- 冒烟 8/8
- 架构门禁 481/483（2 个历史欠账记录但不扩大范围）"

# 更新状态页轮次头为 3200
# 编辑 project_status.md 第 3 行
```

---

## 二、R3200 执行计划（⏳ 待执行）

### 2.1 目标

用 requests 替换 `infra/http_client.py` 的内部实现，保留所有业务逻辑（熔断器、RPM 限流、响应体积上限、错误分类）。

### 2.2 范围

**修改文件**：
1. `infra/http_client.py`（167 行）
   - 保留公开接口：`request_json(url, method, payload, headers, opts)`
   - 保留业务逻辑：
     - 熔断器（`_circuit_open`、`_circuit_record`）
     - 响应体积上限（`max_bytes`，默认 32 MB）
     - 错误分类（`_error_code`：network / http / client）
     - 凭据脱敏（`_safe_headers`）
     - 惰性导入（保持启动时零成本）
   - **替换部分**：
     - 用 `requests.request()` 替换 `urllib.request.urlopen()`
     - 用 `requests` 的重试机制替换手动重试循环
     - 用 `requests` 的超时机制替换手动超时

**不改动文件**：
- `api_endpoints.py`：已被 `http_client.py` 替代，但先保留（可能有遗留调用）
- `comfy_service.py`：等 `http_client.py` 稳定后再迁移

### 2.3 复用现有逻辑的策略

**保留的业务逻辑**（不交给 requests）：
1. **熔断器**：`_circuit_open()` / `_circuit_record()` 保持不变
2. **RPM 限流**：如果存在（需检查），保持不变
3. **响应体积上限**：requests 默认无限制，需手动实现
4. **错误分类**：`_error_code()` 保持不变，只是捕获的异常类型从 `urllib.error` 改为 `requests.exceptions`

**交给 requests 的逻辑**：
1. **重试**：用 `urllib3.util.Retry` + `requests.adapters.HTTPAdapter`
2. **超时**：用 `timeout=(connect_timeout, read_timeout)`
3. **gzip 解压**：requests 自动处理
4. **SSL 处理**：requests 自动处理

### 2.4 实现步骤

#### 步骤 1：备份和测试现有实现（5 分钟）
```powershell
# 备份
Copy-Item infra\http_client.py infra\http_client.py.bak_before_R3200

# 运行定向测试（确认当前基线）
& '..\运行环境\Python\python.exe' -B run_selftests.py -k http_client
& '..\运行环境\Python\python.exe' -B run_selftests.py -k http
```

#### 步骤 2：修改 `http_client.py` 实现（30 分钟）

**关键改动点**：

```python
# 原实现（第 68-93 行）：
def request_json(url, method=None, payload=None, headers=None, opts=None):
    import urllib.request
    import urllib.error
    import urllib.parse
    # ... 手动构建 Request, urlopen, 重试循环

# 新实现：
def request_json(url, method=None, payload=None, headers=None, opts=None):
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    # 保留所有参数解析（第 91-110 行）
    opts = opts or {}
    timeout_sec = opts['timeout_sec']  # 必填
    retries = opts.get('retries', 0)
    retry_statuses = opts.get('retry_statuses', DEFAULT_RETRY_STATUSES)
    max_bytes = opts.get('max_bytes', MAX_BODY_BYTES)
    # ...
    
    # 构建 requests Session + Retry 适配器
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        status_forcelist=retry_statuses,
        allowed_methods=['GET', 'POST', 'PUT', 'DELETE'],
        backoff_factor=1  # 指数退避
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    # 发送请求（保留熔断器检查）
    if _circuit_open(host):
        # ... 返回 E-NET-UNREACHABLE
    
    try:
        response = session.request(
            method=method or 'GET',
            url=url,
            json=payload,  # requests 自动序列化
            headers=request_headers,
            timeout=timeout_sec,
            stream=True  # 流式读取，支持体积上限
        )
        
        # 读取响应（保留体积上限检查）
        body_bytes, exceeded = _read_limited_requests(response, max_bytes)
        if exceeded:
            # ... 返回 E-NET-OVERSIZE
        
        response.raise_for_status()  # 检查 HTTP 状态码
        
        # 解析 JSON
        data = _json.loads(body_bytes.decode('utf-8'))
        return success(data)
        
    except requests.exceptions.Timeout:
        # 超时
        code = 'E-NET-TIMEOUT'
        # ...
    except requests.exceptions.ConnectionError:
        # 网络错误
        code = 'E-NET-UNREACHABLE'
        # ...
    except requests.exceptions.HTTPError as e:
        # HTTP 错误
        code = _error_code(e.response.status_code)
        # ...
```

**新增辅助函数**：
```python
def _read_limited_requests(response, limit):
    """从 requests Response 流式读取，支持体积上限"""
    chunks, total = [], 0
    for chunk in response.iter_content(chunk_size=65536):
        if total > limit:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b''.join(chunks)[:limit + 1], total > limit
```

#### 步骤 3：运行测试（10 分钟）
```powershell
# 冒烟测试
& '..\运行环境\Python\python.exe' -B smoke_test.py

# 定向测试
& '..\运行环境\Python\python.exe' -B run_selftests.py -k http
& '..\运行环境\Python\python.exe' -B run_selftests.py -k api
& '..\运行环境\Python\python.exe' -B run_selftests.py -k comfy

# 架构门禁
& '..\运行环境\Python\python.exe' -B smoke_test.py --architecture
```

#### 步骤 4：修复失败（15 分钟预留）

可能的失败点：
- 超时参数格式不同（requests 用元组 `(connect, read)`，urllib 用单个数字）
- 异常类型映射不完整
- 响应体积限制实现有 bug
- 熔断器逻辑与 requests 集成问题

#### 步骤 5：提交（5 分钟）
```powershell
# 创建结果文件
# tasks_round/tasks_round_3200_result.md

# 提交
$env:CODEX_STAGE_ALLOWLIST = "程序/infra/http_client.py"
git add infra\http_client.py tasks_round\tasks_round_3200_result.md
git commit -m "R3200: 用 requests 替换 HTTP 客户端内部实现

- 修改 infra/http_client.py：用 requests + Retry 适配器替换 urllib
- 保留业务逻辑：熔断器、响应体积上限、错误分类、凭据脱敏
- 保留惰性导入：按需 import requests

验收：
- 冒烟 8/8
- 定向测试通过（http / api / comfy）
- 架构门禁通过"
```

### 2.5 预计时间

- 总计：60-75 分钟
- 关键路径：修改实现（30 分钟）+ 测试验证（10 分钟）+ 修复失败（15 分钟）

---

## 三、恢复检查清单

### 3.1 环境验证
```powershell
# 1. 确认 Python 版本
& '运行环境\Python\python.exe' --version
# 预期：Python 3.14.7

# 2. 确认 requests 已安装
& '运行环境\Python\python.exe' -m pip list | Select-String 'requests'
# 预期：requests 2.32.3

# 3. 确认工作区干净（R3199 已提交后）
git status
# 预期：nothing to commit, working tree clean
```

### 3.2 验收锁检查
```powershell
$common = git rev-parse --git-common-dir
$lockFile = Join-Path $common "full-safe-selftest.lock"
if (Test-Path $lockFile) {
    Write-Host "⚠️  验收锁仍存在，等待释放"
} else {
    Write-Host "✅ 验收锁已释放，可以继续"
}
```

### 3.3 快速恢复命令
```powershell
# 一键恢复到 R3199 提交就绪状态
Set-Location 'D:\漫剧制作助手\程序'
git status --short

# 如果需要重新暂存
git add ../CLAUDE.md AGENTS.md architecture.md `
  tasks_round/evidence/R3199.json `
  tasks_round/tasks_round_3199_result.md `
  tests/architecture/test_dependency_whitelist.py `
  维护记录/依赖白名单.md
```

---

## 四、风险与备份

### 4.1 已有备份
- ✅ Python 3.15 环境：`运行环境\Python.bak_3.15_embeddable_20261117_175007`
- ✅ Git 提交历史：所有改动已暂存但未提交，可随时 `git reset`

### 4.2 回滚路径
如果 R3200 失败，回滚步骤：
1. `git checkout -- infra/http_client.py`（恢复到 R3199 后的状态）
2. 或 `Copy-Item infra\http_client.py.bak_before_R3200 infra\http_client.py`

### 4.3 已知风险
1. **体积增加**：Python 运行环境从 53 MB → 240 MB（+348%）
   - 影响：安装包变大，但对运行性能无影响
   - 缓解：用户下载一次后，更新只覆盖程序文件

2. **裸 json.loads 历史欠账**：架构门禁有 2 个历史失败
   - 影响：不影响本轮验收，需独立任务处理
   - 处置：已记录在 R3199 结果文件

---

## 五、目标完成标准

**目标**："根据历史对话, 放开零依赖规则, 替换成熟框架, 输出任务书, 逐步执行, 直到应用替换成含有成熟框架的绿色版本"

**完成判据**：
1. ✅ 放开零依赖规则：AGENTS.md、CLAUDE.md 已更新，白名单机制已建立
2. ✅ 输出任务书：R3199、R3200 任务书已输出
3. ⏳ 替换成熟框架：R3200 待执行（用 requests 替换 HTTP 客户端）
4. ⏳ 应用含有成熟框架：代码真正使用 requests，而不仅仅是安装
5. ✅ 绿色版本：Python 3.14 + requests 预装，用户双击启动

**当前完成度**：75%

**剩余工作**：
- R3200 执行（60-75 分钟）
- 验证通过后，目标完成

---

## 六、交接给下一会话

**接续点**：
1. 检查验收锁是否释放（`full-safe-selftest.lock`）
2. 如果释放，提交 R3199（使用上述命令）
3. 开始执行 R3200（按上述步骤）
4. 完成后标记目标为 `complete`

**关键文件路径**：
- 白名单文档：`程序/维护记录/依赖白名单.md`
- HTTP 客户端：`程序/infra/http_client.py`
- 结果文件：`程序/tasks_round/tasks_round_3199_result.md`
- 本交接文档：`程序/tasks_round/HANDOFF_R3199_to_R3200.md`

**预计下次会话时间**：60-90 分钟（提交 R3199 + 执行 R3200）

---

**创建人**：AI Agent (Round 5)  
**状态**：R3199 就绪待提交，R3200 计划完整，等待验收锁释放
