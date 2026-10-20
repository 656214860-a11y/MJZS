"""REQ-S06 测试锚定：连贯性漂移范围与页面／发布边界。"""
import tempfile
import unittest
from pathlib import Path

import continuity_ledger
from agent.core import save
from desktop_media_pages import MediaPagesMixin


class ReqS06AnchorTests(unittest.TestCase):
    def test_req_s06_16_drift_compares_character_anchors_only(self):
        """REQ-S06-16：漂移只比较角色锚点，场景／道具冻结值不产生漂移项。"""
        ledger = {'batches': [{'frozen_anchors': [
            {'kind': 'character', 'id': 'CHAR_001', 'state': '', 'anchor': '银发'},
            {'kind': 'scene', 'id': 'LOC_001', 'state': '', 'anchor': '旧门'},
            {'kind': 'prop', 'id': 'PROP_001', 'state': '', 'anchor': '旧刀'},
        ]}]}
        assets = {
            'CHAR_001': {'character_anchor': '黑发'},
            'LOC_001': {'spatial_anchors': [{'object': '门', 'position': '新门'}]},
            'PROP_001': {'character_anchor': '新刀'},
        }
        rows = continuity_ledger.drift(ledger, assets)
        self.assertEqual([row['kind'] for row in rows], ['character'])
        self.assertEqual(rows[0]['id'], 'CHAR_001')

    def test_req_s06_25_page_preview_is_read_only_but_manual_generate_publishes(self):
        """REQ-S06-25：页面数据现场计算不落盘；手动生成才写台账并同步问题登记。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'board.json'
            save(source, {'shots': [{'id': 'SH001', 'characters': ['CHAR_001'],
                                     'location': 'LOC_001', 'props': []}]})
            page = type('Page', (), {})()
            page.current_frame_json = lambda: source
            page.asset_requirements = lambda: {}
            before = {path.relative_to(root) for path in root.rglob('*')}
            ledger = MediaPagesMixin.continuity_ledger_data(page)
            after = {path.relative_to(root) for path in root.rglob('*')}
            self.assertEqual(after, before, '现场计算不得新增或改写文件')
            self.assertEqual(ledger['summary']['shots'], 1)

            page.write_continuity_ledger = lambda value: page.writes.append(value)
            page.sync_continuity_issues = lambda value: page.issued.append(value)
            page.pet_report = lambda *args: page.reports.append(args)
            page.show = lambda *args: page.shown.append(args)
            page.status = type('Status', (), {'set': lambda _self, text: page.status_text.append(text)})()
            page.page_index = None
            page.writes, page.issued, page.reports, page.shown, page.status_text = [], [], [], [], []
            MediaPagesMixin.generate_continuity_ledger(page, ledger)
            self.assertEqual(page.writes, [ledger])
            self.assertEqual(page.issued, [ledger])
            self.assertEqual(page.shown, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
