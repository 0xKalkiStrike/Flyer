import re

class StatusExtractor:
    @staticmethod
    def normalize_status(status_text: str) -> str:
        """Normalize various website availability messages into standard states."""
        text = status_text.upper()
        
        available_keywords = ["IN STOCK", "AVAILABLE", "ADD TO CART", "BUY NOW", "IN-STOCK", "LOGIN", "LOGIN TO BUY"]
        out_of_stock_keywords = ["OUT OF STOCK", "SOLD OUT", "UNAVAILABLE", "TEMPORARILY UNAVAILABLE", "RESTOCKING"]
        
        # Special Case: Login means Available on this site
        if "LOGIN" in text:
            # Check for explicit negation
            if "OUT OF STOCK" not in text and "SOLD OUT" not in text:
                return "AVAILABLE"

        for kw in out_of_stock_keywords:
            if kw in text:
                return "OUT_OF_STOCK"
                
        for kw in available_keywords:
            if kw in text:
                return "AVAILABLE"
                
        return "UNKNOWN"

    @staticmethod
    def extract_from_html(html_content: str) -> str:
        """Basic extraction from HTML if Playwright selectors fail."""
        # This is a fallback
        if "out of stock" in html_content.lower() or "sold out" in html_content.lower():
            return "OUT_OF_STOCK"
        if "add to cart" in html_content.lower():
            return "AVAILABLE"
        return "UNKNOWN"
