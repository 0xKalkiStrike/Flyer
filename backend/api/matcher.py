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

    def normalize_sku(self, text: str) -> str:
        """Normalize SKUs by removing all whitespace."""
        return re.sub(r'\s+', '', self.normalize(text))

    def match_products(self, flyer_hints: list[str], website_products: list[dict], brand: str = "", category: str = "") -> list[dict]:
        """
        Matches flyer hints against website products with brand/category context.
        """
        matches = []
        
        # Prepare website data for matching
        choices = [self.normalize(p['name']) for p in website_products]
        sku_choices = {self.normalize_sku(p.get('sku', '')): i for i, p in enumerate(website_products) if p.get('sku')}
        
        norm_brand = self.normalize(brand)
        norm_cat = self.normalize(category)
        
        for hint in flyer_hints:
            norm_hint = self.normalize(hint)
            sku_hint = self.normalize_sku(hint)
            if not norm_hint:
                continue
            
            best_match = None
            
            # 1. Try SKU/Code match first
            for sku, idx in sku_choices.items():
                if sku and (sku in sku_hint or sku_hint in sku):
                    best_match = website_products[idx]
                    break
            if best_match:
                matches.append({"flyer_hint": hint, "matched_product": best_match, "score": 100, "match_type": "SKU"})
                continue

            # 2. Try Keyword Overlap Match (with Context)
            # Create a pool of words from hint + brand + category
            hint_pool = set(norm_hint.split()) | set(norm_brand.split()) | set(norm_cat.split())
            for idx, choice in enumerate(choices):
                choice_words = set(choice.split())
                common = hint_pool.intersection(choice_words)
                # Significant overlap if 2+ words match (ignoring small particles)
                significant_overlap = [w for w in common if len(w) > 2]
                if len(significant_overlap) >= 2:
                    # Special check: the hint must contribute at least one word to the overlap
                    # otherwise we just match every product to every hint
                    if any(w in set(norm_hint.split()) for w in significant_overlap):
                        best_match = website_products[idx]
                        matches.append({
                            "flyer_hint": hint,
                            "matched_product": best_match,
                            "score": 95,
                            "match_type": "Keyword Match"
                        })
                        break
            if best_match: continue

            # 3. Try Fuzzy name match (Partial Ratio)
            if choices:
                # Use partial_ratio to match hints like "DELUXE BLUE" inside "SMOXY DELUXE TORCH BLUE"
                result = process.extractOne(norm_hint, choices, scorer=fuzz.partial_ratio)
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
