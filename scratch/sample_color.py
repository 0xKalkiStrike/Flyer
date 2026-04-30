import cv2
import numpy as np

img = cv2.imread("uploads/smoxy-121-125.jpg")
pixel = img[665, 140]
print(f"Color at y=665 (140, 665): {pixel}")
hsv_pixel = cv2.cvtColor(np.uint8([[pixel]]), cv2.COLOR_BGR2HSV)[0][0]
print(f"HSV at y=665 (140, 665): {hsv_pixel}")
# Exit early to avoid error
import sys
sys.exit(0)
