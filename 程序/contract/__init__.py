"""L0 契约包：纯事实与协议模块，无 Tk、无 IO 副作用。

纯度口径以 `tests/architecture/test_contract_purity.py`（K9 门禁，清单权威任务书 K-H1）
为唯一权威：只允许白名单标准库、os.path 纯函数与第一方包；违规以「文件:符号:类型」
登记 `维护记录/架构统一基数.json`「L0 纯度」段，只减不增。
"""
