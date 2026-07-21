"""
app.py — Mettics Creative Agent web frontend.
Run: python3.11 -m uvicorn app:app --reload --port 8000
"""

import os
import uuid
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Mettics Creative Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory session store
sessions: dict = {}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/search")
async def search(request: Request):
    data = await request.json()
    company_name = data.get("company_name", "").strip()
    location = data.get("location", "").strip()
    if not company_name or not location:
        return JSONResponse({"error": "Company name and location required"}, status_code=400)

    from main import search_business
    results = search_business(company_name, location)

    session_id = str(uuid.uuid4())
    sessions[session_id] = {"company_name": company_name, "location": location}

    return {"session_id": session_id, "results": results}


@app.post("/api/scrape")
async def scrape(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    url = data.get("url", "").strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    if session_id not in sessions:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    from main import scrape_website, _detect_industry
    scraped = scrape_website(url)
    industry, image_style = _detect_industry(scraped)

    sessions[session_id].update({
        "scraped": scraped,
        "industry": industry,
        "url": url,
    })

    return {
        "industry": industry,
        "brand_signals": scraped.get("brand_signals", {}),
        "h1": scraped.get("h1", [])[:3],
        "paragraph_count": len(scraped.get("paragraphs", [])),
        "subpages": list(scraped.get("subpages", {}).keys()),
    }


@app.post("/api/generate")
async def generate(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    feedback = data.get("feedback", "")

    if session_id not in sessions:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    session = sessions[session_id]
    config = json.load(open("config.json"))

    from main import generate_campaign, validate_output
    try:
        campaign_json = generate_campaign(
            session["scraped"],
            session["company_name"],
            session["location"],
            config,
            feedback,
        )
    except Exception as e:
        return JSONResponse({"error": f"Generation failed: {e}"}, status_code=500)

    is_valid, campaign_data, val_error = validate_output(campaign_json)
    if not is_valid:
        return JSONResponse({"error": f"Validation failed: {val_error}"}, status_code=500)

    configured = config.get("platforms", ["meta"])
    campaign_data["platforms"] = {
        k: v for k, v in campaign_data["platforms"].items() if k in configured
    }

    industry = session.get("industry", "general_business")

    # Generate a real ad image for every variant so the reviewer picks from
    # actual creatives. Reuse this session's output dir across regenerations.
    if config.get("image_generation", {}).get("enabled", False):
        from main import generate_variant_images, get_output_dir
        output_dir = session.get("output_dir") or get_output_dir(session["company_name"])
        session["output_dir"] = output_dir
        os.makedirs(output_dir, exist_ok=True)
        try:
            site_photos = session.get("scraped", {}).get("images", [])
            campaign_data = generate_variant_images(
                campaign_data, output_dir, config, industry, scraped_images=site_photos)
            bust = uuid.uuid4().hex[:8]  # cache-buster so regenerated images refresh
            for pdata in campaign_data["platforms"].values():
                for vkey, vdata in pdata.items():
                    if vkey.startswith("variant_"):
                        p = vdata.get("image_path", "")
                        if p and os.path.exists(p):
                            vdata["image_url"] = f"/api/image/{p}?t={bust}"
        except Exception as e:
            return JSONResponse({"error": f"Image generation failed: {e}"}, status_code=500)

    campaign_data["_meta"] = {
        "industry": industry,
        "url": session.get("url", ""),
    }
    sessions[session_id]["campaign"] = campaign_data
    return campaign_data


@app.post("/api/save")
async def save(request: Request):
    data = await request.json()
    session_id = data.get("session_id")
    selections = data.get("selections", {})  # {"meta": "variant_1", ...}

    if session_id not in sessions:
        return JSONResponse({"error": "Session not found"}, status_code=404)

    session = sessions[session_id]
    campaign_data = json.loads(json.dumps(session["campaign"]))

    for platform_key, variant_key in selections.items():
        if platform_key in campaign_data["platforms"]:
            variants = campaign_data["platforms"][platform_key]
            if variant_key in variants:
                campaign_data["platforms"][platform_key] = variants[variant_key]

    import shutil
    from main import save_output, get_output_dir
    config = json.load(open("config.json"))
    output_dir = session.get("output_dir") or get_output_dir(session["company_name"])
    os.makedirs(f"{output_dir}/images", exist_ok=True)

    # Images were already generated per-variant at review time. Promote the
    # selected variant's image to the canonical {platform}.jpg the outputs expect.
    image_urls = {}
    for platform, pdata in campaign_data["platforms"].items():
        src = pdata.get("image_path", "")
        if src and os.path.exists(src):
            canonical = f"{output_dir}/images/{platform}.jpg"
            if os.path.abspath(src) != os.path.abspath(canonical):
                shutil.copyfile(src, canonical)
            pdata["image_path"] = canonical
            image_urls[platform] = f"/api/image/{canonical}"

    save_output(campaign_data, output_dir)

    return {
        "output_dir": output_dir,
        "image_urls": image_urls,
        "files": [f for f in ["meta.md", "tiktok.md", "linkedin.md", "campaign.json", "preview.html", "meta_export.json"]
                  if os.path.exists(f"{output_dir}/{f}")],
    }


@app.get("/api/image/{filepath:path}")
async def serve_image(filepath: str):
    if not os.path.exists(filepath):
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(filepath, media_type="image/jpeg")


@app.get("/api/download/{output_dir:path}/{filename}")
async def download(output_dir: str, filename: str):
    path = f"{output_dir}/{filename}"
    if not os.path.exists(path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(path, filename=filename)
