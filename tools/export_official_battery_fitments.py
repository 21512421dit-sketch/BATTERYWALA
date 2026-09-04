"""Export factual battery fitments from Amaron's official public sitemap."""

import argparse
import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://www.amaron.com/"
SITEMAP_URL = urljoin(BASE_URL, "sitemap.xml")
FITMENT_CATEGORIES = {
    "passengers",
    "two-wheelers",
    "three-wheelers",
    "commercial",
    "farm-vehicles",
    "earth-moving-equipment",
    "genset",
}


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def money(value):
    match = re.search(r"(?:₹|Rs\.?\s*)([\d,]+)", value or "", re.I)
    return int(match.group(1).replace(",", "")) if match else None


def number(value):
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:Ah|AH)\b", value or "")
    return float(match.group(1)) if match else None


def scalar(value):
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    return float(match.group()) if match else None


class ComparisonTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.table_depth = 0
        self.row = None
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            if self.in_table:
                self.table_depth += 1
            elif attrs.get("id") in ("comparisonTable", "proComparisionTable"):
                self.in_table, self.table_depth = True, 1
            return
        if not self.in_table:
            return
        if tag == "tr":
            self.row = []
        elif tag in ("th", "td") and self.row is not None:
            self.cell = {"tag": tag, "text": [], "href": None, "image_url": None}
        elif self.cell is not None and tag == "a" and not self.cell["href"]:
            self.cell["href"] = urljoin(BASE_URL, attrs.get("href", ""))
        elif self.cell is not None and tag == "img" and not self.cell["image_url"]:
            self.cell["image_url"] = attrs.get("src")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag in ("th", "td") and self.cell is not None:
            self.cell["text"] = clean("".join(self.cell["text"]))
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_table = False


class Client:
    def __init__(self, delay):
        self.delay = delay
        self.next_request = 0.0
        self.lock = threading.Lock()

    def get(self, url):
        for attempt in range(4):
            try:
                with self.lock:
                    wait = self.next_request - time.monotonic()
                    if wait > 0:
                        time.sleep(wait)
                    self.next_request = time.monotonic() + self.delay
                request = Request(url, headers={"User-Agent": "BatteryWala-official-fitment-index/1.0"})
                with urlopen(request, timeout=45) as response:
                    return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise
            except OSError:
                if attempt == 3:
                    raise
            time.sleep(2 ** attempt)


def sitemap_locations(xml):
    return [node.text for node in ET.fromstring(xml).iter() if node.tag.endswith("loc") and node.text]


def fitment_urls(client):
    child_maps = [url for url in sitemap_locations(client.get(SITEMAP_URL)) if "amaron.com" in url]
    urls = []
    for sitemap in child_maps:
        for url in sitemap_locations(client.get(sitemap)):
            parts = [unquote(part) for part in urlparse(url).path.strip("/").split("/")]
            if len(parts) == 5 and parts[0] == "battery" and parts[1] in FITMENT_CATEGORIES:
                urls.append(url)
    return sorted(set(urls))


def specification(product, *needles):
    for label, value in product["specifications"].items():
        if any(needle in label.lower() for needle in needles):
            return value
    return None


def parse_fitment(url, html):
    parser = ComparisonTableParser()
    parser.feed(html)
    if not parser.rows:
        raise ValueError("official comparison table not found")
    header = max(parser.rows, key=lambda row: sum("AAM-" in cell["text"] for cell in row))
    if len(header) < 2:
        raise ValueError("battery columns not found")
    products = []
    for cell in header[1:]:
        model = re.search(r"\bAAM-[A-Z0-9-]+\b", cell["text"], re.I)
        products.append({
            "brand": "Amaron",
            "model_no": model.group(0).upper() if model else None,
            "title": cell["text"],
            "image_url": cell["image_url"],
            "product_url": None,
            "specifications": {},
        })
    for row in parser.rows:
        if len(row) < 2:
            continue
        label = clean(row[0]["text"])
        for index, cell in enumerate(row[1 : len(products) + 1]):
            if cell["href"] and "/product/" in cell["href"]:
                products[index]["product_url"] = cell["href"]
            if label and cell["text"]:
                products[index]["specifications"][label] = cell["text"]
    for product in products:
        base = specification(product, "base price")
        total = specification(product, "total price")
        rebate = specification(product, "rebate on return")
        capacity = specification(product, "battery capacity", "capacity (ah)", "ampere hour", "amphere hour")
        total_warranty = specification(product, "total warranty")
        product.update({
            "capacity_ah": scalar(capacity) or number(product["title"]),
            "warranty_months": scalar(total_warranty),
            "free_warranty_months": scalar(specification(product, "free warranty")),
            "prorata_warranty_months": scalar(specification(product, "pro-rata warranty")),
            "base_price_inr": money(base),
            "current_price_inr": money(total),
            "old_battery_rebate_inr": money(rebate),
        })
    parts = [unquote(part) for part in urlparse(url).path.strip("/").split("/")]
    return {
        "application": parts[1],
        "vehicle_make": parts[2].replace("-", " ").title(),
        "vehicle_make_slug": parts[2],
        "vehicle_model": parts[3].replace("-", " ").title(),
        "vehicle_model_slug": parts[3],
        "fuel_type": parts[4].replace("-", " ").title(),
        "fuel_type_slug": parts[4],
        "source_url": url,
        "batteries": products,
    }


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def export(args):
    output = Path(args.output)
    payload = json.loads(output.read_text("utf-8")) if args.resume and output.exists() else {
        "schema_version": "1.0",
        "source": "Amaron official website",
        "source_home": BASE_URL,
        "source_sitemap": SITEMAP_URL,
        "usage_note": "Factual internal-use export. Obtain source-owner approval before public or commercial republication.",
        "fitments": [],
        "errors": [],
    }
    completed = {item["source_url"] for item in payload["fitments"]}
    client = Client(args.delay)
    urls = [url for url in fitment_urls(client) if url not in completed]
    if args.limit:
        urls = urls[: args.limit]
    print(f"Official fitment pages queued: {len(urls)}")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(lambda item: parse_fitment(item, client.get(item)), url): url for url in urls}
        for count, future in enumerate(as_completed(futures), 1):
            url = futures[future]
            payload["errors"] = [item for item in payload["errors"] if item["source_url"] != url]
            try:
                payload["fitments"].append(future.result())
            except Exception as error:
                payload["errors"].append({"source_url": url, "error": str(error)[:300]})
            if count % args.checkpoint_every == 0:
                payload["fitments"].sort(key=lambda item: item["source_url"])
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                atomic_write(output, payload)
                print(f"Processed {count}/{len(urls)}; saved {len(payload['fitments'])} fitments")
    payload["fitments"].sort(key=lambda item: item["source_url"])
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write(output, payload)
    return payload


def self_test():
    sample = '''<table id="comparisonTable"><tr><th></th><th><img src="battery.jpg">AMARON FLO - 40B20L (AAM-FL-00040B20L)</th></tr>
    <tr><th></th><td><a href="/product/example">Select</a></td></tr>
    <tr><th>Base Price (Inclusive of GST)</th><td>₹5,486</td></tr>
    <tr><th>Total Price (Inclusive of GST)</th><td>₹5,160</td></tr>
    <tr><th>Battery Capacity (AH)</th><td>35 Ah</td></tr></table>'''
    item = parse_fitment("https://www.amaron.com/battery/passengers/toyota/innova/petrol", sample)
    assert item["vehicle_make"] == "Toyota"
    assert item["batteries"][0]["model_no"] == "AAM-FL-00040B20L"
    assert item["batteries"][0]["current_price_inr"] == 5160
    print("self-test passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="output/official_amaron_fitments.json")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.5, help="Global minimum seconds between requests")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    result = export(args)
    print(f"Done: {len(result['fitments'])} fitments, {len(result['errors'])} errors -> {args.output}")


if __name__ == "__main__":
    main()
