from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.api.routes import router as api_router

app = FastAPI(
    title="Flyer Product Verification System",
    description="Production-ready backend for flyer product verification using OCR + Playwright + MySQL",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)

app.mount("/", StaticFiles(directory=str(BASE_DIR / "frontend" / "public"), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
"""
backend/
│
├── api/
│   ├── __init__.py
│   ├── routes.py
│   ├── upload.py
│   ├── verification.py
│   └── reports.py
│
├── automation/
│   ├── __init__.py
│   ├── playwright_engine.py
│   ├── login_handler.py
│   └── product_checker.py
│
├── ocr/
│   ├── __init__.py
│   ├── pdf_reader.py
│   ├── image_reader.py
│   └── extractor.py
│
├── database/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   └── queries.py
│
├── reports/
│   ├── __init__.py
│   ├── pdf_report.py
│   ├── excel_report.py
│   └── csv_report.py
│
├── queue/
│   ├── __init__.py
│   ├── processor.py
│   └── scheduler.py
│
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   ├── config.py
│   └── helpers.py
│
├── uploads/
├── screenshots/
├── logs/
├── main.py
├── requirements.txt
└── .env
"""
