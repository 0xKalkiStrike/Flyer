from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException, Depends, Request
from typing import Optional
from datetime import datetime
from pathlib import Path
import os
import shutil
import re

from .extractor import OCRExtractor
from .playwright_engine import PlaywrightEngine
from .json_store import append_verification_result, load_verification_results

router = APIRouter()

async def get_optional_file(request: Request) -> Optional[UploadFile]:
    form = await request.form()
    flyer = form.get("flyer")
    return flyer if flyer and flyer.filename else None

SQL_TABLE_QUERIES = """
CREATE TABLE upload_history (
  flyer_id INT PRIMARY KEY AUTO_INCREMENT,
  flyer_name VARCHAR(255) NOT NULL,
  upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  uploaded_by VARCHAR(255)
);

CREATE TABLE website_verification_data (
  id INT PRIMARY KEY AUTO_INCREMENT,
  target_url VARCHAR(512) NOT NULL,
  login_used BOOLEAN DEFAULT FALSE,
  flyer_id INT,
  FOREIGN KEY (flyer_id) REFERENCES upload_history(flyer_id)
);

CREATE TABLE product_verification_results (
  id INT PRIMARY KEY AUTO_INCREMENT,
  flyer_id INT,
  product_name VARCHAR(255) NOT NULL,
  status VARCHAR(50) NOT NULL,
  issue_type VARCHAR(100),
  product_url VARCHAR(512),
  screenshot_path VARCHAR(512),
  verification_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (flyer_id) REFERENCES upload_history(flyer_id)
);
"""


@router.get("/health")
def health_check():
    return {
        "status": "success",
        "message": "API routes working successfully"
    }


def cleanup_product_text(lines: list[str]) -> list[str]:
    cleaned = []
    # Patterns to exclude
    exclude_patterns = [
        r'http[s]?://',           # URLs
        r'www\.',                 # URLs
        r'\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}', # Phone numbers
        r'\d{3}[-\.\s]??\d{4}',   # Short phone/ID
        r'^\d+$',                  # Just numbers
        r'email|contact|phone|cell|office|address|@', # Contact words
        r'\.com|\.net|\.org',     # TLDs
    ]
    
    seen = set()
    for line in lines:
        line = line.strip()
        # Basic character cleanup
        normalized = re.sub(r"[^A-Za-z0-9 \-&'\/]", " ", line)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        if len(normalized) < 5:
            continue
            
        # Check against exclusion patterns
        should_exclude = False
        for pattern in exclude_patterns:
            if re.search(pattern, normalized, re.IGNORECASE):
                should_exclude = True
                break
        
        if not should_exclude and normalized.lower() not in seen:
            cleaned.append(normalized)
            seen.add(normalized.lower())
            
    return cleaned


def build_summary(results: list[dict]) -> dict:
    counts = {
        "Available": 0,
        "Out of Stock": 0,
        "Discontinued": 0,
        "Product Missing": 0,
        "Restricted": 0,
        "Broken Product Page": 0,
        "Unknown": 0,
    }
    for item in results:
        issue = item.get("issue_type") or "Unknown"
        if issue not in counts:
            counts[issue] = 0
        counts[issue] += 1

    total = len(results)
    summary = {
        "total_products": total,
        "counts": counts,
        "errors": [item for item in results if item.get("status") != "Verified" or item.get("issue_type") != "Available"]
    }
    return summary


async def verification_pipeline(filepath: str, website_url: str, username: Optional[str], password: Optional[str], manual_products: Optional[str] = None):
    """The Autonomous Discovery Pipeline: Website-driven verification."""
    from .navigator import WebsiteNavigator
    from .scraper import ProductScraper
    from .matcher import ProductMatcher
    from .status_extractor import StatusExtractor
    
    start_time = datetime.utcnow()
    
    # 1. OCR Discovery (Hints Only)
    brand_hint = "Unknown"
    category_hint = "Unknown"
    flyer_hints = []
    
    if filepath:
        extractor = OCRExtractor()
        discovery = extractor.extract_from_image(filepath)
        brand_hint = discovery.get("brand_hint", "Unknown")
        category_hint = discovery.get("category_hint", "Unknown")
        flyer_hints = discovery.get("product_hints", [])
    elif manual_products:
        flyer_hints = [p.strip() for p in manual_products.split('\n') if p.strip()]
    
    if not flyer_hints:
        raise RuntimeError("No product hints found from flyer or manual input.")

    # 2. Start Playwright
    engine = PlaywrightEngine()
    await engine.start()
    
    try:
        # 3. Navigate to Brand and Category
        main_page = await engine.context.new_page()
        navigator = WebsiteNavigator(main_page)
        scraper = ProductScraper(main_page)
        matcher = ProductMatcher()
        
        # Step 2.1 - Brand Search
        brand_found = await navigator.search_and_navigate_brand(brand_hint, website_url)
        
        # Step 2.2 - Category Navigation
        category_found = await navigator.find_category_on_page(category_hint)
        
        # 4. Product Discovery from Website
        all_website_products = await scraper.scrape_category_products()
        
        if not all_website_products:
            # Fallback: if no products found in category, try to search for the first hint
            logger.info("No products in category, falling back to direct search.")
            await main_page.goto(f"{website_url}/?s={flyer_hints[0]}", wait_until='networkidle')
            all_website_products = await scraper.scrape_category_products()

        # 5. Product Matching (Flyer -> Website)
        matches = matcher.match_products(flyer_hints, all_website_products)
        
        # 6. Stock Status Extraction
        final_results = []
        for match in matches:
            hint = match["flyer_hint"]
            product = match["matched_product"]
            
            # Open product page to get deep stock status
            status = await engine.verify_product_stock(product["url"])
            
            final_results.append({
                "product_name": product["name"],
                "flyer_hint": hint,
                "status": "Verified",
                "issue_type": status.replace("_", " ").title(),
                "product_url": product["url"],
                "match_score": match["score"],
                "match_type": match["match_type"]
            })

        # Add missing products
        matched_hints = {m["flyer_hint"] for m in matches}
        for hint in flyer_hints:
            if hint not in matched_hints:
                final_results.append({
                    "product_name": hint,
                    "status": "Not Found",
                    "issue_type": "Product Missing",
                    "product_url": None
                })

        record = {
            "flyer_name": Path(filepath).name if filepath else "Manual Input",
            "website_url": website_url,
            "brand": brand_hint,
            "category": category_hint,
            "started_at": start_time.isoformat() + "Z",
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "summary": build_summary(final_results),
            "results": final_results
        }
        append_verification_result(record)
        return record

    finally:
        await engine.close()


@router.post("/start-verification")
async def start_verification(
    request: Request,
    website_url: str = Form(...),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    products: Optional[str] = Form(None),
    flyer: Optional[UploadFile] = Depends(get_optional_file)
):
    """
    Main endpoint for flyer product verification.
    Accepts either an uploaded flyer or a manual product list.
    """
    if flyer:
        os.makedirs("uploads", exist_ok=True)
        file_path = f"uploads/{flyer.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(flyer.file, buffer)
    else:
        file_path = None

    if not flyer and not products:
        raise HTTPException(status_code=400, detail="Upload a flyer or provide manual product names.")

    try:
        record = await verification_pipeline(file_path, website_url, username, password, products)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "completed",
        "flyer_name": flyer.filename if flyer else None,
        "website_url": website_url,
        "login_used": True if username and password else False,
        "message": "Verification completed live in a visible browser.",
        "report": record,
        "sql_help": SQL_TABLE_QUERIES
    }


@router.post("/start-verification-manual")
async def start_verification_manual(
    website_url: str = Form(...),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    products: str = Form(...)
):
    """
    Alternative endpoint for manual product verification without flyer upload.
    """
    try:
        record = await verification_pipeline(None, website_url, username, password, products)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "completed",
        "flyer_name": None,
        "website_url": website_url,
        "login_used": True if username and password else False,
        "message": "Verification completed live in a visible browser.",
        "report": record,
        "sql_help": SQL_TABLE_QUERIES
    }


@router.get("/results")
def get_results(latest: bool = Query(False)):
    results = load_verification_results()
    if latest and results:
        return results[-1]
    return results


@router.get("/reports")
def get_reports():
    results = load_verification_results()
    return {
        "status": "success",
        "reports_saved": len(results),
        "latest_report": results[-1] if results else None
    }


@router.get("/sql-help")
def get_sql_help():
    return {
        "status": "success",
        "sql": SQL_TABLE_QUERIES
    }


@router.get("/logs")
def get_logs():
    return {
        "status": "success",
        "message": "Logs endpoint ready"
    }
