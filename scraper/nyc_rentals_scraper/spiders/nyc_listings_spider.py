from __future__ import annotations

import re
from urllib.parse import urljoin

import scrapy

from nyc_rentals_scraper.items import RentalListingItem


class NycListingsSpider(scrapy.Spider):
    name = "nyc_rentals"
    allowed_domains = ["newyork.craigslist.org"]
    start_urls = ["https://newyork.craigslist.org/search/apa?query=nyc"]

    def __init__(self, max_pages: int = 2, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = max(int(max_pages), 1)
        self.page_count = 0

    def parse(self, response: scrapy.http.Response, **kwargs):
        self.page_count += 1

        for card in response.css("li.cl-static-search-result"):
            detail_url = card.css("a::attr(href)").get()
            if detail_url:
                yield response.follow(detail_url, callback=self.parse_listing)

        if self.page_count >= self.max_pages:
            return

        next_page = response.css("a.button.next::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_listing(self, response: scrapy.http.Response):
        title = self._clean_text(
            response.css("#titletextonly::text, span#titletextonly::text").get()
        )
        body_parts = response.css("section#postingbody::text").getall()
        description = self._clean_text(" ".join(body_parts))
        price_text = self._clean_text(
            response.css("span.price::text, span.priceinfo::text").get()
        )
        attr_groups = response.css("p.attrgroup span::text").getall()
        map_address = self._clean_text(response.css("div.mapaddress::text").get())
        image_url = response.css("div.swipe-wrap img::attr(src)").get(default="")
        latitude = response.css("div.viewposting::attr(data-latitude)").get(default="")
        longitude = response.css("div.viewposting::attr(data-longitude)").get(default="")

        cleaned_attrs = [self._clean_text(value) for value in attr_groups if self._clean_text(value)]
        neighborhood = self._extract_neighborhood(response)
        borough = self._infer_borough(response.url, neighborhood, map_address)
        beds = self._extract_number(cleaned_attrs, r"(\d+(?:\.\d+)?)BR", default=0)
        baths = self._extract_number(cleaned_attrs, r"(\d+(?:\.\d+)?)Ba", default=1)
        sqft = int(self._extract_number(cleaned_attrs, r"(\d+)\s*ft2", default=0))

        item = RentalListingItem()
        item["id"] = response.url.rstrip("/").split("/")[-1].replace(".html", "")
        item["title"] = title or "NYC Rental Listing"
        item["description"] = description or "No description provided."
        item["borough"] = borough
        item["neighborhood"] = neighborhood or borough
        item["address"] = map_address or "New York, NY"
        item["price"] = int(self._digits_only(price_text) or 0)
        item["beds"] = beds
        item["baths"] = baths
        item["sqft"] = sqft
        item["property_type"] = self._infer_property_type(cleaned_attrs, title)
        item["available_from"] = ""
        item["lease_term"] = "12 months"
        item["image_url"] = image_url
        item["listing_url"] = response.url
        item["latitude"] = latitude
        item["longitude"] = longitude
        item["pet_friendly"] = self._contains_any(cleaned_attrs + [description], ["cats are ok", "dogs are ok", "pet"])
        item["furnished"] = self._contains_any(cleaned_attrs + [title, description], ["furnished"])
        item["has_doorman"] = self._contains_any([title, description], ["doorman"])
        item["has_laundry"] = self._contains_any(cleaned_attrs + [description], ["laundry", "w/d", "washer/dryer"])
        item["near_subway"] = self._contains_any([description, map_address], ["subway", "train", "station"])
        item["allows_guarantors"] = self._contains_any([description], ["guarantor"])
        item["featured"] = self._contains_any([title], ["luxury", "new", "renovated"])
        yield item

    @staticmethod
    def _clean_text(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _digits_only(value: str) -> str:
        return "".join(char for char in value if char.isdigit())

    @staticmethod
    def _extract_number(values: list[str], pattern: str, default: float = 0) -> float:
        regex = re.compile(pattern, re.IGNORECASE)
        for value in values:
            match = regex.search(value)
            if match:
                return float(match.group(1))
        return default

    @staticmethod
    def _contains_any(values: list[str], terms: list[str]) -> bool:
        lowered = " ".join(values).lower()
        return any(term.lower() in lowered for term in terms)

    def _extract_neighborhood(self, response: scrapy.http.Response) -> str:
        hood_text = self._clean_text(response.css("small::text").get())
        if hood_text.startswith("(") and hood_text.endswith(")"):
            hood_text = hood_text[1:-1]
        if hood_text:
            return hood_text

        title = self._clean_text(
            response.css("title::text").get() or response.css("#titletextonly::text").get()
        )
        parts = [segment.strip() for segment in re.split(r"[-|/]", title) if segment.strip()]
        if len(parts) > 1:
            return parts[-1]
        return "NYC"

    def _infer_borough(self, url: str, neighborhood: str, address: str) -> str:
        text = f"{url} {neighborhood} {address}".lower()
        mapping = {
            "manhattan": ["manhattan", "midtown", "harlem", "upper west", "chelsea", "les", "village"],
            "brooklyn": ["brooklyn", "williamsburg", "park slope", "fort greene", "dumbo", "bushwick"],
            "queens": ["queens", "astoria", "lic", "long island city", "jackson heights", "flushing"],
            "bronx": ["bronx", "mott haven", "south bronx", "riverdale"],
            "staten island": ["staten island", "st. george"],
        }
        for borough, hints in mapping.items():
            if any(hint in text for hint in hints):
                return borough.title() if borough != "staten island" else "Staten Island"
        return "Manhattan"

    @staticmethod
    def _infer_property_type(attrs: list[str], title: str) -> str:
        text = " ".join(attrs + [title]).lower()
        if "studio" in text:
            return "Studio"
        if "duplex" in text:
            return "Duplex"
        if "loft" in text:
            return "Loft"
        if "condo" in text:
            return "Condo"
        if "brownstone" in text:
            return "Brownstone"
        return "Apartment"
