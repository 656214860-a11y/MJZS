# R2047 结果：合入 codex/wip-R2046 到 master（合并轮）

## 内容
- 合入 R2046：登录闸登录成功后，若当前停在「会员账户」页就重画，不再露出登录前画的「未登录」旧页。
- 登录、注册、验证码登录成功后，先核验本机验签后的状态；仍是未登录就留在表单上报错，不跳转，也不报「登录成功」。
- 详见 `tasks_round/tasks_round_2046_result.md`。

## 验证
- R2046 的验证在工作树中实跑：账号相关 4 个测试文件 83 条，ALL TESTS PASSED；`smoke_test.py --architecture` 只有已知遗留的 3 项红。
- 合并后在主目录复跑同一组测试：83 条，ALL TESTS PASSED。
