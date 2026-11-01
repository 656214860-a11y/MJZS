# R2328 结果：取消确认弹窗文案「你」改「您」（修复轮）

R2324 新增的 desktop_writing_page.py:818 对用户说「你需要重新确认」，违反界面文案「您」规则，致 test_copy_rules 在全量中红。改为「您」。断言未动。
验证：run_selftests -k copy_rules writing_unconfirm 见本轮命令输出；R2327 上干净检出全量仅此一红（466 秒），修复后需再跑全量确认。
