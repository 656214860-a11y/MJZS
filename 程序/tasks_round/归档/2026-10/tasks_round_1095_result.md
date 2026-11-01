# R1095：创作信息表单上传即同步

- 类型：§3.2 修复轮；用户任务书标题 R1089 已占用，中央实际领取 1095。独立于已验收 R1094 简化。
- 测试：新增无头 8/8、定向 137/137、受影响冒烟 9/9、独立架构 309/309、默认冒烟 8/8 全通过。
- 欠账：修复表单旧快照与复用窗口丢弃最新引用；不改附件解析和简报门禁。

## 根因与最小改动

原 refresh_attachment_fields 捕获开窗 attachment_reference；上传成功后调用仍用旧引用。已有窗口只置顶并返回，发送路径 prepared['attachments'] 被丢弃；发送又已清空附件选择，不能靠选择列表恢复该引用。

desktop.py 无参 refresh 在调用时使用 draft_text()、当前附件选择，经 stage_idea_attachment_reference 现算；显式引用直接交给既有 stage_idea_brief_defaults，不二次解析。更新提取值也使用当前未发送文本，不捕获旧 current_text。AST 回归禁止 refresh 直接引用外层 attachment_reference。

复用窗口在传入引用（含空字典）或存在选择时先刷新再置顶；上传回调仍调用无参 refresh，只有表单存在时显示已自动同步文案。填入条件仍是 tk.Text、未编辑、为空且有提取值；手填与主动清空不覆盖。

仅 production desktop.py +12/-4；新增 tests/test_idea_chat_attachment_refresh.py。idea_attachments、stage_execution_service、receive_brief 及发送 prepared 引用接线本体未改。无新层级、路径或存储契约。

## 实跑与未运行项

- 新增测试先修正测试入口 PYTHONPATH 与 ProjectContext 桩；这些错误不算产品缺陷证据。
- 修复前 8 项中 6 失败、1 错误，覆盖旧快照、复用丢引用及缺少显式参数；修复后 8/8、0.110 秒。
- 无头使用临时项目、文本控件桩与真实桌面方法/字段提取；覆盖五字段补齐、手填和清空保持、显式/选择复用、两种刷新同源、当前文本、关闭表单状态文案以及 AST 闭包门禁。
- `run_selftests.py -k idea_chat idea_attachment`：137/137、64.3 秒、0 红。
- `smoke_test.py --affected idea_chat`：9/9、0 红。
- `run_selftests.py --layer architecture --all`：309/309、0 红。首次仅 TODO 注释快照行号失配，按实际位置 2479→2487 校准后复跑通过；注释内容和分类不变。
- 默认冒烟：8/8。
- 未启动真实助手，未读取真实用户项目或调用外部模型；真实文件上传和 UI 实机验收未运行。
- 不冒用 R1094 全量覆盖本轮。本轮未变启动、Tk 创建/销毁或事件绑定、删除语义和层级登记；现有窗口的字段数据刷新没有改变生命周期，距离最近全量 1 轮，按 §5 不单独升级全量。

## 收尾

现有断言零删除零弱化；修复提交 f4e4dd7 已快进合入 master，状态与接力同步。用户主树预设不入提交，SHA256 核对保持 E596C86C8D362FD6C6797FE9F9E19B4A7507D4F6ACE19BB91CE955EFF47E4651。diff 检查通过，敏感凭据形状扫描无命中。需重启助手加载修复，本轮未替用户启动应用。
