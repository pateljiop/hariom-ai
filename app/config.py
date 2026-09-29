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

PROVIDERS = {
    'openai': {
        'key': os.getenv('OPENAI_API_KEY', ''),
        'model': os.getenv('OPENAI_MODEL', 'gpt-5-mini'),
        'base': 'https://api.openai.com/v1/chat/completions',
        'supports_tools': True, 'supports_streaming': True, 'supports_json': True,
        'supports_vision': True, 'speed': 7, 'coding': 8, 'reasoning': 8,
    },
    'gemini': {
        'key': os.getenv('GEMINI_API_KEY', ''),
        'model': os.getenv('GEMINI_MODEL', 'gemini-flash-latest'),
        'supports_tools': False, 'supports_streaming': False, 'supports_json': True,
        'supports_vision': True, 'speed': 8, 'coding': 7, 'reasoning': 7,
    },
    'groq': {
        'key': os.getenv('GROQ_API_KEY', ''),
        'models': [
            os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b'),
            os.getenv('GROQ_FALLBACK_MODEL', 'openai/gpt-oss-20b'),
            os.getenv('GROQ_SECOND_FALLBACK_MODEL', 'qwen/qwen3.8-27b'),
        ],
        'base': 'https://api.groq.com/openai/v1/chat/completions',
        'supports_tools': True, 'supports_streaming': True, 'supports_json': True,
        'supports_vision': False, 'speed': 10, 'coding': 8, 'reasoning': 7,
    },
    'cerebras': {
        'key': os.getenv('CEREBRAS_API_KEY', ''),
        'model': os.getenv('CEREBRAS_MODEL', 'gpt-oss-120b'),
        'base': 'https://api.cerebras.ai/v1/chat/completions',
        'supports_tools': True, 'supports_streaming': True, 'supports_json': True,
        'supports_vision': False, 'speed': 10, 'coding': 8, 'reasoning': 7,
    },
    'openrouter': {
        'key': os.getenv('OPENROUTER_API_KEY', ''),
        'model': os.getenv('OPENROUTER_MODEL', 'openrouter/free'),
        'base': 'https://openrouter.ai/api/v1/chat/completions',
        'openrouter': True,
        'supports_tools': True, 'supports_streaming': True, 'supports_json': True,
        'supports_vision': True, 'speed': 7, 'coding': 8, 'reasoning': 8,
    },
    'mistral': {
        'key': os.getenv('MISTRAL_API_KEY', ''),
        'model': os.getenv('MISTRAL_MODEL', 'devstral-small-latest'),
        'base': 'https://api.mistral.ai/v1/chat/completions',
        'supports_tools': True, 'supports_streaming': True, 'supports_json': True,
        'supports_vision': False, 'speed': 8, 'coding': 10, 'reasoning': 7,
    },
    'cloudflare': {
        'key': os.getenv('CLOUDFLARE_API_TOKEN', ''),
        'account_id': os.getenv('CLOUDFLARE_ACCOUNT_ID', ''),
        'model': os.getenv('CLOUDFLARE_MODEL', '@cf/openai/gpt-oss-120b'),
        'base': 'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions',
        'cloudflare': True,
        'supports_tools': False, 'supports_streaming': True, 'supports_json': True,
        'supports_vision': False, 'speed': 8, 'coding': 7, 'reasoning': 7,
    },
}

ROUTING_PROFILES = {
    'hariom/auto': {},
    'hariom/fast': {'speed': 1.0, 'latency': 2.0},
    'hariom/coding': {'coding': 2.0},
    'hariom/reasoning': {'reasoning': 2.0},
    'hariom/free': {'free_first': True},
}

ROUTER_COOLDOWN_SECONDS = int(os.getenv('HARIOM_ROUTER_COOLDOWN', '60'))
ROUTER_RETRIES = int(os.getenv('HARIOM_ROUTER_RETRIES', '2'))
ROUTER_TIMEOUT_SECONDS = int(os.getenv('HARIOM_ROUTER_TIMEOUT', '90'))
CACHE_TTL_SECONDS = int(os.getenv('HARIOM_CACHE_TTL', '300'))
CACHE_ENABLED = os.getenv('HARIOM_CACHE_ENABLED', '1').lower() not in {'0', 'false', 'no'}

GATEWAY_HOST = os.getenv('HARIOM_GATEWAY_HOST', '127.0.0.1')
GATEWAY_PORT = int(os.getenv('HARIOM_GATEWAY_PORT', '8080'))
GATEWAY_API_KEY = os.getenv('HARIOM_GATEWAY_API_KEY', '')
