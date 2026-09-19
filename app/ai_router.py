import json
import requests
from .config import PROVIDERS


class AIRouter:
    def __init__(self,activity):
        self.activity=activity

    def available(self):
        return [n for n,c in PROVIDERS.items() if c.get('key')]

    def chat(self,prompt,system='',preferred=None):
        order=[]
        if preferred in PROVIDERS:
            order.append(preferred)
        order += [n for n in PROVIDERS if n not in order]
        errors=[]
        for name in order:
            cfg=PROVIDERS[name]
            if not cfg.get('key'):
                continue
            try:
                self.activity.emit(f'AI -> trying {name} ({cfg["model"]})')
                text=self._gemini(cfg,prompt,system) if name=='gemini' else self._compatible(cfg,prompt,system)
                self.activity.emit(f'AI OK -> {name}')
                return text,name
            except Exception as e:
                errors.append(f'{name}: {e}')
                self.activity.emit(f'AI FAILED -> {name}')
        raise RuntimeError('No working provider. Configure a key and check quota/network. '+ ' | '.join(errors))

    def plan(self,prompt,system):
        order=[n for n in PROVIDERS if PROVIDERS[n].get('key')]
        errors=[]
        for name in order:
            cfg=PROVIDERS[name]
            try:
                self.activity.emit(f'AI -> planning with {name} ({cfg["model"]})')
                text=self._gemini_json(cfg,prompt,system) if name=='gemini' else self._compatible_json(cfg,prompt,system)
                plan=json.loads(text)
                if not isinstance(plan,dict):
                    raise ValueError('Planner returned a non-object JSON value.')
                self.activity.emit(f'AI OK -> planner {name}')
                return plan,name
            except Exception as e:
                errors.append(f'{name}: {e}')
                self.activity.emit(f'AI FAILED -> planner {name}')
        raise RuntimeError('No working planner provider. '+ ' | '.join(errors))

    def _compatible(self,cfg,prompt,system):
        messages=[]
        if system:
            messages.append({'role':'system','content':system})
        messages.append({'role':'user','content':prompt})
        r=requests.post(cfg['base'],headers={'Authorization':'Bearer '+cfg['key'],'Content-Type':'application/json'},json={'model':cfg['model'],'messages':messages,'temperature':0.2},timeout=90)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']

    def _compatible_json(self,cfg,prompt,system):
        messages=[]
        if system:
            messages.append({'role':'system','content':system})
        messages.append({'role':'user','content':prompt})
        payload={'model':cfg['model'],'messages':messages,'temperature':0.1}
        r=requests.post(cfg['base'],headers={'Authorization':'Bearer '+cfg['key'],'Content-Type':'application/json'},json=payload,timeout=90)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']

    def _gemini(self,cfg,prompt,system):
        return self._gemini_request(cfg,prompt,system)['text']

    def _gemini_json(self,cfg,prompt,system):
        schema={
            'type':'OBJECT',
            'properties':{
                'steps':{
                    'type':'ARRAY',
                    'items':{
                        'type':'OBJECT',
                        'properties':{
                            'tool':{'type':'STRING','enum':['list_workspace','read_file','write_file','run_command']},
                            'args':{'type':'OBJECT'},
                        },
                        'required':['tool','args'],
                    },
                },
                'goal':{'type':'STRING'},
            },
            'required':['steps','goal'],
        }
        return self._gemini_request(cfg,prompt,system,{'responseMimeType':'application/json','responseSchema':schema})['text']

    def _gemini_request(self,cfg,prompt,system,generation_config=None):
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent"
        headers={'x-goog-api-key':cfg['key'],'Content-Type':'application/json'}
        payload={'contents':[{'role':'user','parts':[{'text':prompt}]}]}
        if system:
            payload['systemInstruction']={'parts':[{'text':system}]}
        if generation_config:
            payload['generationConfig']=generation_config
        r=requests.post(url,headers=headers,json=payload,timeout=90)
        r.raise_for_status()
        data=r.json()
        candidates=data.get('candidates') or []
        if not candidates:
            raise RuntimeError('Gemini returned no candidates: '+str(data.get('promptFeedback',data)))
        parts=candidates[0].get('content',{}).get('parts',[])
        text=''.join(part.get('text','') for part in parts if part.get('text'))
        if not text:
            raise RuntimeError('Gemini returned no text: '+str(data))
        return {'text':text,'raw':data}
