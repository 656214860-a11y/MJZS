# R543 功能轮结果

日期：2026-09-29  
范围：剧本准备页的创意文件归档、引用与受控请求注入；未修改 `brief_raw.md` 逻辑，未引入第三方依赖。

## 轮次自答

1. 本轮是功能轮还是整理轮？功能轮。
2. 测试跑了吗？三个基线过了吗？新增/相关服务测试 15/15 通过；用户指定 `smoke_test.py --affected idea_chat writing` 已完成定向门禁。默认、架构、全量安全基线本轮未运行。
3. `project_status.md` 的欠账少了吗？减少：创意文件已有项目内归档、可见文件列与受控引用链路；启动性能 P1 阻塞不在本轮范围。

## 改动

- `idea_attachments.py`：新增 `.docx` 的 `zipfile + xml.etree` 正文提取；上传的 `.md/.txt/.docx` 转存到 `stage_path_service.write_dir(root, 'script') / 输入 / 故事创意_<时间戳>.md`。发送时只从该项目目录解析：`@文件名` 精确引用优先，否则选中项加最近文件，最多三份。
- `desktop.py`：上传后显示“已引用：文件名（N 字）”；输入 `@` 弹出已归档文件菜单，选择即插入引用；提交正文自动拼接受边界保护的附件内容。聊天记录只记录文件名，不显示本地路径或正文。
- `script_workspace_service.py`：`01剧本准备/输入/故事创意_*.md` 纳入“项目设定”列。
- `tests/test_idea_attachments.py`、`tests/test_idea_chat.py`、`tests/test_script_workspace_service.py`：覆盖归档、最近引用、文件表归类和桌面端入库行为。

## 验证

1. `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_idea_attachments tests.test_script_workspace_service`：**15/15 通过**。
2. `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --affected idea_chat writing`：定向门禁已运行完成；改动涉及的剧本准备 UI/服务测试未报失败。

## 说明

归档文件名采用时间戳而不是源文件名，避免同名覆盖；`.docx` 仅读取 `word/document.xml` 中的段落文本，不执行宏或嵌入对象。重新启动应用即可加载本轮桌面端改动。
