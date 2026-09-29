import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')

APP_DIR = Path(os.getenv('APPDATA', ROOT / 'runtime')) / 'HariomAI'
APP_DIR.mkdir(parents=True, exist_ok=True)

WORKSPACE = Path(
    os.getenv('HARIOM_WORKSPACE', Path.home() / 'HariomAI' / 'projects')
).resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)

# Provider pool. Empty keys are ignored automatically.
PROVIDERS = {
    # Optional local Manifest meta-router. If it is unavailable, the router
    # automatically continues with the direct provider pool below.
    'manifest': {
        'key': os.getenv('MNFST_API_KEY', ''),
        'model': os.getenv('MNFST_MODEL', 'manifest/auto'),
        'base': os.getenv(
            'MNFST_BASE_URL',
            'http://localhost:2099/v1/chat/completions',
        ),
    },
    'openai': {
        'key': os.getenv('OPENAI_API_KEY', ''),
        'model': os.getenv('OPENAI_MODEL', 'gpt-5-mini'),
        'base': 'https://api.openai.com/v1/chat/completions',
    },
    'gemini': {
        'key': os.getenv('GEMINI_API_KEY', ''),
        'model': os.getenv('GEMINI_MODEL', 'gemini-flash-latest'),
    },
    'groq': {
        'key': os.getenv('GROQ_API_KEY', ''),
        'model': os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b'),
        'models': [
            os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b'),
            os.getenv('GROQ_FALLBACK_MODEL', 'openai/gpt-oss-20b'),
            os.getenv('GROQ_SECOND_FALLBACK_MODEL', 'qwen/qwen3.8-27b'),
        ],
        'base': 'https://api.groq.com/openai/v1/chat/completions',
    },
    'cerebras': {
        'key': os.getenv('CEREBRAS_API_KEY', ''),
        'model': os.getenv('CEREBRAS_MODEL', 'gpt-oss-120b'),
        'base': 'https://api.cerebras.ai/v1/chat/completions',
    },
    'openrouter': {
        'key': os.getenv('OPENROUTER_API_KEY', ''),
        'model': os.getenv('OPENROUTER_MODEL', 'openrouter/free'),
        'base': 'https://openrouter.ai/api/v1/chat/completions',
        'openrouter': True,
    },
    'mistral': {
        'key': os.getenv('MISTRAL_API_KEY', ''),
        'model': os.getenv('MISTRAL_MODEL', 'devstral-small-latest'),
        'base': 'https://api.mistral.ai/v1/chat/completions',
    },
    # Cloudflare Workers AI has a separate account-scoped OpenAI-compatible
    # endpoint. It stays disabled until both values are supplied.
    'cloudflare': {
        'key': os.getenv('CLOUDFLARE_API_TOKEN', ''),
        'account_id': os.getenv('CLOUDFLARE_ACCOUNT_ID', ''),
        'model': os.getenv('CLOUDFLARE_MODEL', '@cf/openai/gpt-oss-120b'),
        'base': 'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions',
        'cloudflare': True,
    },
}
