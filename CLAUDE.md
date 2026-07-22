# Community Trust Creative Agent — Master Project Briefing
## Mettics Consulting | Track 1 | Intern: Aditya Tyagi | 2026

---

## Mission
Build an autonomous AI agent that takes a company name and location,
finds their website autonomously, scrapes it for brand intelligence,
and generates a complete localized ad campaign across Meta, TikTok,
and LinkedIn — including real AI generated images — with zero manual
input beyond the initial company name and location.

This is Track 1 of the Mettics AI Advertising Agent Program.
The end product is a production ready tool that any Mettics consultant
can use to onboard a new SMB client and generate a full campaign in
under 60 seconds.

---

## Current State (What Is Built And Working)
- Web app (app.py, FastAPI) is the primary interface — `uvicorn app:app`
- Stage 1: DuckDuckGo search finds the business website; user confirms URL in the browser
- Stage 2: BeautifulSoup scrapes H1/H2/paragraphs + subpages, real product photos, and brand signals
- Stage 3: STRANDS MULTI-AGENT pipeline generates the campaign (see below)
- Stage 4: Python validates every field; json_repair recovers malformed LLM JSON
- Stage 5: Fal.ai generates a real, designed ad image per variant (edit real product
  photos for retail; generate on-brand hero images for other industries) + 4x upscale
- Stage 6: meta.md + campaign.json saved automatically; images promoted on save
- Config: config.json swaps AI provider, image model, and multi-agent on/off in one line
- GitHub: All work on feat/creative-engine branch of metticsai/intern-agents

### The live multi-agent pipeline (Strands SDK)
A code-based supervisor (the web request handler) orchestrates four specialist agents;
HITL gates live in the browser. If any agent fails it falls back to a single-call hybrid
path so the app never breaks. Toggle with `ai_generation.use_agents`.
- Brand Intelligence Agent (Claude Sonnet) → structured brand brief
- Copy Generation Agent (Claude Sonnet) → 3 strategic variants (tuned image-prompt rules)
- Platform Spec Agent (Python) → character-limit + CTA validation
- Compliance Agent (Claude Haiku) → real PASS/FLAG/REJECT per variant

Verified end-to-end on three industries: retail (The Urban Geek — edited product photos),
food_beverage (Sense of Thai — generated dishes, Book Now), home_services (Pioneer
Plumbing — generated technician scenes, Get Quote/Call Now).

---

## Architecture (Current — Multi-Agent Pipeline + Hybrid Fallback)

Python handles all mechanical stages. A code-based supervisor orchestrates the Strands
specialist agents for the creative work; if any agent fails, the system falls back to a
single-call hybrid path. Deliberate Mettics tradeoff: richer architecture, without
sacrificing reliability, cost control, or demo predictability.
INPUT: Company Name + Location
↓
STAGE 1 — SEARCH (Python/DuckDuckGo)

Search for company name + location
Return top 3 results
User confirms which URL to use (browser)
↓
STAGE 2 — SCRAPE (Python/BeautifulSoup)
Fetch homepage + About/Services/Reviews subpages
Extract H1/H2/paragraphs, real product photos, brand signals
Detect industry from content + company name
Fail gracefully if wrong page
↓
STAGE 3 — MULTI-AGENT GENERATION (Strands SDK)
Supervisor → Brand Intel (Sonnet) → Copy Gen (Sonnet)
          → Platform Spec (Python) → Compliance (Haiku)
Falls back to single-call hybrid generation on any failure
↓
STAGE 4 — VALIDATE OUTPUT (Python)
json_repair recovers malformed LLM JSON (unescaped quotes, trailing commas)
Validate all required fields exist; auto-retry once
↓
STAGE 5 — IMAGE GENERATION (Fal.ai)
Retail: edit real product photos (flux-pro/kontext); else generate (flux-pro/v1.1)
Design overlay (Pillow) + 4x upscale (aura-sr); one finished image per variant
↓
STAGE 6 — SAVE OUTPUT (Python)
Save meta.md, tiktok.md, linkedin.md, campaign.json
Folder named dynamically from company name
↓
OUTPUT: output/{company}_v1/ with all campaign files


---

## Target Architecture (What We Are Building Toward)

Based on the Mettics Agentic Creative Generator Architecture doc,
the final system is a multi-agent supervisor/worker pipeline:
SUPERVISOR AGENT
Orchestrates full workflow, manages state, routes tasks
↓
┌─────────────────┬──────────────────┬──────────────────┐
↓                 ↓                  ↓                  ↓
BRAND            COPY GEN         PLATFORM SPEC      COMPLIANCE
INTEL AGENT      AGENT            AGENT              AGENT
Scrapes site     Generates        Enforces char      Validates brand
Extracts:        3-5 variants     limits, format     safety, tone,

Voice          per platform     rules, hashtags,   policy, accuracy
USPs           Uses few-shot    keywords           Pass/Flag/Reject
Products       prompting
Visual ID      Chain of thought
Audience       Temperature 0.7-0.9


### LLM Selection Per Task (From Architecture Doc)
- Brand analysis + extraction: Claude Sonnet 4
- Creative copy generation: Claude Sonnet 4 / Opus 4
- Platform spec validation: Amazon Nova Lite (fast, cheap)
- Compliance checking: Claude Haiku 4.5 (fast classification)
- Orchestration/routing: Claude Haiku 4.5

### Human In The Loop Gates (HITL — Required)
1. Pre-scrape confirmation: Agent shows discovered URL before crawling
2. Brand identity approval: User validates extracted brand brief
3. Creative review gate: User approves/edits/rejects copy before saving
4. Progressive autonomy: After 10+ approved campaigns, auto-approve safe variants
5. NEVER auto-publish without at least one human touchpoint

---

## Platform Specs (From Architecture Doc)

### Meta/Instagram
- Hook: under 125 characters, scroll stopping, emotional trigger
- Body: 2-3 short sentences, visual and emotional
- CTA: short and direct (Book Now, Call Us Today)
- Headline: 40 chars max
- Image: hyper-local, brand specific, 4:5 ratio for feed

### TikTok
- Hook: pattern interrupt in first 2 seconds, casual, unexpected
- Script: 3-4 lines written like a person talking not an ad
- Caption: 150 chars max
- CTA: conversational (Link in bio, Comment below)
- Image: dynamic, energetic, UGC style

### LinkedIn
- Hook: professional problem or story opener
- Body: 3-4 credibility building sentences, up to 1300 chars
- CTA: professional (Learn more, Let's connect)
- Image: clean, professional, data forward

### Google (Future)
- 15 Headlines (30 chars each)
- 4 Descriptions (90 chars each)
- Keyword rich, benefit driven, strong CTAs

### Amazon (Future)
- Sponsored Brands: 50 char headline
- DSP Display: 25-50 char headline, 90 char body
- Purchase intent language, Prime eligibility, deal callouts

---

## File Structure
zero-to-one-engine/
├── main.py              # Full pipeline entry point — run this
├── system_prompt.txt    # Lean AI instructions for copy generation
├── PROMPTS.md           # Full prompt documentation (Mettics IP)
├── CLAUDE.md            # This file — full project briefing
├── DESIGN.md            # Architecture design document
├── config.json          # AI provider + image model settings
├── .env                 # API keys (never committed to GitHub)
├── .gitignore           # Excludes .env permanently
├── client_assets/
│   └── brief.txt        # Optional client brief fallback
└── output/
└── {company}_v1/
├── meta.md
├── tiktok.md
├── linkedin.md
├── campaign.json
└── images/
├── meta.jpg
├── tiktok.jpg
└── linkedin.jpg

---

## Config (config.json)
```json
{
  "ai_generation": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
    "use_agents": true
  },
  "image_generation": {
    "enabled": true,
    "provider": "fal",
    "model": "flux-pro/v1.1",
    "cost_per_image": 0.025,
    "resolution": "1024x1024"
  },
  "platforms": ["meta"],
  "output_format": ["markdown", "json"]
}
```

- `ai_generation.provider` — "anthropic" (active) or "gemini"; swappable in one line.
- `ai_generation.use_agents` — true runs the Strands multi-agent pipeline; false forces the hybrid single-call path.
- `image_generation.enabled` — false skips image generation (text-only, faster/cheaper).
No code changes needed — config.json controls everything.

---

## API Keys (.env)
ANTHROPIC_API_KEY=...  # Active — Claude Sonnet (copy/brand) + Haiku (compliance)
FAL_KEY=...            # Active — Fal.ai image generation, editing, upscaling
GEMINI_API_KEY=...     # Optional — only if provider switched to gemini

---

## How To Run
```bash
cd ~/Desktop/zero-to-one-engine
python3 -m pip install -r requirements.txt   # first time only
python3 -m uvicorn app:app --reload --port 8000
```
Open http://127.0.0.1:8000, enter a company name + location, confirm the URL, then
review and export. (CLI path still exists: `python3 main.py` for the hybrid pipeline,
`python3 run_agents.py` for the standalone multi-agent CLI.)

---

## Demo Command (Claude Code Interactive Mode)
Agent, we just onboarded Pioneer Plumbers in Brambleton VA.
Find their information autonomously and generate a complete
Meta, TikTok, and LinkedIn campaign in the output folder.

---

## GitHub
- Repo: github.com/metticsai/intern-agents
- Branch: feat/creative-engine
- Commit style: feat/creative-engine: description of change
- Rule: NEVER commit .env — gitignore is permanently configured
- PRs required every Friday afternoon

---

## What Is Working Right Now
- Full end-to-end web app: `uvicorn app:app` → search → confirm URL → generate → review → export
- Strands multi-agent pipeline (Brand Intel + Copy Gen on Sonnet, Compliance on Haiku)
- Real compliance verdicts (PASS/FLAG/REJECT) rendered as badges on the review cards
- Fal.ai real designed ad images per variant — flux-pro/kontext (edit real retail photos),
  flux-pro/v1.1 (generate), aura-sr (4x upscale)
- Three distinct designed layouts (social proof / bold / editorial) + premium type
  (Avenir Next, Didot); emojis stripped from overlay text; no cut-off copy
- Industry detection from scraped content AND company name (survives JS-rendered sites)
- json_repair + auto-retry recover malformed LLM output; hybrid fallback if agents fail
- Human-in-the-loop in the browser: URL confirmation + creative review; never auto-publishes
- Graceful error handling at every stage; requirements.txt for one-command setup

---

## Current Blockers
- Google and Amazon platforms not yet added (Meta is the focused demo scope; TikTok/LinkedIn scaffolded)
- Benign `Event loop is closed` log warning from the async SDK client (cosmetic, never reaches the browser)
- PR not yet opened (branch is many commits ahead)

---

## Immediate Next Steps (This Week)
1. Open the PR (overdue per Mettics Friday policy)
2. Optional: suppress the async-cleanup log warning
3. Optional: expand active platforms beyond Meta (TikTok/LinkedIn already scaffolded)

---

## Medium Term (Weeks 5-6)
1. Build Brand Intelligence Agent as separate module
2. Add compliance validation agent
3. Expand to Google Ads platform
4. Add few-shot prompting with top performing ad examples
5. Prompt caching for brand briefs (saves 60-70% token costs)

---

## Consultant Dashboard (Weeks 6-7)
- React/Next.js or simple HTML front end
- Input: Company name + location
- Display: All three platform ads side by side
- Actions: Approve / Edit / Reject per variation
- Export: Download campaign.json for platform upload
- campaign.json structure already ready for this

---

## End Goal (Week 8 Handoff)
A production ready tool where any Mettics consultant can:
1. Type a company name and location
2. Watch the agent find, scrape, and analyze the business
3. Review and approve generated campaigns
4. Download platform ready ad packages
5. All in under 60 seconds, at ~$0.03 per campaign

The system must work for any SMB in any industry in any US location.
Pioneer Plumbers in Brambleton VA is the primary test client.
Must be tested on at least 2-3 different business types before handoff.

---

## Key Decisions Made
- Multi-agent pipeline is the live system, with the hybrid single-call path as an
  automatic fallback: get the richer architecture without risking reliability
- Code-based supervisor (not an LLM supervisor): HITL gates live in the browser, so the
  web handler orchestrates the agents — more reliable and easier to instrument
- Anthropic (Claude) as the active provider: Sonnet for creative work, Haiku for compliance
- Fal.ai for images: kontext to edit real retail product photos, v1.1 to generate,
  aura-sr to upscale
- Edit real photos only for product industries; generate on-brand hero images for
  food/service/health (their site photos are storefronts/stock people/press logos)
- Industry detection scores the company name too, so JS-rendered sites still classify
- system_prompt.txt separate from PROMPTS.md: Reduces token consumption
- config.json for all provider settings: One line swap, no code changes
- .env permanently gitignored: Fixed malformed .gitignore (.env - → .env)

---

## Mettics Philosophy (The Samyak Standard)
- Right Effort and precision
- Eliminate technical debt before it is written
- Build precisely what is needed, no more no less
- Scalable products with complete transparency for SMB owners
- Tooling First: use Gemini, Claude Code, sandboxes aggressively
- Friday Demo-or-Die: working code every Friday at 3pm, no slide decks