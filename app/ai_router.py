import requests
from .config import PROVIDERS
class AIRouter:
    def __init__(self,activity): self.activity=activity
    def available(self): return [n for n,c in PROVIDERS.items() if c.get('key')]
    def chat(self,prompt,system='',preferred=None):
        order=[]
        if preferred in PROVIDERS: order.append(preferred)
        order += [n for n in PROVIDERS if n not in order]
        errors=[]
        for name in order:
            cfg=PROVIDERS[name]
            if not cfg.get('key'): continue
            try:
                self.activity.emit(f'AI -> trying {name} ({cfg["model"]})')
                text=self._gemini(cfg,prompt,system) if name=='gemini' else self._compatible(cfg,prompt,system)
                self.activity.emit(f'AI OK -> {name}')
                return text,name
            except Exception as e:
                errors.append(f'{name}: {e}')
                self.activity.emit(f'AI FAILED -> {name}')
        raise RuntimeError('No working provider. Configure a key and check quota/network. '+ ' | '.join(errors))
    def _compatible(self,cfg,prompt,system):
        messages=[]
        if system: messages.append({'role':'system','content':system})
        messages.append({'role':'user','content':prompt})
        r=requests.post(cfg['base'],headers={'Authorization':'Bearer '+cfg['key'],'Content-Type':'application/json'},json={'model':cfg['model'],'messages':messages,'temperature':0.2},timeout=90)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    def _gemini(self,cfg,prompt,system):
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent"
        text=(system+'\n\n' if system else '')+prompt
        r=requests.post(url,params={'key':cfg['key']},json={'contents':[{'role':'user','parts':[{'text':text}]}]},timeout=90)
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text']
