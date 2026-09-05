"""Build one BatteryWala-ready JSON file from public manufacturer sources."""

import argparse
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


SOURCES = {
    "Exide": "https://www.exidecare.com/sitemap.xml",
    "Livguard": "https://www.livguard.com/sitemap.xml",
    "Tata Green": "https://www.tatagreenbattery.com/product-sitemap.xml",
}
POWERZONE_PDF = "https://www.powerzoneworld.com/wp-content/uploads/2025/06/Application-Chart-PowerZone-Website.pdf"
SF_PDF = "https://docs.exideindustries.com/pdf/mrp-list/mrcp-sf-vehicular-and-2wl-batteries.pdf"
DYNEX_PDF = "https://docs.exideindustries.com/pdf/mrp-list/mrcp-dynex-vehicular-and-2wl-batteries.pdf"


def get(url, data=None, headers=None):
    request = Request(url, data=data, headers={"User-Agent": "BatteryWala-official-fitment-index/1.0", **(headers or {})})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def text(url):
    return get(url).decode("utf-8", "replace")


def clean(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def number(value):
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    return float(match.group()) if match else None


def locs(xml):
    return [node.text for node in ET.fromstring(xml).iter() if node.tag.endswith("loc") and node.text]


def path_fields(url):
    parts = [unquote(value) for value in urlparse(url).path.strip("/").split("/")]
    return parts


def battery(brand, model, title=None, capacity=None, warranty=None, price=None, product_url=None):
    months = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", warranty or "")]
    return {
        "brand": brand,
        "model_no": clean(model).upper(),
        "title": clean(title) or clean(model),
        "capacity_ah": number(capacity),
        "warranty": clean(warranty) or None,
        "warranty_months": sum(months[:2]) if months else None,
        "current_price_inr": number(price),
        "product_url": product_url,
    }


def fitment(application, make, model, fuel, source_url, batteries, source_kind="vehicle_finder"):
    return {
        "application": clean(application).lower().replace(" ", "-"),
        "vehicle_make": clean(make) or None,
        "vehicle_model": clean(model),
        "fuel_type": clean(fuel) or None,
        "source_kind": source_kind,
        "source_url": source_url,
        "batteries": batteries,
    }


def parse_exide(url, page):
    parts = path_fields(url)
    products = []
    pattern = re.compile(
        r"<div class='contPart1'>.*?<h3>(.*?)<samp>\((.*?)\)</samp></h3>.*?"
        r"<strong>(.*?)</strong>.*?<div class='contPart2'>.*?<b>MRP:\s*Rs\s*([\d.]+)</b>.*?"
        r"<a href='([^']+)'",
        re.S | re.I,
    )
    for title, model, warranty, price, link in pattern.findall(page):
        products.append(battery("Exide", model, clean(title), warranty=warranty, price=price,
                                product_url=urljoin("https://www.exidecare.com", link)))
    if not products:
        raise ValueError("no official recommendation cards")
    return fitment(parts[1], parts[2].replace("-", " "), parts[3].replace("-", " "),
                    parts[4].replace("-", " "), url, products)


def parse_livguard(url, page):
    parts = path_fields(url)
    products = []
    for body in re.findall(r"<tbody[^>]*>(.*?)</tbody>", page, re.S | re.I):
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S | re.I):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
            link = re.search(r'href="(https://www\.livguard\.com/product/([^"/]+))"', row, re.I)
            if len(cells) >= 3 and link:
                products.append(battery("Livguard", link.group(2), clean(cells[0]), clean(cells[1]),
                                        clean(cells[2]), product_url=link.group(1)))
    unique = {item["model_no"]: item for item in products}
    if not unique:
        raise ValueError("no official recommendation table")
    return fitment(parts[1], parts[2].replace("-", " "), parts[3].replace("-", " "),
                    parts[4].replace("-", " "), url, list(unique.values()))


def parallel_pages(urls, parser, workers, fetch_page=True):
    found, errors = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        task = (lambda u: parser(u, text(u))) if fetch_page else (lambda u: parser(u, None))
        futures = {pool.submit(task, url): url for url in urls}
        for count, future in enumerate(as_completed(futures), 1):
            url = futures[future]
            try:
                found.append(future.result())
            except Exception as error:
                errors.append({"source_url": url, "error": str(error)[:200]})
            if count % 250 == 0:
                print(f"  processed {count}/{len(urls)}; fitments {len(found)}")
    return found, errors


def exide(workers):
    urls = [url for url in locs(text(SOURCES["Exide"])) if len(path_fields(url)) == 5 and "/battery-for/" in url]
    return parallel_pages(urls, parse_exide, workers)


def livguard(workers):
    urls = [url for url in locs(text(SOURCES["Livguard"])) if len(path_fields(url)) == 5 and "/battery/" in url]
    type_codes = {"two-wheeler": "2W", "three-wheeler": "3W", "bus-and-truck": "CV",
                  "tractor": "tractor", "car-and-suv": "carnsuv"}

    def slug(value):
        return re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", value.lower().strip()))

    groups = {}
    for url in urls:
        category, brand_slug = path_fields(url)[1:3]
        groups.setdefault((category, brand_slug), []).append(url)
    model_maps, errors = {}, []
    for (category, brand_slug), brand_urls in groups.items():
        brand = brand_slug.replace("-", " ").upper()
        query = urlencode({"selectedBrand": brand, "vtype": type_codes[category]})
        try:
            models = json.loads(text("https://www.livguard.com/battery/get-models?" + query))["models"]
            model_maps[(category, brand_slug)] = {slug(model): model for model in models}
        except Exception as error:
            errors.append({"source_url": brand_urls[0], "error": f"brand model list: {error}"[:200]})

    def lookup(url):
        category, brand_slug, model_slug, fuel_slug = path_fields(url)[1:5]
        brand = brand_slug.replace("-", " ").upper()
        model = model_maps.get((category, brand_slug), {}).get(model_slug, model_slug.replace("-", " ").title())
        fuel = fuel_slug.replace("-", " ").title()
        query = urlencode({"selectedBrand": brand, "selectedModel": model, "selectedFuel": fuel,
                           "vtype": type_codes[category]})
        data = json.loads(text("https://www.livguard.com/battery/get-recommended-batteries?" + query))
        products = []
        for item in data.get("recommendedBatteries", []):
            product = battery("Livguard", item.get("modelNumber"), item.get("newTitle") or item.get("name"),
                              item.get("capacity"), item.get("warranty"),
                              product_url=urljoin("https://www.livguard.com", item.get("batterySlug", "")))
            product["specifications"] = {"dimensions": item.get("dimensions") or None,
                                           "polarity": item.get("polarity") or None}
            products.append(product)
        if not products:
            raise ValueError("official finder returned no recommendations")
        return fitment(category, brand, model, fuel, url, products)

    records, page_errors = parallel_pages(urls, lambda url, unused: lookup(url), workers, fetch_page=False)
    return records, errors + page_errors


def tata_green(workers):
    urls = [url for url in locs(text(SOURCES["Tata Green"])) if "/product/" in url]

    def parse(url, page):
        compatible = re.search(r"Compatible Products:\s*</strong>(.*?)</p>", page, re.S | re.I)
        if not compatible:
            raise ValueError("no official compatible-products field")
        title = clean((re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I) or [None, path_fields(url)[-1]])[1])
        model = re.sub(r"\s+(?:Car|Two Wheeler|Tractor|Commercial Vehicle|Battery).*", "", title, flags=re.I)
        capacity = re.search(r"Capacity:\s*</?[^>]*>?\s*([\d.]+\s*Ah)", page, re.I)
        warranty = re.search(r"Warranty:\s*</?[^>]*>?\s*([^<]+)", page, re.I)
        price = re.search(r"(?:Offer Price|price)[^₹]{0,100}₹\s*([\d,]+)", page, re.I)
        item = battery("Tata Green", model, title, capacity.group(1) if capacity else None,
                       warranty.group(1) if warranty else None, price.group(1) if price else None, url)
        models = [clean(value) for value in clean(compatible.group(1)).split(",") if clean(value)]
        return [fitment("automotive", None, vehicle, None, url, [item], "product_compatibility") for vehicle in models]

    nested, errors = parallel_pages(urls, parse, workers)
    return [item for group in nested for item in group], errors


def powerzone(pdf_path):
    import pdfplumber
    rows = []
    with pdfplumber.open(pdf_path) as document:
        for page in document.pages[1:]:
            for table in page.extract_tables():
                if len(table) < 5 or not any("Vehicle Model" in (cell or "") for row in table[:4] for cell in row):
                    continue
                heading = clean(table[0][0]).upper()
                application = next((name for name in ("two-wheelers", "three-wheelers", "four-wheelers", "tractors", "commercial-vehicles", "special-purpose-vehicles", "genset") if name.replace("-", " ").upper() in heading.replace("2 WHEELERS", "TWO WHEELERS").replace("3 WHEELERS", "THREE WHEELERS").replace("4 WHEELERS", "FOUR WHEELERS")), "automotive")
                warranties = [clean(cell) for cell in table[3][4:] if clean(cell)]
                previous = [None] * 4
                for row in table[4:]:
                    if len(row) < 5:
                        continue
                    for index in range(min(4, len(row))):
                        if clean(row[index]):
                            previous[index] = clean(row[index])
                    vehicle_models = previous[3]
                    if not vehicle_models:
                        continue
                    products = []
                    for index, value in enumerate(row[4:]):
                        code = clean(value)
                        if code and re.search(r"\d", code):
                            products.append(battery("PowerZone", code, warranty=warranties[index] if index < len(warranties) else None))
                    if products:
                        rows.append(fitment(application, previous[1], vehicle_models, None, POWERZONE_PDF, products, "official_application_chart"))
    return rows


def price_list(pdf_path, brand, source_url):
    import pdfplumber
    with pdfplumber.open(pdf_path) as document:
        raw = "\n".join(page.extract_text() or "" for page in document.pages)
    pattern = re.compile(r"(?<![\d,])(\d+(?:\.\d+)?)\s+([A-Z0-9][A-Z0-9./&()-]*[A-Z0-9])\s+(\d+(?:F|M)(?:\+\d+P|\s+FOC)?)\s+([\d,]{3,})")
    return [battery(brand, code, capacity=capacity + " Ah", warranty=warranty, price=price)
            for capacity, code, warranty, price in pattern.findall(raw)]


def prediction_catalog(payload):
    application_keys = {
        "passengers": "four_wheeler", "four-wheelers": "four_wheeler", "car-and-suv": "four_wheeler",
        "car-suv-muv": "four_wheeler",
        "two-wheelers": "two_wheeler", "two-wheeler": "two_wheeler",
        "three-wheelers": "three_wheeler", "three-wheeler": "three_wheeler",
        "commercial": "commercial_vehicle", "commercial-vehicles": "commercial_vehicle",
        "bus-and-truck": "commercial_vehicle", "farm-vehicles": "tractor", "tractors": "tractor",
        "earth-moving-equipment": "earth_mover", "special-purpose-vehicles": "earth_mover", "genset": "generator",
    }

    def split_models(value):
        parts, current, depth = [], [], 0
        for char in value:
            depth += char == "("
            depth -= char == ")" and depth > 0
            if char in ",;" and depth == 0:
                part = clean("".join(current))
                if part:
                    parts.append(part)
                current = []
            else:
                current.append(char)
        final = clean("".join(current))
        return parts + ([final] if final else [])

    grouped = {}
    for row in payload["fitments"]:
        models = split_models(row["vehicle_model"]) if row["source_kind"] == "official_application_chart" else [row["vehicle_model"]]
        for model in models:
            application = application_keys.get(row["application"], row["application"])
            make = clean(row.get("vehicle_make"))
            model = clean(model)
            fuel = clean(row.get("fuel_type")) or None
            if not make or not model:
                continue
            key = (application, make, model, fuel or "")
            entry = grouped.setdefault(key, {"application": application, "vehicle_make": make,
                                              "vehicle_model": model, "fuel_type": fuel, "batteries": {}})
            for item in row["batteries"]:
                if not item.get("model_no"):
                    continue
                battery_key = (clean(item["brand"]), clean(item["model_no"]).upper())
                entry["batteries"][battery_key] = {"brand": battery_key[0], "model_no": battery_key[1],
                                                     "capacity_ah": item.get("capacity_ah")}
    fitments = []
    for entry in grouped.values():
        entry["batteries"] = sorted(entry["batteries"].values(), key=lambda item: (item["brand"], item["model_no"]))
        fitments.append(entry)
    fitments.sort(key=lambda item: (item["application"], item["vehicle_make"], item["vehicle_model"], item.get("fuel_type") or ""))
    return {"schema_version": "1.0", "fitments": fitments}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/official_battery_fitments_all_brands.json")
    parser.add_argument("--catalog", default="app/data/fitments.json")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--skip-network", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        sample = "<tbody><tr><td><a href=\"https://www.livguard.com/product/zu42b20l\">ZU42B20L</a></td><td>35 Ah</td><td>30 + 30 Months</td></tr></tbody>"
        result = parse_livguard("https://www.livguard.com/battery/car-and-suv/maruti/baleno/petrol", sample)
        assert result["batteries"][0]["model_no"] == "ZU42B20L"
        print("self-test passed")
        return

    output = Path(args.output)
    payload = {
        "schema_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "usage_note": "Manufacturer-sourced factual index. Verify dimensions, terminal layout and current warranty before sale; obtain source-owner approval before commercial republication.",
        "fitments": [], "products_without_vehicle_fitment": [], "errors": [], "sources": [],
    }
    amaron_path = Path("output/official_amaron_fitments.json")
    amaron = json.loads(amaron_path.read_text("utf-8"))
    for item in amaron["fitments"]:
        item.setdefault("source_kind", "vehicle_finder")
    payload["fitments"].extend(amaron["fitments"])
    payload["errors"].extend(amaron.get("errors", []))
    payload["sources"].append({"brand": "Amaron", "url": "https://www.amaron.com/sitemap.xml", "fitments": len(amaron["fitments"])})

    if args.skip_network:
        raise SystemExit("network sources cannot be skipped when building the full file")
    for brand, loader in (("Exide", exide), ("Livguard", livguard), ("Tata Green", tata_green)):
        print(f"Fetching {brand} official data")
        records, errors = loader(args.workers)
        payload["fitments"].extend(records)
        payload["errors"].extend(errors)
        payload["sources"].append({"brand": brand, "url": SOURCES[brand], "fitments": len(records), "errors": len(errors)})

    temp = Path("tmp/pdfs")
    temp.mkdir(parents=True, exist_ok=True)
    pdfs = ((POWERZONE_PDF, temp / "powerzone-application-chart.pdf"), (SF_PDF, temp / "sf-mrp.pdf"), (DYNEX_PDF, temp / "dynex-mrp.pdf"))
    for url, path in pdfs:
        if not path.exists():
            path.write_bytes(get(url))
    powerzone_rows = powerzone(pdfs[0][1])
    payload["fitments"].extend(powerzone_rows)
    payload["sources"].append({"brand": "PowerZone", "url": POWERZONE_PDF, "fitments": len(powerzone_rows)})
    for brand, source, path in (("SF Sonic", SF_PDF, pdfs[1][1]), ("Dynex", DYNEX_PDF, pdfs[2][1])):
        products = price_list(path, brand, source)
        payload["products_without_vehicle_fitment"].extend(products)
        payload["sources"].append({"brand": brand, "url": source, "fitments": 0, "products": len(products), "limitation": "Official current product list found, but no public official vehicle-fitment mapping found."})

    payload["fitments"].sort(key=lambda item: (item["batteries"][0]["brand"], item.get("vehicle_make") or "", item["vehicle_model"], item["source_url"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    catalog = Path(args.catalog)
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(json.dumps(prediction_catalog(payload), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Done: {len(payload['fitments'])} fitments, {len(payload['products_without_vehicle_fitment'])} unmapped products -> {output}; catalog -> {catalog}")


if __name__ == "__main__":
    main()
