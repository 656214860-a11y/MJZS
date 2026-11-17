"""Read reference-image prompts from character cards; match names, never Cxx ordinals."""
from pathlib import Path
import hashlib,re

IGNORE={'历史版本','分镜历史','历史归档','回收站','.git'}
AUTO_FIELDS=('image_prompt','negative_prompt','prompt_source','prompt_source_character','prompt_source_name','prompt_import_hash')

def fingerprint(positive,negative):
    return hashlib.sha256((positive+'\n'+negative).encode('utf-8')).hexdigest()

def key(name):return re.sub(r'\s+','',str(name)).strip('《》「」“”\"').casefold()

def cards(text):
    text=text.replace('\r\n','\n').replace('**','')
    headings=list(re.finditer(r'^#{1,3}\s*(?:角色卡|人物卡|角色设定)\s*[：:]\s*(.+?)\s*#*$',text,re.M))
    result=[]
    for i,heading in enumerate(headings):
        body=text[heading.end():headings[i+1].start() if i+1<len(headings) else len(text)]
        # Only the labelled reference prompt section is imported, not instructions elsewhere.
        section=re.search(r'^#{1,6}\s*(?:角色)?(?:参考图|图像|生图)提示词\s*$',body,re.M)
        if not section:continue
        content=body[section.end():]
        next_heading=re.search(r'^#{1,6}\s+',content,re.M)
        if next_heading:content=content[:next_heading.start()]
        positive=re.search(r'^\s*(?:Prompt|正向提示词|正向)\s*[：:]\s*(.*?)(?=^\s*(?:Negative|负向提示词|负向)\s*[：:]|\Z)',content,re.M|re.S|re.I)
        negative=re.search(r'^\s*(?:Negative|负向提示词|负向)\s*[：:]\s*(.*)',content,re.M|re.S|re.I)
        def clean(match):return '\n'.join(line for line in match.group(1).strip().splitlines() if not line.strip().startswith('```')).strip() if match else ''
        prompt=clean(positive)
        if not prompt:continue
        identifier=re.search(r'(?:角色|人物)\s*ID\s*[：:]\s*(CHAR_\d+|C\d+)',body,re.I)
        result.append({'name':heading.group(1).strip(),'id':identifier.group(1) if identifier else '',
                       'positive':prompt,'negative':clean(negative)})
    return result

def discover(project,source_script=None):
    from contract.project_stages import writing
    from domain.storyboard_catalog_service import discover_files
    project=Path(project).resolve();writing=writing(project).resolve();candidates=[]
    script=(project/Path(source_script)).resolve() if source_script else None
    preferred=script.parent if script and script.is_relative_to(writing) else None
    for path,_resolved,stat in discover_files((writing,), {'.md'}, IGNORE):
        try:
            if stat.st_size>2*1024*1024:continue
            found=cards(path.read_text(encoding='utf-8-sig'))
        except (OSError,UnicodeError):continue
        if found:candidates.append((path,found,stat.st_mtime_ns))
    # Once the selected screenplay's folder has role cards, do not mix other creative versions.
    local=[item for item in candidates if preferred and item[0].parent==preferred]
    return sorted(local or candidates,key=lambda item:item[2],reverse=True)

def sync_reference_prompts(project,planned,source_script=None,documents=None):
    project=Path(project).resolve()
    if documents is None:documents=discover(project,source_script)
    index={}
    for path,found,modified in documents:
        local={}
        for card in found:local.setdefault(key(card['name']),[]).append(card)
        for name,choices in local.items():
            if name not in index:index[name]=(path,choices)
    for aid,asset in planned.items():
        if not aid.startswith('CHAR_'):continue
        # A prompt changed manually since the previous import remains user-owned.
        old_hash=asset.get('prompt_import_hash')
        # Structured prompts written by an Agent or the user take priority over legacy cards.
        if not old_hash and any(asset.get(k) for k in ('image_prompt','positive_prompt','prompt')):continue
        if old_hash and old_hash!=fingerprint(asset.get('image_prompt',''),asset.get('negative_prompt','')):continue
        names=[asset.get('name','')]+asset.get('aliases',[])
        primary=index.get(key(names[0]))
        matches=[primary] if primary else [index[key(name)] for name in names[1:] if key(name) in index]
        valid={(str(path),card['name']):(path,card) for path,choices in matches for card in choices}
        if len(valid)!=1:
            if old_hash:
                for field in AUTO_FIELDS:asset.pop(field,None)
            continue
        path,card=next(iter(valid.values()))
        # Explicit CHAR IDs must agree. C01 is only a document ID, not CHAR_001.
        if card['id'].startswith('CHAR_') and card['id']!=aid:continue
        if asset.get('image_prompt') and not asset.get('prompt_source'):continue
        asset.update(image_prompt=card['positive'],negative_prompt=card['negative'],
                     prompt_source=path.relative_to(project).as_posix(),prompt_source_character=card['id'],
                     prompt_source_name=card['name'],prompt_import_hash=fingerprint(card['positive'],card['negative']))
    return planned


def display_prompt(asset):
    if not isinstance(asset, dict):
        return ''
    positive=next((asset.get(k) for k in ('image_prompt','positive_prompt','prompt') if isinstance(asset.get(k),str) and asset[k].strip()),'')
    if not positive:return ''
    negative=asset.get('negative_prompt')
    return positive+('\n\n负向提示词：'+str(negative) if isinstance(negative,str) and negative.strip() else '')
