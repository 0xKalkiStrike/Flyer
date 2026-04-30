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


async def verification_pipeline(filepath: str, website_url: str, username: Optional[str], password: Optional[str], products: Optional[str] = None):
    start_time = datetime.utcnow()
    if products:
        # Use manually provided products
        product_list = [p.strip() for p in products.split('\n') if p.strip()]
        if not product_list:
            product_list = ["Unknown Product"]
    elif filepath:
        # Extract products from flyer using OCR
        extractor = OCRExtractor()
        file_suffix = filepath.lower().split(".")[-1]
        
        if file_suffix == "pdf":
            raw_lines = extractor.extract_from_pdf(filepath)
            product_list = cleanup_product_text(raw_lines)[:30]
            search_prefix = ""
        else:
            discovery = extractor.extract_from_image(filepath)
            products_detected = discovery.get("products", [])
            brand = discovery.get("brand", "Unknown")
            category = discovery.get("category", "Unknown")
            
            # Combine brand and category for better search results
            search_prefix = ""
            if brand != "Unknown":
                search_prefix += f"{brand} "
            if category != "Unknown":
                search_prefix += f"{category} "
                
            product_list = products_detected if products_detected else ["Unknown Product"]

        if not product_list:
            product_list = ["Unknown Product"]
    else:
        raise RuntimeError("Either upload a flyer for OCR or provide a manual product list.")

    engine = PlaywrightEngine()
    await engine.start()

    login_used = False
    if username and password:
        login_used = await engine.login(website_url, username, password)

    results = []
    for product in product_list:
        # Use discovery prefix if available
        search_query = f"{search_prefix}{product}" if search_prefix else product
        res = await engine.verify_product(search_query, website_url)
        # Restore original product name for the report
        res["product_name"] = product
        results.append(res)

    await engine.close()

    record = {
        "flyer_name": Path(filepath).name if filepath else "Manual Input",
        "website_url": website_url,
        "login_used": login_used,
        "started_at": start_time.isoformat() + "Z",
        "completed_at": datetime.utcnow().isoformat() + "Z",
        "summary": build_summary(results),
        "results": results
    }
    append_verification_result(record)
    return record


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
