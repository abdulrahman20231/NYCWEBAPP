BOT_NAME = "nyc_rentals_scraper"

SPIDER_MODULES = ["nyc_rentals_scraper.spiders"]
NEWSPIDER_MODULE = "nyc_rentals_scraper.spiders"

ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 1.0
CONCURRENT_REQUESTS_PER_DOMAIN = 4
FEED_EXPORT_ENCODING = "utf-8"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

ITEM_PIPELINES = {
    "nyc_rentals_scraper.pipelines.CsvExportPipeline": 300,
}

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en",
    "User-Agent": "Mozilla/5.0 (compatible; RentScoutBot/1.0; +https://example.com/bot)",
}
