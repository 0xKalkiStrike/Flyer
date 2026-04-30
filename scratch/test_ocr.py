import cv2
import numpy as np
import pytesseract
from pytesseract import Output

def detect_blue_underlined_text(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"Could not read image at {image_path}")
        return
    print(f"Image shape: {img.shape}")

    # Convert to HSV for better color segmentation
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Use morphological operations to find horizontal lines
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Adaptive threshold to handle gradients
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    mask = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
    
    # Optional: save mask to see what we are getting
    cv2.imwrite("scratch/horizontal_mask.png", mask)
    
    # Find contours of the horizontal lines
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Total horizontal contours found: {len(contours)}")
    
    underlines = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        print(f"Blue contour: x={x}, y={y}, w={w}, h={h}")
        # Underlines are wide and short
        if w > 10: 
            underlines.append((x, y, w, h))
    
    print(f"Filtered underlines: {len(underlines)}")

    # Get text data
    d = pytesseract.image_to_data(img, output_type=Output.DICT)
    n_boxes = len(d['text'])
    
    extracted_products = []
    
    # Group words by line (using top coordinate)
    lines = {}
    for i in range(n_boxes):
        text = d['text'][i].strip()
        if not text:
            continue
            
        conf = int(d['conf'][i])
        if conf < 30:
            continue
            
        x, y, w, h = d['left'][i], d['top'][i], d['width'][i], d['height'][i]
        print(f"Text: '{text}' at ({x},{y},w={w},h={h}) conf={conf}")
        
        # Check if there is an underline near this word (slightly below it)
        has_underline = False
        for ux, uy, uw, uh in underlines:
            # Check if underline is below the word and horizontally overlapping
            # Relaxing horizontal overlap requirement
            horiz_overlap = (ux <= x + w + 20 and ux + uw >= x - 20)
            # The underline is BELOW the word, so uy > y+h
            vert_dist = uy - (y + h)
            
            if horiz_overlap and (vert_dist >= -10 and vert_dist <= 50):
                has_underline = True
                print(f"  -> Match found with underline at ({ux},{uy}) dist={vert_dist}")
                break
        
        if has_underline:
            # Use 'top' to group lines, allow some tolerance
            line_key = y // 15
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append((x, text))

    # Sort words in each line by x-coordinate and join them
    for line_key in sorted(lines.keys()):
        words = sorted(lines[line_key], key=lambda x: x[0])
        product_name = " ".join([w[1] for w in words])
        if product_name:
            extracted_products.append(product_name)
            
    return extracted_products

if __name__ == "__main__":
    image_path = "uploads/smoxy-121-125.jpg"
    products = detect_blue_underlined_text(image_path)
    print("Detected Products with Blue Underline:")
    for p in products:
        print(f"- {p}")
