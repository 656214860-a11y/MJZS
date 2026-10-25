"""R2051：启动登录闸挡着的时候，三虎一个弹窗都不出；闸门过了，压着的话再补说。"""
import unittest

from test_pet_ui import PetTestCase


class LoginGateQuietTests(PetTestCase):
    def setUp(self):
        super().setUp()
        self.fake.login_gate_active = True

    def test_nothing_pops_while_the_gate_is_up(self):
        self.assertTrue(self.pet.login_locked())
        self.assertFalse(self.pet.can_pop())
        self.assertIsNone(self.pet.open_chat())
        self.assertIsNone(self.pet.cloud().show(pinned=True))
        self.pet.broadcast('闸门期间的一句话')
        self.assertFalse(self.pet.cloud_visible(), '登录闸挡着，云朵不许冒出来')
        self.assertEqual(self.pet.bstate.held_broadcast, '闸门期间的一句话')

    def test_held_line_is_said_after_the_gate_passes(self):
        self.pet.broadcast('闸门期间的一句话')
        self.fake.login_gate_active = False
        self.assertFalse(self.pet.login_locked())
        self.pet.pump()
        self.assertFalse(self.pet.bstate.held_broadcast)
        self.assertIn('闸门期间的一句话', self.pet.cloud().transcript())

    def test_a_cloud_already_up_is_closed_when_the_gate_appears(self):
        from desktop_login_gate import LoginGateMixin
        self.fake.login_gate_active = False
        self.pet.open_chat()
        self.assertTrue(self.pet.cloud_visible())
        self.fake.pet = self.pet
        self.fake.win = self.win
        self.fake.login_gate = None
        self.fake._build_login_form = lambda *a, **k: None
        self.fake._login_gate_passed = lambda: None
        LoginGateMixin.show_login_gate(self.fake)
        self.assertFalse(self.pet.cloud_visible())


if __name__ == '__main__':
    unittest.main()
