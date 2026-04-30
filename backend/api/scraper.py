from playwright.async_api import Page
import logging

logger = logging.getLogger(__name__)

class ProductScraper:
    def __init__(self, page: Page):
        self.page = page

    async def scrape_category_products(self) -> list[dict]:
        """Fetch all products listed on the current page."""
        products = []
        try:
            # Target common WooCommerce/Astra selectors
            product_elements = await self.page.query_selector_all(".product, li.product, .ast-shop-thumbnail-wrap")
            
            for el in product_elements:
                try:
                    name_el = await el.query_selector(".woocommerce-loop-product__title, h2, h3")
                    link_el = await el.query_selector("a")
                    img_el = await el.query_selector("img")
                    
                    name = await name_el.inner_text() if name_el else "Unknown"
                    url = await link_el.get_attribute("href") if link_el else None
                    img_url = await img_el.get_attribute("src") if img_el else None
                    
                    # Try to extract SKU from name or data attributes
                    sku_match = None
                    # Many sites put SKU in parentheses or after a dash
                    import re
                    match = re.search(r'\(([^)]+)\)', name)
                    if match:
                        sku_match = match.group(1)
                    
                    products.append({
                        "name": name.strip(),
                        "sku": sku_match,
                        "url": url,
                        "image_url": img_url
                    })
                except Exception as inner_e:
                    logger.warning(f"Failed to parse individual product element: {inner_e}")
            
            logger.info(f"Scraped {len(products)} products from page.")
            return products
        except Exception as e:
            logger.error(f"Failed to scrape products: {e}")
            return []
