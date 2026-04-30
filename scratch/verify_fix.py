import sys
from pathlib import Path

# Add backend to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.api.extractor import OCRExtractor

def verify_extraction():
    extractor = OCRExtractor()
    image_path = "uploads/smoxy-121-125.jpg"
    try:
        discovery = extractor.extract_from_image(image_path)
        print(f"Brand: {discovery.get('brand')}")
        print(f"Category: {discovery.get('category')}")
        print("\nSuccessfully extracted products:")
        for p in discovery.get('products', []):
            print(f"- {p}")
    except Exception as e:
        print(f"Extraction failed: {e}")

if __name__ == "__main__":
    verify_extraction()
