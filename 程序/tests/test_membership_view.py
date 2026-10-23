# -*- coding: utf-8 -*-
"""会员状态文案（纯函数）：未登录、试用剩余天数、临期、到期、时钟异常。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))

import entitlement_service as ent
from test_account_client import DID, KEYS, NOW, evaluate, payload, sign

DAY=86400


def view(**over):
    return ent.membership_view(evaluate(sign(payload(**over))),NOW)


class MembershipViewTests(unittest.TestCase):
    def test_signed_out_explains_trial_and_free_stages(self):
        v=ent.membership_view(ent.Entitlement(ent.SIGNED_OUT),NOW)
        text=''.join(v['lines'])
        self.assertIn('免费试用 3 天',text)
        self.assertIn('永久免费',text)
        self.assertEqual(v['badge'],'未登录')

    def test_trial_days_left_plain_then_warn(self):
        plain=view(trial_ends_at=NOW+5*DAY)
        self.assertEqual(plain['lines'],['试用还剩 5 天。'])
        self.assertEqual((plain['level'],plain['badge']),('info',''))
        warn=view(trial_ends_at=NOW+2*DAY-10)
        self.assertEqual((warn['level'],warn['badge']),('warn','剩2天'))
        self.assertIn('兑换码',''.join(warn['lines']))

    def test_active_member_uses_period_end(self):
        v=view(state='active',plan='monthly',period_end=NOW+30*DAY,trial_ends_at=None,expires_at=NOW+31*DAY,grace_until=NOW+33*DAY)
        self.assertEqual(v['lines'],['会员还剩 30 天。'])

    def test_expired_shows_date_and_redeem_hint(self):
        v=view(state='expired',trial_ends_at=NOW-DAY,expires_at=NOW+DAY)
        self.assertEqual(v['level'],'expired')
        self.assertEqual(v['badge'],'已到期')
        text=''.join(v['lines'])
        self.assertIn('已于 ',text);self.assertIn('永久免费',text);self.assertIn('请联系发放兑换码的渠道',text)

    def test_clock_suspect_and_days_left_edges(self):
        ent_=ent.Entitlement(ent.CLOCK_SUSPECT,payload())
        self.assertEqual(ent.membership_view(ent_,NOW)['badge'],'时间异常')
        self.assertEqual(ent.days_left({'state':'trial','trial_ends_at':NOW-5},NOW),0)
        self.assertIsNone(ent.days_left({'state':'trial'},NOW))


if __name__=='__main__':
    unittest.main()
