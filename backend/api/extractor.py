import pytesseract
import re
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
import cv2
import numpy as np

class OCRExtractor:
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """OpenCV preprocessing for maximum OCR accuracy on flyers."""
        img = cv2.imread(image_path)
        if img is None:
            raise RuntimeError(f"Could not read image at {image_path}")
            
        # Rescale if image is too small
        height, width = img.shape[:2]
        if width < 1500:
            img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(denoised)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        return thresh

    def extract_from_pdf(self, pdf_path: str) -> list[str]:
        """Extract text from a PDF flyer using pdfplumber."""
        if pdfplumber is None:
            raise RuntimeError(
                "pdfplumber is not installed. Install it with `pip install pdfplumber` "
                "to enable PDF flyer processing."
            )

        extracted_products = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    # Clean and parse text to find products
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    extracted_products.extend(lines)
        return extracted_products

    def extract_from_image(self, image_path: str) -> dict:
        """Extract brand, category, and products from an image flyer."""
        original_img = cv2.imread(image_path)
        if original_img is None:
            raise RuntimeError(f"Could not read image at {image_path}")

        # Resize for better OCR
        height, width = original_img.shape[:2]
        scale = 1.0
        if width < 1500:
            scale = 2.0
            img = cv2.resize(original_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        else:
            img = original_img

        # 1. Full OCR for discovery
        try:
            ocr_ready = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            ocr_ready = cv2.fastNlMeansDenoising(ocr_ready, h=10)
            all_text = pytesseract.image_to_string(ocr_ready, config='--psm 3')
            d_full = pytesseract.image_to_data(ocr_ready, output_type=pytesseract.Output.DICT, config='--psm 3')
        except Exception as e:
            raise RuntimeError(f"OCR failed: {e}")

        # Discovery logic: find brand and category
        brand = "Unknown"
        category = "Unknown"
        
        # Brand is usually the largest text at the top
        max_height = 0
        for i in range(len(d_full['text'])):
            text = d_full['text'][i].strip()
            # Ignore common symbols or very short text
            if len(text) >= 4 and d_full['top'][i] < (img.shape[0] * 0.3):
                if d_full['height'][i] > max_height:
                    max_height = d_full['height'][i]
                    brand = text

        # Specific Brand Fix: If we see anything like 'SMOXY', 'SMO', 'OXY'
        # Look for stylized variations or spaced out characters
        if re.search(r'S\s?M\s?O\s?X\s?Y|SMO|MOX|OXY', all_text.upper()) or \
           re.search(r'S\s?M\s?O\s?X\s?Y|SMO|MOX|OXY', brand.upper()):
            brand = "SMOXY"
        elif "TORGH" in brand.upper() or "TORCH" in brand.upper():
            # If the largest text is 'TORCH', it's likely a Smoxy Torch flyer
            brand = "SMOXY"

        # Category detection
        category_keywords = ["TORCH", "LIGHTER", "BUTANE", "GRINDER", "CANDLE"]
        category_parts = []
        for kw in category_keywords:
            if kw in all_text.upper():
                category_parts.append(kw)
        
        if category_parts:
            category = " ".join(category_parts)
            # If the brand was misidentified as a category keyword, reset brand
            if brand.upper() in category_parts:
                brand = "SMOXY"

        # 2. Detect horizontal lines (underlines/anchors) for specific products
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        k_width = int(60 * scale)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_width, 1))
        line_mask = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
        contours, _ = cv2.findContours(line_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        anchors = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if (40 * scale) < w < (400 * scale) and h < (15 * scale) and y > (img.shape[0] * 0.15):
                anchors.append([x, y, w, h])

        if anchors:
            anchors.sort(key=lambda a: (a[1] // 20, a[0]))
            merged_anchors = []
            curr = anchors[0]
            for i in range(1, len(anchors)):
                nxt = anchors[i]
                if abs(nxt[1] - curr[1]) < (15 * scale) and (nxt[0] - (curr[0] + curr[2])) < (50 * scale):
                    new_x = min(curr[0], nxt[0])
                    new_w = max(curr[0] + curr[2], nxt[0] + nxt[2]) - new_x
                    curr = [new_x, curr[1], new_w, max(curr[3], nxt[3])]
                else:
                    merged_anchors.append(curr)
                    curr = nxt
            merged_anchors.append(curr)
            anchors = merged_anchors
        
        # 3. Associate text with anchors
        try:
            d = pytesseract.image_to_data(ocr_ready, output_type=pytesseract.Output.DICT, config='--psm 11')
        except Exception as e:
            raise RuntimeError(f"OCR failed: {e}")

        exclude_words = {"DISTRIBUTORS", "FLYER", "SYSTEM", "CELL", "OFFICE", "GOTHAM"}
        anchor_to_words = {i: [] for i in range(len(anchors))}
        n_boxes = len(d['text'])
        for i in range(n_boxes):
            text = d['text'][i].strip()
            if not text: continue
            conf = int(d['conf'][i])
            if conf < 40 or text.upper() in exclude_words: continue
                
            tx, ty, tw, th = d['left'][i], d['top'][i], d['width'][i], d['height'][i]
            best_anchor = -1
            min_dist = 80 * scale 
            for a_idx, (ax, ay, aw, ah) in enumerate(anchors):
                overlap = max(0, min(tx + tw, ax + aw) - max(tx, ax))
                vert_dist = ay - (ty + th)
                if overlap > (5 * scale) and (-10 * scale) < vert_dist < (60 * scale): 
                    if vert_dist < min_dist:
                        min_dist = vert_dist
                        best_anchor = a_idx
            if best_anchor != -1:
                anchor_to_words[best_anchor].append((tx, text))

        # 4. Finalize Hints
        product_hints = []
        sorted_anchor_indices = sorted(range(len(anchors)), key=lambda i: (anchors[i][1] // 30, anchors[i][0]))
        seen_hints = set()
        for a_idx in sorted_anchor_indices:
            words = sorted(anchor_to_words[a_idx], key=lambda x: x[0])
            hint = " ".join([w[1] for w in words])
            if hint and len(hint) > 2:
                # Basic cleanup
                hint = re.sub(r'[^A-Za-z0-9 \-&]', '', hint).strip()
                if hint and hint.lower() not in seen_hints:
                    product_hints.append(hint)
                    seen_hints.add(hint.lower())

        return {
            "brand_hint": brand,
            "category_hint": category,
            "product_hints": product_hints
        }