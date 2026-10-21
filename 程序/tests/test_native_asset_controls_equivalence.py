"""native_assets.attach_controls 改写成 _AssetControls：HEAD 旧实现原样内嵌，与新实现建同样的窗口，
对照初态控件树、逐个点按钮后的控件树与宿主回调记录。"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk

import native_assets as module
from skip_reasons import PLATFORM_TKINTER
from window_diff_support import FakeApp, drive, legacy

LEGACY = "def attach_controls(app, win, form, footer, project, base, selection, status, reload_rows, context_matches):\n    import tkinter as tk\n    from tkinter import ttk, messagebox\n    from ui_widgets import BusyState, Card, SelectBox, PrimaryButton, ProgressLabel, SecondaryButton, notify\n    from responsive_ui import FlowBar\n    progress_text=tk.StringVar()\n    events=queue.Queue()\n    prefsfile=project/'ui_settings.json'\n    prefs=read(prefsfile) if prefsfile.is_file() else {}\n    saved=prefs.get('asset_workflow',{})\n    model=tk.StringVar(value=saved.get('model',LOCAL));aspect=tk.StringVar(value=saved.get('aspect_ratio','1:1'))\n    config=Card(form);config.pack(fill='x',padx=14,pady=10)\n    config.columnconfigure(1,weight=1)\n    ttk.Label(config,text='生图模型').grid(row=0,column=0,columnspan=4,sticky='w')\n    ttk.Label(config,text='模型').grid(row=1,column=0,sticky='w',padx=(0,8))\n    selector=SelectBox(config,textvariable=model,values=MODELS);selector.grid(row=1,column=1,sticky='ew',padx=SPACING['xs'])\n    ttk.Label(config,text='画幅').grid(row=1,column=2,padx=(12,4))\n    shape=SelectBox(config,textvariable=aspect,values=['1:1','9:16','16:9']);shape.grid(row=1,column=3,padx=SPACING['xs'])\n    hint=tk.StringVar();account_text=tk.StringVar(value='云模型账号 / 密钥')\n    ProgressLabel(config,textvariable=hint,wraplength=730).grid(row=2,column=0,columnspan=4,sticky='w',pady=SPACING['sm'])\n    def update_hint():\n        account_text.set('火山 API 设置' if model.get()=='Seedream 5.0 Pro' else '云模型账号 / 密钥')\n        if model.get()=='Seedream 5.0 Pro':\n            from seedream_api import public_profile\n            try:detail='当前模型：'+public_profile()['model']\n            except ValueError:detail='请保存实际模型 ID 和 API Key。'\n            hint.set('使用自己的火山 API，费用计入火山账户。'+detail)\n        else:hint.set('本地运行，无需登录。提示词与参考图直接提交 ComfyUI。' if model.get()==LOCAL else '使用 Comfy 账户余额；请在“云模型账号 / 密钥”登录并配置 Comfy API Key。')\n    def selected(event=None):\n        update_hint()\n        prefs=read(prefsfile) if prefsfile.is_file() else {}\n        prefs['asset_workflow']={'model':model.get(),'aspect_ratio':aspect.get(),'quality':'medium','seed':42};save(prefsfile,prefs)\n    selector.bind('<<ComboboxSelected>>',selected);shape.bind('<<ComboboxSelected>>',selected)\n    def account():\n        if model.get()=='Seedream 5.0 Pro':\n            from seedream_settings import show\n            show(win,on_saved=update_hint)\n        else:\n            from cloud_assets import settings\n            settings(win)\n    SecondaryButton(config,textvariable=account_text,command=lambda:app.safe(account)).grid(row=3,column=0,columnspan=2,sticky='w')\n    update_hint()\n    check_stop=threading.Event()\n    gen_stop=threading.Event()\n    def cancel():\n        check_stop.set();gen_stop.set()\n    def check():\n        if app.worker:raise ValueError('请等待当前任务完成。')\n        if not app.launch_comfy():return\n        progress_text.set('正在检测本地 ComfyUI…（可取消）')\n        url=app.settings.get('comfy_url','http://127.0.0.1:8188')\n        check_stop.clear();busy.set_busy(True,progress_interval=15);cancel_button.configure(text='取消检测');cancel_button.state(['!disabled'])\n        def probe():\n            from comfy_service import Comfy\n            from urllib.error import HTTPError                  # 第 34 期第 9 条：HTTP 栈按需加载\n            try:\n                client=Comfy(url)\n            except Exception as exc:\n                return 'ComfyUI 地址不可用：'+str(exc)\n            deadline=time.monotonic()+75\n            while not check_stop.is_set():\n                try:\n                    client.request('/system_stats',timeout=5)\n                except Exception:\n                    if time.monotonic()>=deadline:\n                        return 'ComfyUI 未在 75 秒内就绪，请确认程序已打开、本机地址正确（'+url+'）。可点击“强制关闭 ComfyUI”后重新检测。'\n                    time.sleep(1)\n                    continue\n                try:\n                    client.request('/drama/assets/health',timeout=5)\n                    return 'ComfyUI 已连接，检测通过。正在自动开始制图…'\n                except HTTPError as exc:\n                    if exc.code==404:\n                        return 'ComfyUI 已启动，但缺少资产批量接收组件（/drama/assets/health 404）。请在 ComfyUI 安装/启用 drama 资产工作流组件后，点击“强制关闭 ComfyUI”重启再检测。'\n                except Exception:\n                    app_logging.swallowed()\n                if time.monotonic()>=deadline:\n                    return 'ComfyUI 已启动，但资产接收组件未就绪，请重启本地 ComfyUI 后再检测。'\n                time.sleep(1)\n            return '已取消检测'\n        def done(result):\n            busy.set_busy(False);cancel_button.state(['disabled']);cancel_button.configure(text='取消检测');progress_text.set(result)\n            if result.startswith('ComfyUI 已连接'):\n                app.safe(start)\n        app.async_(probe,done,show_progress=False)\n    progress=ttk.Progressbar(form,mode='indeterminate');progress.pack(fill='x',padx=14,pady=6)\n    ProgressLabel(form,textvariable=progress_text,wraplength=760,justify='left').pack(anchor='w',padx=14,pady=(0,4))\n    busy=BusyState(progress_text,progress)\n    def poll():\n        if not win.winfo_exists():return\n        try:\n            while True:progress_text.set(events.get_nowait())\n        except queue.Empty:pass\n    tk_timers.repeat(win,250,poll)\n    def start():\n        if app.worker:raise ValueError('当前任务正在处理，请等待完成。')\n        if not context_matches():raise ValueError('项目或分镜范围已切换，请重新打开制图窗口。')\n        reload_rows();items=selection()\n        if not items:raise ValueError('请至少勾选一项待生成资产。')\n        options={'model':model.get(),'aspect_ratio':aspect.get(),'quality':'medium','seed':42};selected()\n        if options['model']=='Seedream 5.0 Pro':\n            from seedream_api import load_profile\n            try:options['seedream_profile']=load_profile()['profile_id']\n            except ValueError as exc:\n                progress_text.set(str(exc));account();return\n            from seedream_settings import confirm_unsettled\n            from asset_context import generated_dir\n            confirm_unsettled(win,generated_dir(base),[aid for aid,_ in items],'资产')\n            progress_text.set(seedream_cost_preview(project, base, items, options))\n        elif options['model']!=LOCAL:\n            from cloud_assets import get_key\n            if not get_key():\n                progress_text.set('请先保存 Comfy API Key，或切换到 Seedream 5.0 Pro（使用火山方舟 Seedream Key）。');account();return\n        if options['model']!='Seedream 5.0 Pro':\n            if not app.launch_comfy(silent=True):return             # 第 62 期任务 8：静默拉起，不弹选择框\n        progress_text.set('正在启动制图：'+options['model']);busy.set_busy(True,controls=[selector,shape],progress_interval=15)\n        gen_stop.clear();cancel_button.configure(text='停止制图');cancel_button.state(['!disabled'])\n        url=app.settings.get('comfy_url','http://127.0.0.1:8188')\n        def finished(result):\n            app.status.set(result)\n            try:\n                if win.winfo_exists():\n                    busy.set_busy(False)\n                    cancel_button.state(['disabled']);cancel_button.configure(text='取消检测')\n                    while not events.empty():events.get_nowait()\n                    reload_rows();progress_text.set(result)\n            except Exception:\n                app_logging.swallowed()\n            if app.root==project:app.show(2)\n            try:\n                if win.winfo_exists():\n                    # 按资产库里的落盘结果判断，不靠返回文案里的关键字：取消、超时、\n                    # 只导入一部分的批次都不算完成，不能弹「已自动保存」。\n                    from asset_batch_service import batch_complete\n                    if batch_complete(base,[aid for aid,_ in items]):\n                        notify(win, result+'\\n\\n已自动保存到资产库。', title='制作完成', status=app.status)\n                    else:\n                        notify(win, result, level='warning', title='制图提示', status=app.status)\n                    win.destroy()\n            except Exception:\n                app_logging.swallowed()\n        def work():\n            try:return run(project,base,items,url,events.put,options=options,stop=gen_stop)\n            except Exception as exc:\n                # 第 65 期任务 1：这里原来把异常原文直接拼给用户\n                # （弹窗里那句英文「HTTP Error 500 ...」就是这么漏出来的）。\n                # 现在只报一句人话，异常原文留在终端日志里方便排查。\n                LOGGER.warning('制图未开始：%r', exc)\n                return '制图没能开始，请点「启动并检测」重试'\n        app.async_(work,finished,show_progress=False)\n    # 第 65 期任务 1：这一排只留「启动并检测」和「取消检测」。「手动制作资产」撤掉——检测通过就自动开跑\n    # （见上面 done）；「桌面打开 ComfyUI」主界面已经有一颗；「强制关闭 ComfyUI」与「制作记录」搬到主界面\n    # 「阶段配置」右边（desktop.asset_page）。同一件事只留一个入口。\n    buttons=FlowBar(form);buttons.pack(fill='x',padx=14,pady=(2,8))\n    check_button=PrimaryButton(buttons,text='启动并检测',command=lambda:app.safe(check));check_button.pack(side='left')\n    def preview_cost():\n        if not context_matches():raise ValueError('项目或分镜范围已切换，请重新打开制图窗口。')\n        if model.get() != 'Seedream 5.0 Pro':raise ValueError('当前金额预估支持 Seedream 直连，请按实际供应商核对其他模型费用。')\n        progress_text.set(seedream_cost_preview(project, base, selection(), {}))\n    SecondaryButton(buttons,text='预估费用',command=lambda:app.safe(preview_cost)).pack(side='left',padx=(6,0))\n    cancel_button=SecondaryButton(buttons,text='取消检测',command=cancel,state='disabled');cancel_button.pack(side='left',padx=(6,0))\n    def update_buttons():\n        if not win.winfo_exists():return\n        check_button.state(['!disabled'] if (not app.worker and selection()) else ['disabled'])\n    tk_timers.repeat(win,250,update_buttons)\n    tk_timers.repeat(win,250,poll)\n    update_buttons()\n"


def _session(root, fn, items):
    log = []
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        top = tk.Toplevel(root)
        form = ttk.Frame(top); form.pack(fill='both', expand=True)
        footer = ttk.Frame(top); footer.pack(fill='x')
        app = FakeApp(root, log)
        fn(app, top, form, footer, project, project / 'assets', lambda: list(items), app.status,
           lambda: log.append(('reload',)), lambda: True)
        steps = drive(top, [td], log, skip=('云模型账号 / 密钥', '火山 API 设置'))
        top.destroy()
    return steps


class AssetControlsEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except Exception:
            cls.root = None
            return
        cls.root.withdraw()
        _session(cls.root, legacy(module, LEGACY, 'attach_controls'), [])   # 预热：首次建窗布局不同

    @classmethod
    def tearDownClass(cls):
        if cls.root is not None:
            cls.root.destroy()

    def setUp(self):
        if self.root is None:
            self.skipTest(PLATFORM_TKINTER)

    def test_matches_legacy(self):
        old = legacy(module, LEGACY, 'attach_controls')
        for items in ([], [('a1', {'name': '甲'})]):
            with self.subTest(items=items):
                self.assertEqual(_session(self.root, module.attach_controls, items), _session(self.root, old, items))


if __name__ == '__main__':
    unittest.main()
