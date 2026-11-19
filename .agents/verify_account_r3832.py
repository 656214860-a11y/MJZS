from pathlib import Path
import re,json,unicodedata,hashlib
r=Path(r'D:\漫剧制作助手\.agents\worktrees\account-design-consolidation')
p=r/'程序/docs/specs/07_业务域规格.md'; n=p.read_text(encoding='utf-8'); o=(r/'程序/说明/账户会员云端设计.md').read_text(encoding='utf-8'); m=(r/'程序/docs/records/账户设计条款迁移映射.md').read_text(encoding='utf-8')
checks=[]
def check(name,ok,detail=''):
 checks.append((name,bool(ok),detail))
for i in range(1,9):check('stable_7.'+str(i),len(re.findall(r'^## 7\.'+str(i)+r' ',n,re.M))==1)
for i in range(1,11):check('source_section_'+str(i),bool(re.search(r'^### 7\.9\.'+str(i)+r' ',n,re.M)))
for t in ['user','identity','device','session','subscription','trial_ledger','user_password','email_code','audit_log','redeem_code']:
 row=next(x for x in o.splitlines() if x.startswith('| `'+t+'` |')); toks=re.findall(r'`([^`]+)`',row); check('table_'+t,all('`'+x+'`' in n for x in toks),toks)
lease=o[o.index('`payload` 字段：'):o.index('### 4.2')]
fields=re.findall(r'^\| `([^`]+)`',lease,re.M)
check('lease_14_fields',len(fields)==14 and all('| `'+x+'`' in n for x in fields),fields)
api=o[o.index('### 3.2'):o.index('### 3.3')]
api_tokens=set(re.findall(r'`([^`]+)`',api)); missing=sorted(x for x in api_tokens if '`'+x+'`' not in n)
# Original incorrect /me wording has been deliberately corrected; its token was not a field identity.
check('original_api_tokens',not missing,missing)
for id in [*('D'+str(i) for i in range(1,17)),'D11b',*('Q'+str(i) for i in range(1,9))]:
 check('decision_'+id,bool(re.search(r'^\| '+id+r'(?:[ （])',n,re.M)) and bool(re.search(r'^\| '+id+r'(?:[ （])',m,re.M)))
check('no_old_authority_pointer','完整设计仍在' not in n and '完整设计权威是 [`说明/' not in n)
check('metering_not_implemented','两端路由／消费者均不存在' in n)
# Compare settings/assets/models/dependencies verbatim except one intentionally normalized contract link.
orig=(r/'程序/docs/specs/07_业务域规格.md').read_text(encoding='utf-8')
import subprocess
base=subprocess.check_output(['git','show','b860721f:程序/docs/specs/07_业务域规格.md'],cwd=r).decode('utf-8')
mid=base[base.index('## 7.4 设置'):base.index('## 7.8 未决事项')].replace('`说明/生成服务失败处理契约.md`','[生成服务失败处理契约](../contracts/生成服务失败处理契约.md)')
check('non_account_domains_preserved',mid in n)
def slug(s):
 s=s.strip().lower();s=re.sub(r'[`*_~]','',s);s=''.join(c for c in s if c.isalnum() or c in ' -_');return s.replace(' ','-')
def anchors(text):return {slug(x) for x in re.findall(r'^#{1,6}\s+(.+)$',text,re.M)}
links=[]
for source in [p,r/'程序/docs/records/账户设计条款迁移映射.md']:
 text=source.read_text(encoding='utf-8')
 for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)',text):
  if '://' in target:continue
  path,_,frag=target.partition('#'); dest=(source.parent/path).resolve() if path else source
  status='OK' if dest.is_file() else 'PENDING_ROOT_MOVE'
  if status=='OK' and frag and frag not in anchors(dest.read_text(encoding='utf-8')):status='BAD_ANCHOR'
  links.append({'source':source.name,'target':target,'status':status})
check('no_bad_anchors',all(x['status']!='BAD_ANCHOR' for x in links),[x for x in links if x['status']=='BAD_ANCHOR'])
report=json.dumps({'checks':checks,'total':len(checks),'passed':sum(x[1] for x in checks),'link_count':len(links),'link_ok':sum(x['status']=='OK' for x in links),'pending_links':[x for x in links if x['status']!='OK'],'sources':[{'path':str(x.relative_to(r)),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in [r/'程序/说明/账户会员云端设计.md',r/'程序/说明/账户会员云端立项前清单.md']]},ensure_ascii=False,indent=2)
Path(r'D:\漫剧制作助手\.agents\account_r3832_checks_utf8.json').write_text(report,encoding='utf-8')
print('old_api',len(set(re.findall(r'`((?:GET|POST|DELETE) /v1/[^`]+)`',api))),'all_old_identifiers_missing', sorted(x for x in set(re.findall(r'`([^`\n]+)`',o)) if '`'+x+'`' not in n))
print('checks',len(checks),'passed',sum(x[1] for x in checks),'links',len(links),'ok',sum(x['status']=='OK' for x in links))
raise SystemExit(0 if all(x[1] for x in checks) else 1)
