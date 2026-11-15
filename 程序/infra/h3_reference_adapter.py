"""Bind selected local assets to native H3 Ref2VA conditioning."""
from agent.shot_assets import assets

MODEL='minimax_h3_ref2va_pruned_int8_convrot.safetensors'

def attach(graph,options,episode_path,shot):
    chosen=shot.get('local_asset_ids',[])
    if not chosen:return []
    rows=assets(episode_path,shot)
    refs=[r for r in rows if r['id'] in chosen]
    missing=set(chosen)-{r['id'] for r in refs}
    if missing:raise ValueError('勾选资产不属于当前镜头：'+'、'.join(sorted(missing)))
    if len(refs)>9:raise ValueError('H3最多支持9张参考资产图，请减少勾选')
    for row in refs:
        if not row['ready']:raise ValueError('参考资产图片缺失：'+row['id']+' '+row['name'])
    nid=options.get('prompt','104.prompt').split('.',1)[0]
    node=graph[nid]
    if node['class_type']!='MiniMaxH3ImageToVideo':raise ValueError('自动资产接入需要 H3 首帧工作流；请先选择已跑通的 API 工作流')
    for item in graph.values():
        if 'LoraLoader' in item.get('class_type',''):
            raise ValueError('当前工作流含LoRA，请先使用不含FL2VA LoRA的首帧工作流接入Ref2VA')
    loaders=[n for n in graph.values() if n.get('class_type')=='UNETLoader' and 'minimax_h3_fl2va' in n.get('inputs',{}).get('unet_name','').lower()]
    if len(loaders)!=1:raise ValueError('无法唯一识别H3主模型加载器，请使用已跑通的原生首帧工作流')
    loaders[0]['inputs']['unet_name']=MODEL
    original=dict(node['inputs'])
    inputs={k:original[k] for k in ('clip','vae','prompt','width','height','length')}
    inputs['ref_image_size']='match'
    guide_id='assistant_h3_first_frame'
    if guide_id in graph:raise ValueError('工作流含同名资产接入节点')
    def reroute(value):
        if isinstance(value,list) and len(value)==2 and value[0]==nid and value[1] in (0,1):return [guide_id,value[1]]
        return value
    for item in graph.values():
        item['inputs']={k:reroute(v) for k,v in item['inputs'].items()}
    graph[nid]={'class_type':'MiniMaxH3ReferenceToVideo','inputs':inputs}
    graph[guide_id]={'class_type':'MiniMaxH3AddGuide','inputs':{'positive':[nid,0],'latent':[nid,1],'vae':original['vae'],'image':original['first_frame'],'frame_idx':0}}
    mapping=[]
    for index,row in enumerate(refs):
        image_id=f'assistant_h3_asset_{index}'
        if image_id in graph:raise ValueError('工作流含同名参考图节点')
        graph[image_id]={'class_type':'LoadImage','inputs':{'image':'pending_upload.png'}}
        inputs[f'ref_images.ref_image_{index}']=[image_id,0]
        mapping.append(f"<Picture {index+1}> 对应 {row['id']} {row['name']}")
        row['node_id']=image_id;row['picture']=index+1
    inputs['prompt']+='\n参考图对应关系：'+'；'.join(mapping)+'。角色参考图用于保持脸型、发型、服装和身份；场景、道具参考图仅约束对应资产。保持首帧的构图和人物站位，不把资产图拼成画面。'
    return refs
