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
            
            # Step 1: Try Direct Brand URL (Common in WooCommerce)
            brand_slug = brand_name.lower().replace(" ", "-")
            brand_url = f"{base_url.rstrip('/')}/brand/{brand_slug}/"
            try:
                logger.info(f"Trying direct brand URL: {brand_url}")
                await self.page.goto(brand_url, wait_until='domcontentloaded', timeout=40000)
                # Wait for any product-like element to appear
                try:
                    await self.page.wait_for_selector(".product, li.product, .woocommerce-loop-product__title", timeout=10000)
                except:
                    pass
                # Count current products
                current_count = await self.page.evaluate("document.querySelectorAll('li.product, .product-group-item, .woocommerce-loop-product__title').length")
                logger.info(f"Loaded {current_count} products...")
                
                if not await self.page.query_selector(".product, li.product"):
                    logger.warning("Direct brand URL empty, falling back to search.")
                else:
                    return True
            except:
                logger.warning("Direct brand URL failed, falling back to search.")

            # Step 2: Fallback to Search
            search_param = "s" if "gothamdistro" in base_url.lower() else "q"
            search_url = f"{base_url.rstrip('/')}/?{search_param}={brand_name}"
            logger.info(f"Navigating to brand search: {search_url}")
            await self.page.goto(search_url, wait_until='networkidle')
            return True
        except Exception as e:
            logger.error(f"Brand navigation failed: {e}")
            return False

    async def find_category_on_page(self, category_hint: str) -> bool:
        """Find and click the most relevant category link on the current page."""
        try:
            if category_hint == "Unknown":
                return False
                
            # Focus on common navigation/category areas first (especially left side panel)
            selectors = [
                "aside .product-categories", 
                ".widget_product_categories", 
                "aside", 
                "nav", 
                ".cat-item", 
                ".menu-item"
            ]
            link_data = []
            
            for selector in selectors:
                containers = await self.page.query_selector_all(selector)
                for container in containers:
                    links = await container.query_selector_all("a")
                    for link in links:
                        try:
                            text = await link.inner_text()
                            if text and len(text.strip()) > 2:
                                link_data.append({"text": text.strip(), "handle": link})
                        except Exception:
                            continue # Context might have been destroyed for this link
            
            # If no targeted links, try all links
            if not link_data:
                all_links = await self.page.query_selector_all("a")
                for link in all_links:
                    try:
                        text = await link.inner_text()
                        if text and len(text.strip()) > 2:
                            link_data.append({"text": text.strip(), "handle": link})
                    except Exception:
                        continue

            if not link_data:
                return False

            choices = [l['text'] for l in link_data]
            result = process.extractOne(category_hint, choices, scorer=fuzz.token_set_ratio)
            
            if result and result[1] > 60:
                logger.info(f"Matched category '{category_hint}' to link '{result[0]}' (Score: {result[1]})")
                target_link = link_data[result[2]]['handle']
                # Scroll to it first to ensure it's clickable
                await target_link.scroll_into_view_if_needed()
                await target_link.click()
                await self.page.wait_for_load_state('networkidle')
                return True
            
            return False
        except Exception as e:
            logger.error(f"Category navigation failed: {e}")
            return False
