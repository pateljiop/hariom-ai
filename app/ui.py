import threading,tkinter as tk
from tkinter import ttk,messagebox,filedialog
from .config import WORKSPACE
from .activity import ActivityBus
from .ai_router import AIRouter
from .workspace import Workspace
from .terminal import run_command
from .agent import Agent


class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('Hariom AI - Personal Workstation'); self.geometry('1200x760'); self.minsize(900,600)
        self.activity=ActivityBus(); self.router=AIRouter(self.activity); self.ws=Workspace(); self.agent=Agent(self.router,self.ws,self.activity); self.build(); self.activity.subscribe(self.log_line)
        self.activity.emit('SYSTEM -> workspace: '+str(self.ws.root)); self.activity.emit('SYSTEM -> providers: '+(', '.join(self.router.available()) or 'none'))

    def build(self):
        top=ttk.Frame(self,padding=10); top.pack(fill='x'); ttk.Label(top,text='HARIOM AI',font=('Segoe UI',20,'bold')).pack(side='left'); ttk.Button(top,text='Refresh',command=self.refresh).pack(side='right')
        panes=ttk.PanedWindow(self,orient='horizontal'); panes.pack(fill='both',expand=True,padx=10,pady=10)
        left=ttk.Frame(panes,padding=8); right=ttk.Frame(panes,padding=8); panes.add(left,weight=3); panes.add(right,weight=2)
        ttk.Label(left,text='Task / Chat').pack(anchor='w');
        provider_row=ttk.Frame(left); provider_row.pack(fill='x'); ttk.Label(provider_row,text='Provider:').pack(side='left'); self.provider=tk.StringVar(value='Auto'); self.provider_box=ttk.Combobox(provider_row,textvariable=self.provider,state='readonly',values=['Auto','Gemini','Mistral','Cavoti','OpenAI','Groq','OpenRouter','Cerebras'],width=14); self.provider_box.pack(side='left',padx=6); self.prompt=tk.Text(left,height=7,wrap='word'); self.prompt.pack(fill='x',pady=6); self.prompt.insert('1.0','Describe what you want Hariom AI to do...')
        b=ttk.Frame(left); b.pack(fill='x'); ttk.Button(b,text='Ask AI',command=self.ask).pack(side='left'); ttk.Button(b,text='Run Agent',command=self.run_agent).pack(side='left',padx=6); ttk.Button(b,text='List Workspace',command=self.list_workspace).pack(side='left'); ttk.Button(b,text='Choose Workspace',command=self.choose_workspace).pack(side='left',padx=6)
        ttk.Label(left,text='Response').pack(anchor='w',pady=(12,4)); self.response=tk.Text(left,wrap='word',state='disabled'); self.response.pack(fill='both',expand=True)
        ttk.Label(right,text='Live Activity').pack(anchor='w'); self.log=tk.Text(right,wrap='word',state='disabled'); self.log.pack(fill='both',expand=True,pady=6)
        row=ttk.Frame(right); row.pack(fill='x'); self.command=tk.Entry(row); self.command.pack(side='left',fill='x',expand=True); ttk.Button(row,text='Run',command=self.run).pack(side='left',padx=5)
        self.status=tk.StringVar(value='Ready'); ttk.Label(self,textvariable=self.status,relief='sunken',anchor='w').pack(fill='x',side='bottom')

    def log_line(self,line):
        self.after(0,lambda:self.append(self.log,line)); self.after(0,lambda:self.status.set(line))

    def append(self,w,text):
        w.configure(state='normal'); w.insert('end',text+'\n'); w.see('end'); w.configure(state='disabled')

    def refresh(self):
        self.activity.emit('SYSTEM -> providers: '+(', '.join(self.router.available()) or 'none'))

    def ask(self):
        p=self.prompt.get('1.0','end').strip()
        if not p:return
        self.append(self.response,'You: '+p); threading.Thread(target=self.ask_worker,args=(p,),daemon=True).start()

    def ask_worker(self,p):
        try:
            text,provider=self.router.chat(p,preferred=self._selected_provider(),system='You are Hariom AI, a transparent local workstation assistant. Give actionable plans. Never claim an action was performed unless a tool actually performed it.')
            self.after(0,lambda:self.append(self.response,f'Hariom AI ({provider}):\n{text}'))
        except Exception as e:
            err=str(e)
            self.after(0,lambda err=err: messagebox.showerror('AI error',err))

    def _selected_provider(self):
        value=self.provider.get().strip().lower()
        return None if value == 'auto' else value

    def run_agent(self):
        p=self.prompt.get('1.0','end').strip()
        if not p:return
        self.append(self.response,'You (Agent): '+p)
        self.activity.emit('AGENT -> starting')
        threading.Thread(target=self.agent_worker,args=(p,),daemon=True).start()

    def agent_worker(self,p):
        try:
            summary,results=self.agent.run(p,preferred=self._selected_provider())
            self.after(0,lambda:self.append(self.response,f'Hariom AI Agent:\n{summary}'))
        except Exception as e:
            err=str(e)
            self.after(0,lambda err=err: messagebox.showerror('Agent error',err))

    def list_workspace(self):
        try:
            items=self.ws.list_files(); self.append(self.response,'\n'.join(str(p.relative_to(self.ws.root)) for p in items[:300]) or 'Workspace is empty.')
        except Exception as e:
            err=str(e)
            messagebox.showerror('Workspace',err)

    def choose_workspace(self):
        p=filedialog.askdirectory(initialdir=str(self.ws.root))
        if p:
            self.ws=Workspace(p)
            self.agent.workspace=self.ws
            self.activity.emit('SYSTEM -> workspace changed to '+str(self.ws.root))

    def run(self):
        c=self.command.get().strip()
        if not c:return
        try:
            code,out=run_command(c,self.activity,cwd=self.ws.root); self.append(self.response,'$ '+c+'\n'+out)
        except Exception as e:
            err=str(e)
            messagebox.showwarning('Command blocked',err)


def launch(): App().mainloop()
