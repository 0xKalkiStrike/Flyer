import cv2
import numpy as np
import pytesseract
from pytesseract import Output

def detect_products_by_red_price(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"Could not read image at {image_path}")
        return []

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Red has two ranges in HSV
    lower_red1 = np.array([0, 50, 50]) # Lowered saturation/value
    upper_red1 = np.array([20, 255, 255]) # Widened hue
    lower_red2 = np.array([150, 50, 50]) # Widened hue
    upper_red2 = np.array([180, 255, 255])
    
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)
    
    cv2.imwrite("scratch/red_mask.png", mask)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    price_regions = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Red price pills are usually around 80-150px wide and 30-60px high
        if 30 < w < 250 and 10 < h < 100:
            price_regions.append((x, y, w, h))
            print(f"Red Price Pill at ({x}, {y}, w={w}, h={h})")

    # Get text data
    d = pytesseract.image_to_data(img, output_type=Output.DICT)
    n_boxes = len(d['text'])
    
    # Map each red pill to the text above it
    pill_to_text = {i: [] for i in range(len(price_regions))}
    
    for i in range(n_boxes):
        text = d['text'][i].strip()
        if not text or int(d['conf'][i]) < 40:
            continue
            
        tx, ty, tw, th = d['left'][i], d['top'][i], d['width'][i], d['height'][i]
        
        # Find the best matching red pill (the one it's directly above)
        best_pill = -1
        min_dist = 1000
        
        for p_idx, (px, py, pw, ph) in enumerate(price_regions):
            # Horizontal overlap
            horiz_overlap = max(0, min(tx + tw, px + pw) - max(tx, px))
            if horiz_overlap > 5: # Some overlap
                vert_dist = py - (ty + th)
                if 5 < vert_dist < 100:
                    if vert_dist < min_dist:
                        min_dist = vert_dist
                        best_pill = p_idx
        
        if best_pill != -1:
            pill_to_text[best_pill].append((tx, text))
            print(f"Text '{text}' assigned to Pill {best_pill}")

    extracted_products = []
    for p_idx in range(len(price_regions)):
        words = sorted(pill_to_text[p_idx], key=lambda x: x[0])
        name = " ".join([w[1] for w in words])
        if name and len(name) > 3:
            extracted_products.append(name)

    return extracted_products

if __name__ == "__main__":
    products = detect_products_by_red_price("uploads/smoxy-121-125.jpg")
    print("\nFinal Detected Products:")
    for p in products:
        print(f"- {p}")
