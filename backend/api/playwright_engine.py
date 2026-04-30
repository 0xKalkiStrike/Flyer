from playwright.async_api import async_playwright
import asyncio
import logging
import os
import re

logger = logging.getLogger(__name__)

class PlaywrightEngine:
    def __init__(self):
        self.browser = None
        self.context = None

    async def start(self):
        playwright = await async_playwright().start()
        # Launch browser in visible mode so the user can watch live verification progress
        self.browser = await playwright.chromium.launch(headless=False, slow_mo=100, args=["--start-maximized"])
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def login(self, url: str, username: str, password: str) -> bool:
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until='networkidle')
            await page.fill('input[type="email"], input[name="username"]', username)
            await page.fill('input[type="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state('networkidle')
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
        finally:
            await page.close()

    async def verify_product(self, product_name: str, website_url: str) -> dict:
        page = await self.context.new_page()
        result = {
            "product_name": product_name,
            "status": "Failed",
            "issue_type": "Unknown",
            "product_url": None,
            "screenshot_path": None
        }
        try:
            # Use 's' for WooCommerce/GothamDistro, fallback to 'q'
            search_param = "s" if "gothamdistro" in website_url.lower() else "q"
            search_url = f"{website_url.rstrip('/')}/?{search_param}={product_name.replace(' ', '+')}"
            
            await page.goto(search_url, wait_until='networkidle', timeout=30000)
            
            # Check for the specific 'Nothing Found' message used by GothamDistro (Astra theme)
            not_found_indicators = [
                "It seems we can't find what you're looking for",
                "nothing found",
                "no products were found",
                "404"
            ]
            
            content = await page.content()
            content_lower = content.lower()
            
            is_not_found = any(kw.lower() in content_lower for kw in not_found_indicators)
            
            if is_not_found:
                result["status"] = "Not Found"
                result["issue_type"] = "Product Missing"
            else:
                # Target the first product result container to check availability
                # GothamDistro (Astra) uses 'li.product' or '.astra-shop-thumbnail-wrap'
                first_product = page.locator(".products .product").first
                
                if await first_product.count() > 0:
                    # Check for 'Sold Out' badge specifically within the product card
                    # We look for the badge class or the 'Sold Out' text node within the card
                    sold_out_badge = first_product.locator(".ast-shop-product-out-of-stock, .out-of-stock")
                    card_text = (await first_product.inner_text()).lower()
                    
                    if await sold_out_badge.count() > 0 or "sold out" in card_text:
                        result["status"] = "Verified"
                        result["issue_type"] = "Out of Stock"
                    else:
                        result["status"] = "Verified"
                        result["issue_type"] = "Available"
                else:
                    # Fallback if the layout is different or it's a single product page
                    if "sold out" in content_lower or "out of stock" in content_lower:
                        # Re-verify it's not just the sidebar
                        main_content = await page.locator("#main, #primary, .site-content").inner_text()
                        if "sold out" in main_content.lower() or "out of stock" in main_content.lower():
                            result["status"] = "Verified"
                            result["issue_type"] = "Out of Stock"
                        else:
                            result["status"] = "Verified"
                            result["issue_type"] = "Available"
                    else:
                        result["status"] = "Verified"
                        result["issue_type"] = "Available"
        finally:
            await page.close()
            await asyncio.sleep(0.5)
            
        return result

    async def verify_product_stock(self, product_url: str) -> str:
        """Navigate to a specific product page and extract normalized availability."""
        page = await self.context.new_page()
        try:
            await page.goto(product_url, wait_until='networkidle', timeout=20000)
            
            # Common selectors for availability
            selectors = [
                ".stock", 
                ".availability", 
                ".ast-stock-status", 
                ".woocommerce-variation-availability",
                "p.stock.out-of-stock",
                "p.stock.in-stock"
            ]
            
            status_text = ""
            for selector in selectors:
                el = await page.query_selector(selector)
                if el:
                    status_text = await el.inner_text()
                    break
            
            if not status_text:
                # Fallback to page content
                status_text = await page.inner_text("body")
            
            from .status_extractor import StatusExtractor
            return StatusExtractor.normalize_status(status_text)
        except Exception as e:
            logger.error(f"Stock check failed for {product_url}: {e}")
            return "UNKNOWN"
        finally:
            await page.close()
            await asyncio.sleep(0.5)