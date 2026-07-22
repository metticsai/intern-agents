# Community Trust Creative Agent — Full Project Breakdown

> **Purpose of this document:** A complete, self-contained explanation of the project
> for generating a presentation. It covers what the product does, why it exists, how it
> is built, the key engineering decisions, the problems solved, and the results.
> Everything needed to build slides is here — no other files required.

---

## 1. One-Line Summary

An autonomous AI agent that turns a **company name + location** into a complete,
platform-ready **Instagram/Meta ad campaign** — finding the business's website,
reading its brand, writing three strategically distinct ad variants, and generating
real, professionally designed ad images — in about a minute, for roughly three cents.

**Program:** Mettics AI Advertising Agent Program — Track 1
**Author:** Aditya Tyagi (Intern, 2026)
**Repo/Branch:** `github.com/metticsai/intern-agents` → `feat/creative-engine`

---

## 2. The Problem It Solves

Small and mid-sized businesses (SMBs) rarely have the budget for a creative agency.
Onboarding a new SMB client and producing a full ad campaign traditionally means:

- Manually researching the business and its brand voice
- Writing copy for each platform, in each platform's format
- Sourcing or shooting product photography
- Designing the actual ad creative
- Hours of work, often hundreds of dollars, per client

**The goal:** collapse that entire workflow into a single input — a company name and
a location — so any Mettics consultant can generate a campaign-ready ad package in
under 60 seconds, at about $0.03 per campaign, for **any SMB in any industry in any US
location**.

---

## 3. What The Product Does (End-to-End Flow)

A consultant using the web app experiences six steps:

1. **Enter** a company name and location (e.g., "The Urban Geek", "Brambleton VA").
2. **Find website** — the agent searches and returns candidate URLs; the user confirms
   the correct official site (a human-in-the-loop safety gate before any scraping).
3. **Read brand** — the agent scrapes the homepage plus About/Services/Reviews subpages,
   extracting headings, body copy, real product photos, and hard "brand signals"
   (star ratings, review counts, years in business, certifications, service areas).
4. **Generate** — a four-agent pipeline runs: a Brand Intelligence agent reads the site
   into a structured brand brief, a Copy Generation agent writes three strategically
   distinct variants, a Platform Spec agent validates format/character limits, and a
   Compliance agent checks each variant for brand safety (Pass / Flag / Reject).
5. **Review** — all three variants are rendered as **real, finished ad images** the
   consultant can compare side by side, each with its own photo and its own layout.
6. **Export** — the chosen variant is saved as upload-ready files (`meta.md`,
   `campaign.json`, and the final image) for Meta Ads Manager.

**Human-in-the-loop by design:** the system never auto-publishes. There is always at
least one human touchpoint — URL confirmation and creative approval.

---

## 4. The Three Ad Variants (Creative Strategy)

Every campaign produces three variants, each a **different, deliberate persuasion angle** —
not three rewordings of the same idea. This mirrors how real performance-marketing teams
test creative:

| Variant | Strategy | What it leads with |
|---|---|---|
| **Variant 1** | **Social Proof** | Reviews, ratings, years in business — makes the buyer feel safe |
| **Variant 2** | **Pain Point / Urgency** | Speaks to the problem the customer has *right now* |
| **Variant 3** | **Personality / Story** | Who the business actually is — family-owned, local, human |

Crucially, each strategy also gets its **own visual design** (see Section 7), so the
three ads look like a creative team explored three directions — not one template with
swapped text.

---

## 5. Architecture

### 5.1 The Multi-Agent Pipeline (Strands SDK) — the live system

The web app runs on a **supervisor/worker multi-agent architecture** built with the
Strands Agents SDK, matching the Mettics Agentic Creative Generator architecture doc.
Because the human-in-the-loop gates live in the browser (URL confirmation, creative
review), the **supervisor is code-based** — the web request handler orchestrates the
specialist agents in sequence rather than an LLM driving blocking prompts. Each creative
step is a real Strands LLM agent, using the right model tier for its job:

- **Supervisor** (code-based orchestrator) — runs the four agents in order, manages state
- **Brand Intelligence Agent** (Claude Sonnet) — reads the scraped site into a structured
  brand brief: voice, value propositions, products/services, visual identity, audience,
  competitor positioning
- **Copy Generation Agent** (Claude Sonnet) — writes the three strategic variants, using
  the brand brief plus the fully tuned creative/image-prompt rules
- **Platform Spec Agent** (Python) — validates character limits and CTA rules per platform
- **Compliance Agent** (Claude Haiku) — checks each variant for brand safety, competitor
  mentions, and unsubstantiated claims → Pass / Flag / Reject

Capable models do the creative work; a fast/cheap model (Haiku) does classification and
compliance — exactly the model-per-task split the architecture doc calls for.

```
INPUT: Company Name + Location
   │
   ▼
STAGE 1 — SEARCH (Python)             Find the business website, user confirms URL
   ▼
STAGE 2 — SCRAPE (Python)             Homepage + subpages: text, photos, brand signals
   ▼
STAGE 3 — MULTI-AGENT GENERATION      Supervisor orchestrates:
           Brand Intel → Copy Gen → Platform Spec → Compliance
   ▼
STAGE 4 — VALIDATE OUTPUT (Python)    Parse, repair malformed JSON, check every field
   ▼
STAGE 5 — IMAGE GENERATION (Fal.ai)   Real ad images per variant (edit or generate)
   ▼
STAGE 6 — SAVE (Python)               meta.md, campaign.json, final image
   │
   ▼
OUTPUT: output/{company}_v1/  — upload-ready campaign package
```

### 5.2 The Hybrid Fallback (reliability guarantee)

The earlier design was a **hybrid pipeline** — deterministic Python for the mechanical
stages, a single Claude call for copy. That path still exists and now serves as an
**automatic fallback**: if any agent in the multi-agent chain fails, the system silently
drops back to the single-call hybrid path so the app never breaks mid-demo. A config flag
(`ai_generation.use_agents`) can also force the hybrid path as a kill-switch. The design
principle throughout — don't pay an LLM to do string parsing, and never let a
hallucination break file I/O — still holds: search, scraping, spec validation, JSON
repair, image compositing, and file output are all deterministic Python.

### 5.3 Configuration-Driven (no code changes to swap providers)

`config.json` controls the whole system. Swapping the AI provider or image model is a
one-line change — no code edits:

```json
{
  "ai_generation":    { "provider": "anthropic", "model": "claude-sonnet-4-6",
                        "use_agents": true },
  "image_generation": { "provider": "fal", "model": "flux-pro/v1.1",
                        "enabled": true, "cost_per_image": 0.025 },
  "platforms":        ["meta"],
  "output_format":    ["markdown", "json"]
}
```

(`use_agents: true` runs the multi-agent pipeline; `false` forces the hybrid fallback.)

---

## 6. The Image Pipeline — The Hardest & Most Differentiated Part

Generating ad copy is comparatively easy; generating images that look like **real ads
made by top creators**, not obvious AI output, is the hard problem. The solution has
several layers:

### 6.1 Use the client's real product photos (not generic AI images)

Early versions generated images from scratch, which produced generic "person at a desk"
stock-photo lookalikes that never showed the actual product. The current pipeline:

1. **Scrapes real photos** from the client's website — `og:image` plus every large
   `<img>` — then **downloads and verifies** each candidate (minimum 500×400, sane aspect
   ratio) and ranks them by resolution. Logos, icons, and sprites are filtered out.
2. **Re-shoots each photo with Fal's `flux-pro/kontext` model** used as an AI photo
   editor: the actual product/venue stays clearly recognizable, but lighting, color,
   sharpness, and composition are upgraded to premium-ad quality — with the bottom third
   of the frame kept clean for the headline.
3. **Each variant uses a *different* scraped photo**, so the three ads don't look
   identical.
4. **Falls back to fresh generation** (`flux-pro/v1.1`) only when the site has no usable
   photos, or an edit fails.

### 6.2 Quality controls

- **4× upscaling** via Fal's AuraSR model for crisp, high-resolution output
- **Negative prompts** that exclude dark/dim/gloomy/low-key/cartoon/watermark artifacts
- **A vibrance pass** (brightness/saturation/contrast) so every photo reads bright and
  appetizing rather than moody
- A hard **lighting rule** in the prompt: always bright natural daylight, never dark or
  candlelit

### 6.3 Parallel generation

All three variant images are generated **simultaneously** (thread pool) at review time,
so the consultant picks from finished creatives, and saving the chosen one is instant.

---

## 7. Making It Look Human-Designed, Not AI-Generated

This was a specific, iterative focus. Three levers took the output from "obvious template"
to "agency-quality":

### 7.1 A real type system (Pillow / PIL compositing)

The ad overlay is composited in Python using a named typographic system built from
premium fonts:

- **Avenir Next Heavy** — display headlines (modern, geometric, the weight top DTC brands use)
- **Avenir Next Demi** — eyebrows, labels, rating text
- **Avenir Next Medium** — body/hook copy
- **Didot Bold** — a high-fashion serif used for the story variant's editorial feel
- Graceful fallbacks (Helvetica Neue → Helvetica) if a font is missing on another machine

### 7.2 Three distinct layout archetypes (one per strategy)

The single biggest fix for the "template" look: each variant strategy gets its own
composition, not just different text in the same frame.

- **Social Proof layout** — a drawn 5-star row with the *real scraped* rating and review
  count ("4.9 · 4,273 reviews") above the headline. Only renders when real review data
  was actually found — never fabricated proof.
- **Bold/Urgency layout** — an oversized headline (up to 3 lines) with a brand-color
  **marker box behind the punchline** (the trailing words of the headline), plus a solid
  location badge chip.
- **Editorial/Story layout** — a centered Didot serif composition with a thin accent rule
  and an outlined (rather than filled) CTA — reads like a founder's letter.

### 7.3 Designed overlay details

- Brand-tinted gradient (derived from the industry palette) instead of a generic black bar
- Auto-fitting headline that shrinks to fit rather than truncating mid-word
- A CTA pill with a **vector-drawn arrow** (a polygon, not a font glyph — so it always renders)
- Industry-specific color palettes (7 industries) for on-brand accents

---

## 8. Industry Intelligence

The system auto-classifies the business into one of seven industries
(food & beverage, home services, health & beauty, health & fitness, professional
services, retail, general business) using **word-boundary keyword scoring** across all
industries — the highest-scoring category wins.

This classification drives:
- The **image style** (e.g., "hero shot of the dish" for food vs. "product close-up" for retail)
- The **color palette** for the overlay
- The **few-shot examples** fed to Claude (7 curated example files, one per industry)
- **CTA appropriateness** (a restaurant gets "Book Now," a store gets "Shop Now," a
  contractor gets "Get Quote")

**A real bug caught and fixed:** a Thai restaurant was misclassified as "home services"
because the old detector matched the first substring it found — the word "heat" inside
"Southern Thai heat" triggered the home-services category before food could be checked.
The rewrite to whole-word scoring across all categories fixed it.

---

## 9. Reliability Engineering (Production-Readiness)

Because this is meant to work in front of a client, several safeguards were added so
transient AI quirks never surface as errors:

- **Multi-agent with a hybrid safety net:** the four-agent pipeline is the primary path,
  but if any agent fails (API error, unusable output), the system silently falls back to
  the single-call hybrid generation — so the richer architecture never costs reliability.
- **Malformed-JSON recovery:** LLMs occasionally emit invalid JSON (unescaped quotes
  inside copy, trailing commas). The validator uses the `json_repair` library to recover
  these automatically, with a dependency-free regex cleanup as a fallback. This fixed a
  recurring crash where a headline containing a quoted word broke the whole generation.
- **Automatic retry:** if a generation is still unusable after repair, the server silently
  regenerates once instead of showing an error screen.
- **Graceful degradation** at every stage — a failed subpage scrape, a failed image edit,
  a failed compliance check, or a missing font never crashes the run; it falls back and continues.
- **Human-in-the-loop gates** — URL confirmation before scraping, creative approval before
  saving, and never auto-publishing.
- **Reproducible setup** — a pinned `requirements.txt` for one-command environment setup.

---

## 10. The Consultant Web App (UI)

A clean FastAPI + Jinja2 single-page web app (not a slide deck, not a CLI) with:

- A branded home screen (Mettics Creative Agent)
- Live progress stages that surface the agents (Find Website → Read Brand →
  Brand Intel + Copy agents → Spec + Compliance agents → Generate Image)
- A side-by-side variant review screen showing the three ads as real
  Instagram-style mockups with the generated creative in place
- **Real per-variant compliance badges** (Pass / Flag / Reject) driven by the live
  Compliance agent — e.g., it flags a variant that names a competitor brand — plus the
  industry tag and brand-signal summary
- One-click regenerate, regenerate-with-feedback, and export
- A completion screen with the final image and downloadable campaign files

---

## 11. Output Package

Each campaign saves to `output/{company}_v1/`:

- **`meta.md`** — the ad copy formatted for reading/handoff (headline, hook, body, CTA, hashtags)
- **`campaign.json`** — the structured campaign data, ready for programmatic upload to
  Meta Ads Manager
- **`images/`** — the final, designed ad creative(s)

The `campaign.json` structure is intentionally shaped for a future dashboard and for
direct platform upload.

---

## 12. Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Web framework | FastAPI + Jinja2, Uvicorn |
| Scraping | requests + BeautifulSoup (DuckDuckGo HTML search, no paid API) |
| Multi-agent orchestration | Strands Agents SDK — Brand Intel + Copy Gen (Sonnet), Compliance (Haiku), code-based supervisor |
| Copy generation | Anthropic Claude (Sonnet), provider-swappable via config |
| Image generation | Fal.ai — `flux-pro/kontext` (photo editing), `flux-pro/v1.1` (generation), AuraSR (4× upscale) |
| Image compositing | Pillow (PIL) — fully code-drawn ad overlays |
| JSON resilience | json_repair |
| Frontend | Vanilla HTML/CSS/JS (no build step) |

---

## 13. Key Engineering Decisions (and the "why")

- **Multi-agent architecture with a hybrid fallback** — the specialist-agent pipeline is
  the live system (it adds a real brand brief and real compliance checking), but it falls
  back to the single-call hybrid path on any failure, so richer architecture never costs
  reliability.
- **Code-based supervisor, not an LLM supervisor** — because the human-in-the-loop gates
  live in the browser, the web handler orchestrates the agents deterministically; that's
  more reliable and easier to instrument than an LLM making tool calls with blocking prompts.
- **Edit real photos instead of generating from scratch** — the actual product appears in
  the ad, which is the single biggest driver of "this looks real."
- **One layout per strategy** — kills the template look that makes AI creative obvious.
- **Config-driven providers** — swap Claude/Gemini or Fal/Pollinations in one line, no code changes.
- **Never fabricate social proof** — the star row only appears when real ratings were scraped.
- **`.env` permanently gitignored** — API keys are never committed; this was enforced early
  and deliberately.
- **Human-in-the-loop, never auto-publish** — trust and safety for the SMB owner.

---

## 14. The Development Story (Arc for the Presentation)

The project evolved through clear phases, visible in the commit history:

1. **Foundation** — a hardcoded scraping + validation pipeline; prove the mechanical stages work.
2. **Creative generation** — add AI copy generation, website selection, provider config.
3. **Multi-platform + intelligence** — TikTok/LinkedIn support, industry detection, few-shot examples.
4. **Multi-agent architecture (CLI)** — Strands supervisor/worker agents, first built as a
   separate command-line pipeline.
5. **Real images** — Fal.ai integration, negative prompts, upscaling, designed overlays.
6. **The web app** — a consultant-facing UI replacing the CLI.
7. **The polish push (demo-readiness):**
   - Generate all three variant images up front so the user picks from real creatives
   - Fix industry misclassification and dark/moody images
   - Remix real site photos via Kontext photo editing
   - Three distinct designed layouts to kill the template look
   - A premium type system (Avenir Next / Didot)
   - Bulletproof JSON recovery + auto-retry so nothing breaks mid-demo
8. **Multi-agent integration** — wired the Strands agents into the live web app behind a
   code-based supervisor, with the hybrid pipeline retained as an automatic fallback, so
   the production system now *is* the multi-agent architecture the requirements call for.

---

## 15. Results & Impact

- **Time:** company name → full designed campaign in ~60 seconds
- **Cost:** roughly $0.03 per campaign (about $0.025 per image)
- **Quality:** ads feature the client's *actual* product, premium typography, and three
  genuinely different creative directions — not obvious AI output
- **Generality:** works across industries (validated on home services, food & beverage,
  and retail) and any US location
- **Reliability:** recovers automatically from malformed AI output; never auto-publishes;
  human approval built in

---

## 16. What's Next (Roadmap)

- Expand beyond Meta to the already-scaffolded TikTok and LinkedIn outputs, plus Google
  and Amazon ad formats
- A consultant dashboard with approve/edit/reject per variant and one-click export
- Progressive autonomy — after enough approved campaigns, auto-approve clearly-safe variants
- Prompt caching for brand briefs to cut token costs further
- Tuning image composition so the product sits even higher/cleaner in frame

---

## 17. What This Demonstrates (Skills / Talking Points)

- **AI systems engineering** — orchestrating multiple models (Claude for copy, Fal for
  images) into one reliable pipeline
- **Prompt engineering** — strict structured-output prompts, few-shot examples, negative
  prompts, per-industry style guidance
- **Multi-agent design** — a working supervisor/worker system on the Strands SDK, with a
  code-based supervisor and the right model tier per agent (Sonnet for creative work,
  Haiku for compliance), driving a real web app rather than a toy demo
- **Production reliability** — a multi-agent primary path with an automatic hybrid
  fallback, malformed-output recovery, retries, and graceful degradation at every stage
- **Design/typography in code** — building genuinely premium ad creative programmatically
  with Pillow
- **Product thinking** — human-in-the-loop safety, config-driven flexibility, a real
  consultant-facing UI, cost discipline
- **Debugging judgment** — root-causing subtle bugs (substring industry misclassification,
  unescaped-quote JSON crashes) rather than patching symptoms
