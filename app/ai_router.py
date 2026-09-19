import json
import requests
import time
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
                self.activity.emit(f'AI FAILED -> {name}: {self._safe_error(e)}')
        raise RuntimeError('No working provider. Configure a key and check quota/network. '+ ' | '.join(errors))

    def plan(self,prompt,system,preferred=None):
        order=[]
        if preferred in PROVIDERS and PROVIDERS[preferred].get('key'):
            order.append(preferred)
        order += [n for n in PROVIDERS if n not in order and PROVIDERS[n].get('key')]
        errors=[]
        for name in order:
            cfg=PROVIDERS[name]
            try:
                self.activity.emit(f'AI -> planning with {name} ({cfg["model"]})')
                text=self._gemini_json(cfg,prompt,system) if name=='gemini' else self._compatible_json(cfg,prompt,system)
                plan=self._parse_plan(text)
                self.activity.emit(f'AI OK -> planner {name}')
                return plan,name
            except Exception as e:
                errors.append(f'{name}: {e}')
                self.activity.emit(f'AI FAILED -> planner {name}')
        raise RuntimeError('No working planner provider. '+ ' | '.join(errors))

    def _parse_plan(self, text):
        if not isinstance(text, str):
            raise ValueError("Planner returned non-text content.")
        cleaned = text.strip()
        if cleaned.startswith("```"):
            parts = cleaned.splitlines()
            if parts and parts[0].strip().startswith("```"):
                parts = parts[1:]
            if parts and parts[-1].strip() == "```":
                parts = parts[:-1]
            cleaned = "\n".join(parts).strip()
        try:
            plan = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise ValueError(f"Planner returned invalid JSON: {error}") from error
        if not isinstance(plan, dict):
            raise ValueError("Planner returned a non-object JSON value.")
        if not isinstance(plan.get("steps"), list):
            raise ValueError("Planner JSON must contain a steps list.")
        return plan

    def _safe_error(self, error):
        if isinstance(error, requests.HTTPError) and error.response is not None:
            body=(error.response.text or '').replace('\\n',' ')[:500]
            return f'HTTP {error.response.status_code}: {body}'
        return str(error)[:500]

    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    MAX_RETRIES = 2
    RETRY_DELAYS = (1, 2)

    def _post(self, url, **kwargs):
        last_response = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = requests.post(url, **kwargs)
                last_response = response
                if response.status_code not in self.RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response
                if attempt >= self.MAX_RETRIES:
                    response.raise_for_status()
            except requests.RequestException as error:
                status = getattr(getattr(error, 'response', None), 'status_code', None)
                if status not in self.RETRYABLE_STATUS_CODES or attempt >= self.MAX_RETRIES:
                    raise
            delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
            self.activity.emit(f"AI -> temporary provider error; retrying in {delay}s")
            time.sleep(delay)
        raise RuntimeError("Provider request failed after retries.")

    def _compatible(self,cfg,prompt,system):
        messages=[]
        if system:
            messages.append({'role':'system','content':system})
        messages.append({'role':'user','content':prompt})
        r=self._post(cfg['base'],headers={'Authorization':'Bearer '+cfg['key'],'Content-Type':'application/json'},json={'model':cfg['model'],'messages':messages,'temperature':0.2},timeout=90)
        return r.json()['choices'][0]['message']['content']

    def _compatible_json(self,cfg,prompt,system):
        messages=[]
        if system:
            messages.append({'role':'system','content':system})
        messages.append({'role':'user','content':prompt})
        payload={'model':cfg['model'],'messages':messages,'temperature':0.1}
        r=self._post(cfg['base'],headers={'Authorization':'Bearer '+cfg['key'],'Content-Type':'application/json'},json=payload,timeout=90)
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
                            'tool':{'type':'STRING','enum':['project_context','list_workspace','read_file','write_file','patch_file','run_command','run_tests','git_status','git_diff','git_log','git_branch']},
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
        r=self._post(url,headers=headers,json=payload,timeout=90)
        data=r.json()
        candidates=data.get('candidates') or []
        if not candidates:
            raise RuntimeError('Gemini returned no candidates: '+str(data.get('promptFeedback',data)))
        parts=candidates[0].get('content',{}).get('parts',[])
        text=''.join(part.get('text','') for part in parts if part.get('text'))
        if not text:
            raise RuntimeError('Gemini returned no text: '+str(data))
        return {'text':text,'raw':data}
