# Free AI Provider Catalog

Last audited: 2026-09-26

This catalog is for Hariom AI's personal-use, Windows-first provider router. It separates recurring free tiers from one-time credits/trials.

## A. Recurring/free access worth checking

| Provider | Type | Current free access | Card | Hariom AI use |
|---|---|---|---|---|
| Google AI Studio / Gemini | LLM + multimodal | Free tier exists for selected Gemini models; limits vary by model/project | No | Primary chat, planning, multimodal |
| Groq | LLM | Free API tier; limits vary by model | No | Fast coding/chat fallback |
| Mistral | LLM | Free API mode with limits | No | Coding/planning fallback |
| OpenRouter | LLM gateway | Free-model pool and free router; limits/models rotate | No | Large fallback pool |
| Cloudflare Workers AI | LLM/image/audio | 10,000 Neurons/day on Workers Free; model availability varies | No for Free plan | Image/audio/LLM experiments |
| Hugging Face Inference Providers | Multi-model | Free users receive a small monthly credit; usage beyond credits is paid | No for free access | Experimental model access |
| Cohere | LLM/rerank/embeddings | Free/evaluation access with limits | No | Rerank/LLM backup |
| Pexels | Stock media | Free API quota | No | Photos + videos |
| Pixabay | Stock media | Free API quota | No | Photos + videos fallback |

## B. Promo / trial credit — useful but NOT permanent free

| Provider | Type | Notes |
|---|---|---|
| Cerebras | LLM | Free/trial access can depend on current account offer; do not assume permanent free |
| NVIDIA | LLM/image/video ecosystem | Current model/catalog access and credits vary; verify account-specific offer |
| Replicate | Image/video/audio | New-account credits/trials may be available; usage after credits is paid |
| Runway | Video | Trial/free credits may exist; API usage is normally paid |
| fal.ai | Image/video/audio | Promotional/trial credits may be available; normally paid after credits |

## C. Important rules

1. Never commit API keys.
2. Never treat a one-time credit as a permanent free tier.
3. Check provider pricing/terms before enabling a provider for automatic fallback.
4. The router must stop on exhausted quota instead of causing unexpected charges.
5. Free model names and quotas change; verify before hardcoding them.
6. For card-required services, keep billing disabled or spending limits at zero where the provider supports that control.

## Current 2026 findings

- Google currently lists a Free Tier for Gemini 3.7 Flash and other selected models.
- Cloudflare currently gives 10,000 free Neurons/day on Workers Free, while some high-resource models require Workers Paid.
- Hugging Face currently gives Free users $0.10/month of Inference Provider credits; extra usage can become billable.
- Community-maintained free-API catalogs show additional providers, but Hariom AI should only integrate a provider after its own official pricing/terms are verified.

## Planned router policy

```
Task
  -> capability filter
  -> free/paid classification
  -> provider health
  -> quota/cooldown
  -> selected provider
  -> fallback
  -> stop before unexpected billing
```

This file is a discovery catalog, not a guarantee that every provider is available in every country/account.
