"""One-time importer for the supplied 2026 catalogues.

Usage: python tools/import_supplied_catalogs.py "C:/path/to/Data"
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'app' / 'data' / 'catalogs'
SOURCE = Path(sys.argv[1])
STAMP = datetime.now(timezone.utc).isoformat()


def save(name, records):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps({
        'schema_version': '2.0', 'updated_at': STAMP, 'records': records
    }, indent=2), encoding='utf-8')
    print(f'{name}: {len(records)} records')


def application(section):
    section = section.upper()
    if '2-WHEELER' in section:
        return 'two_wheeler'
    if 'E-RICKSHAW' in section:
        return 'vehicle'
    return 'vehicle'


def exide_retail():
    path = SOURCE / 'Humsafar Price List-EXIDE-VEH&2W-20thMar26.pdf'
    records = []
    with pdfplumber.open(path) as pdf:
        for table in pdf.pages[0].extract_tables():
            if not table or not table[0] or not table[0][0]:
                continue
            section = table[0][0].replace('\n', ' ')
            if ':' not in section:
                continue
            for row in table[1:]:
                if len(row) != 4 or not row[0] or not row[1] or not row[3]:
                    continue
                try:
                    capacity = float(re.search(r'\d+(?:\.\d+)?', row[0]).group())
                    price = float(row[3].replace(',', ''))
                except (AttributeError, ValueError):
                    continue
                records.append({
                    'source': path.name, 'source_type': 'retail', 'page': 1,
                    'brand': 'EXIDE', 'series': section, 'model_no': row[1].strip(),
                    'capacity_ah': capacity, 'application': application(section),
                    'warranty': row[2].strip(), 'mrp': price
                })
    save('exide-retail.json', records)


def exide_scrap():
    path = SOURCE / 'Mobility Dealer Scrap Price List-26thMar26.pdf'
    with pdfplumber.open(path) as pdf:
        lines = (pdf.pages[0].extract_text(layout=True) or '').splitlines()
    records = []
    for line in lines:
        values = [float(x.replace(',', '')) for x in re.findall(r'\d[\d,]*(?:\.\d+)?', line)]
        if len(values) == 6 and values[0] <= 250 and values[3] <= 250:
            for offset in (0, 3):
                records.append({
                    'source': path.name, 'source_type': 'scrap', 'page': 1,
                    'brand': 'EXIDE', 'model_no': None, 'application': 'automotive_scrap',
                    'capacity_ah': values[offset], 'scrap_price': values[offset + 1],
                    'unbranded_scrap_price': values[offset + 2]
                })
    save('exide-scrap.json', records)


def prycal():
    path = SOURCE / 'PMK-PRYCAL AUTO DP & MRP WEF 18 05 2026.pdf'
    rows = [
        ('PN 40 Z R/L',35,2820,4108),('PN 40 ZL BH',35,3130,4569),('PN 45 Z R/L',45,4110,5965),
        ('PN 60 R/L',60,4250,6079),('PN 700 R/L',65,4700,6839),('PN 75',75,5130,7445),
        ('PN 80',80,5540,8061),('PN 90',90,6110,8903),('PN 100',100,6670,9734),
        ('PN 120',120,7850,11418),('PN 130',130,8390,12199),('PN 135',135,8670,12620),
        ('PN 150',150,9450,13739),('PN 165',165,10350,15063),('PN 180',180,11110,16162),
        ('PN 200',200,11840,17230),('PN 75D 23LBH',68,5160,7968),('PN 80D23 R',68,5250,8071),
        ('PN 95 H29R',95,6570,9579),('PNS 1200 L',120,7750,11259),('DIN 50',50,4120,5976),
        ('DIN 60 R/L',60,4710,6859),('DIN 66',66,5560,8090)
    ]
    save('pmk-prycal-retail.json', [{
        'source': path.name, 'source_type': 'retail', 'page': 1, 'brand': 'PMK-PRYCAL',
        'model_no': model, 'capacity_ah': capacity, 'application': 'vehicle',
        'warranty': '18+18 months', 'dealer_price': dp, 'mrp': mrp
    } for model, capacity, dp, mrp in rows])


def amaron():
    path = SOURCE / 'IMG-20260606-WA0006.jpg'
    rows = """
AAM-PR-00050B20L 4565
AAM-PR-00050B20R 4565
AAM-PR-0055B24LS 6853
AAM-PR-574102069 10073
AAM-PR-600109087 16694
AAM-PR-0BH80D31L 14759
AAM-FL-00040B20L 3948
AAM-FL-00040B20R 3948
AAM-FL-00042B20L 4204
AAM-FL-00042B20R 4204
AAM-FL-0BH40B20L 4399
AAM-FL-0BH45D20L 5891
AAM-FL-0BH90D23L 6363
AAM-FL-545106036 5378
AAM-FL-555112054 6811
AAM-FL-566112060 6961
AAM-FL-00080D23L 6049
AAM-FL-550113042 5952
AAM-FL-550114042 5952
AAM-FL-555111054 6811
AAM-FL-565106590 6974
AAM-FL-580112073 10154
AMS-FL-00040B20L 3948
AMS-FL-00042B20L 4204
AMS-FL-00042B20R 4204
AMS-FL-550114042 5952
AMS-FL-565106590 6974
AAM-GO-00034B20L 3689
AAM-GO-00034B20R 3689
AAM-GO-00038B20L 3405
AAM-GO-00038B20R 3405
AAM-GO-0BH38B20R 4307
AAM-GO-00050B24L 5780
AAM-GO-00095D26L 6660
AAM-GO-00095D26R 6660
AAM-GO-565106590 6722
AAM-GO-00085D23R 6312
AAM-GO-00105D26R 7319
AAM-GO-00105D26L 7319
AAM-GO-00105D31R 7174
AAM-GO-00105D31L 7174
AAM-GO-00135D31R 7851
AAM-GO-00135D31L 7851
AAM-BL-0BL0300RMF 3006
AAM-BL-0BL0400LMF 3274
AAM-BL-0BL0400RMF 3274
AAM-BL-BL00500RS 5589
AAM-BL-BL00500LS 5589
AAM-BL-0BL0700LMF 6132
AAM-BL-0BL0700RMF 6132
AAM-BL-0BL0800LMF 6241
AAM-BL-0BL0800RMF 6241
AAM-BL-BL880D31R 6430
AAM-BL-BL880D31L 6430
AAM-BL-0BL900LMF 6768
AAM-BL-0BL900RMF 6768
AAM-BL-BL1000LMF 7318
AAM-BL-BL1000RMF 7318
AAM-BL-BL1300RMF 10043
AAM-BL-BL1500RMF 11933
AAM-BL-BL1600LMF 5052
AAM-BL-BL1600RMF 5052
AAM-BL-BL0030RMF 2833
AAM-BL-BL0040LMF 3141
AAM-BL-BL0040RMF 3141
AAM-BL-BL0050LS 5344
AAM-BL-BL0050RS 5344
AAM-BL-BL0060LMF 4810
AAM-BL-BL0060RMF 4810
AAM-BL-BL0070LMF 5877
AAM-BL-BL0070RMF 5877
AAM-BL-BL0080LMF 5985
AAM-BL-BL0080RMF 5985
AAM-BL-BL0090LMF 6422
AAM-BL-BL0090RMF 6422
AAM-BL-BL090E41L 6581
AAM-BL-BL090E41R 6581
AAM-BL-BL100E41L 7176
AAM-BL-BL100E41R 7176
AAM-BL-0BL100LMF 7083
AAM-BL-0BL100RMF 7083
AAM-BL-0BL130RMF 9699
AAM-BL-0BL150RMF 11561
AAM-HW-HC620D31R 6738
AAM-HW-NT650L29R 7262
AAM-HW-NT800D04R 11967
AAM-HW-NTX000D04R 13691
AAM-HW-HC180N04R 15517
AAM-HW-HCX20H52R 15942
AAM-HW-NT800L41R 9603
AAM-HW-NT700F41R 8480
AAM-HW-NT800F51R 10600
AAM-HR-TR500D31L 6669
AAM-HR-TR500D31R 6669
AAM-HR-NT600H29L 7190
AAM-HR-NT600H29R 7190
AAM-HR-NT600E41R 7465
AAM-HR-NT600E41L 7465
""".strip().splitlines()
    save('amaron-retail.json', [{
        'source': path.name, 'source_type': 'retail', 'page': 1, 'brand': 'AMARON',
        'model_no': line.rsplit(' ', 1)[0], 'capacity_ah': None, 'application': 'vehicle',
        'mrp': float(line.rsplit(' ', 1)[1])
    } for line in rows])


exide_retail()
exide_scrap()
prycal()
amaron()
