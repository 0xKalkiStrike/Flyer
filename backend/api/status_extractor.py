import re

class StatusExtractor:
    @staticmethod
    def normalize_status(status_text: str) -> str:
        """Normalize various website availability messages into standard states."""
        text = status_text.upper()
        
        available_keywords = ["IN STOCK", "AVAILABLE", "ADD TO CART", "BUY NOW", "IN-STOCK"]
        out_of_stock_keywords = ["OUT OF STOCK", "SOLD OUT", "UNAVAILABLE", "TEMPORARILY UNAVAILABLE", "RESTOCKING"]
        
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
