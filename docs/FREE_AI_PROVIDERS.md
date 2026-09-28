# Free AI Provider Catalog

Last audited: 2026-09-28

This catalog is for Hariom AI's personal-use, Windows-first provider router. It separates recurring free tiers from one-time credits/trials.

## A. Recurring/free access worth checking

| Provider | Type | Current free access | Card | Hariom AI use |
|---|---|---|---|---|
| Google AI Studio / Gemini | LLM + multimodal + realtime audio | Selected Gemini models and Gemini 3.8 Live variants have a Free Tier; limits vary by model/project | No for AI Studio free access | Primary chat, planning, multimodal, realtime voice |
| Groq | LLM | Free API tier; limits/models can change | No | Fast coding/chat fallback |
| Mistral | LLM | Free API mode with limits | No | Coding/planning fallback |
| OpenRouter | LLM gateway | Free-model pool/free router; models and limits rotate | No | Large fallback pool |
| Cloudflare Workers AI | LLM/image/audio | 10,000 Neurons/day on Workers Free; excess usage requires Workers Paid | No for Free plan | Image/audio/LLM experiments |
| Hugging Face Inference Providers | Multi-model | Free users receive $0.10/month inference credits; extra usage requires purchased credits | No for free credits | Experimental model access |
| Cohere | LLM/rerank/embeddings | Free/evaluation access with limits | No | Rerank/LLM backup |
| Pexels | Stock media | Free API quota | No | Photos + videos |
| Pixabay | Stock media | Free API quota | No | Photos + videos fallback |

## B. Promo / trial credit — useful but NOT permanent free

| Provider | Type | Notes |
|---|---|---|
| Cerebras | LLM | Account/offer dependent; do not assume permanent free |
| NVIDIA | LLM/image/video ecosystem | Catalog and promotional access vary; verify account-specific terms |
| Replicate | Image/video/audio | Trial/promotional credits may be available; usage after credits is paid |
| Runway | Video | Trial/free credits may exist; API usage is normally paid |
| fal.ai | Image/video/audio | Promotional/trial credits may be available; normally paid after credits |

## C. Important rules

1. Never commit API keys.
2. Never treat one-time credits as a permanent free tier.
3. Verify official pricing/terms before automatic fallback.
4. The router must stop when a free quota is exhausted instead of silently causing charges.
5. Free model names and quotas change; verify before hardcoding.
6. Card-required services are not automatically considered free; billing controls and account terms must be checked separately.

## Current verified changes — 2026-09-28

### Gemini 3.8 Live family
Google's current Gemini API pricing lists gemini-3.8-live, gemini-3.8-live-extended-thinking, and gemini-3.1-flash-live-preview with Free Tier input/output pricing. These are audio-to-audio models intended for realtime voice agents and live dialogue. Search grounding is supported, with a separate paid-tier allowance of 5,000 free search requests/month shared across Gemini 3.x models. This makes the Live family relevant to a future voice-controlled Hariom AI agent.

### Cloudflare Workers AI
Cloudflare's pricing page, updated Aug 28, 2026, confirms 10,000 Neurons/day at no charge on Workers Free. If the daily free allocation is exceeded, operations fail on Free rather than silently continuing; Workers Paid charges $0.011 per 1,000 Neurons above the free allocation. Treat individual model availability and per-model costs separately.

### Hugging Face
Official pricing currently gives Free users $0.10/month of Inference Provider credits, subject to change. Extra usage requires purchased credits. Therefore this remains a small free-credit tier, not an unlimited free API.

## Video-generation finding

No new recurring-free, sufficiently verified hosted video-generation API was identified in this audit. Do not add a provider merely because a website advertises free generations or temporary credits.

## Planned router policy

Task -> capability filter -> free/paid classification -> provider health -> quota/cooldown -> selected provider -> fallback -> stop before unexpected billing

This file is a discovery catalog, not a guarantee that every provider is available in every country/account.