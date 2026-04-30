from playwright.async_api import Page
import logging
import re

logger = logging.getLogger(__name__)

class ProductScraper:
    def __init__(self, page: Page):
        self.page = page

    async def scrape_category_products(self) -> list[dict]:
        """Fetch all products on the page using persistent infinite scrolling."""
        try:
            logger.info("Starting persistent scroll to load all products...")
            last_count = 0
            retries = 0
            
            while retries < 8: # Maximum 8 checks with no new products
                # Scroll to bottom
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(1500) # Wait for spinner
                
                # Count current products
                current_count = await self.page.evaluate("document.querySelectorAll('li.product, .product-group-item, .woocommerce-loop-product__title, .name').length")
                logger.info(f"Loaded {current_count} products...")
                
                if current_count > last_count:
                    last_count = current_count
                    retries = 0 # Reset retries if we found more
                else:
                    retries += 1
                
                if current_count > 200: # Safety break
                    break
            
            # Final wait for images/status
            await self.page.wait_for_timeout(1000)
            
            # Use JS to extract data directly from the DOM
            products = await self.page.evaluate('''() => {
                const results = [];
                // 1. Check for single product with grouped items (as in Smoxy screenshot)
                const groupItems = document.querySelectorAll(".woocommerce-grouped-product-list-item, .product-group-item, tr.product");
                if (groupItems.length > 0) {
                    groupItems.forEach(el => {
                        const name_el = el.querySelector(".woocommerce-grouped-product-list-item__label, .name, td:nth-child(2)");
                        const link_el = el.querySelector("a") || { href: window.location.href };
                        const status_el = el.querySelector(".woocommerce-grouped-product-list-item__status, .status, td:nth-child(3)");
                        if (name_el) {
                            results.push({
                                name: name_el.innerText.trim(),
                                url: link_el.href,
                                availability: status_el ? status_el.innerText.trim() : "Available",
                                image_url: null,
                                sku: null
                            });
                        }
                    });
                }
                
                // 2. Check for standard product cards
                const cards = document.querySelectorAll("li.product, .product, .ast-shop-thumbnail-wrap, article.product");
                cards.forEach(el => {
                    const name_el = el.querySelector(".woocommerce-loop-product__title, h2, h3, .name");
                    const link_el = el.querySelector("a");
                    const img_el = el.querySelector("img");
                    const status_el = el.querySelector(".ast-shop-product-out-of-stock, .out-of-stock, .onsale");
                    
                    if (name_el && link_el) {
                        results.push({
                            name: name_el.innerText.trim(),
                            url: link_el.href,
                            availability: status_el ? status_el.innerText.trim() : "Available",
                            image_url: img_el ? img_el.src : null,
                            sku: null
                        });
                    }
                });

                // 3. Fallback for generic name/link pairs
                if (results.length === 0) {
                   const links = document.querySelectorAll("a");
                   links.forEach(l => {
                       if (l.href.includes('/product/') && l.innerText.length > 10) {
                           results.push({
                               name: l.innerText.trim(),
                               url: l.href,
                               sku: null
                           });
                       }
                   });
                }

                return results;
            }''')
            
            # Clean and deduplicate
            seen_urls = set()
            unique_products = []
            for p in products:
                # Extract SKU via regex in Python
                match = re.search(r'([A-Z]{1,3}\s?\d{2,4})', p['name'])
                if match:
                    p['sku'] = match.group(1).replace(" ", "")
                
                uid = f"{p['name']}_{p['url']}"
                if uid not in seen_urls:
                    unique_products.append(p)
                    seen_urls.add(uid)
            
            logger.info(f"Scrape found {len(unique_products)} unique products.")
            return unique_products
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            return []
