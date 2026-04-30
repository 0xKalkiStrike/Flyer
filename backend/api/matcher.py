from rapidfuzz import fuzz, process
import re

class ProductMatcher:
    def __init__(self, threshold=70):
        self.threshold = threshold

    def normalize(self, text: str) -> str:
        """Clean and normalize text for better matching."""
        if not text:
            return ""
        # Remove special characters, extra spaces, and convert to lowercase
        text = re.sub(r'[^a-zA-Z0-9 ]', '', text.lower())
        return " ".join(text.split())

    def match_products(self, flyer_hints: list[str], website_products: list[dict]) -> list[dict]:
        """
        Matches flyer hints against website products.
        website_products is a list of dicts: {'name': '...', 'sku': '...', 'url': '...'}
        """
        matches = []
        
        # Prepare website data for matching
        choices = [self.normalize(p['name']) for p in website_products]
        sku_choices = {self.normalize(p.get('sku', '')): i for i, p in enumerate(website_products) if p.get('sku')}
        
        for hint in flyer_hints:
            norm_hint = self.normalize(hint)
            if not norm_hint:
                continue
            
            best_match = None
            
            # 1. Try SKU/Code match first (highest priority)
            # Check if any SKU is contained in the hint or vice-versa
            for sku, idx in sku_choices.items():
                if sku in norm_hint or norm_hint in sku:
                    best_match = website_products[idx]
                    break
            
            if best_match:
                matches.append({
                    "flyer_hint": hint,
                    "matched_product": best_match,
                    "score": 100,
                    "match_type": "SKU"
                })
                continue

            # 2. Try Fuzzy name match
            if choices:
                result = process.extractOne(norm_hint, choices, scorer=fuzz.token_set_ratio)
                if result and result[1] >= self.threshold:
                    match_idx = result[2]
                    best_match = website_products[match_idx]
                    matches.append({
                        "flyer_hint": hint,
                        "matched_product": best_match,
                        "score": result[1],
                        "match_type": "Fuzzy"
                    })
        
        return matches
