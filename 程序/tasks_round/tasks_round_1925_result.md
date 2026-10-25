# R1925 结果：会员账号页「推荐线路」（功能轮）

- 本轮类型：功能轮。服务端阶段 3 已在 `D:\漫剧服务端` 提交 a99ca4e 并部署测试服（迁移 0006、`GET /v1/providers`、后台「线路」页、总开关默认关闭）。
- 客户端改动：`account_client.providers()`、`account_controller.providers()`、`desktop_account_page` 新增「推荐模型线路」卡片（按需联网读取；显示接口地址／模型说明；「复制地址」「注册／邀请链接」按钮；固定提示：第三方服务、费用另计不属于会员、合规自负、软件不保管 Key）；新增 `account_banned` 提示文案。
- 不做：不下发 Key、不建 Key 池；邀请链接在后台留空前不显示按钮。
- 测试：账号定向 `run_selftests.py -k account_security account_client account_page account_entry` 90 条 0 红（本轮实测）；服务端 pytest 全绿（本轮实测）。`--architecture` 输出 0 条用例，不能当作门禁通过证据，未另行验证。
- 断言未动；仅新增用例。
- 未验证：真实界面手工点击、测试服上与客户端联调。
- 是否已提交：见下方 commit。
