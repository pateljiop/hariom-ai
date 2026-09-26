import os
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parent.parent
load_dotenv(ROOT/'.env')
APP_DIR=Path(os.getenv('APPDATA',ROOT/'runtime'))/'HariomAI'
APP_DIR.mkdir(parents=True,exist_ok=True)
_configured_workspace = os.getenv('HARIOM_WORKSPACE','').strip()
if _configured_workspace:
    WORKSPACE = Path(_configured_workspace).expanduser().resolve()
elif Path('A:/').exists():
    WORKSPACE = Path('A:/project').resolve()
else:
    WORKSPACE = (Path.home()/'HariomAI'/'projects').resolve()
WORKSPACE.mkdir(parents=True,exist_ok=True)
PROVIDERS={
'openai':{'key':os.getenv('OPENAI_API_KEY',''),'model':os.getenv('OPENAI_MODEL','gpt-5-mini'),'base':'https://api.openai.com/v1/chat/completions'},
'gemini':{'key':os.getenv('GEMINI_API_KEY',''),'model':os.getenv('GEMINI_MODEL','gemini-flash-latest')},
'mistral':{'key':os.getenv('MISTRAL_API_KEY',''),'model':os.getenv('MISTRAL_MODEL','mistral-small-latest'),'base':'https://api.mistral.ai/v1/chat/completions'},
'groq':{'key':os.getenv('GROQ_API_KEY',''),'model':os.getenv('GROQ_MODEL','openai/gpt-oss-120b'),'base':'https://api.groq.com/openai/v1/chat/completions'},
'openrouter':{'key':os.getenv('OPENROUTER_API_KEY',''),'model':os.getenv('OPENROUTER_MODEL','openrouter/free'),'base':'https://openrouter.ai/api/v1/chat/completions'},
'cerebras':{'key':os.getenv('CEREBRAS_API_KEY',''),'model':os.getenv('CEREBRAS_MODEL','llama-3.3-70b'),'base':'https://api.cerebras.ai/v1/chat/completions'},
'freellmapi':{'key':os.getenv('FREELLMAPI_API_KEY',''),'model':os.getenv('FREELLMAPI_MODEL','auto'),'base':os.getenv('FREELLMAPI_BASE_URL','http://127.0.0.1:3001/v1').rstrip('/')+'/chat/completions'}
}
