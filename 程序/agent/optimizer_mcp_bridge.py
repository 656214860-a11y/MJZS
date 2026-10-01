"""Private stdio bridge to the installed prompt-optimizer-mcp npm package."""
import asyncio,json,os,sys
from pathlib import Path

def classify_error(value):
    text=str(value).lower()
    for tokens,message in [
        (('insufficient_quota','billing','credit balance'),'文本 API 余额或额度不足，请检查 OpenAI API 账单；ChatGPT 订阅不等于 API 额度。'),
        (('401','invalid_api_key','incorrect api key'),'文本 API 密钥无效或已失效，请检查 MCP 设置。'),
        (('403','permission','unsupported_country'),'文本 API 访问被拒绝，请检查模型权限及服务可用地区。'),
        (('404','model_not_found','does not exist'),'文本模型不存在或当前密钥无权访问，请检查文本模型 ID。'),
        (('429','rate_limit'),'文本 API 请求频率或额度受限，请稍后再试并检查额度。'),
        (('timeout','timed out'),'文本 API 连接或响应超时，请检查网络后重试。'),
        (('connection','connecterror','ssl','proxy'),'无法连接文本 API，请检查网络、代理或证书设置。'),
        (('temperature','unsupported_parameter'),'当前文本模型不接受优化服务的参数，请更换兼容模型或调整参数。'),
        (('modulenotfound','no module named','importerror'),'MCP 运行环境缺少依赖，请检查服务安装。'),
        (('400','invalid_request'),'文本 API 拒绝了请求参数，请检查模型 ID、地址及请求格式。')]:
        if any(token in text for token in tokens):return message
    return 'MCP 服务执行失败，未取得可识别的 API 错误；原提示词保留。'

def error_details(exc):
    nested=getattr(exc,'exceptions',None)
    return ' '.join(error_details(e) for e in nested) if nested else str(exc)

async def optimize(data):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    env=dict(os.environ)
    env.update(OPTIMIZER_API_BASE=data['base_url'],OPTIMIZER_API_KEY=data['api_key'],OPTIMIZER_MODEL=data['model'],PYTHONIOENCODING='utf-8')
    server=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).resolve()),'--server',data['server']],env=env)
    with open(os.devnull,'w') as errors:
        async with stdio_client(server,errlog=errors) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                result=await session.call_tool('iterate_prompt',{'current_prompt':data['prompt'],'iterate_input':data['instructions']})
                if result.isError:raise RuntimeError(' '.join(c.text for c in result.content if getattr(c,'type',None)=='text'))
                return '\n'.join(c.text for c in result.content if getattr(c,'type',None)=='text')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--server':
        import importlib.util
        spec=importlib.util.spec_from_file_location('installed_prompt_optimizer',sys.argv[2])
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.client=module.client.with_options(max_retries=0,timeout=90)
        module.mcp.run()
    else:
        try:
            data=json.load(sys.stdin)
            output=asyncio.run(asyncio.wait_for(optimize(data),timeout=110))
            print(json.dumps({'text':output},ensure_ascii=True))
        except Exception as exc:
            print(json.dumps({'error':classify_error(error_details(exc))},ensure_ascii=True))
            sys.exit(1)
