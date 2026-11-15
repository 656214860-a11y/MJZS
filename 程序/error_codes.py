"""L0 统一错误码注册表的历史入口；实体已迁至 ``contract.error_codes``。

测试与外部脚本仍按扁平名导入；生产侧一律 ``from contract.error_codes import …``。
门面清除轮统一改写测试导入后删除本文件。
"""
from contract.error_codes import (CODES, ErrorCode, code_data, code_of, describe,
                                  from_http_result, lookup)
