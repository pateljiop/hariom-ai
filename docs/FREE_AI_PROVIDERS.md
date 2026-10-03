# Free AI Provider Catalog

Last audited: 2026-10-03

This catalog is for Hariom AI's personal-use, Windows-first provider router. It separates recurring free tiers from one-time credits/trials.

## A. Recurring/free access worth checking

| Provider | Type | Current free access | Card | Hariom AI use |
|---|---|---|---|---|
| Google AI Studio / Gemini | LLM + multimodal + realtime audio + TTS | Selected Gemini models, Gemini 3.8 Live, and Gemini 3.8 Flash-Lite TTS have Free Tier access; limits vary by model/project | No for AI Studio free access | Primary chat, planning, multimodal, realtime voice, narration |
| Groq | LLM + STT | Free API tier; limits/models can change | No | Fast coding/chat + speech-to-text fallback |
| Mistral | LLM | Free API mode with limits | No | Coding/planning fallback |
| OpenRouter | LLM gateway | Free-model pool/free router; models and limits rotate | No | Large fallback pool |
| Cloudflare Workers AI | LLM/image/audio | 10,000 Neurons/day on Workers Free; excess usage requires Workers Paid; selected models remain available on Free | No for Free plan | Image/audio/LLM experiments |
| Cloudflare AI Gateway | AI gateway | Core gateway features are free on all plans; Free plan has 100,000 persistent logs total across gateways | No | Provider routing, caching, rate limiting, observability |
| Hugging Face Inference Providers | Multi-model | Free users receive $0.10/month inference credits; extra usage requires purchased credits | No for free credits | Experimental model access |
| ElevenLabs | TTS + STT + voice/media | 10,000 free credits/month; API endpoints are available on the free plan; exact feature consumption varies | No credit card required for free signup | High-quality TTS, realtime voice-agent TTS, STT, voice/media fallback |
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

## Current verified changes — 2026-09-30

### Gemini 3.5 Transcribe
Google's current Gemini API pricing lists `gemini-3.5-transcribe` with **Free Tier input and output**. It is a speech-to-text model with automatic language detection, speaker diarization, word-level timestamps, and custom vocabulary biasing. This is directly useful for Hariom AI's voice-command and transcription pipeline, subject to account/model rate limits. It should be treated as a recurring free-tier capability, not unlimited usage. citeturn0search38

### Cloudflare Workers AI model restrictions — confirmed
Cloudflare's pricing page was updated September 7, 2026 and confirms the **10,000 Neurons/day** Workers Free allocation. It also explicitly identifies several models that require Workers Paid, including Kimi K2.6/K2.7 Code, GLM 5.2/5.3/5.3 Flash, and DeepSeek V4 variants. Free-plan requests beyond the daily allocation fail rather than automatically becoming paid. citeturn0search37turn0search39

## Current verified changes — 2026-09-29

### Gemini 3.8 Flash-Lite TTS
Google's current Gemini API pricing lists `gemini-3.8-flash-lite-tts` with **Free Tier input and output**. The same page states it is optimized for high-throughput, low-latency conversational speech. This makes it a strong candidate for Hariom AI narration/voiceover, subject to the account/model rate limits. citeturn0search15

### Google Vids — free video service, not free API
Google's September 23, 2026 announcement confirms free HD video creation with Gemini Omni 1.1 Flash in Google Vids for Google/Workspace accounts. Because this is a Vids product capability rather than a documented free public video API, keep it outside the automated API router. citeturn1search11

### Gemini 3.8 Flash agent availability
Google's current Antigravity agent documentation lists Gemini 3.8 Flash as the default model for `antigravity-preview-09-2026`. This is relevant to future managed-agent integration, but the catalog must not label the managed agent itself as permanently free without a confirmed pricing entitlement. citeturn1search12

### Previous verified changes — 2026-09-28

### Gemini 3.8 Live family
Google's current Gemini API pricing lists Gemini 3.8 Live variants with Free Tier input/output pricing. These are audio-to-audio models intended for realtime voice agents and live dialogue. This makes the Live family relevant to a future voice-controlled Hariom AI agent.

Google's current tool pricing also lists free Google Search grounding for Gemini 3.x as 5,000 requests/month shared across the Gemini 3.x family before paid usage.

### Cloudflare Workers AI
Cloudflare's current pricing, updated September 7, 2026, confirms 10,000 Neurons/day at no charge on Workers Free. If the daily free allocation is exceeded, further operations fail on Free; Workers Paid charges $0.011 per 1,000 Neurons above the free allocation.

Cloudflare has restricted several resource-intensive models from Workers Free. Current examples requiring Paid include `@cf/moonshotai/kimi-k2.6`, `@cf/moonshotai/kimi-k2.7-code`, `@cf/zai-org/glm-5.2`, and other listed frontier models. Models such as `@cf/zai-org/glm-4.7-flash`, `@cf/google/gemma-4-26b-a4b-it`, and `@cf/nvidia/nemotron-3-120b` remain listed as available on Workers Free. Never assume every model in the catalog is free.

### Cloudflare AI Gateway
Cloudflare's current pricing says AI Gateway core features are free on all plans. Free-plan persistent logging is capped at 100,000 logs total across gateways. This is useful as an infrastructure layer around Hariom AI's multiple providers, but it does not make paid model inference free.

### Hugging Face
Official pricing currently gives Free users $0.10/month of Inference Provider credits, subject to change. Extra usage requires purchased credits. Therefore this remains a small free-credit tier, not an unlimited free API.

### Groq STT
Groq remains relevant not only for LLM fallback but also for speech-to-text. Treat exact Whisper/model names and limits as volatile and verify them against Groq's current model/rate-limit documentation before hardcoding.

## Video-generation finding

**New service-level finding (not an API): Google Vids.** Google announced on September 23, 2026 that anyone with a Google or Google Workspace account can create HD videos for free in Google Vids using Gemini Omni 1.1 Flash; generated clips include an imperceptible SynthID watermark. Google also says Gemini 3.8 Flash-Lite TTS voiceover is coming to Vids. This is useful for manual/assisted video production, but Google has not established a recurring-free public video-generation API in the announcement, so it is **not** added as an API provider or automatic router target. citeturn1search11

Google had also announced on April 2, 2026 that Google Vids could generate free video clips with Veo 3.1 (10 free generations/month at that time). Treat current Vids quotas as product-level and subject to change; do not infer API quota from them. citeturn1search14

No new recurring-free, sufficiently verified **hosted video-generation API** was identified in this audit. Do not add a provider merely because a website advertises free generations or temporary credits.

## Router policy

Task -> capability filter -> free/paid classification -> provider health -> quota/cooldown -> selected provider -> fallback -> stop before unexpected billing

This file is a discovery catalog, not a guarantee that every provider is available in every country/account.


## Current verified changes — 2026-10-01

### OpenRouter free pool — newly verified current state
OpenRouter's current free-model offering remains useful as a fallback pool, but the exact model roster and limits rotate. A current OpenRouter model page/search result shows newly available zero-price models, including experimental/preview models. These should be treated as opportunistic free capacity rather than a guaranteed stable provider. The router should continue using the documented `openrouter/free` route rather than hardcoding volatile model names.

### ElevenLabs — verification status
Current third-party reports still advertise a 10,000-credit/month free plan, but this run did not obtain a sufficiently authoritative current official pricing/API source to promote it into the recurring-free section. Keep it **unlisted/unverified** rather than assuming the earlier claim is permanent.

### Deepgram — verification status
Deepgram's commonly advertised signup credit remains a promotional/trial offer rather than recurring free access. It stays in the trial/promo category and is not a free fallback target.

### No new verified free hosted video API
No newly available recurring-free hosted video-generation API met the verification threshold in this run. Google Vids remains a free product capability, not a documented free public API.

## Current verified changes — 2026-10-03

### ElevenLabs — recurring free API access verified
ElevenLabs' current official developer page explicitly offers **10,000 free credits** on signup, with **no credit card required**, and says the free tier includes API access. Its API help documentation also states that most API endpoints are available on all plans, including the free plan. This qualifies ElevenLabs for the recurring-free catalog; it must still be quota-guarded because the 10,000 credits are limited, not unlimited. citeturn1search17turn1search15

The current official ElevenLabs changelog (September 28, 2026) adds **Eleven v4** and **Eleven v4 Turbo**. v4 is available through the Text to Dialogue API, while v4 Turbo is intended for realtime agent/interactive use through WebSocket. This is directly relevant to Hariom AI's planned voice-agent layer. citeturn1search10

### Gemini API status correction — 2.0 models are shut down
Google's official Gemini API release notes state that `gemini-2.0-flash`, `gemini-2.0-flash-001`, `gemini-2.0-flash-lite`, and `gemini-2.0-flash-lite-001` were shut down on **June 1, 2026**. Hariom AI must not add these model IDs as free fallbacks; migrations should use currently supported models such as Gemini 3.5 Flash or Gemini 3.1 Flash-Lite where appropriate. citeturn1search18

### Gemini 3.8 TTS GA status
Google's official release notes confirm `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts` reached GA on **September 22, 2026**, including the Gemini API Voices endpoint. The catalog already tracks the Lite TTS free-tier capability; the full 3.8 TTS model should not be labeled free unless its current pricing row explicitly grants free-tier access. citeturn1search18

### No new recurring-free hosted video-generation API verified
Current official/vendor evidence reviewed in this run did not establish a new recurring-free public video-generation API that meets the catalog's verification bar. Do not promote product-level free video features or promotional credits into the automatic API router without an explicit free API quota.