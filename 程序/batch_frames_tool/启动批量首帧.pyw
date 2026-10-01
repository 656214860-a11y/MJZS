import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import threading,queue,argparse
from batch_frames import read,save,preflight,run,Client

parser=argparse.ArgumentParser()
parser.add_argument('--source',default='')
parser.add_argument('--url',default='')
parser.add_argument('--shot-id',default='')
parser.add_argument('--shot-ids',default=None)
args=parser.parse_args()
root=tk.Tk();root.title('ComfyUI · 分镜批量首帧');root.geometry('850x790')
root.attributes('-topmost',True)
root.after_idle(root.lift)
cfg=read(Path(__file__).with_name('config.json'));events=queue.Queue();stop=threading.Event();busy=False
frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
ttk.Label(frame,text='FLUX.2 Klein 4B · 按镜头逐张生成',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w',pady=8)
ttk.Label(frame,text='选择第4步刷新的JSON；仅处理参考图齐全、尚无首帧且未删除的镜头。').pack(anchor='w')
source=tk.StringVar(value=args.source);ttk.Entry(frame,textvariable=source).pack(fill='x',pady=8)
def choose():
    if busy:return
    path=filedialog.askopenfilename(parent=root,initialdir=str(Path(source.get()).parent) if source.get() else 'D:/漫剧下载/项目',filetypes=[('镜头JSON','*.json')])
    if path:source.set(path)
ttk.Button(frame,text='选择镜头 JSON',command=choose).pack(anchor='w')
ttk.Label(frame,text='ComfyUI地址（使用浏览器当前显示的本机地址）').pack(anchor='w',pady=(12,0))
url=tk.StringVar(value=cfg['url'] if cfg.get('api_settings_saved') else args.url or cfg['url']);ttk.Entry(frame,textvariable=url).pack(fill='x')
api_fields={}
api_box=ttk.LabelFrame(frame,text='API 模型设置（可自定义）',padding=6);api_box.pack(fill='x',pady=5);api_box.columnconfigure(1,weight=1)
for row,(key,label) in enumerate([('model','图像模型'),('text_encoder','文本编码器'),('vae','VAE')]):
    ttk.Label(api_box,text=label).grid(row=row,column=0,sticky='w')
    api_fields[key]=tk.StringVar(value=cfg.get(key,''));ttk.Entry(api_box,textvariable=api_fields[key]).grid(row=row,column=1,sticky='ew')
def save_api_settings(notify=True):
    if busy:raise ValueError('请等待当前批次完成后修改接口设置')
    values={key:var.get().strip() for key,var in api_fields.items()}
    Client(url.get().strip())
    if not all(values.values()):raise ValueError('请填写模型、文本编码器和 VAE 名称')
    cfg.update(values);cfg.update(url=url.get().strip().rstrip('/'),api_settings_saved=True)
    cfg.update(width=432 if ratio.get().startswith('竖') else 768,height=768 if ratio.get().startswith('竖') else 432)
    save(Path(__file__).with_name('config.json'),cfg)
    if notify:messagebox.showinfo('已保存','API 地址和模型设置已保存，下次打开自动回填。',parent=root)
def save_api_action():
    try:save_api_settings()
    except (ValueError,OSError) as exc:messagebox.showerror('API 设置',str(exc),parent=root)
ttk.Button(api_box,text='保存设置',command=save_api_action).grid(row=0,column=2,padx=8)
def delete_model():
    if busy:messagebox.showinfo('任务进行中','请等待当前批次完成后删除模型配置。',parent=root);return
    model=api_fields['model'].get().strip()
    if not model:messagebox.showinfo('选择模型','请先填写或选择模型。',parent=root);return
    if not messagebox.askyesno('删除模型',f'删除模型配置 {model}？\n只移除助手中的选择，不删除本地模型和已生成首帧。',parent=root):return
    try:
        updated=dict(cfg,model='');save(Path(__file__).with_name('config.json'),updated)
        cfg.update(updated);api_fields['model'].set('')
    except OSError as exc:messagebox.showerror('API 设置',str(exc),parent=root)
ttk.Button(api_box,text='删除模型',command=delete_model).grid(row=1,column=2,padx=8)
ttk.Label(frame,text='镜头编号：留空批量生成，或填写 EP001_SH001 先测试一镜').pack(anchor='w',pady=(10,0))
sid=tk.StringVar(value=args.shot_id);ttk.Entry(frame,textvariable=sid,state='readonly' if args.shot_id else 'normal').pack(fill='x')
if args.shot_id:root.title('ComfyUI · 单个首帧 · '+args.shot_id)
ratio=tk.StringVar(value='竖屏 432×768' if cfg.get('width',768)<cfg.get('height',432) else '横屏 768×432');ttk.Combobox(frame,textvariable=ratio,values=['横屏 768×432','竖屏 432×768'],state='readonly').pack(anchor='w',pady=10)
log=tk.Text(frame,height=13,wrap='word');log.pack(fill='both',expand=True)
buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=10)
def start(check_only):
    global busy
    if busy:return
    if not Path(source.get()).is_file():messagebox.showerror('请选择JSON','请先选择有效的镜头JSON',parent=root);return
    try:save_api_settings(False)
    except (ValueError,OSError) as exc:messagebox.showerror('API 设置',str(exc),parent=root);return
    settings=dict(cfg,url=url.get().strip(),shot_id=sid.get().strip())
    if args.shot_ids is not None:
        if Path(source.get()).resolve()!=Path(args.source).resolve():
            messagebox.showerror('勾选范围已失效','请返回助手，重新选择分镜并勾选镜头。',parent=root);return
        settings['shot_ids']=[item for item in args.shot_ids.split(',') if item]
    settings.update(width=432 if ratio.get().startswith('竖') else 768,height=768 if ratio.get().startswith('竖') else 432)
    selected=source.get();busy=True;stop.clear();check.configure(state='disabled');generate.configure(state='disabled')
    def work():
        try:
            if check_only:
                _,_,_,ready,skipped=preflight(selected,settings)
                events.put(f'检查完成：可生成 {len(ready)} 镜，跳过 {len(skipped)} 镜。')
                for item in skipped:events.put(item)
            else:run(selected,settings,events.put,stop)
        except Exception as e:events.put('未完成：'+str(e))
        finally:events.put(None)
    threading.Thread(target=work,daemon=True).start()
check=ttk.Button(buttons,text='1. 检查模型与参考资产',command=lambda:start(True));check.pack(side='left',padx=4)
generate=ttk.Button(buttons,text='2. 开始逐镜生成',command=lambda:start(False));generate.pack(side='left',padx=4)
ttk.Button(buttons,text='暂停（不再提交下一镜）',command=stop.set).pack(side='left',padx=4)
def tick():
    global busy
    while True:
        try:value=events.get_nowait()
        except queue.Empty:break
        if value is None:busy=False;check.configure(state='normal');generate.configure(state='normal')
        else:log.insert('end',value+'\n');log.see('end')
    root.after(150,tick)
def close():
    if busy:stop.set();messagebox.showinfo('正在暂停','请等待当前请求结束后关闭，任务编号会保留。',parent=root)
    else:root.destroy()
root.protocol('WM_DELETE_WINDOW',close);root.after(150,tick);root.mainloop()
