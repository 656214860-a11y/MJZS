# R2025 结果（修复轮）

## 用户反馈
1. 「00 会员账户」下的小字删掉。
2. 右侧布局：按钮移到对应栏目右侧，减少空白。
3. 「当前状态」卡文字太多，简化、删无效信息。

## 改动
- `desktop_account_page.py`
  - 删页首说明 `self.note(...)`；删状态卡里与免费说明重复的规则行（仅测试期不拦截时保留一句「测试期暂不拦截。」）。
  - 状态卡：标题行右侧放「立即续签／退出登录」；账号／套餐／到期日并成一行；删「离线可用至」。
  - 兑换：输入框与「兑换」按钮同一行，提示显示在标题行右侧。
  - 推荐线路、已绑定设备、导出账号数据：按钮移到标题行右侧；线路与设备的提示信息放在按钮左侧；设备标题缩为「已绑定设备」（限额信息读取后在摘要里给出）。
  - 注销：验证码输入框与两个按钮同一行。
  - `STATE_TEXT` 缩短（授权已失效／本机时间早于服务器时间）。
- `entitlement_service.py`：`membership_view` 文案精简——每个状态 1～2 行；`REDEEM_HINT` 改为「输入兑换码即可续期。」；免费说明改为「「剧本准备」「剧本结构」永久免费。」。
- 侧栏「00 会员账户」按钮代码里没有任何附带小字，已确认页内说明是本次删的那行；若红框是另一处，请指出。

## 测试（契约有意变更，断言未弱化）
- `test_membership_view`、`test_account_page`：“请联系发放兑换码的渠道”改为“输入兑换码即可续期”（文案精简）；其余断言未动。
- `test_account_page.test_login_flow_and_logout`：退出按钮查找由两层改为递归（按钮移入标题行），断言未动。

## 验证
- gui_hidden 定向：account／membership／entitlement／desktop_startup 共 115 条通过。
- `smoke_test.py --architecture`：剩余红项均为既有基线（agents_md 基准历史、complexity_ratchet Desktop 1303>1302、round_baselines、skill_reference_injection），非本轮引入。
- 未在真实窗口目测排版。
