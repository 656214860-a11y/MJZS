import re, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
ROOT = pathlib.Path(__file__).resolve().parents[3]
names = ['edit_habits_dialog','project_settings_dialog','stage_contract_report','storyboard_catalog',
         'idea_script_heuristic','stage_animatic_gateways','stage_asset_gateways','stage_gate_gateways',
         'stage_handoff_gateways','stage_previs_gateways','stage_publication','stage_write_preparation_service',
         'store_program_locator','white_model_persistence_controller','writing_preparation_ledger',
         'model_protocol','pet_settings_contract','shot_selection','script_brief']
alt = '|'.join(names)
imp = re.compile(r'^\s*(?:import|from)\s+(?:' + alt + r')\b')
imp2 = re.compile(r'^\s*from\s+orchestrator\s+import\b.*\b(?:storyboard_catalog|stage_contract_report)\b')
dyn = re.compile(r'(?:import_module|__import__)\s*\(\s*[\'\"](?:' + alt + r')[\'\"]')
patchstr = re.compile(r'[\'\"](?:' + alt + r')(?:\.[\w.]+)?[\'\"]')
skip_dirs = ('维护记录/', 'tasks_round/', '__pycache__', 'deadcode_20261116', '.git')
hits = []
for p in ROOT.rglob('*'):
    if p.suffix not in ('.py', '.pyw'): continue
    s = p.relative_to(ROOT).as_posix()
    if any(x in s for x in skip_dirs): continue
    try: lines = p.read_text(encoding='utf-8').splitlines()
    except Exception: continue
    for i, ln in enumerate(lines, 1):
        st = ln.strip()
        if st.startswith('#'): continue
        if imp.match(ln) or imp2.search(ln) or dyn.search(ln):
            hits.append(f'{s}:{i}: {st[:110]}')
        elif patchstr.search(ln) and re.search(r'patch|mock|spec', st, re.I):
            hits.append(f'{s}:{i}: PATCH? {st[:110]}')
print(len(hits), 'hits')
for h in hits: print(h)
