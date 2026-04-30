import asyncio
import sys
from pathlib import Path

# Add backend to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from backend.api.routes import verification_pipeline

async def test():
    image_path = "uploads/smoxy-121-125.jpg"
    website_url = "https://gothamdistro.com"
    try:
        print("Starting pipeline test...")
        record = await verification_pipeline(image_path, website_url, None, None)
        print("\nPipeline Complete!")
        print(f"Brand: {record.get('brand')}")
        print(f"Category: {record.get('category')}")
        print(f"Products Matched: {len(record.get('results', []))}")
        for res in record.get('results', []):
            print(f"- {res['product_name']}: {res['issue_type']}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
