import cv2
import numpy as np

img = cv2.imread("uploads/smoxy-121-125.jpg")
# Scan vertically at x=100 from y=640 to y=680
strip = img[640:680, 100, :]
for i, pixel in enumerate(strip):
    print(f"y={640+i}: BGR={pixel}")
