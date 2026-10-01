import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import threading,queue
from batch_frames import read,preflight,run

root=tk.Tk();root.title('ComfyUI · 分镜批量首帧');root.geometry('850x650')
cfg=read(Path(__file__).with_name('config.json'));events=queue.Queue();stop=threading.Event();busy=False
frame=ttk.Frame(root,padding=18);frame.pack(fill='both',expand=True)
ttk.Label(frame,text='FLUX.2 Klein 4B · 按镜头逐张生成',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w',pady=8)
ttk.Label(frame,text='选择第4步刷新的JSON；仅处理参考图齐全、尚无首帧且未删除的镜头。').pack(anchor='w')
source=tk.StringVar();ttk.Entry(frame,textvariable=source).pack(fill='x',pady=8)
def choose():
    if busy:return
    path=filedialog.askopenfilename(parent=root,initialdir='D:/漫剧下载/项目',filetypes=[('镜头JSON','*.json')])
    if path:source.set(path)
ttk.Button(frame,text='选择镜头 JSON',command=choose).pack(anchor='w')
ttk.Label(frame,text='ComfyUI地址（使用浏览器当前显示的本机地址）').pack(anchor='w',pady=(12,0))
url=tk.StringVar(value=cfg['url']);ttk.Entry(frame,textvariable=url).pack(fill='x')
ttk.Label(frame,text='镜头编号：留空批量生成，或填写 EP001_SH001 先测试一镜').pack(anchor='w',pady=(10,0))
sid=tk.StringVar();ttk.Entry(frame,textvariable=sid).pack(fill='x')
ratio=tk.StringVar(value='竖屏 432×768');ttk.Combobox(frame,textvariable=ratio,values=['竖屏 432×768','横屏 768×432'],state='readonly').pack(anchor='w',pady=10)
log=tk.Text(frame,height=13,wrap='word');log.pack(fill='both',expand=True)
buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=10)
def start(check_only):
    global busy
    if busy:return
    if not Path(source.get()).is_file():messagebox.showerror('请选择JSON','请先选择有效的镜头JSON',parent=root);return
    settings=dict(cfg,url=url.get().strip(),shot_id=sid.get().strip())
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
