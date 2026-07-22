/* ── State ────────────────────────────────────────────────── */
const state = {
  sessionId: null,
  companyName: "",
  location: "",
  campaign: null,
  selectedVariants: {},  // { meta: "variant_1" }
  outputDir: null,
  outputFiles: [],
};

/* ── View Router ──────────────────────────────────────────── */
function showView(id) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ── Toast ────────────────────────────────────────────────── */
function toast(msg, duration = 3000) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), duration);
}

/* ── Stage Progress ───────────────────────────────────────── */
function setStage(stageId, status, statusText) {
  const el = document.getElementById(stageId);
  if (!el) return;
  el.className = "stage " + (status === "done" ? "done" : status === "running" ? "active" : "");
  const badge = el.querySelector(".stage-badge");
  badge.className = "stage-badge " + status;
  badge.textContent = status === "done" ? "✓" : status === "running" ? "..." : status === "error" ? "✗" : "—";
  if (statusText) el.querySelector(".stage-status").textContent = statusText;
}

/* ── Search ───────────────────────────────────────────────── */
async function startSearch() {
  const company = document.getElementById("company-name").value.trim();
  const location = document.getElementById("location").value.trim();

  if (!company || !location) {
    toast("Enter a company name and location first");
    return;
  }

  state.companyName = company;
  state.location = location;
  state.selectedVariants = {};

  document.getElementById("btn-search").disabled = true;

  showView("view-loading");
  document.getElementById("loading-title").textContent = "Finding website...";
  document.getElementById("loading-sub").textContent = "Searching DuckDuckGo for the official site";
  setStage("stage-search", "running");

  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_name: company, location }),
    });
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    state.sessionId = data.session_id;
    setStage("stage-search", "done", "Website options found");
    showUrlSelection(data.results);
  } catch (err) {
    setStage("stage-search", "error", err.message);
    toast("Search failed: " + err.message, 4000);
    document.getElementById("btn-search").disabled = false;
    showView("view-home");
  }
}

function showUrlSelection(results) {
  document.getElementById("company-label").textContent = state.companyName;
  const list = document.getElementById("url-list");
  list.innerHTML = "";

  results.forEach((url, i) => {
    const card = document.createElement("div");
    card.className = "url-card";
    card.innerHTML = `
      <div class="url-number">${i + 1}</div>
      <div class="url-text">${url}</div>
    `;
    card.onclick = () => selectUrl(url);
    list.appendChild(card);
  });

  showView("view-urls");
}

/* ── Scrape + Generate ────────────────────────────────────── */
async function selectUrl(url) {
  showView("view-loading");
  document.getElementById("loading-title").textContent = "Reading the brand...";
  document.getElementById("loading-sub").textContent = "Scraping website content — usually under 30 seconds";

  setStage("stage-search", "done");
  setStage("stage-scrape", "running", "Fetching pages...");

  try {
    const scrapeRes = await fetch("/api/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, url }),
    });
    const scrapeData = await scrapeRes.json();
    if (scrapeData.error) throw new Error(scrapeData.error);

    setStage("stage-scrape", "done", `Found ${scrapeData.paragraph_count} content blocks`);
    setStage("stage-generate", "running", "Brand Intel + Copy Gen agents...");

    document.getElementById("loading-title").textContent = "Building your ads...";
    document.getElementById("loading-sub").textContent = "Writing copy and rendering a real image for all 3 variants — about 60 seconds";

    await runGenerate();

  } catch (err) {
    setStage("stage-scrape", "error", err.message);
    toast("Scrape failed: " + err.message, 4000);
    showView("view-home");
    document.getElementById("btn-search").disabled = false;
  }
}

async function runGenerate(feedback = "") {
  // One request now writes 3 variants AND renders a real ad image for each (~60s).
  setStage("stage-generate", "running", "Brand Intel + Copy Gen agents...");

  const imgTicks = [
    "Generating 3 ad images with Fal.ai...",
    "Upscaling to 4x resolution...",
    "Compositing headlines + CTAs...",
    "Finishing the creatives...",
  ];
  // After a few seconds, move the visual focus from copy → image generation
  const toImage = setTimeout(() => {
    setStage("stage-generate", "done", "3 variants ready");
    setStage("stage-validate", "done", "Spec + Compliance agents ✓");
    setStage("stage-image", "running", imgTicks[0]);
  }, 5000);
  let ti = 0;
  const ticker = setInterval(() => {
    ti = Math.min(ti + 1, imgTicks.length - 1);
    setStage("stage-image", "running", imgTicks[ti]);
  }, 12000);

  try {
    const genRes = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, feedback }),
    });
    const campaign = await genRes.json();
    if (campaign.error) throw new Error(campaign.error);

    clearTimeout(toImage);
    clearInterval(ticker);
    setStage("stage-generate", "done", "3 variants ready");
    setStage("stage-validate", "done", "Spec + Compliance agents ✓");
    setStage("stage-image", "done", "3 ad images ready");
    await new Promise(r => setTimeout(r, 300));

    state.campaign = campaign;
    showReview(campaign);

  } catch (err) {
    clearTimeout(toImage);
    clearInterval(ticker);
    setStage("stage-generate", "error", err.message);
    setStage("stage-image", "error", err.message);
    toast("Generation failed: " + err.message, 4000);
    showView("view-home");
    document.getElementById("btn-search").disabled = false;
  }
}

/* ── Review ───────────────────────────────────────────────── */
function showReview(campaign) {
  document.getElementById("review-company").textContent = state.companyName;

  const metaPlatform = campaign.platforms?.meta;
  const industry = campaign._meta?.industry || "general_business";
  const location = campaign.location || state.location;

  // Build a company-info object from the fields the backend actually sends
  const companyInfo = {
    name: campaign.client || state.companyName,
    website: campaign._meta?.url || "",
    location: location,
    industry: industry,
  };

  document.getElementById("review-industry").textContent = "📍 " + location;
  document.getElementById("review-signals").textContent = "🏷 " + industry.replace(/_/g, " ");

  const grid = document.getElementById("variants-grid");
  grid.innerHTML = "";

  if (metaPlatform) {
    const variants = Object.entries(metaPlatform);
    variants.forEach(([key, variant]) => {
      grid.appendChild(buildVariantCard(key, variant, companyInfo));
    });
  }

  showView("view-review");
}

const INDUSTRY_GRADIENTS = {
  food_beverage:         ["#3B1F0A", "#7C4A1E"],
  home_services:         ["#0A1F3B", "#1A3A6B"],
  health_beauty:         ["#2D0A1A", "#8B3052"],
  health_fitness:        ["#0A0A14", "#CC4A08"],
  retail:                ["#1A0A2E", "#5C3680"],
  professional_services: ["#060E2A", "#0F2460"],
  general_business:      ["#111827", "#374151"],
};

function buildVariantCard(variantKey, variant, companyInfo) {
  const wrapper = document.createElement("div");
  wrapper.className = "ig-wrapper";

  const labelMap = { variant_1: "Variant 1", variant_2: "Variant 2", variant_3: "Variant 3" };
  const angleMap = { variant_1: "Social Proof", variant_2: "Urgency", variant_3: "Story" };

  const compliance = variant.compliance || {};
  const complianceStatus = compliance.status || "pass";

  const hook     = variant.hook || "";
  const body     = variant.body || "";
  const cta      = variant.cta || "Learn More";
  const headline = variant.headline || companyInfo?.name || "";
  const rawTags  = variant.hashtags || [];
  const tagArray = Array.isArray(rawTags) ? rawTags : String(rawTags).split(/\s+/).filter(Boolean);
  const hashtags = tagArray.map(h => h.startsWith("#") ? h : `#${h}`).join(" ");
  const domain   = (companyInfo?.website || "").replace(/^https?:\/\//, "").split("/")[0];
  const industry = state.campaign?._meta?.industry || "general_business";
  const [g1, g2] = INDUSTRY_GRADIENTS[industry] || INDUSTRY_GRADIENTS.general_business;

  // Accent color per industry (matches Python palette btn colors)
  const accentMap = {
    food_beverage: "#D2781E", home_services: "#1E50B4", health_beauty: "#C8506E",
    health_fitness: "#FF5A0A", retail: "#643CA0", professional_services: "#0A2878",
    general_business: "#6366F1",
  };
  const accent = accentMap[industry] || "#6366F1";

  // Show the full copy on the review card so the consultant can read it all. Only a
  // very long body (e.g. a 1300-char LinkedIn post) is trimmed — and always on a word
  // boundary with a proper "… more", never mid-word.
  const truncBody = body.length > 400
    ? body.slice(0, 400).replace(/\s+\S*$/, "") + "… more"
    : body;
  const shortHook = hook.length > 80  ? hook.slice(0, 80)  + "…" : hook;

  wrapper.innerHTML = `
    <div class="ig-variant-label">
      <span>${labelMap[variantKey] || variantKey} · <em style="font-weight:400;font-style:normal;color:var(--text-muted)">${angleMap[variantKey]}</em></span>
      <span class="compliance-badge ${complianceStatus}">${complianceStatus.toUpperCase()}</span>
    </div>

    <div class="ig-card" id="card-${variantKey}" onclick="toggleVariant('${variantKey}', this)">

      <!-- Instagram header -->
      <div class="ig-top">
        <div class="ig-avatar"></div>
        <div>
          <div class="ig-handle">${escHtml(companyInfo?.name || state.companyName)}</div>
          <div class="ig-sponsored-tag">Sponsored</div>
        </div>
        <div style="margin-left:auto;color:#aaa;font-size:18px">&#8942;</div>
      </div>

      <!-- Real generated ad creative (headline/CTA baked in), or gradient fallback -->
      ${variant.image_url
        ? `<img class="ig-real-img" src="${variant.image_url}" alt="Ad creative for ${escHtml(headline)}">`
        : `<div class="ig-creative" style="background:linear-gradient(160deg, ${g1} 0%, ${g2} 100%)">
        <div class="ig-creative-inner">
          <div class="ig-creative-accent" style="background:${accent}"></div>
          <div class="ig-creative-headline">${escHtml(headline)}</div>
          <div class="ig-creative-hook">${escHtml(shortHook)}</div>
          <div class="ig-creative-cta" style="background:${accent}">${escHtml(cta)}</div>
        </div>
      </div>`}

      <!-- Caption below image -->
      <div class="ig-actions-row">
        <span class="ig-action-icon">♡</span>
        <span class="ig-action-icon">&#128172;</span>
        <span class="ig-action-icon">&#10148;</span>
      </div>

      <div class="ig-post-body">
        <p><strong>${escHtml(companyInfo?.name || state.companyName)}</strong> ${escHtml(truncBody)}</p>
        ${hashtags ? `<p class="ig-tags">${escHtml(hashtags)}</p>` : ""}
      </div>

      <div class="ig-footer">
        <div>
          <div class="ig-headline-small">${escHtml(headline)}</div>
          <div class="ig-domain">${escHtml(domain)}</div>
        </div>
        <div class="ig-cta-btn" style="background:${accent}">${escHtml(cta)}</div>
      </div>

      <button class="select-btn" id="selbtn-${variantKey}"
        onclick="event.stopPropagation(); toggleVariant('${variantKey}', document.getElementById('card-${variantKey}'))">
        Select this variant
      </button>
    </div>
  `;

  return wrapper;
}

function toggleVariant(variantKey, cardEl) {
  const isSelected = state.selectedVariants.meta === variantKey;

  if (isSelected) {
    delete state.selectedVariants.meta;
    cardEl.classList.remove("selected");
    document.getElementById(`selbtn-${variantKey}`).classList.remove("selected");
    document.getElementById(`selbtn-${variantKey}`).textContent = "Select this variant";
  } else {
    // Deselect previous
    Object.values(state.selectedVariants).forEach(prev => {
      const prevCard = document.getElementById(`card-${prev}`);
      const prevBtn = document.getElementById(`selbtn-${prev}`);
      if (prevCard) prevCard.classList.remove("selected");
      if (prevBtn) { prevBtn.classList.remove("selected"); prevBtn.textContent = "Select this variant"; }
    });

    state.selectedVariants.meta = variantKey;
    cardEl.classList.add("selected");
    const btn = document.getElementById(`selbtn-${variantKey}`);
    btn.classList.add("selected");
    btn.textContent = "✓ Selected";
  }

  document.getElementById("btn-save").disabled = Object.keys(state.selectedVariants).length === 0;
}

/* ── Save ─────────────────────────────────────────────────── */
async function saveSelected() {
  if (Object.keys(state.selectedVariants).length === 0) {
    toast("Select a variant first");
    return;
  }

  const btn = document.getElementById("btn-save");
  btn.disabled = true;
  btn.textContent = "Saving...";

  // Images are already rendered at review time — save just writes the files.
  try {
    const res = await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.sessionId,
        selections: state.selectedVariants,
      }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    state.outputDir = data.output_dir;
    state.outputFiles = data.files;
    showComplete(data);

  } catch (err) {
    toast("Save failed: " + err.message, 4000);
    btn.disabled = false;
    btn.innerHTML = 'Save &amp; Export <svg class="btn-icon" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>';
  }
}

/* ── Complete ─────────────────────────────────────────────── */
function showComplete(saveData) {
  // Show generated image if available
  const imgWrap = document.getElementById("generated-image-wrap");
  const imgEl = document.getElementById("generated-image");
  if (saveData.image_urls?.meta) {
    imgEl.src = saveData.image_urls.meta;
    imgWrap.style.display = "block";
  } else {
    imgWrap.style.display = "none";
  }

  document.getElementById("output-info").textContent = saveData.output_dir;

  const icons = {
    "meta.md": "📄",
    "tiktok.md": "📄",
    "linkedin.md": "📄",
    "campaign.json": "📦",
    "meta_export.json": "📤",
    "preview.html": "🖥",
  };

  const dlGrid = document.getElementById("download-links");
  dlGrid.innerHTML = "";

  saveData.files.forEach(file => {
    const a = document.createElement("a");
    a.className = "download-btn";
    a.href = `/api/download/${encodeURIComponent(saveData.output_dir)}/${file}`;
    a.download = file;
    a.innerHTML = `
      <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
      ${icons[file] || "📄"} ${file}
    `;
    dlGrid.appendChild(a);
  });

  showView("view-complete");
}

/* ── Regenerate ───────────────────────────────────────────── */
function regenerate() {
  showView("view-feedback");
}

async function regenerateWithFeedback() {
  const feedback = document.getElementById("feedback-input").value.trim();
  document.getElementById("feedback-input").value = "";

  showView("view-loading");
  document.getElementById("loading-title").textContent = "Regenerating...";
  document.getElementById("loading-sub").textContent = "Writing new variants with your feedback";

  setStage("stage-search", "done");
  setStage("stage-scrape", "done");
  setStage("stage-generate", "running", "Applying your feedback...");
  setStage("stage-validate", "pending");

  state.selectedVariants = {};
  document.getElementById("btn-save").disabled = true;

  await runGenerate(feedback);
}

/* ── Start Over ───────────────────────────────────────────── */
function startOver() {
  state.sessionId = null;
  state.campaign = null;
  state.selectedVariants = {};
  state.outputDir = null;

  document.getElementById("company-name").value = "";
  document.getElementById("location").value = "";
  document.getElementById("btn-search").disabled = false;

  setStage("stage-search", "pending", "Searching DuckDuckGo");
  setStage("stage-scrape", "pending", "Scraping site + subpages");
  setStage("stage-generate", "pending", "Brand Intel + Copy Gen agents");
  setStage("stage-validate", "pending", "Platform Spec + Compliance agents");
  setStage("stage-image", "pending", "Fal.ai + 4x upscale");

  showView("view-home");
}

/* ── Helpers ──────────────────────────────────────────────── */
function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ── Enter key on inputs ──────────────────────────────────── */
["company-name", "location"].forEach(id => {
  document.getElementById(id)?.addEventListener("keydown", e => {
    if (e.key === "Enter") startSearch();
  });
});
