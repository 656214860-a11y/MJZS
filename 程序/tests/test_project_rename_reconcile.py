# -*- coding: utf-8 -*-
"""项目目录改名后的一级认领；所有案例只使用临时目录。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import project_stages
import projects as projects_mod
from projects import Projects, reconcile_missing


def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')


class RenameReconcileTests(unittest.TestCase):
    def make_service(self,folder,old='故事_20261001'):
        app=Path(folder)/'程序';base=Path(folder)/'库'/'项目';base.mkdir(parents=True)
        dump(app/'config.json',{'downloads_root':str(Path(folder)/'库')})
        dump(app/'projects.json',{'active':str(base/old),'projects':[{'name':'故事','path':str(base/old),'created_at':1,'status':'making'}]})
        return Projects(app),base

    def renamed(self,base,name='新故事_20261001',old=None):
        item=base/name;story=project_stages.storyboard(item)/'分镜拆分'
        story.mkdir(parents=True)
        dump(item/'config.json',{'episode_dir':str(Path(old)/'03初步分镜'/'分镜拆分'),
                                 'episode_file':str(Path(old)/'03初步分镜'/'分镜拆分'/'episode.json')})
        return item

    def test_one_to_one_rename_claims_and_rewrites_live_paths(self):
        with tempfile.TemporaryDirectory() as td:
            service,base=self.make_service(td);old=service.info['active'];new=self.renamed(base,old=old)
            cloud=new/'cloud_video'/'job';dump(cloud/'config.json',{'episode_dir':str(Path(old)/'03初步分镜')})
            out=service.reconcile_missing(old)
            self.assertEqual(out['state'],'claimed');self.assertEqual(out['path'],str(new))
            self.assertEqual(service.info['active'],str(new));self.assertEqual(service.info['projects'][0]['status'],'making')
            self.assertEqual(json.loads((new/'config.json').read_text())['episode_dir'],str(new/'03初步分镜'/'分镜拆分'))
            self.assertEqual(json.loads((cloud/'config.json').read_text())['episode_dir'],str(new/'03初步分镜'))
            self.assertTrue((new/'12质检交付').is_dir())

    def test_multiple_fingerprint_candidates_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            service,base=self.make_service(td);old=service.info['active']
            self.renamed(base,'甲_20261001',old);self.renamed(base,'乙_20261001',old)
            out=service.reconcile_missing(old)
            self.assertEqual(out['state'],'confirm');self.assertEqual(len(out['choices']),2)
            self.assertEqual(service.info['active'],old)

    def test_unmatched_candidate_can_be_registered_as_new_project(self):
        with tempfile.TemporaryDirectory() as td:
            service,base=self.make_service(td);candidate=base/'新来的_20261002'
            (candidate/'01剧本准备').mkdir(parents=True)
            self.assertEqual(reconcile_missing(service.info,base)['matches'][service.info['active']],[])
            service.register_discovered_project(candidate)
            self.assertIn(str(candidate),[x['path'] for x in service.info['projects']])

    def test_recycle_base_never_becomes_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            service,base=self.make_service(td);recycled=base/'工作流任务'/'旧项目'
            (recycled/'01剧本准备').mkdir(parents=True)
            result=reconcile_missing(service.info,base)
            self.assertNotIn(str(recycled),result['candidates'])

    def test_failed_live_rewrite_rolls_back_every_file(self):
        with tempfile.TemporaryDirectory() as td:
            service,base=self.make_service(td);old=service.info['active'];new=self.renamed(base,old=old)
            before_registry=service.registry.read_bytes();before_config=(new/'config.json').read_bytes()
            original=projects_mod.save_bytes;calls=[]
            def fail_second(path,data):
                calls.append(path)
                if len(calls)==2:raise PermissionError('locked')
                return original(path,data)
            with patch.object(projects_mod,'save_bytes',side_effect=fail_second):
                with self.assertRaises(PermissionError):service.claim_reconciled(old,new)
            self.assertEqual(service.registry.read_bytes(),before_registry)
            self.assertEqual((new/'config.json').read_bytes(),before_config)

    def test_scan_never_recurses_into_stage_directories(self):
        with tempfile.TemporaryDirectory() as td:
            service,base=self.make_service(td);root=base/'候选_20261003';(root/'01剧本准备'/'深层').mkdir(parents=True)
            original=Path.iterdir;calls=[]
            def counted(path):
                calls.append(str(path));return original(path)
            with patch.object(Path,'iterdir',new=counted):
                reconcile_missing(service.info,base)
            self.assertEqual(calls,[str(base)])


if __name__=='__main__':unittest.main()
