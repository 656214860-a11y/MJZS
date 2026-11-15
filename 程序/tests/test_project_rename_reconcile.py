# -*- coding: utf-8 -*-
"""项目目录改名后的一级认领；所有案例只使用临时目录。"""
import json
import inspect
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import MagicMock, patch

import desktop
from desktop_project_pages import ProjectPageServices

import project_stages
import projects as projects_mod
from projects import Projects, reconcile_missing
from stage_execution_service import project_registry_gateway


def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')


class RenameReconcileTests(unittest.TestCase):
    def make_service(self,folder,old='故事_20261001'):
        app=Path(folder)/'程序';base=Path(folder)/'库'/'项目';base.mkdir(parents=True)
        dump(app/'config.json',{'downloads_root':str(Path(folder)/'库')})
        dump(app/'projects.json',{'active':str(base/old),'projects':[{'name':'故事','path':str(base/old),'created_at':1,'status':'making'}]})
        return Projects(app,gateway=project_registry_gateway()),base

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
            out=service.reconcile_missing(old).data
            self.assertEqual(out['state'],'claimed');self.assertEqual(out['path'],str(new))
            self.assertEqual(service.info['active'],str(new));self.assertEqual(service.info['projects'][0]['status'],'making')
            self.assertEqual(json.loads((new/'config.json').read_text(encoding='utf-8'))['episode_dir'],str(new/'03初步分镜'/'分镜拆分'))
            self.assertEqual(json.loads((cloud/'config.json').read_text(encoding='utf-8'))['episode_dir'],str(new/'03初步分镜'))
            self.assertTrue((new/'13质检交付').is_dir())

    def test_multiple_fingerprint_candidates_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            service,base=self.make_service(td);old=service.info['active']
            self.renamed(base,'甲_20261001',old);self.renamed(base,'乙_20261001',old)
            out=service.reconcile_missing(old).data
            self.assertEqual(out['state'],'confirm');self.assertEqual(len(out['choices']),2)
            self.assertEqual(service.info['active'],old)

    def test_unmatched_candidate_can_be_registered_as_new_project(self):
        with tempfile.TemporaryDirectory() as td:
            service,base=self.make_service(td);candidate=base/'新来的_20261002'
            (candidate/'01剧本准备').mkdir(parents=True)
            self.assertEqual(reconcile_missing(service.info,base)['matches'][service.info['active']],[])
            self.assertTrue(service.register_discovered_project(candidate).ok)
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
            gateway=project_registry_gateway();original=gateway['publish_bytes'];calls=[]
            def fail_second(path,data):
                calls.append(path)
                if len(calls)==2:raise PermissionError('locked')
                return original(path,data)
            gateway['publish_bytes']=fail_second;service.gateway=gateway;service._require_gateway()
            outcome=service.claim_reconciled(old,new)
            self.assertFalse(outcome.ok)
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


class DesktopRenameReconcileTests(unittest.TestCase):
    def make_desktop(self, service):
        app=MagicMock()
        app.projects=service
        app._project_result_data=lambda result:desktop.Desktop._project_result_data(app,result)
        app._sync_project_picker=lambda **kw:desktop.Desktop._sync_project_picker(app,**kw)
        app._sync_project_group_styles=lambda:desktop.Desktop._sync_project_group_styles(app)
        app.mark_current_project=lambda:desktop.Desktop.mark_current_project(app)
        app.fill_projects=lambda tree:desktop.Desktop.fill_projects(app,tree)
        app.project_row_text=lambda p:desktop.Desktop.project_row_text(app,p)
        app.reload=lambda:desktop.Desktop.reload(app)
        app.reload()
        return app

    def picker_paths(self, app):
        return [p['path'] for p in app._picker_items]

    def test_automatic_claim_refreshes_picker_before_selecting_and_building_page(self):
        fixture=RenameReconcileTests()
        for deferred in (False,True):
            with self.subTest(deferred=deferred),tempfile.TemporaryDirectory() as td:
                service,base=fixture.make_service(td)
                old=service.info['active'];new=fixture.renamed(base,old=old)
                app=self.make_desktop(service)
                self.assertIn(old,self.picker_paths(app))
                with patch.object(desktop,'open_studio',return_value=None):
                    desktop.Desktop.load(app,old,defer_page=deferred)
                paths=self.picker_paths(app)
                self.assertNotIn(old,paths)
                self.assertIn(str(new),paths)
                app.project_picker.current.assert_called_with(paths.index(str(new)))
                self.assertEqual(app.root,new)
                app._sync_desktop_project_paths.assert_called_once_with(old,str(new))
                self.assertEqual(service.info['active'],str(new))
                if deferred:
                    app.win.after.assert_called_once()
                    app.show.assert_not_called()
                else:app.show.assert_called_once_with(0)

    def test_unchanged_project_keeps_valid_picker_and_opens_normally(self):
        fixture=RenameReconcileTests()
        with tempfile.TemporaryDirectory() as td:
            service,base=fixture.make_service(td)
            root=Path(service.info['active']);root.mkdir()
            app=self.make_desktop(service)
            before=self.picker_paths(app)
            with patch.object(desktop,'open_studio',return_value=None):
                desktop.Desktop.load(app,str(root))
            self.assertEqual(self.picker_paths(app),before)
            app.project_picker.current.assert_called_with(before.index(str(root)))
            app.show.assert_called_once_with(0)
            app._sync_desktop_project_paths.assert_not_called()


class DesktopMissingRegistrationTests(unittest.TestCase):
    """真实登记与两个真实列表联动；窗口保持隐藏，不操作用户桌面。"""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service,self.base=RenameReconcileTests().make_service(self.temp.name)
        self.old=self.service.info['active']
        self.win=tk.Tk();self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.app=MagicMock()
        # 页面服务改为注入后，MagicMock 的宿主要带真服务，desktop.confirm 补丁才会生效（R1983 J2，断言未动）。
        self.app.project_page_services=ProjectPageServices(open_path=lambda *a, **k: desktop.open_path(*a, **k),
            context_menu=lambda *a, **k: desktop.ContextMenu(*a, **k),
            confirm=lambda *a, **k: desktop.confirm(*a, **k))
        self.app.win=self.win;self.app.root=None;self.app.projects=self.service
        self.app.content=ttk.Frame(self.win)
        self.app._project_home_tree=None
        self.app._project_result_data=lambda r:desktop.Desktop._project_result_data(self.app,r)
        self.app._sync_project_picker=lambda **kw:desktop.Desktop._sync_project_picker(self.app,**kw)
        self.app._sync_project_group_styles=lambda:desktop.Desktop._sync_project_group_styles(self.app)
        self.app.refresh_sidebar_title=lambda:desktop.Desktop.refresh_sidebar_title(self.app)
        self.app.fill_projects=lambda tree:desktop.Desktop.fill_projects(self.app,tree)
        self.app.reload=lambda:desktop.Desktop.reload(self.app)
        self.app.reload();desktop.Desktop.project_home(self.app)
        self.home=next(w for w in self.app.content.winfo_children() if isinstance(w,ttk.Treeview))
        self.before=self.service.registry.read_bytes()

    def clear(self,confirmed=True):
        return desktop.Desktop.clear_missing_project(self.app,{'path':self.old},confirmed=confirmed)

    def picker_has(self,path):
        return any(p['path']==path for p in getattr(self.app,'_picker_items',[]))

    def assert_unchanged(self):
        self.assertEqual(self.service.registry.read_bytes(),self.before)
        self.assertTrue(self.picker_has(self.old))
        self.assertTrue(self.home.exists(self.old))

    def test_clear_refreshes_picker_and_home_without_rebuilding_page_or_touching_other_tree(self):
        other=ttk.Treeview(self.app.content);other.insert('','end',iid='unrelated',text='保留')
        self.assertTrue(self.clear())
        self.assertEqual(self.service.refresh_registry(),{'active':None,'projects':[]})
        self.assertFalse(self.picker_has(self.old))
        self.assertFalse(self.home.exists(self.old),'homepage retained cleared ghost registration')
        self.assertTrue(other.exists('unrelated'))
        self.assertTrue(self.home.winfo_exists())
        self.app.show.assert_not_called()

    def test_cancel_preserves_registration_and_both_lists(self):
        with patch.object(desktop,'confirm',return_value=False):
            self.assertFalse(self.clear(confirmed=False))
        self.assert_unchanged()

    def test_existing_project_is_not_cleared(self):
        Path(self.old).mkdir()
        with self.assertRaisesRegex(ValueError,'仍存在'):
            self.clear()
        self.assertTrue(Path(self.old).is_dir())
        self.assert_unchanged()

    def test_write_failure_preserves_registration_and_both_lists(self):
        with patch.object(self.service,'_publish_json',side_effect=PermissionError('locked')):
            self.assertFalse(self.clear())
        self.assert_unchanged()
        self.assertIn('清除失效项目登记失败',self.app.status.set.call_args.args[0])

    def test_destroyed_homepage_is_not_refreshed(self):
        self.home.destroy()
        self.assertTrue(self.clear())
        self.assertFalse(self.picker_has(self.old))
        self.assertEqual(self.service.refresh_registry()['projects'],[])


if __name__=='__main__':unittest.main()
