from playwright.async_api import Page
from rapidfuzz import fuzz, process
import logging

logger = logging.getLogger(__name__)

class WebsiteNavigator:
    def __init__(self, page: Page):
        self.page = page

    async def search_and_navigate_brand(self, brand_name: str, base_url: str) -> bool:
        """Search for a brand and navigate to its primary page."""
        try:
            logger.info(f"Navigating to brand: {brand_name}")
            # Search for the brand
            search_param = "s" if "gothamdistro" in base_url.lower() else "q"
            await self.page.goto(f"{base_url.rstrip('/')}/?{search_param}={brand_name}", wait_until='networkidle')
            
            # Check if we landed on a result page or a single product
            # In Astra/WooCommerce, brands often have dedicated pages or attributes
            # For now, we look for 'Smoxy' in headings or filters
            return True
        except Exception as e:
            logger.error(f"Brand navigation failed: {e}")
            return False

    async def find_category_on_page(self, category_hint: str) -> bool:
        """Find and click the most relevant category link on the current page."""
        try:
            # Extract all links that look like categories
            # GothamDistro uses 'li.cat-item a' or generic menu links
            links = await self.page.query_selector_all("a")
            link_data = []
            for link in links:
                text = await link.inner_text()
                if text and len(text.strip()) > 2:
                    link_data.append({"text": text.strip(), "handle": link})
            
            choices = [l['text'] for l in link_data]
            result = process.extractOne(category_hint, choices, scorer=fuzz.token_set_ratio)
            
            if result and result[1] > 60:
                logger.info(f"Matched category '{category_hint}' to link '{result[0]}' (Score: {result[1]})")
                await link_data[result[2]]['handle'].click()
                await self.page.wait_for_load_state('networkidle')
                return True
            
            return False
        except Exception as e:
            logger.error(f"Category navigation failed: {e}")
            return False
