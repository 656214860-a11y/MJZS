# -*- coding: utf-8 -*-
"""宠物父编排 Agent 自检：规则优先路由（不花 Token）、异常分级与退避、参数归一、五类配额硬限制、
通知聚合与免打扰、审批三档、幂等提交。运行：python test_pet_agent.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import pet_agent, pet_bus, infra.pet_llm as pet_llm, infra.pet_state as pet_state
import ui.pet_ui_stages as pet_ui_stages
import ui.desktop_pet_bridge as desktop_pet_bridge

# 第 45 期：这些用例读的（并会写的）是全局配置目录里那一份三虎设置。原来 program 指向本机真
# 安装目录，于是「出厂默认档是半自动」这类断言会被用户机上那份配置左右（那里存过 hint 就红）。
# 指到沙盒目录：读不到真配置，也写不脏真安装目录（见 selftest_sandbox 的说明）。
import selftest_sandbox
selftest_sandbox.isolate(pet_llm)
from test_pet_context_facts import FactsSnapshotTests

DAY = 1750000000 - (1750000000 % 86400)


def at_hour(hour):
    """构造「北京时间正好 hour 点」的时间戳（免打扰与错峰都按北京时间算）。"""
    return DAY - 8 * 3600 + hour * 3600


class SpyClient:
    """假客户端：记录被问了几次，返回固定回复，绝不联网。"""

    def __init__(self, content="", ok=True, error="", data=None):
        self.content = content
        self.ok = ok
        self.error = error
        self.data = data
        self.calls = []

    def ask(self, task, text, context=None, urgent=False, **kwargs):
        self.calls.append({"task": task, "text": text, "context": context})
        if not self.ok:
            return {"ok": False, "error": self.error, "data": None}
        data = self.data if self.data is not None else {"choices": [{"message": {"content": self.content}}]}
        return {"ok": True, "error": None, "model": "deepseek-v4-flash", "data": data}


class PersonaTests(unittest.TestCase):
    """第 15 期：宠物叫三虎。名字在这一份里定义，pet_llm 的前缀与云朵框的签名都取自它。"""

    def test_the_pet_has_a_name_and_a_persona(self):
        self.assertEqual(pet_agent.PET_NAME, '三虎')
        self.assertEqual(pet_agent.PET_PERSONA, '一只可爱的小猫，说话简洁，帮用户把漫剧做完')

    def test_the_name_matches_the_one_in_the_fixed_prefix(self):
        self.assertIn(pet_agent.PET_NAME, pet_llm.SYSTEM_PREFIX)


class RouteTests(unittest.TestCase):
    def test_rule_hit_does_not_spend_token(self):
        spy = SpyClient(content="{\"intent\": \"pause\"}")
        plan = pet_agent.route("继续", client=spy)
        self.assertEqual(plan["intent"], "resume")
        self.assertEqual(plan["source"], "rule")
        self.assertEqual(spy.calls, [])

    def test_progress_question_stays_in_rules(self):
        plan = pet_agent.route("现在到哪一步了？还要多久")
        self.assertEqual(plan["intent"], "progress")
        self.assertIsNone(plan["stage"])

    def test_generate_firstframe_goes_down_the_free_local_path(self):
        """第 23 期：宠物这条路上首帧只走本机 ComfyUI（免费），付费的 Seedream 通道只在页面里。

        所以它是免费动作：半自动档下说一句「批量生成全部首帧」就该真的跑起来，不用再点一次确认
        ——「一键执行」本来就是这么做的。
        """
        plan = pet_agent.route("批量生成全部首帧")
        self.assertEqual((plan["intent"], plan["stage"]), ("generate", "keyframe"))
        self.assertEqual(pet_agent.action_for(plan), "keyframe.local")
        self.assertIn(pet_agent.action_for(plan), pet_agent.FREE_ACTIONS)

    def test_generate_storyboard_is_also_a_free_action(self):
        """第 62 期任务 2：三虎也能自己把分镜做起来——「生成分镜」派单，不用再点一次确认。

        派的是本机 Agent（不产生第三方生成费用），所以与 keyframe.local 一样算免费动作；
        光说「分镜表」还是切页，别把切页那一路抢过来。
        """
        plan = pet_agent.route("生成分镜")
        self.assertEqual((plan["intent"], plan["stage"]), ("generate", "storyboard"))
        self.assertEqual(pet_agent.action_for(plan), "storyboard.local")
        # 免费动作表里就有它：审批那一层不会把它当成「付费步骤」拦下来（见 approve）。
        self.assertIn("storyboard.local", pet_agent.FREE_ACTIONS)
        self.assertNotIn("storyboard.local", pet_agent.PAID_ACTIONS)
        self.assertEqual(pet_agent.route("分镜表")["intent"], "goto")

    def test_export_maps_to_delivery(self):
        plan = pet_agent.route("导出交付")
        self.assertEqual((plan["intent"], plan["stage"]), ("export", "delivery"))

    def test_page_words_map_to_pages(self):
        for text, stage in (("打开资产", "assets"), ("看剧本", "script"), ("分镜表", "storyboard"),
                            ("白模预演", "previs"), ("配音字幕", "audio")):
            with self.subTest(text=text):
                self.assertEqual(pet_agent.route(text)["stage"], stage)

    def test_a_stage_hint_overrides_the_context_stage_for_routing(self):
        """SANHU-FIX-2 S-03：页面问句带着它的阶段——给了 stage 就盖过 context['stage']；
        手打的句子不给 stage，照旧按状态机当前阶段。"""
        plan = pet_agent.route('执行选中', context={'stage': 'assets'}, stage='video')
        self.assertEqual((plan['intent'], plan['stage']), ('skill', 'video'))
        plan = pet_agent.route('执行选中', context={'stage': 'assets'})
        self.assertEqual(plan['stage'], 'assets', '手打句子不带 stage：照旧按状态机当前阶段')

    def test_dispatch_carries_the_stage_hint_down_to_route(self):
        """S-03：云朵框递下来的阶段一路进 route——dispatch 的 stage 参数同样盖过状态机。"""
        agent = pet_agent.Agent(level='semi', persist=False)
        plan = agent.dispatch('执行选中', stage='video')['plan']
        self.assertEqual(plan['stage'], 'video')

    def test_project_questions_stay_in_rules(self):
        """第 37 期第 1 条：三虎要「记住所有项目」——问「有哪些项目」命中规则，不花 Token。"""
        spy = SpyClient(content='{"intent": "未知"}')
        plan = pet_agent.route("有哪些项目", client=spy)
        self.assertEqual((plan["intent"], plan["source"]), ("projects", "rule"))
        self.assertEqual(spy.calls, [])
        for text in ("别的项目", "所有项目", "项目都怎么样", "项目列表"):
            with self.subTest(text=text):
                self.assertEqual(pet_agent.route(text)["intent"], "projects")
        # 「项目做到哪了」问的是进度：进度那条规则排在前面，照旧归它（第 37 期第 1 条）。
        self.assertEqual(pet_agent.route("项目做到哪了")["intent"], "progress")

    def test_hotspot_performance_check_stays_in_rules(self):
        """R3002：热点路径优化检查与另两条性能检查同列规则表，命中不花 Token。"""
        spy = SpyClient(content='{"intent": "未知"}')
        plan = pet_agent.route("运行热点路径优化检查", client=spy)
        self.assertEqual((plan["intent"], plan["source"]), ("performance_hotspot", "rule"))
        self.assertEqual(spy.calls, [])
        self.assertEqual(pet_agent.action_for(plan), "stage.inspect")

    def test_reading_the_projects_is_a_free_action(self):
        """看一眼的事：报项目清单与查进度同一类，哪一档都立刻放行。"""
        action = pet_agent.action_for({"intent": "projects"})
        self.assertIn(action, pet_agent.FREE_ACTIONS)

    def test_the_context_command_says_what_it_really_does(self):
        """`/clear`、`/compact` 不是空口承诺：如实说明每次调用都是固定前缀＋快照，没有历史可清。"""
        for text in ("/clear", "/compact"):
            with self.subTest(text=text):
                plan = pet_agent.route(text)
                self.assertEqual((plan["intent"], plan["source"]), ("context", "rule"))
                self.assertIn("没有历史", plan["reply"])
                self.assertIn("快照", plan["reply"])

    def test_miss_asks_the_model_once(self):
        spy = SpyClient(content='{"intent": "generate", "stage": "video", "params": {"shot": "SH007"}, "reply": "好"}')
        plan = pet_agent.route("把第七个镜头重出一下视频", client=spy)
        self.assertEqual(plan["source"], "llm")
        self.assertEqual(plan["stage"], "video")
        self.assertEqual(plan["params"], {"shot": "SH007"})
        self.assertEqual(spy.calls[0]["task"], "intent.route")
        self.assertEqual(len(spy.calls), 1)

    def test_reply_with_fence_and_noise_is_parsed(self):
        body = '```json\n{"intent": "pause", "stage": "", "params": {}, "reply": "好"}\n```\n以上。'
        spy = SpyClient(content=body)
        plan = pet_agent.route("嗯…先不要动了吧", client=spy)
        self.assertEqual(plan["intent"], "pause")
        self.assertIsNone(plan["stage"])
        self.assertEqual(plan["reply"], "好")

    def test_illegal_stage_is_dropped(self):
        self.assertIsNone(pet_agent.parse_intent('{"intent": "goto", "stage": "配音"}')["stage"])
        spy = SpyClient(content='{"intent": "goto", "stage": "配音", "params": {}}')
        plan = pet_agent.route("嗯…还是你来定吧", client=spy)
        self.assertEqual(plan["source"], "llm")
        self.assertIsNone(plan["stage"])

    def test_unparsable_reply_becomes_unknown(self):
        spy = SpyClient(content="我不知道你在说什么")
        plan = pet_agent.route("随便说点什么吧", client=spy)
        self.assertEqual((plan["intent"], plan["source"]), ("unknown", "llm-unparsed"))

    def test_model_failure_falls_back_with_reason(self):
        spy = SpyClient(ok=False, error="连接超时")
        plan = pet_agent.route("随便说点什么吧", client=spy)
        self.assertEqual(plan["source"], "llm-error")
        self.assertIn("连接超时", plan["reply"])

    def test_responses_wire_reply_is_understood(self):
        data = {"output": [{"content": [{"type": "output_text", "text": '{"intent": "retry"}'}]}]}
        plan = pet_agent.route("随便说点什么吧", client=SpyClient(data=data))
        self.assertEqual(plan["intent"], "retry")

    def test_without_client_the_reply_is_honest(self):
        plan = pet_agent.route("帮我搞个大事")
        self.assertEqual(plan["source"], "none")
        self.assertIn("没听明白", plan["reply"])


class ClassifyTests(unittest.TestCase):
    def test_categories(self):
        cases = (("请求超时，请重试", 408, "timeout"), ("rate limit exceeded", 429, "rate_limit"),
                 ("HTTP 503：服务不可用", None, "server"), ("内容审核未通过", 400, "content"),
                 ("参数不合法：size", 400, "params"), ("余额不足，请充值", 402, "quota"),
                 ("Unauthorized", 401, "auth"), ("莫名其妙的问题", None, "unknown"))
        for error, status, category in cases:
            with self.subTest(error=error):
                self.assertEqual(pet_agent.classify(error, status)["category"], category)

    def test_a_number_inside_a_longer_number_is_not_a_status_code(self):
        """第 71 期任务 1：ComfyUI 退出码 4294967295 里的 429 曾经把它当成「被限流」，
        于是真正的原因被误判而不报；纯数字标记只认「独立的一串数字」。"""
        self.assertEqual(pet_agent.classify("自动制作中断：ComfyUI 进程已退出（退出代码 4294967295）")["category"],
                         "unknown")
        self.assertEqual(pet_agent.classify("被限流", status=429)["category"], "rate_limit")

    def test_only_three_categories_may_retry(self):
        """轮 5B：可重试唯一权威是 error_codes 码表——rate_limit/server/timeout 三码
        retryable=True；params 由旧 VERDICTS 的 True 收敛为 False（对照表唯一行为变化）。"""
        from contract import error_codes
        retryable = {code for _category, code, _marks in error_codes.TEXT_RULES
                     if error_codes.lookup(code).retryable}
        self.assertEqual(retryable, {"E-NET-RATE-LIMIT", "E-NET-SERVER", "E-NET-TIMEOUT"})
        self.assertFalse(pet_agent.classify("参数不合法", 400)["retry"])
        self.assertFalse(pet_agent.classify("命中内容审核")["retry"])

    def test_backoff_sequence_and_ceiling(self):
        delays = [pet_agent.retry_plan(attempt, "请求超时")["delay"] for attempt in range(4)]
        self.assertEqual(delays, [30.0, 60.0, 120.0, 120.0])

    def test_retry_stops_at_the_limit(self):
        self.assertTrue(pet_agent.retry_plan(3, "请求超时")["allow"])
        plan = pet_agent.retry_plan(4, "请求超时")
        self.assertFalse(plan["allow"])
        self.assertIn("交给您确认", plan["hint"])
        self.assertEqual(plan["next_attempt"], 4)

    def test_content_error_never_retries(self):
        plan = pet_agent.retry_plan(0, "命中内容审核")
        self.assertFalse(plan["allow"])
        self.assertEqual(plan["action"], "prompt_fix")

    def test_quota_error_pauses(self):
        self.assertEqual(pet_agent.retry_plan(0, "余额不足", status=402)["action"], "pause")

    def test_params_error_no_longer_retries_automatically(self):
        """轮 5B 对照表唯一行为变化：params → E-NET-CLIENT（retryable=False），
        不再归一后立即重试，转入待确认清单由用户处理；动作名仍是 fix_params。"""
        plan = pet_agent.retry_plan(0, "参数不合法", status=400, params={"width": 3000, "height": 900})
        self.assertFalse(plan["allow"])
        self.assertIsNone(plan["delay"])
        self.assertEqual(plan["action"], "fix_params")
        self.assertEqual(plan["next_attempt"], 0)


class FixParamsTests(unittest.TestCase):
    def test_size_is_snapped_to_a_legal_gear(self):
        result = pet_agent.fix_params({"size": "1024x4096"})
        self.assertEqual((result["params"]["width"], result["params"]["height"]), (720, 1280))
        self.assertEqual(result["fixed"], ["尺寸"])
        self.assertNotIn("size", result["params"])

    def test_legal_size_is_left_alone(self):
        result = pet_agent.fix_params({"size": "1024x1024"})
        self.assertEqual(result["fixed"], [])
        self.assertEqual(result["params"]["size"], "1024x1024")

    def test_duration_is_clamped(self):
        self.assertEqual(pet_agent.fix_params({"duration": 30})["params"]["duration"], 10)
        self.assertEqual(pet_agent.fix_params({"seconds": 0})["params"]["seconds"], 1)
        self.assertEqual(pet_agent.fix_params({"duration": 30})["fixed"], ["时长"])

    def test_model_name_is_canonical(self):
        self.assertEqual(pet_agent.fix_params({"model": "DeepSeek"})["params"]["model"], "deepseek-v4-flash")
        self.assertEqual(pet_agent.fix_params({"model": "kling"})["fixed"], [])
        self.assertEqual(pet_agent.fix_params({"model": ""})["fixed"], ["模型名"])

    def test_empty_params_report_nothing(self):
        self.assertEqual(pet_agent.fix_params({}), {"params": {}, "fixed": []})
        self.assertEqual(pet_agent.fix_params(None), {"params": {}, "fixed": []})

    def test_input_is_not_mutated(self):
        params = {"width": 3000, "height": 900, "duration": 99}
        pet_agent.fix_params(params)
        self.assertEqual(params, {"width": 3000, "height": 900, "duration": 99})


class BudgetTests(unittest.TestCase):
    def test_hard_limit_refuses_and_does_not_charge(self):
        budget = pet_agent.Budget({"image": 2})
        self.assertTrue(budget.spend("image")["ok"])
        self.assertTrue(budget.spend("image")["ok"])
        verdict = budget.spend("image")
        self.assertFalse(verdict["ok"])
        self.assertTrue(verdict["exceeded"])
        self.assertEqual(verdict["used"], 2)
        self.assertEqual(budget.used["image"], 2)

    def test_warning_at_ninety_percent(self):
        budget = pet_agent.Budget({"video": 10})
        self.assertFalse(budget.spend("video", 8)["warning"])
        self.assertTrue(budget.spend("video")["warning"])
        self.assertTrue(budget.spend("video")["ok"])

    def test_aliases_and_defaults(self):
        budget = pet_agent.Budget()
        self.assertEqual(budget.limits["tokens"], 2000000)
        self.assertTrue(budget.check("token")["ok"])
        self.assertEqual(budget.check("keyframe")["kind"], "firstframe")

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            pet_agent.Budget().check("首帧")
        self.assertEqual(pet_agent.Budget({"乱七八糟": 5}).limits, pet_agent.DEFAULT_BUDGET)

    def test_tokens_are_synced_from_the_ledger(self):
        ledger = pet_llm.Ledger(None, clock=lambda: at_hour(12))
        ledger.record("deepseek-v4-flash", {"prompt_tokens": 10, "completion_tokens": 5, "cached_tokens": 0},
                      at=at_hour(12))
        budget = pet_agent.Budget()
        budget.sync_tokens(ledger, at=at_hour(13))
        self.assertEqual(budget.used["tokens"], 15)


class SummarizeTests(unittest.TestCase):
    def test_batch_becomes_one_sentence(self):
        items = [{"stage": "keyframe", "outcome": "success"},
                 {"stage": "keyframe", "outcome": "retry_success", "count": 3},
                 {"stage": "keyframe", "outcome": "need_confirm"}]
        self.assertEqual(pet_agent.summarize(items), "首帧完成，3 张重试成功，1 张需确认")

    def test_two_stages_are_separated(self):
        items = [{"stage": "keyframe", "outcome": "success"}, {"stage": "video", "outcome": "need_confirm"}]
        self.assertEqual(pet_agent.summarize(items), "首帧完成；视频需确认")

    def test_ready_text_is_kept_as_is(self):
        self.assertEqual(pet_agent.summarize([{"text": "Token 配额已用 9/10"}]), "Token 配额已用 9/10")

    def test_empty_is_empty(self):
        self.assertEqual(pet_agent.summarize([]), "")
        self.assertEqual(pet_agent.summarize(None), "")


class NotifierTests(unittest.TestCase):
    def test_flush_outside_the_window_speaks(self):
        notifier = pet_agent.Notifier(None, clock=lambda: at_hour(12), persist=False)
        notifier.add(stage="keyframe")
        self.assertEqual(notifier.flush(at=at_hour(12)), "首帧完成")
        self.assertEqual(len(notifier.sent), 1)

    def test_quiet_window_records_only(self):
        notifier = pet_agent.Notifier(None, clock=lambda: at_hour(23), persist=False)
        notifier.add(stage="keyframe", at=at_hour(23))
        self.assertIsNone(notifier.flush(at=at_hour(23)))
        self.assertIsNone(notifier.flush(at=at_hour(3)))
        self.assertEqual(len(notifier.recorded), 1)
        self.assertEqual(notifier.pending, [])

    def test_catch_up_speaks_after_the_window(self):
        notifier = pet_agent.Notifier(None, clock=lambda: at_hour(23), persist=False)
        notifier.add(stage="keyframe", at=at_hour(23))
        notifier.flush(at=at_hour(23))
        self.assertIsNone(notifier.catch_up(at=at_hour(2)))
        text = notifier.catch_up(at=at_hour(9))
        self.assertEqual(text, "免打扰期间 1 条更新：首帧完成")
        self.assertIsNone(notifier.catch_up(at=at_hour(9)))

    def test_round_trip_through_the_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            notifier = pet_agent.Notifier(project, clock=lambda: at_hour(23), persist=True)
            notifier.add(stage="video", outcome="need_confirm", at=at_hour(23))
            path = notifier.save()
            self.assertTrue(path.is_file())
            again = pet_agent.Notifier(project).load()
            self.assertEqual(again.pending, notifier.pending)
            self.assertEqual(again.window, (23, 7))

    def test_missing_file_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(pet_agent.Notifier(Path(tmp)).load().window, (23, 7))


class ApprovalTests(unittest.TestCase):
    def test_hint_level_only_reports(self):
        agent = pet_agent.Agent(settings={"level": "hint"}, persist=False)
        decision = agent.approve("stage.run")
        self.assertFalse(decision["run"])
        self.assertIn("只提醒", decision["reason"])

    def test_semi_final_asks_before_paid_steps(self):
        # 第 44 期：出厂默认档就是半自动（附件关键决策第 5 条），这一条点名的仍是它。
        agent = pet_agent.Agent(level="semi", persist=False)
        paid = agent.approve("firstframe.generate")
        self.assertFalse(paid["run"])
        self.assertTrue(paid["confirm"])
        self.assertTrue(agent.approve("stage.run")["run"])

    def test_auto_runs_paid_steps(self):
        """REL-09-SYNC（有意契约变更）：全自动档付费步骤同样先要用户点头——
        approve 给「需确认」，授权后才放行；授权前绝不执行。"""
        agent = pet_agent.Agent(level="auto", persist=False)
        decision = agent.approve("video.generate")
        self.assertFalse(decision["run"], "全自动档付费步骤授权前绝不放行")
        self.assertTrue(decision["confirm"], "全自动档付费步骤一样要确认")
        self.assertIn("全自动", decision["reason"])
        self.assertTrue(agent.approve("video.generate", confirmed=True)["run"],
                        "confirmed=True 是用户本人按下的确认，照常放行")

    def test_unknown_level_falls_back_to_the_default(self):
        agent = pet_agent.Agent(level="乱写", persist=False)
        self.assertEqual(agent.level, pet_agent.DEFAULT_LEVEL)
        self.assertEqual(pet_agent.DEFAULT_LEVEL, "hint", "第 64 期任务 7：开机默认是「只提醒」")

    def test_the_default_level_ships_as_hint(self):
        """第 64 期任务 7：用户定的默认档＝只提醒——开机只看着、只提示，不自动往下跑。"""
        agent = pet_agent.Agent(persist=False)
        self.assertEqual(agent.level, "hint")
        free = agent.approve("stage.run")
        self.assertFalse(free["run"], "只提醒档：连免费步骤也不代跑，只提示")
        self.assertFalse(free["confirm"], "只提醒档不弹确认框，用户自己按按钮")
        paid = agent.approve("firstframe.generate")
        self.assertFalse(paid["run"], "会花钱的更不会代跑")
        self.assertFalse(paid["confirm"])

    def test_a_confirm_from_the_user_runs_anyway(self):
        """第 31 期第 6 条：用户自己在对话框里按的「确认」＝他本人的决定。

        只提醒档的说明写的就是「做不做都由你来按」，那一下按下去就不该再被等级挡住，
        也不该为付费步骤再问第二遍——不然那颗按钮就是个哑键（用户报的「点了没反应」）。
        """
        agent = pet_agent.Agent(level="hint", persist=False)
        self.assertFalse(agent.approve("skill.run")["run"], "没按确认：只提醒档照旧挡住")
        confirmed = agent.approve("skill.run", confirmed=True)
        self.assertTrue(confirmed["run"])
        self.assertFalse(confirmed["confirm"], "确认过了，不再问第二遍")
        paid = agent.approve("firstframe.generate", confirmed=True)
        self.assertTrue(paid["run"])

    def test_a_confirm_still_waits_behind_the_pause(self):
        """暂停是用户自己按下的闸：确认按钮不能绕过去。"""
        agent = pet_agent.Agent(level="hint", persist=False)
        agent.pause("配额用完")
        self.assertFalse(agent.approve("skill.run", confirmed=True)["run"])

    def test_dispatch_carries_the_confirmation_into_the_approval(self):
        agent = pet_agent.Agent(level="hint", persist=False)
        blocked = agent.dispatch("执行选中")
        allowed = agent.dispatch("执行选中", confirmed=True)
        self.assertEqual(blocked["action"], allowed["action"], "同一句话路由到同一个动作")
        self.assertFalse(blocked["decision"]["run"], "没确认时被只提醒档挡下")
        self.assertTrue(allowed["decision"]["run"], "确认之后同一句话放行")

    def test_pause_blocks_actions_but_keeps_the_view(self):
        agent = pet_agent.Agent(level="semi", persist=False)
        agent.pause("配额用完")
        self.assertFalse(agent.approve("stage.run")["run"])
        self.assertIn("配额用完", agent.approve("stage.run")["reason"])
        self.assertTrue(agent.approve("progress")["run"])
        agent.resume()
        self.assertTrue(agent.approve("stage.run")["run"])


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.bus = pet_bus.Bus()
        self.machine = pet_state.Machine(self.project, persist=False)
        # 第 22 期起这一组用例统一显式点名「半自动」（那一轮默认档是「只提醒」）；第 44 期起
        # 半自动就是出厂默认，显式点名照旧——这些用例验的是「免费步骤自动跑、付费步骤先问一句」，
        # 与开机默认哪一档是两件事。
        self.agent = pet_agent.Agent(project=self.project, bus=self.bus, machine=self.machine,
                                     level="semi", persist=False)

    def tearDown(self):
        self.tmp.cleanup()

    def kinds(self):
        self.bus.pump()
        return [item["kind"] for item in self.bus.history]

    def test_failure_turns_into_a_backoff_retry_event(self):
        plan = self.agent.fail("keyframe", "HTTP 503：服务不可用", status=503, attempt=0)
        self.assertTrue(plan["allow"])
        self.assertIn("stage.retrying", self.kinds())
        item = [event for event in self.bus.history if event["kind"] == "stage.retrying"][0]
        self.assertEqual((item["attempt"], item["delay"]), (1, 30.0))

    def test_exhausted_retries_go_to_the_failure_list(self):
        plan = self.agent.fail("keyframe", "请求超时", attempt=4)
        self.assertFalse(plan["allow"])
        self.assertIn("stage.failed", self.kinds())
        self.assertEqual(len(self.agent.failures), 1)
        self.assertEqual(self.agent.failures[0]["category"], "timeout")
        self.assertEqual(self.agent.notifier.pending[-1]["outcome"], "need_confirm")

    def test_skip_takes_the_oldest_pending_item(self):
        """「跳过这张」：摘掉最早那条，后面那条仍然留在清单里。"""
        self.agent.fail("keyframe", "请求超时", attempt=4)
        self.agent.fail("video", "被限流", attempt=4)
        entry = self.agent.skip_failure()
        self.assertEqual(entry["stage"], "keyframe")
        self.assertEqual([item["stage"] for item in self.agent.failures], ["video"])

    def test_skip_an_unknown_item_falls_back_to_the_oldest(self):
        self.agent.fail("keyframe", "请求超时", attempt=4)
        entry = self.agent.skip_failure({"stage": "编出来的"})
        self.assertEqual(entry["stage"], "keyframe")
        self.assertEqual(self.agent.failures, [])

    def test_skipping_with_nothing_pending_changes_nothing(self):
        self.assertIsNone(self.agent.skip_failure())
        self.assertEqual(self.agent.failures, [])

    def test_skip_lands_in_the_journal(self):
        self.agent.fail("keyframe", "请求超时", attempt=4)
        self.agent.skip_failure()
        lines = pet_agent.journal_path(self.project).read_text(encoding="utf-8").strip().splitlines()
        skipped = [json.loads(line) for line in lines if json.loads(line)["kind"] == "skip"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual((skipped[0]["stage"], skipped[0]["category"]), ("keyframe", "timeout"))

    def test_bad_stage_does_not_raise(self):
        self.agent.fail("sh020", "请求超时")
        self.assertTrue(self.agent.errors)
        self.assertIn("未登记的制作阶段", self.agent.errors[0][1])

    def test_notifications_are_aggregated_into_one_event(self):
        self.agent.notify({"kind": "stage.completed", "stage": "keyframe"})
        self.agent.note("keyframe", "retry_success", 3)
        self.agent.note("keyframe", "need_confirm")
        text = self.agent.flush(at=at_hour(12))
        self.assertEqual(text, "首帧完成，3 张重试成功，1 张需确认")
        self.assertIn("notify.aggregate", self.kinds())
        self.assertEqual(self.agent.flush(at=at_hour(12)), None)

    def test_night_notifications_are_held_until_morning(self):
        self.agent.notify({"kind": "firstframe.task.failed", "shot": "SH001"}, at=at_hour(23))
        self.assertIsNone(self.agent.flush(at=at_hour(23)))
        self.assertEqual(self.agent.catch_up(at=at_hour(9)), "免打扰期间 1 条更新：首帧需确认")

    def test_unknown_event_is_ignored(self):
        self.assertIsNone(self.agent.notify({"kind": "随便什么"}))
        self.assertEqual(self.agent.notifier.pending, [])

    def test_budget_exceeded_pauses_and_reports(self):
        agent = pet_agent.Agent(project=self.project, settings={"budget_limits": {"image": 2}},
                                bus=self.bus, machine=self.machine, persist=False)
        agent.spend("image")
        agent.spend("image")
        verdict = agent.spend("image", stage="assets")
        self.assertFalse(verdict["ok"])
        self.assertTrue(agent.paused)
        kinds = self.kinds()
        self.assertIn("budget.warning", kinds)
        self.assertIn("budget.exceeded", kinds)
        self.assertIn("已暂停自动执行", agent.notifier.pending[-1]["text"])
        self.assertFalse(agent.approve("image.generate")["run"])

    def test_duplicate_submission_is_skipped(self):
        first = self.agent.submit("keyframe", "SH001", "seedream-5.0", "猫坐在窗边")
        self.assertTrue(first["accepted"])
        again = self.agent.submit("keyframe", "SH001", "seedream-5.0", "  猫坐在窗边  ")
        self.assertFalse(again["accepted"])
        self.assertIn("重复提交", again["reason"])
        self.assertTrue(self.agent.submit("keyframe", "SH001", "seedream-5.0", "猫趴在屋顶")["accepted"])
        lines = pet_agent.journal_path(self.project).read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["stage"], "keyframe")

    def test_progress_comes_from_the_state_machine(self):
        self.machine.start("script")
        self.machine.detail("script", 3, 6)
        state = self.agent.progress()
        # 进度必须随 pet_bus.STAGES 的唯一阶段清单变化；新增阶段后不能遗留旧分母。
        self.assertEqual(state["percent"], round(100.0 * 0.5 / len(pet_bus.STAGES), 1))
        self.assertIn("剧本准备", state["summary"])
        self.assertEqual(state["hit_rate"], 0.0)
        self.assertEqual(state["tokens_today"], 0)
        self.assertEqual(state["level"], "semi")     # 这一只显式点名了半自动

    def test_advance_respects_level_and_pause(self):
        self.assertEqual(self.agent.advance(), "script")
        self.agent.pause("等着")
        self.assertIsNone(self.agent.advance())
        self.agent.resume()
        self.agent.set_level("hint")
        self.assertIsNone(self.agent.advance())

    def test_dispatch_asks_for_confirmation_on_paid_steps(self):
        result = self.agent.dispatch("批量生成全部视频")
        self.assertEqual((result["plan"]["intent"], result["plan"]["stage"]), ("generate", "video"))
        self.assertTrue(result["decision"]["confirm"], "会花钱的那几步在半自动档下要先点头")
        self.assertIn("确认", result["reply"])
        self.assertTrue(self.agent.dispatch("暂停")["decision"]["run"])

    def test_dispatch_uses_the_model_when_rules_miss(self):
        spy = SpyClient(content='{"intent": "goto", "stage": "edit", "params": {}, "reply": "切到剪辑页"}')
        agent = pet_agent.Agent(project=self.project, machine=self.machine, client=spy,
                                level="semi", persist=False)
        result = agent.dispatch("帮我看看时间轴")
        self.assertEqual(result["plan"]["stage"], "edit")
        self.assertEqual(result["reply"], "切到剪辑页")
        self.assertEqual(len(spy.calls), 1)

    def test_settings_are_read_from_the_config_file(self):
        path = pet_agent.config_file()
        self.assertEqual(path.name, "配置.json")
        settings = pet_agent.load_settings(config={"level": "全自动", "dnd": [22, 6], "budget_limits": {"video": 30}})
        self.assertEqual(settings["level"], pet_agent.DEFAULT_LEVEL, "认不出的档位退回默认")
        self.assertEqual(pet_agent.load_settings(config={"level": "auto"})["level"], "auto",
                         "认得出的档位原样放行")
        self.assertEqual(settings["dnd"], (22, 6))
        self.assertEqual(settings["budget_limits"], {"video": 30})


class ProjectContextTests(unittest.TestCase):
    """第 37 期第 1 条：项目清单进快照（模型也看得见手上有哪些项目）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.agent = pet_agent.Agent(project=self.project,
                                     machine=pet_state.Machine(self.project, persist=False),
                                     level="hint", persist=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_without_a_provider_the_snapshot_is_unchanged(self):
        self.assertNotIn("projects", self.agent.context(), "没有供给方就不多这一项")

    def test_the_provider_feeds_the_snapshot(self):
        self.agent.projects = lambda: ["甲|在制作|剧本准备|当前", "乙|已完成|交付"]
        context = self.agent.context()
        self.assertEqual(context["projects"], ["甲|在制作|剧本准备|当前", "乙|已完成|交付"])
        self.assertEqual(context["project"], self.project.name, "当前项目照旧在最前面说清")

    def test_a_broken_provider_never_raises(self):
        def boom():
            raise RuntimeError("登记表读不出来")

        self.agent.projects = boom
        self.assertNotIn("projects", self.agent.context())
        self.assertTrue(any(name == "projects" for name, _text in self.agent.errors))

    def test_the_snapshot_does_not_run_away(self):
        self.agent.projects = lambda: ["项目%d" % index for index in range(50)]
        self.assertEqual(len(self.agent.context()["projects"]), pet_agent.PROJECT_LIMIT)


class FactsContextTests(unittest.TestCase):
    """SANHU-CONTEXT-GAPS：项目事实只在 facts 回调给出非空字典时进快照。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.machine = pet_state.Machine(self.project, persist=False)

    def tearDown(self):
        self.tmp.cleanup()

    def make_agent(self, facts=None, **kwargs):
        kwargs.setdefault("project", self.project)
        kwargs.setdefault("machine", self.machine)
        kwargs.setdefault("level", "hint")
        kwargs.setdefault("persist", False)
        agent = pet_agent.Agent(**kwargs)
        agent.facts = facts
        return agent

    def test_without_facts_the_snapshot_keys_are_unchanged(self):
        context = self.make_agent().context()
        self.assertEqual(set(context), {"project", "stage", "percent", "level", "failed"})

    def test_facts_callback_adds_fixed_shape_snapshot(self):
        facts = {"counts": {"scripts": 1, "storyboards": 3, "adopted": 1, "shots": 40,
                            "frames": 25, "assets": 2, "ready_assets": 2},
                 "gaps": ["2 份分镜 JSON 还没采用（分镜 → 手动采用分镜）",
                          "首帧还差 15 个镜头（首帧 → 手动制作首帧）"],
                 "blocked": ""}
        context = self.make_agent(facts=lambda: facts).context()
        self.assertEqual(context["facts"], facts)
        self.assertEqual(set(context["facts"]), {"counts", "gaps", "blocked"})
        self.assertTrue(all(isinstance(value, int)
                            for value in context["facts"]["counts"].values()))
        self.assertEqual(len(context["facts"]["gaps"]), 2)
        self.assertIsInstance(context["facts"]["blocked"], str)

    def test_empty_or_non_dict_facts_do_not_add_key(self):
        for value in ({}, [], None, ""):
            with self.subTest(value=value):
                self.assertNotIn("facts", self.make_agent(facts=lambda value=value: value).context())

    def test_facts_exception_is_recorded_without_breaking_context(self):
        def boom():
            raise RuntimeError("facts boom")

        agent = self.make_agent(facts=boom)
        agent.projects = lambda: ["甲"]
        agent.pending_offer = "待确认"
        context = agent.context()
        self.assertNotIn("facts", context)
        self.assertEqual(context["projects"], ["甲"])
        self.assertEqual(context["pending_offer"], "待确认")
        self.assertTrue(any(name == "facts" for name, _text in agent.errors))


class IdempotencyTests(unittest.TestCase):
    def test_key_is_stable_and_case_sensitive(self):
        first = pet_agent.idempotency_key("keyframe", "SH001", "m", "猫坐在窗边")
        self.assertEqual(first, pet_agent.idempotency_key("keyframe", "SH001", "m", "猫坐在窗边"))
        self.assertNotEqual(first, pet_agent.idempotency_key("keyframe", "SH001", "m", "猫趴在屋顶"))
        self.assertNotEqual(first, pet_agent.idempotency_key("keyframe", "SH002", "m", "猫坐在窗边"))

    def test_whitespace_and_wrapping_do_not_change_the_key(self):
        self.assertEqual(pet_agent.idempotency_key("video", "SH001", "m", "猫 坐在\n窗边"),
                         pet_agent.idempotency_key("video", "SH001", "m", "猫 坐在 窗边"))


class SaveSettingsTests(unittest.TestCase):
    """设置页落盘：坏值这一把键本次不写（盘上旧值留着），未登记的键与 None 不碰。"""

    def test_bad_values_keep_the_saved_ones(self):
        with tempfile.TemporaryDirectory() as td:
            path = pet_agent.config_file(td)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"dnd": [22, 7], "retry_delays": [5], "max_attempts": 3,
                                        "pool": {"keep": True}}), encoding="utf-8")
            pet_agent.save_settings({"dnd": [1, 2, 3], "retry_delays": [], "max_attempts": 0,
                                     "budget_limits": {"image": 5, "飞船": 9, "video": -1},
                                     "pool": "被改", "anim": None}, program=td)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["dnd"], [22, 7])
            self.assertEqual(data["retry_delays"], [5])
            self.assertEqual(data["max_attempts"], 3)
            self.assertEqual(data["budget_limits"], {"image": 5})
            self.assertEqual(data["pool"], {"keep": True})
            self.assertNotIn("anim", data)
            pet_agent.save_settings({"retry_delays": ("10", 20), "max_attempts": "4"}, program=td)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["retry_delays"], [10, 20])
            self.assertEqual(data["max_attempts"], 4)


class StageAndLevelRuleTests(unittest.TestCase):
    """W6-SANHU-FIX-5：三虎聊天规则认得全部 13 个阶段与三个档位名（只提醒/半自动/全自动）。"""

    def test_every_stage_is_reachable_by_chat(self):
        cases = [("去剧本准备", "script"), ("打开剧本结构", "script_structure"), ("去初步分镜", "storyboard"),
                 ("去分镜预演", "animatic"), ("打开资产管理", "assets"), ("连贯性清单", "continuity"),
                 ("去分镜定稿", "final"), ("去首帧管理", "keyframe"), ("去白模预演", "previs"),
                 ("去视频生成页", "video"), ("去配音与字幕", "audio"), ("去后期剪辑", "edit")]
        for text, stage in cases:
            with self.subTest(text=text):
                plan = pet_agent.match_rule(text)
                self.assertEqual(plan["intent"], "goto")
                self.assertEqual(plan["stage"], stage)
        # 「去质检与交付」先撞上前面的「交付→导出」规则，只核阶段。
        self.assertEqual(pet_agent.match_rule("去质检与交付")["stage"], "delivery")

    def test_level_words_route_to_the_right_level(self):
        cases = [("切到只提醒", "hint"), ("切到半自动", "semi"), ("切到全自动", "auto"), ("切到只提示", "hint")]
        for text, level in cases:
            with self.subTest(text=text):
                plan = pet_agent.match_rule(text)
                self.assertEqual(plan["intent"], "level")
                self.assertEqual(plan["params"]["level"], level)

    def test_bare_level_word_asks_which_level(self):
        plan = pet_agent.match_rule("自动化等级")
        self.assertEqual(plan["intent"], "level")
        self.assertIsNone(plan["params"]["level"])
        for name in ("只提醒", "半自动", "全自动"):
            self.assertIn(name, plan["reply"])

    def test_animatic_goes_to_its_page_and_old_hits_hold(self):
        plan = pet_agent.match_rule("生成分镜预演")
        self.assertEqual((plan["intent"], plan["stage"]), ("goto", "animatic"))
        self.assertEqual((pet_agent.match_rule("生成分镜")["intent"], pet_agent.match_rule("生成分镜")["stage"]),
                         ("generate", "storyboard"))
        self.assertEqual((pet_agent.match_rule("生成视频")["intent"], pet_agent.match_rule("生成视频")["stage"]),
                         ("generate", "video"))
        self.assertEqual((pet_agent.match_rule("预演")["intent"], pet_agent.match_rule("预演")["stage"]),
                         ("goto", "previs"))
        self.assertEqual((pet_agent.match_rule("剧本")["intent"], pet_agent.match_rule("剧本")["stage"]),
                         ("goto", "script"))

    def test_goto_reply_names_each_of_the_thirteen_stages(self):
        for stage in pet_bus.STAGES:
            with self.subTest(stage=stage):
                reply = pet_agent.rule_reply("goto", stage)
                self.assertIn(pet_agent.SHORT_NAMES[stage], reply)
                self.assertNotEqual(reply, "切到对应页面。")


class _PaidFakeDesktop:
    """与 test_pet_ui 同款的桩桌面：会派发（pet_start），但没接授权桥。"""

    def __init__(self):
        self.root = None
        self.started = []

    def pet_start(self, stage):
        self.started.append(stage)
        return '已自动开始「资产管理」'


class _BridgeFakeDesktop(desktop_pet_bridge.PetBridgeMixin):
    """接了真授权桥的桩桌面：派发入口换成记账桩，授权走 PetBridgeMixin 真实现。"""

    def __init__(self):
        self.root = None
        self.started = []
        self.pet = None

    def pet_start(self, stage):
        self.started.append(stage)
        return '已自动开始「资产管理」'


class AutoPaidAuthorizationTests(unittest.TestCase):
    """REL-09-SYNC：全自动档付费步骤的「一次一授权」护栏（N769 Token 边界＋N796 四要素文案）。

    auto 档遇到付费阶段（assets／video／audio）必须经 ``desktop.authorize_paid_stage``
    独立授权：确认框写清步骤名＋当次数量／秒数＋估算 Token＋剩余额度，授权只对这一次
    步骤有效；拒绝／弹窗抛错／超时／配额或 Token 见底一律暂停转人工，绝不派发、绝不
    产生真实付费请求。
    """

    def setUp(self):
        self.bus = pet_bus.Bus()
        self.events = []
        self.bus.subscribe('*', self.events.append)

    def tearDown(self):
        self.bus.release()

    def event_kinds(self):
        self.bus.pump()
        return [item['kind'] for item in self.events]

    def make_agent(self, **kwargs):
        kwargs.setdefault('level', 'auto')
        kwargs.setdefault('persist', False)
        kwargs.setdefault('bus', self.bus)
        return pet_agent.Agent(**kwargs)

    def make_host(self, agent, asker=None, desktop=None):
        """start_stage 走到的最小真宿主：PetStagesMixin 真方法＋按需注入的接缝。"""
        host = pet_ui_stages.PetStagesMixin()
        host.desktop = desktop if desktop is not None else _PaidFakeDesktop()
        host.agent = agent
        host.errors = []
        host.asker = asker
        host.win = None
        host._auto_variables = {}
        host._emit = lambda kind, **payload: pet_bus.emit_safe(self.bus, host.errors, kind, **payload)
        host.advance_stage = lambda stage, at=None: '已提前叫醒'
        return host

    def test_authorized_paid_stage_spends_quota_and_dispatches(self):
        desktop = _PaidFakeDesktop()
        asked = []
        agent = self.make_agent()
        host = self.make_host(agent, asker=lambda title, text: asked.append((title, text)) or True,
                              desktop=desktop)
        reply = host.start_stage('assets')
        self.assertEqual(desktop.started, ['assets'], '授权通过才派发')
        self.assertIn('资产管理', reply)
        self.assertEqual(len(asked), 1, '先问一句再放行')
        self.assertEqual(agent.budget.used['image'], 1, '授权后记一格生产配额')
        self.assertTrue(host._auto_variables['auto_asset_var'].get(),
                        '授权后打开这一步自己的自动开关')
        self.assertFalse(agent.paused)

    def test_the_desktop_authorize_paid_stage_is_the_real_path(self):
        """真桌面接缝：desktop.authorize_paid_stage(stage, var) 是同一份授权实现。"""
        desktop = _BridgeFakeDesktop()
        agent = self.make_agent()
        host = self.make_host(agent, asker=lambda title, text: True, desktop=desktop)
        desktop.pet = host
        self.assertIs(desktop.authorize_paid_stage('assets', 'auto_asset_var'), True)
        self.assertEqual(agent.budget.used['image'], 1)
        self.assertTrue(host._auto_variables['auto_asset_var'].get())

    def test_start_stage_prefers_the_desktop_authorize_paid_stage(self):
        desktop = _BridgeFakeDesktop()
        asked = []
        agent = self.make_agent()
        host = self.make_host(agent, asker=lambda title, text: asked.append(text) or True,
                              desktop=desktop)
        desktop.pet = host
        reply = host.start_stage('assets')
        self.assertEqual(len(asked), 1)
        self.assertEqual(desktop.started, ['assets'])
        self.assertIn('资产管理', reply)

    def test_the_authorization_is_valid_for_one_step_only(self):
        desktop = _PaidFakeDesktop()
        asked = []
        agent = self.make_agent()
        host = self.make_host(agent, asker=lambda title, text: asked.append(text) or True,
                              desktop=desktop)
        host.start_stage('assets')
        host.start_stage('assets')
        self.assertEqual(len(asked), 2, '一次一授权：第二个付费步骤要再问一遍')
        self.assertEqual(desktop.started, ['assets', 'assets'])
        self.assertEqual(agent.budget.used['image'], 2)

    def test_refusal_pauses_the_chain_and_never_dispatches(self):
        desktop = _PaidFakeDesktop()
        agent = self.make_agent()
        host = self.make_host(agent, asker=lambda title, text: False, desktop=desktop)
        reply = host.start_stage('assets')
        self.assertEqual(desktop.started, [], '没授权绝不派发')
        self.assertEqual(agent.budget.used['image'], 0, '没授权就不记账、不产生付费请求')
        self.assertTrue(agent.paused)
        self.assertIn('stage.failed', self.event_kinds())
        self.assertIn('请您接手这一步', reply)

    def test_a_broken_dialog_counts_as_unauthorized(self):
        def boom(title, text):
            raise RuntimeError('弹窗组件坏了')

        desktop = _PaidFakeDesktop()
        agent = self.make_agent()
        host = self.make_host(agent, asker=boom, desktop=desktop)
        host.start_stage('assets')
        self.assertEqual(desktop.started, [])
        self.assertEqual(agent.budget.used['image'], 0)
        self.assertTrue(agent.paused)
        self.assertIn('stage.failed', self.event_kinds())

    def test_no_answer_within_the_wait_is_unauthorized(self):
        desktop = _PaidFakeDesktop()
        agent = self.make_agent()
        host = self.make_host(agent, asker=lambda title, text: None, desktop=desktop)
        host.start_stage('assets')
        self.assertEqual(desktop.started, [])
        self.assertEqual(agent.budget.used['image'], 0)
        self.assertTrue(agent.paused)
        self.assertIn('stage.failed', self.event_kinds())

    def test_quota_exhaustion_skips_the_dialog_and_pauses(self):
        agent = self.make_agent(settings={'budget_limits': {'image': 1}})
        agent.spend('image')                          # 把这一步的阶段配额先用完
        asked = []
        desktop = _PaidFakeDesktop()
        host = self.make_host(agent, asker=lambda title, text: asked.append(text) or True,
                              desktop=desktop)
        host.start_stage('assets')
        self.assertEqual(asked, [], '阶段配额见底不许弹窗——直接转人工')
        self.assertEqual(desktop.started, [])
        self.assertTrue(agent.paused)
        kinds = self.event_kinds()
        self.assertIn('budget.exceeded', kinds)
        self.assertIn('stage.failed', kinds)

    def test_token_edge_blocks_the_step_without_a_dialog(self):
        """N769：Token 见底＝剩余 ≤0 或小于本次估算消耗，都不许弹窗、绝不派发。"""
        limit = self.make_agent().budget.limits['tokens']
        for used in (limit, limit - 1):
            with self.subTest(used=used):
                self.setUp()
                try:
                    asked = []
                    agent = self.make_agent()
                    agent.budget.used['tokens'] = used
                    desktop = _PaidFakeDesktop()
                    host = self.make_host(agent, asker=lambda t, x: asked.append(x) or True,
                                          desktop=desktop)
                    host.start_stage('assets')
                    self.assertEqual(asked, [], 'Token 见底不许弹窗')
                    self.assertEqual(desktop.started, [])
                    self.assertEqual(agent.budget.used['image'], 0)
                    self.assertTrue(agent.paused)
                    self.assertIn('stage.failed', self.event_kinds())
                finally:
                    self.tearDown()

    def test_the_dialog_lists_all_four_facts_and_the_one_step_rule(self):
        """N796：确认框必须同屏写清步骤名＋当次数量／秒数＋估算 Token＋剩余额度＋仅本次。"""
        asked = []
        agent = self.make_agent()
        host = self.make_host(agent, asker=lambda title, text: asked.append(text) or True,
                              desktop=_PaidFakeDesktop())
        host.start_stage('assets')
        self.assertEqual(len(asked), 1)
        text = asked[0]
        self.assertIn('资产管理', text, '① 步骤名')
        self.assertIn('1 次', text, '② 当次数量／秒数（原单位）')
        self.assertIn('预计消耗 Token', text, '③ 估算 Token（正整数）')
        self.assertIn('Token（每天）', text, '④ Token 剩余额度')
        self.assertIn('生图', text, '④ 阶段配额剩余额度')
        self.assertIn('授权只对这一次步骤有效', text, '授权仅对这一次步骤有效的声明')


if __name__ == "__main__":
    unittest.main(verbosity=1)
