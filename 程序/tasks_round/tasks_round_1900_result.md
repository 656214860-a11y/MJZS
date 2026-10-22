# R1900 文档轮：服务端首页与管理后台留痕（服务端仓库 `D:\漫剧服务端`）

## 三问
- 轮次类型：文档轮。代码全部在服务端独立仓库；桌面仓库只改设计文档、状态页和本结果文件，桌面端源码未动。
- 测试与基线（本轮实跑）：
  - 服务端本地 `pytest`：58 项全绿（经 `工作流任务\gui_hidden.py`），新增 `tests/test_admin.py` 5 项。
  - 测试服远端（在服务器上用 curl 访问 `127.0.0.1:8001`）：概览、用户、兑换码、审计 4 页均 200；外来 `Host` 403，跨站 `Origin` 的 POST 403；`ss` 确认 8000、8001 都只监听 `127.0.0.1`。
  - 本机 SSH 隧道实测未做：本会话的权限设置拦了后台隧道命令，留待用户首次打开时确认。
  - 首页：经钉证书访问 `/` 返回 200 `text/html`，`/healthz`、`/v1/meta` 不受影响（服务端 1c07199 时实测）。
  - 桌面仓库未跑测试，未改源码。
- `project_status.md`：轮次头 1900 → 1901。

## 服务端改动（`main`，未推远端；测试服运行 eeb2e14）
- **首页**（1c07199、08b5787、6580cde）：`deploy/www/index.html` 静态页，nginx `location = /` 直接返回，`/favicon.ico` 回 204。按用户意见删掉「试用三天」等字样，更新说明改为「新增账号登录；断网时也能继续正常使用。」
- **管理后台**（eeb2e14）：
  - `app/admin.py`：新 FastAPI 应用，服务端渲染 HTML，不引新依赖（表单用 `parse_qs` 自解析）。
  - `deploy/mj-admin.service`：`127.0.0.1:8001`；`server_setup.sh` 启用并重启它，安装末尾探测 `admin 200`。
  - `app/service.py`：新增 `redeem_batches`、`revoke_redeem_batch`（命令行与后台共用，作废写审计）、`admin_extend`。
  - `scripts/gen_redeem.py` 的 `stats`／`revoke` 改调上述函数，输出不变（`test_redeem` 的命令行用例原样通过，断言未动）。
  - README 新增「管理后台」一节，含隧道命令。
- 用户桌面端兑换测试已在后台看到：批次 `test-desktop-2026-10` 的 1 个码已兑换。

## 后续
- ICP 备案下号后：首页页脚补备案号；`api` A 记录、Let's Encrypt、nginx `server_name`，通知客户端取消证书钉选。
- 爱发电店铺开好后由用户给出各套餐数量，再在后台或命令行生成正式批次。
