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
- main.py runs a full 5 stage pipeline from company name to output files
- Stage 1: DuckDuckGo search finds the business website automatically
- Stage 2: BeautifulSoup scrapes H1, H2, paragraphs, and image URLs
- Stage 3: Gemini 2.5 Flash generates platform specific ad copy
- Stage 4: Python validates all required fields before saving
- Stage 5: Pollinations.ai generates image URLs for each platform
- Output: meta.md, tiktok.md, linkedin.md, campaign.json saved automatically
- Config: config.json makes AI provider and image model swappable in one line
- GitHub: All work on feat/creative-engine branch of metticsai/intern-agents

---

## Architecture (Current — Hybrid Pipeline)

Hardcoded Python handles all mechanical stages.
AI is called once for creative generation only.
This was a deliberate Mettics decision to reduce cost and increase reliability.
INPUT: Company Name + Location
↓
STAGE 1 — SEARCH (Python/DuckDuckGo)

Search for company name + location
Return top 3 results
User selects which URL to use
↓
STAGE 2 — SCRAPE & VALIDATE (Python/BeautifulSoup)
Fetch website HTML
Extract H1, H2, paragraphs, image URLs
Validate minimum content threshold
Fail gracefully if wrong page
↓
STAGE 3 — AI GENERATION (Gemini/Anthropic — configurable)
Send scraped data + system_prompt.txt to AI
AI returns structured JSON
Provider swappable via config.json
↓
STAGE 4 — VALIDATE OUTPUT (Python)
Strip markdown fences from AI response
Validate all platforms and required fields exist
Fail with clear error if missing
↓
STAGE 5 — IMAGE GENERATION (Pollinations.ai now / Fal.ai soon)
Build image URL from each platform image_prompt
Add image_url to campaign data
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
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  },
  "image_generation": {
    "provider": "pollinations",
    "model": "flux",
    "cost_per_image": 0.00,
    "resolution": "1024x1024"
  },
  "platforms": ["meta", "tiktok", "linkedin"],
  "output_format": ["markdown", "json"]
}
```

To swap AI provider change "provider" to "anthropic" and "model" to "claude-sonnet-4-6".
To swap image provider change "provider" to "fal" and "model" to "flux-dev".
No code changes needed — config.json controls everything.

---

## API Keys (.env)
GEMINI_API_KEY=...     # Active — Gemini 2.5 Flash text generation
ANTHROPIC_API_KEY=...  # Configured — needs credits to activate
FAL_KEY=...            # Configured — needs activation for real images

---

## How To Run
```bash
cd ~/Desktop/zero-to-one-engine
python3 main.py
```
Enter company name and location when prompted.
Select which search result to use (1, 2, or 3).
Agent handles everything else automatically.

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
- Full end to end pipeline via python3 main.py
- Gemini 2.5 Flash generating real ad copy
- All three platforms generating correctly
- JSON and Markdown output saving correctly
- Pollinations.ai image URLs generating for each platform
- Dynamic output folder from company name
- Website selection from search results
- Graceful error handling at every stage

---

## Current Blockers
- Fal.ai key needs activating for real downloaded images
- Anthropic API needs credits for Claude as text provider
- Human review gate not yet built
- Multi-agent architecture not yet implemented
- Google and Amazon platforms not yet added

---

## Immediate Next Steps (This Week)
1. Remove debug output (RAW GEMINI OUTPUT lines) from main.py
2. Add human review gate — show campaign preview, ask approve/reject
3. Activate Fal.ai for real image generation
4. Test with second client to prove generalizability
5. Commit clean version and open PR

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
- Hybrid pipeline over pure agent: More reliable, cheaper, demo predictable
- Gemini over Anthropic for now: Free tier available while credits pending
- Pollinations.ai over Fal.ai for now: Free testing before real key activated
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