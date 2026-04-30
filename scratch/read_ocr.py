with open("scratch/ocr_output.txt", "rb") as f:
    content = f.read()
    # Try different encodings
    for enc in ["utf-8", "utf-16", "utf-16-le", "latin-1"]:
        try:
            text = content.decode(enc)
            print(f"--- Decoded with {enc} ---")
            lines = text.splitlines()
            for line in lines:
                if "Text:" in line or "Contour:" in line:
                    print(line)
            break
        except:
            continue
