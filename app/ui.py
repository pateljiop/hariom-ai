import threading,tkinter as tk
from tkinter import ttk,messagebox,filedialog
from .config import WORKSPACE
from .activity import ActivityBus
from .ai_router import AIRouter
from .workspace import Workspace
from .terminal import run_command

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('Hariom AI - Personal Workstation'); self.geometry('1200x760'); self.minsize(900,600)
        self.activity=ActivityBus(); self.router=AIRouter(self.activity); self.ws=Workspace(); self.build(); self.activity.subscribe(self.log_line)
        self.activity.emit('SYSTEM -> workspace: '+str(self.ws.root)); self.activity.emit('SYSTEM -> providers: '+(', '.join(self.router.available()) or 'none'))
    def build(self):
        top=ttk.Frame(self,padding=10); top.pack(fill='x'); ttk.Label(top,text='HARIOM AI',font=('Segoe UI',20,'bold')).pack(side='left'); ttk.Button(top,text='Refresh',command=self.refresh).pack(side='right')
        panes=ttk.PanedWindow(self,orient='horizontal'); panes.pack(fill='both',expand=True,padx=10,pady=10)
        left=ttk.Frame(panes,padding=8); right=ttk.Frame(panes,padding=8); panes.add(left,weight=3); panes.add(right,weight=2)
        ttk.Label(left,text='Task / Chat').pack(anchor='w'); self.prompt=tk.Text(left,height=7,wrap='word'); self.prompt.pack(fill='x',pady=6); self.prompt.insert('1.0','Describe what you want Hariom AI to do...')
        b=ttk.Frame(left); b.pack(fill='x'); ttk.Button(b,text='Ask AI',command=self.ask).pack(side='left'); ttk.Button(b,text='List Workspace',command=self.list_workspace).pack(side='left',padx=6); ttk.Button(b,text='Choose Workspace',command=self.choose_workspace).pack(side='left')
        ttk.Label(left,text='Response').pack(anchor='w',pady=(12,4)); self.response=tk.Text(left,wrap='word',state='disabled'); self.response.pack(fill='both',expand=True)
        ttk.Label(right,text='Live Activity').pack(anchor='w'); self.log=tk.Text(right,wrap='word',state='disabled'); self.log.pack(fill='both',expand=True,pady=6)
        row=ttk.Frame(right); row.pack(fill='x'); self.command=ttk.Entry(row); self.command.pack(side='left',fill='x',expand=True); ttk.Button(row,text='Run',command=self.run).pack(side='left',padx=5)
        self.status=tk.StringVar(value='Ready'); ttk.Label(self,textvariable=self.status,relief='sunken',anchor='w').pack(fill='x',side='bottom')
    def log_line(self,line): self.after(0,lambda:self.append(self.log,line)); self.after(0,lambda:self.status.set(line))
    def append(self,w,text): w.configure(state='normal'); w.insert('end',text+'\n'); w.see('end'); w.configure(state='disabled')
    def refresh(self): self.activity.emit('SYSTEM -> providers: '+(', '.join(self.router.available()) or 'none'))
    def ask(self):
        p=self.prompt.get('1.0','end').strip()
        if not p:return
        self.append(self.response,'You: '+p); threading.Thread(target=self.ask_worker,args=(p,),daemon=True).start()
    def ask_worker(self,p):
        try:
            text,provider=self.router.chat(p,system='You are Hariom AI, a transparent local workstation assistant. Give actionable plans. Never claim an action was performed unless a tool actually performed it.')
            self.after(0,lambda:self.append(self.response,f'Hariom AI ({provider}):\n{text}'))
        except Exception as e:self.after(0,lambda:messagebox.showerror('AI error',str(e)))
    def list_workspace(self):
        try:
            items=self.ws.list_files(); self.append(self.response,'\n'.join(str(p.relative_to(self.ws.root)) for p in items[:300]) or 'Workspace is empty.')
        except Exception as e:messagebox.showerror('Workspace',str(e))
    def choose_workspace(self):
        p=filedialog.askdirectory(initialdir=str(self.ws.root))
        if p:
            self.ws=Workspace(p)
            self.activity.emit('SYSTEM -> workspace changed to '+str(self.ws.root))
    def run(self):
        c=self.command.get().strip()
        if not c:return
        try:
            code,out=run_command(c,self.activity); self.append(self.response,'$ '+c+'\n'+out)
        except Exception as e:messagebox.showwarning('Command blocked',str(e))

def launch(): App().mainloop()
