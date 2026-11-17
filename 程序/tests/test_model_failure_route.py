import unittest
from types import SimpleNamespace
from unittest.mock import patch
import infra.model_router as m
import contract.platform_tools as platform_tools

class FailureRouteTests(unittest.TestCase):
    def router(self, first, budget=None):
        calls=[]
        class Adapter(m.ModelAdapter):
            models={'a': {'capabilities': ['reasoning']}, 'b': {'capabilities': ['reasoning']}}
            def available(self): return True
            def chat(self, messages, options=None, model='', **kw):
                calls.append(model)
                return dict(first) if model=='a' else {'ok': True, 'status': 200, 'text': 'ok', 'model': model}
        router=m.ModelRouter(adapters=[Adapter()], budget=budget)
        skill=SimpleNamespace(tools=[], preferredModels=['a'], capabilities=['reasoning'], fallbackModels=['b','a','b'])
        return router, router.select(skill), calls

    def test_rate_limit_can_switch_once_and_retains_attempt_reason(self):
        r,c,calls=self.router({'ok': False, 'status': 429})
        out=r.chat(c,[])
        self.assertEqual(calls,['a','b'])
        self.assertTrue(out['ok'])
        self.assertEqual(out['attempts'][0]['reason_code'],'rate_limit')

    def test_ambiguous_and_terminal_failures_never_switch(self):
        for response in [{'status':0}, {'status':503}, {'status':401}, {'status':400},
                         {'status':429,'provider_task_id':'accepted-id'}, {'status':429,'accepted':True}]:
            with self.subTest(response=response):
                r,c,calls=self.router(dict(ok=False,**response));r.chat(c,[])
                self.assertEqual(calls,['a'])

    def test_confirmed_rejection_503_can_switch_but_unknown_cannot(self):
        r,c,calls=self.router({'ok':False,'status':503,'accepted':False})
        self.assertTrue(r.chat(c,[])['ok']);self.assertEqual(calls,['a','b'])

    def test_fallback_rechecks_budget(self):
        class Budget:
            def __init__(self): self.n=0
            def check(self,*args):
                self.n+=1
                return (self.n<3,'limit')
        r,c,calls=self.router({'ok':False,'status':429},Budget())
        out=r.chat(c,[])
        self.assertEqual(calls,['a']);self.assertEqual(out['route_stop'],'budget')

    def test_cancelled_context_stops_before_submission(self):
        r,c,calls=self.router({'ok':False,'status':429})
        control=platform_tools.ExecutionControl();control.cancel()
        with platform_tools.execution_scope(control):
            with self.assertRaises(platform_tools.ExecutionStopped): r.chat(c,[])
        self.assertEqual(calls,[])

    def test_stream_lost_response_does_not_repeat_paid_request(self):
        adapter=m.ModelAdapter(key='test')
        with patch.object(m.model_pool,'http_stream',side_effect=TimeoutError), patch.object(adapter,'chat') as chat:
            out=adapter.stream([],model='a',on_chunk=lambda text:None)
        chat.assert_not_called();self.assertFalse(out['ok'])
        self.assertEqual(out['failure']['acceptance'],'unknown')

    def test_explicit_model_is_not_silently_replaced(self):
        r,c,calls=self.router({'ok':False,'status':429})
        skill=SimpleNamespace(tools=[],fallbackModels=['b'],capabilities=[])
        c=r.select(skill,{'model':'a'})
        self.assertFalse(r.chat(c,[])['ok']);self.assertEqual(calls,['a'])

    def test_adapter_deadline_is_bounded_and_remote_id_prevents_retry(self):
        seen=[]
        def transport(url,payload,headers,timeout):
            seen.append(timeout)
            return {'ok':False,'status':503,'accepted':False,'task_id':'remote-1'}
        adapter=m.ModelAdapter(key='test',transport=transport,timeout=60)
        adapter.base_url='https://example.invalid'
        with platform_tools.execution_scope(platform_tools.ExecutionControl(timeout=1)):
            out=adapter.chat([],model='a')
        self.assertLessEqual(seen[0],1)
        self.assertFalse(m.failure_policy(out)['retryable'])
        self.assertEqual(m.failure_policy(out)['provider_task_id'],'remote-1')
