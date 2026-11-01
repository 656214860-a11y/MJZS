# R2175 结果：修复全项目审查前 5 条潜伏缺陷（缺陷轮）

## 三问
- 轮次类型：缺陷轮（§3）。用户要求修复 /code-review 全项目扫描清单的前 5 条。
- 轮次号：起草和测试时按 R2155；提交时中央计数器已到 R2174，按 commit-msg 钩子改领 R2175。结果报告和测试文件随之改名，测试内容未变；下面「修复前红」里的输出是改名前原样。
- 测试和三个基线：在 worktree 分支 `claude/intelligent-swanson-cda9e3` 上运行（经 gui_hidden）。
  - `run_selftests.py -k latent_defects_r2175`：14 条；修复前 ✗17（见下），修复后全过。
  - `run_selftests.py -k model_call_error_kind model_pool pet_ui pet_cloud pet_agent recycle storage writing qwen latent_defects_r2175`：39 个文件 1054 条全过。
  - 默认冒烟：通过 8 项、失败 0 项。
  - `smoke_test.py --affected model_pool storage_maintenance pet_ui_support pet_cloud pet_ui_stages desktop_writing_page qwen_setup`：9 项全过，其中定向自检 77 个文件 1962 条，0 个文件有红。
  - `--architecture` 首跑：411 条，红 3 条、错误 1 条。
    - 本轮引入、已改正：`test_complexity_ratchet.test_registries_track_real_values`（`Cloud` 类缩到 1096 行，登记 1112 超出余量 15）；`test_todo_comment_snapshot`（`firstframe_batch` 一行含「暂时」的快照注释被我续写了半句）。
    - 环境：`test_agents_md.test_performance_history_is_declared_as_historical_only` 报 ERROR，因为 `维护记录/基准历史.json` 被 `.gitignore` 忽略，worktree 里没有。已从主检出复制一份（不入库）。
  - `--architecture` 改正后复跑：411 条红 1 条，即 `test_round_baselines.test_round_number_continuous`（复跑时报 2153 != 2156；报告改用 R2175 后同理为 2153 != 2176）。本分支新增了结果报告，按规定不写状态页，合并轮登记后转绿。
  - 全量 `--all --safe` 本轮未手动运行，由提交后钩子后台补跑。
  - 真机未手动核对。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 根因
1. 模型请求异常误归类：urllib 只把连接、发送阶段（`h.request()`）的 OSError 包成 `URLError`。读响应阶段（`getresponse()`、`read()`）抛出的 `TimeoutError`、`RemoteDisconnected`（OSError）和 `IncompleteRead`（`http.client.HTTPException`，不是 OSError）原样冒出，落进 `_http_transport` 的 `except Exception`，被记成 `kind='bug'`。调用方于是按程序缺陷处理，创意聊天显示「系统内部错误」。
2. Qwen「测试连接」：`qwen_setup.probe` 用裸 `urlopen`。默认重定向处理器会把 `Authorization` 头带到跳转目标（301／302／303／307／308 都跟），请求还带着 `Python-urllib/3.x` 默认 User-Agent。模型调用早已走 `model_pool._http_opener()`（不跟随重定向）和 `_request_headers()`（补 User-Agent），这里没走同一条出站路径。
3. 云朵确认派发：`Cloud.dispatch` 靠「带 `confirmed=True` 调，遇 `TypeError` 去掉再调」判断签名。编排器内部抛出的 TypeError 也会触发回退，同一句话被派发两遍，第二遍还丢了 `confirmed`。
4. 分镜／首帧批次：`PetStagesMixin.storyboard_batch`、`firstframe_batch` 用同样的回退。宿主内部的 TypeError 会让自动链再无参派发一遍，宿主按默认 `trigger='manual'` 当成手动操作。
5. 同批回收：`recycle_paths` 对每条路径各自写前计划，不去重，也不合并父子路径。
   - 「先文件后目录」：目录被 `shutil.move` 套进文件已建出的同名回收目录（a → a/a），之后恢复会冲突。
   - 「先目录后文件」或同一目录两次：第二项的源已不在，整批撤回并报错。
   - 写作页 `delete_selected_scripts` 部分成功（有的文件已不在）时先报错、不刷新列表，已进回收站的文件仍列在页面上。

## 改动
- `model_pool.py`：
  - `_http_transport` 的 `except urllib.error.URLError` 放宽为 `except (OSError, http.client.HTTPException)`。URLError 本就是 OSError，HTTPError 仍在前面单独处理。读响应阶段的超时、断线、截断一律归 `kind='network'`，SSLEOFError 的重试判据不变。
  - `payload` 为 None 时发只读 GET（不带正文），`http_transport` 文档同步。
  - 净行数 0（1117／上限 1117）。
- `qwen_setup.py`：`probe` 改走 `model_pool.http_transport(url, None, headers, 15)`，不跟随重定向，并补默认 User-Agent。界面文案不变，跳转按「连接失败（HTTP 3xx）」报。
- `pet_ui_support.py`：新增 `accepts_keyword(func, name)`，用 `inspect.signature` 判断能否按关键字收某参数。`**kwargs` 和仅关键字参数算能收，仅位置参数不算；签名读不出时按能收处理。
- `pet_cloud.py`：`Cloud.dispatch` 先认签名、只调一次（1356／上限 1357）。
- `pet_ui_stages.py`：`storyboard_batch`、`firstframe_batch` 同上；外层 `except Exception` 照旧把内部错误收成「…批次未派发：…」提示。`firstframe_batch` 那行快照注释保持原文，补充说明另起一行（1201／上限 1202）。
- `tests/architecture/test_complexity_ratchet.py`：`Cloud` 类行数上限按门禁提示由 1112 下调到 1111（只降不升）。
- `storage_maintenance.py`：新增 `_distinct_outermost`，同批同一路径只留第一次，祖先目录已在批内的子项不再单列（随目录一起搬），保持原顺序。`recycle_paths` 写前计划之后先过它。
- `desktop_writing_page.py`：批量删除先 `fill_script_list()`，再按数量报错，报错文案不变。

## 测试
- 新增 `tests/test_latent_defects_r2175.py`（14 条，沿用 R1853 先例：每条先复现，再验证修复）：
  - 用真实回环套接字复现读超时、读完请求就断开、正文截断三种失败，断言 `kind='network'`，且超时仍被 `model_router.error_class` 认成 `timeout`；普通程序错误仍是 `bug`。
  - 只换掉 urllib 面向套接字的两个处理器，重定向走真实机制：5 种跳转都只发 1 个请求，报「连接失败（HTTP 3xx）」；200 时为 GET、带密钥、User-Agent 为 `model_pool.HTTP_USER_AGENT`；其余回答的文案不变。
  - 云朵与两个批次：实现内部抛 TypeError 时只派发一次；不认该参数的老接口照旧可用；另测 `accepts_keyword` 的签名判定。
  - 回收：「文件在前／目录在前／同一目录两次」都只回收一项、目录完整、清单为 committed、可整批恢复；写作页部分成功时，报错前已刷新列表。
- 修复前红：修复前原样运行 `gui_hidden.py … -- python.exe -B run_selftests.py -k latent_defects_r2175`，退出码 1。最后两行的临时目录后段以 … 省略：

```text
  test_latent_defects_r2155     14 条     1.2 秒  ✗ 17
共 14 条用例，1.9 秒；1 个文件有红

AssertionError: Lists differ: ['auto', 'manual'] != ['auto']
AssertionError: Lists differ: ['auto', 'manual'] != ['auto']
AssertionError: Lists differ: [('执行选中', True), ('执行选中', False)] != [('执行选中', True)]
AssertionError: Lists differ: ['htt[23 chars]compatible-mode/v1/models', 'https://collector.invalid/models'] != ['htt[23 chars]compatible-mode/v1/models']
（同一断言共 5 条：301／302／303／307／308）
AssertionError: 'Python-urllib/3.15' != 'ManjuAssistant/1.0'
AssertionError: Lists differ: ['剧本准备/a/x.txt', '剧本准备/a'] != ['剧本准备/a']
AssertionError: Lists differ: [] != ['refresh']
AssertionError: 'bug' != 'network'
AssertionError: 'bug' != 'network'
AssertionError: 'bug' != 'network'
ImportError: cannot import name 'accepts_keyword' from 'pet_ui_support'
FileNotFoundError: [WinError 3] 系统找不到指定的路径。: '…\\tmpuxp7g31y\\剧本准备\\a\\x.txt' -> '…\\tmpuxp7g31y\\工作流任务…'
FileNotFoundError: [WinError 2] 系统找不到指定的文件。: '…\\tmp2lc0sysd\\剧本准备\\a' -> '…\\tmp2lc0sysd\\工作流任务…'
```

- 修复后：14 条全过（0.9 秒）。
- 定向输出里另有 Tcl 读 `pkgIndex.tcl` 报 `unknown encoding "cp1252"` 的警告，以及一条 after 回调 `invalid command name "…greet"`，均未计为失败。本轮没改相关代码，也未单独追查。
- 已有测试断言未动；只按门禁提示收紧了一个棘轮登记值（见「改动」）。

## 用户需做
重启应用后生效。
