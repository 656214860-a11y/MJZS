# R513 结构治理轮：剧本工具空成果拦截

## 完成内容

- `writing_tools.write_file()` 在正式剧本目录发布前拒绝空白正文，避免模型空响应留下可被误判为成果的空文件。
- 路径授权和既有 `agent.core.save_text()` 原子写入保持不变；仅收紧内容校验。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_writing_api -q`：19/19 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8/8 通过。
- 未修改用户项目数据、密钥或可见界面。
