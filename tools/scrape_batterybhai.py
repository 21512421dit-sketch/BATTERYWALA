"""Export BatteryBhai vehicle-fitment results to JSON using its public finder endpoints."""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE_URL = "https://www.batterybhai.com/"
PRODUCT_TYPES = {"1": "Four Wheeler Batteries", "10": "2 Wheeler Batteries", "13": "Truck Batteries"}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def amount(text):
    match = re.search(r"Rs\.?\s*([\d,]+)", text or "", re.I)
    return int(match.group(1).replace(",", "")) if match else None


class OptionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.options, self.value, self.text = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "option":
            self.value = dict(attrs).get("value", "")
            self.text = []

    def handle_data(self, data):
        if self.value is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self.value is not None:
            name = clean("".join(self.text))
            if self.value and name:
                self.options.append({"id": self.value, "name": name})
            self.value = None


class ProductParser(HTMLParser):
    fields = {"title", "warranty_list", "reducedfrom", "offer_price2", "price1"}

    def __init__(self):
        super().__init__()
        self.products, self.card, self.div_depth, self.stack = [], None, 0, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        if tag == "div" and "col_1_of_3" in classes and self.card is None:
            self.card = {name: [] for name in self.fields}
            self.card.update({"detail_url": None, "image_url": None, "sold_out": False})
            self.div_depth = 1
        elif self.card is not None and tag == "div":
            self.div_depth += 1

        if self.card is not None:
            if "sold_out" in classes:
                self.card["sold_out"] = True
            ancestors = set().union(*(item[1] for item in self.stack)) if self.stack else set()
            if tag == "a" and "title" in ancestors and not self.card["detail_url"]:
                self.card["detail_url"] = urljoin(BASE_URL, attrs.get("href", ""))
            if tag == "img" and "product_image" in ancestors and not self.card["image_url"]:
                self.card["image_url"] = attrs.get("data-original") or attrs.get("src")
        self.stack.append((tag, classes))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.card is None:
            return
        active = set().union(*(item[1] for item in self.stack)) if self.stack else set()
        for field in self.fields & active:
            self.card[field].append(data)

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()
        if self.card is not None and tag == "div":
            self.div_depth -= 1
            if self.div_depth == 0:
                product = self._finish(self.card)
                if product:
                    self.products.append(product)
                self.card = None

    @staticmethod
    def _finish(card):
        title = clean("".join(card["title"]))
        detail_url = card["detail_url"]
        if not title or not detail_url:
            return None
        parts = [part for part in urlparse(detail_url).path.split("/") if part]
        try:
            marker = next(i for i, part in enumerate(parts) if part.endswith("-details"))
            model_no, product_id, brand_id = parts[marker + 1 : marker + 4]
        except (StopIteration, ValueError):
            model_no = product_id = brand_id = None
        capacity = re.search(r"\(([\d.]+)\s*Ah\)", title, re.I)
        price_lines = [clean(value) for value in card["price1"]]
        return {
            "product_id": product_id,
            "brand_id": brand_id,
            "model_no": model_no.strip("-") if model_no else None,
            "title": title,
            "capacity_ah": float(capacity.group(1)) if capacity else None,
            "warranty": clean("".join(card["warranty_list"])).removeprefix("Warranty:").strip(),
            "mrp": amount(clean("".join(card["reducedfrom"]))),
            "discount_percent": next((int(x) for x in re.findall(r"\d+", clean("".join(card["offer_price2"])))), None),
            "price_with_exchange": next((amount(x) for x in price_lines if "with old" in x.lower()), None),
            "price_without_exchange": next((amount(x) for x in price_lines if "without old" in x.lower()), None),
            "sold_out": card["sold_out"],
            "detail_url": detail_url.replace("http://", "https://"),
            "image_url": card["image_url"],
        }


class Client:
    def __init__(self, delay):
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.delay, self.last_request = delay, 0.0

    def get(self, path, params=None):
        wait = self.delay - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        url = urljoin(BASE_URL, path)
        if params:
            url += "?" + urlencode(params)
        request = Request(url, headers={"User-Agent": "BatteryWala-fitment-export/1.0 (+authorized internal use)"})
        with self.opener.open(request, timeout=30) as response:
            self.last_request = time.monotonic()
            return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    def options(self, action, **params):
        parser = OptionParser()
        parser.feed(self.get("ajax_process_home.php", {"action": action, **params}))
        return parser.options


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def scrape(args):
    output = Path(args.output)
    payload = json.loads(output.read_text(encoding="utf-8")) if args.resume and output.exists() else {
        "schema_version": "1.0",
        "source": BASE_URL,
        "location": {"state_id": args.state_id, "city_id": args.city_id},
        "predictions": [],
        "errors": [],
    }
    if payload["location"] != {"state_id": args.state_id, "city_id": args.city_id}:
        raise SystemExit("Existing JSON uses a different location; choose another output file or omit --resume.")

    done = {(x["product_type_id"], x["manufacturer_id"], x["vehicle_model_id"]) for x in payload["predictions"]}
    client, fetched = Client(args.delay), 0
    for product_type_id in args.product_types.split(","):
        product_type_id = product_type_id.strip()
        if product_type_id not in PRODUCT_TYPES:
            raise SystemExit(f"Unsupported fitment product type: {product_type_id}")
        manufacturers = client.options("fetchManufacturer", btype=product_type_id)
        brands = {x["id"]: x["name"] for x in client.options("fetchBrand", brandSelection=product_type_id)}
        for manufacturer in manufacturers:
            for model in client.options("fetchModel", selectedManufacturer=manufacturer["id"]):
                key = (product_type_id, manufacturer["id"], model["id"])
                if key in done:
                    continue
                try:
                    html = client.get("search_result.php", {
                        "bType": product_type_id,
                        "manufactID": manufacturer["id"],
                        "modelID": model["id"],
                        "bBrand_Wheeler": "",
                        "stateID": args.state_id,
                        "frmSearchCity_Wheeler": args.city_id,
                    })
                    parser = ProductParser()
                    parser.feed(html)
                    for product in parser.products:
                        product["brand"] = brands.get(product["brand_id"])
                    payload["predictions"].append({
                        "product_type_id": product_type_id,
                        "product_type": PRODUCT_TYPES[product_type_id],
                        "manufacturer_id": manufacturer["id"],
                        "manufacturer": manufacturer["name"],
                        "vehicle_model_id": model["id"],
                        "vehicle_model": model["name"],
                        "batteries": parser.products,
                    })
                except Exception as error:
                    payload["errors"].append({"key": key, "error": str(error)[:300]})
                done.add(key)
                fetched += 1
                if fetched % args.checkpoint_every == 0:
                    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                    atomic_write(output, payload)
                    print(f"Saved {len(payload['predictions'])} predictions to {output}")
                if args.limit and fetched >= args.limit:
                    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                    atomic_write(output, payload)
                    return payload
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write(output, payload)
    return payload


def self_test():
    options = OptionParser()
    options.feed('<select><option value="">Select</option><option value="7">Maruti &amp; Suzuki</option></select>')
    assert options.options == [{"id": "7", "name": "Maruti & Suzuki"}]
    products = ProductParser()
    products.feed('''<div class="col_1_of_3"><div class="product_image"><img src="x.jpg"></div>
    <p class="title"><a href="car-batteries-details/AAM-GO-38B20R/12/2/1/35/1">Amaron AAM-GO-38B20R (35 Ah)</a></p>
    <p class="warranty_list">Warranty: 60 Months</p><span class="reducedfrom">MRP: Rs. 5,014</span>
    <span class="offer_price2">35 % OFF</span><div class="price1">With old Battery: Rs. 3,299</div>
    <div class="price1">Without old Battery: Rs. 4,199</div></div>''')
    assert products.products[0]["model_no"] == "AAM-GO-38B20R"
    assert products.products[0]["price_without_exchange"] == 4199
    print("self-test passed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="output/batterybhai_predictions.json")
    parser.add_argument("--product-types", default="1,10,13", help="Comma-separated IDs: 1 cars, 10 bikes, 13 trucks")
    parser.add_argument("--state-id", default="1", help="Pricing state ID; default 1 (Delhi)")
    parser.add_argument("--city-id", default="1", help="Pricing city ID; default 1 (New Delhi)")
    parser.add_argument("--delay", type=float, default=1.0, help="Minimum seconds between requests")
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0, help="Stop after N new vehicle models (0 = all)")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--i-have-written-permission", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.i_have_written_permission:
        parser.error("BatteryBhai's terms prohibit wholesale copying without advance written permission. Obtain it, then pass --i-have-written-permission.")
    result = scrape(args)
    print(f"Done: {len(result['predictions'])} predictions, {len(result['errors'])} errors")


if __name__ == "__main__":
    main()
