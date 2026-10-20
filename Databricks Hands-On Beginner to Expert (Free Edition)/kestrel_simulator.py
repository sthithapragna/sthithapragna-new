# Databricks notebook source
# MAGIC %md
# MAGIC # Kestrel Foods: source system simulator
# MAGIC
# MAGIC Creates the Kestrel catalog and landing volumes, then writes the raw files that Kestrel's
# MAGIC four source systems deliver: till (POS) transactions, web order events, loyalty CRM changes
# MAGIC and warehouse stock snapshots, plus the store, product and promotion reference files.
# MAGIC
# MAGIC Everything is seeded, so every viewer gets exactly the same files and the same numbers.
# MAGIC
# MAGIC | Mode | What it does |
# MAGIC |---|---|
# MAGIC | `setup` | Creates the catalog, schemas and volumes. Safe to re-run. |
# MAGIC | `backfill` | Writes September 2026: deliveries from 1 September to 1 October. Skips anything already written. |
# MAGIC | `next_day` | Delivers the next day's files, one day after the last delivery. |
# MAGIC | `status` | Shows the simulated date and what has been delivered. |
# MAGIC | `reset` | Deletes the whole Kestrel catalog. Needs `confirm_reset` set to `YES`. |
# MAGIC
# MAGIC Course: Databricks hands-on, beginner to expert. Episode 02. Simulator version 1.1.1.
# MAGIC
# MAGIC **1.1.1:** warehouse snapshots are written with microsecond timestamps (serverless can't read Parquet nanoseconds).
# MAGIC Run `setup` once to fix snapshots an older version wrote. Every value is unchanged.

# COMMAND ----------

import os, json, shutil, datetime as dt
import numpy as np
import pandas as pd

try:
    dbutils  # injected by Databricks
    IN_DATABRICKS = True
except NameError:
    IN_DATABRICKS = False

if IN_DATABRICKS:
    dbutils.widgets.dropdown("mode", "status", ["setup", "backfill", "next_day", "status", "reset"], "Mode")
    dbutils.widgets.text("catalog", "kestrel", "Catalog")
    dbutils.widgets.text("confirm_reset", "", "Type YES to reset")
    MODE = dbutils.widgets.get("mode")
    CATALOG = dbutils.widgets.get("catalog").strip()
    CONFIRM = dbutils.widgets.get("confirm_reset").strip()
    ROOT = f"/Volumes/{CATALOG}"
else:
    MODE = os.environ.get("SIM_MODE", "status")
    CATALOG = "kestrel"
    CONFIRM = os.environ.get("SIM_CONFIRM", "")
    ROOT = os.path.join(os.environ.get("SIM_LOCAL_ROOT", "/tmp/kestrel_sim"), "Volumes", CATALOG)

print(f"mode={MODE}  catalog={CATALOG}  root={ROOT}")

# COMMAND ----------

# MAGIC %md ## The frozen landscape
# MAGIC These constants are Kestrel's landscape. Do not change them: every episode relies on them.

# COMMAND ----------

SIM_VERSION = "1.1.1"
SEED = 20260901
FIRST_DELIVERY = dt.date(2026, 9, 1)     # reference files and the CRM full export arrive
FIRST_BUSINESS = dt.date(2026, 9, 1)     # first trading day in the history
BACKFILL_LAST_DELIVERY = dt.date(2026, 10, 1)

SCHEMAS = ["landing", "bronze", "silver", "gold", "ops"]
LANDING_VOLUMES = ["pos", "ecom", "crm", "wms", "reference"]

REGIONS = [  # code, name, share of stores
    ("LON", "London", 0.16), ("SE", "South East", 0.16), ("SW", "South West", 0.10),
    ("MID", "Midlands", 0.15), ("NW", "North West", 0.13), ("NE", "North East", 0.06),
    ("YH", "Yorkshire and the Humber", 0.10), ("SCO", "Scotland", 0.09), ("WAL", "Wales", 0.05),
]
TOWNS = {
    "LON": [("Kensington", "W8"), ("Camden", "NW1"), ("Hackney", "E8"), ("Croydon", "CR0"), ("Wimbledon", "SW19"), ("Ealing", "W5"), ("Greenwich", "SE10"), ("Islington", "N1")],
    "SE": [("Brighton", "BN1"), ("Reading", "RG1"), ("Guildford", "GU1"), ("Maidstone", "ME14"), ("Oxford", "OX1"), ("Milton Keynes", "MK9"), ("Canterbury", "CT1"), ("Crawley", "RH10")],
    "SW": [("Bristol", "BS1"), ("Exeter", "EX1"), ("Plymouth", "PL1"), ("Bath", "BA1"), ("Swindon", "SN1"), ("Taunton", "TA1"), ("Truro", "TR1")],
    "MID": [("Birmingham", "B1"), ("Coventry", "CV1"), ("Leicester", "LE1"), ("Nottingham", "NG1"), ("Derby", "DE1"), ("Wolverhampton", "WV1"), ("Northampton", "NN1"), ("Stoke", "ST1")],
    "NW": [("Manchester", "M1"), ("Liverpool", "L1"), ("Preston", "PR1"), ("Chester", "CH1"), ("Bolton", "BL1"), ("Lancaster", "LA1"), ("Warrington", "WA1")],
    "NE": [("Newcastle", "NE1"), ("Sunderland", "SR1"), ("Durham", "DH1"), ("Middlesbrough", "TS1")],
    "YH": [("Leeds", "LS1"), ("Sheffield", "S1"), ("York", "YO1"), ("Hull", "HU1"), ("Bradford", "BD1"), ("Harrogate", "HG1")],
    "SCO": [("Glasgow", "G1"), ("Edinburgh", "EH1"), ("Aberdeen", "AB10"), ("Dundee", "DD1"), ("Inverness", "IV1"), ("Stirling", "FK8")],
    "WAL": [("Cardiff", "CF10"), ("Swansea", "SA1"), ("Newport", "NP20"), ("Wrexham", "LL11"), ("Bangor", "LL57")],
}
FORMATS = {  # format: store count, sqft range, baskets per day, mean extra lines per basket, tills, hours
    "Superstore": dict(n=60, sqft=(40000, 90000), baskets=100, lines=5.0, tills=12, hours=(7, 22)),
    "Local":      dict(n=250, sqft=(3000, 6000), baskets=30, lines=2.0, tills=3, hours=(7, 23)),
    "Express":    dict(n=90, sqft=(1500, 3000), baskets=15, lines=0.8, tills=2, hours=(6, 23)),
    "Dark":       dict(n=12, sqft=(20000, 35000), baskets=0, lines=0.0, tills=0, hours=(0, 0)),
}
FLAGSHIP = "0001"            # Kensington Superstore. 12x a normal superstore (quirk 17)
FLAGSHIP_BASKETS = 1200
NEW_STORE = "0413"           # opens 2026-09-20, missing from reference until 2026-09-23 (quirk 18)
NEW_STORE_OPENS = dt.date(2026, 9, 20)
NEW_STORE_REF_DELIVERY = dt.date(2026, 9, 23)
DOW = [0.90, 0.90, 0.95, 1.00, 1.15, 1.25, 0.85]   # Monday .. Sunday

CATEGORIES = [  # name, share, price range, VAT rate
    ("Fresh Produce", 0.100, (0.35, 3.50), 0.0), ("Bakery", 0.060, (0.60, 3.50), 0.0),
    ("Dairy", 0.080, (0.50, 4.50), 0.0), ("Meat and Fish", 0.080, (2.00, 12.00), 0.0),
    ("Chilled", 0.100, (1.00, 6.00), 0.0), ("Frozen", 0.080, (1.00, 7.00), 0.0),
    ("Ambient Grocery", 0.200, (0.40, 5.00), 0.0), ("Drinks", 0.080, (0.50, 6.00), 0.20),
    ("Alcohol", 0.060, (4.00, 25.00), 0.20), ("Household", 0.070, (1.00, 9.00), 0.20),
    ("Health and Beauty", 0.060, (1.00, 12.00), 0.20), ("Baby", 0.015, (1.00, 15.00), 0.0),
    ("Pet", 0.015, (0.80, 14.00), 0.20),
]
ITEMS = {
    "Fresh Produce": ["Bananas", "Apples", "Carrots", "Potatoes", "Onions", "Tomatoes", "Broccoli", "Strawberries", "Grapes", "Salad Leaves"],
    "Bakery": ["White Loaf", "Wholemeal Loaf", "Croissants", "Bagels", "Crumpets", "Sourdough", "Rolls", "Muffins"],
    "Dairy": ["Semi Skimmed Milk", "Whole Milk", "Cheddar", "Greek Yoghurt", "Butter", "Double Cream", "Eggs", "Mozzarella"],
    "Meat and Fish": ["Chicken Breast", "Beef Mince", "Pork Sausages", "Salmon Fillets", "Bacon", "Cod Fillets", "Lamb Chops"],
    "Chilled": ["Hummus", "Fresh Pasta", "Coleslaw", "Ready Meal", "Soup", "Pizza", "Quiche", "Sandwich"],
    "Frozen": ["Peas", "Chips", "Fish Fingers", "Ice Cream", "Frozen Pizza", "Mixed Veg", "Garlic Bread"],
    "Ambient Grocery": ["Pasta", "Rice", "Baked Beans", "Chopped Tomatoes", "Cereal", "Tea Bags", "Coffee", "Biscuits", "Crisps", "Jam", "Flour", "Olive Oil"],
    "Drinks": ["Orange Juice", "Cola", "Sparkling Water", "Still Water", "Lemonade", "Squash"],
    "Alcohol": ["Lager", "Red Wine", "White Wine", "Prosecco", "Gin", "Cider", "Whisky"],
    "Household": ["Washing Up Liquid", "Laundry Capsules", "Kitchen Roll", "Toilet Roll", "Bin Bags", "Surface Spray"],
    "Health and Beauty": ["Shampoo", "Toothpaste", "Shower Gel", "Deodorant", "Paracetamol", "Hand Cream"],
    "Baby": ["Nappies", "Baby Wipes", "Baby Food", "Formula"],
    "Pet": ["Dog Food", "Cat Food", "Cat Litter", "Dog Treats"],
}
BRANDS = ["Kestrel", "Kestrel Finest", "Kestrel Value", "Hartwell", "Ridgeway", "Morland", "Castleford", "Brookfield", "Ashby", "Penrose"]
PACKS = ["1 each", "4 pack", "6 pack", "250g", "500g", "1kg", "2kg", "330ml", "500ml", "1l", "2l", "750ml", "12 pack", "x2"]
N_PRODUCTS = 4000
RANGE = {"Superstore": 4000, "Local": 1200, "Express": 500, "Dark": 2500}
PRICE_CHANGE_DATE = dt.date(2026, 9, 14)  # quirk 16
N_PRICE_CHANGES = 300

N_MEMBERS = 1_200_000
FIRST_MEMBER_ID = 10_000_001
FIRST_NAMES = ["Oliver", "Amelia", "George", "Isla", "Harry", "Ava", "Noah", "Mia", "Jack", "Ivy", "Leo", "Lily", "Arthur", "Freya", "Muhammad", "Florence", "Oscar", "Grace", "Charlie", "Emily", "Jacob", "Sophie", "Thomas", "Olivia", "James", "Poppy", "William", "Ella", "Henry", "Rosie", "Priya", "Aisha", "Rhys", "Cerys", "Callum", "Eilidh", "Sean", "Niamh", "Daniel", "Hannah"]
LAST_NAMES = ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Patel", "Robinson", "Wright", "Thompson", "Evans", "Walker", "White", "Roberts", "Green", "Hall", "Thomas", "Clarke", "Jackson", "Wood", "Harris", "Edwards", "Turner", "Martin", "Cooper", "Hill", "Ward", "Hughes", "Moore", "Clark", "King", "Harrison", "Lewis", "Baker", "Lee", "Allen", "Morris", "Khan", "Scott", "Watson", "Davis", "Parker", "Campbell", "Anderson", "MacDonald", "Singh", "Ali", "Kelly"]
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.co.uk", "hotmail.co.uk", "icloud.com", "btinternet.com"]
TIERS = (["Blue", "Silver", "Gold"], [0.70, 0.22, 0.08])

ECOM_ORDERS_PER_DAY = 1500
CRM_CHANGES_PER_DAY = 2000
WEB_PRICE_STRING_FROM = dt.date(2026, 9, 10)  # quirk 11: app 5.2 sends prices as strings

# Planted delivery quirks
LATE_FILE = ("WAL", dt.date(2026, 9, 12), dt.date(2026, 9, 15))    # quirk 5: region, business date, delivered
RESENT_FILE = ("SCO", dt.date(2026, 9, 16), dt.date(2026, 9, 18))  # quirk 4
HEADER_IN_MIDDLE = ("MID", dt.date(2026, 9, 8))                     # quirk 22
PROMO_CODE_FROM = dt.date(2026, 9, 22)                             # quirk 6: new column

# Live events: changes that happen after the September history, while the course runs (from 1.1)
TILL_UPGRADE_FROM = dt.date(2026, 10, 4)   # live event 1: checkout_type inserted after till_id

# COMMAND ----------

# MAGIC %md ## Helpers

# COMMAND ----------

def rng(*keys):
    """A generator seeded by the landscape seed plus the given integer keys."""
    return np.random.default_rng([SEED, *[int(k) for k in keys]])

def dkey(d):
    return int(d.strftime("%Y%m%d"))

def path(*parts):
    return os.path.join(ROOT, *parts)

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def write_text_atomic(target, text):
    # Written in place: volumes are object storage, so no temp-and-rename. A day is only
    # marked delivered after all its files are written, so a failed day is simply redone.
    ensure_dir(os.path.dirname(target))
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

def write_csv(df, target):
    write_text_atomic(target, df.to_csv(index=False, float_format="%.2f", lineterminator="\n"))

def retail_price(x):
    """Round to a price that ends in 9, like a real shelf edge label."""
    return np.maximum(np.round(np.round(x * 10) / 10 - 0.01, 2), 0.19)

# COMMAND ----------

# MAGIC %md ## Reference data: stores, products, promotions, members

# COMMAND ----------

def build_stores():
    r = rng(1)
    rows, sid = [], 1
    fmt_list = []
    for fmt, spec in FORMATS.items():
        fmt_list += [fmt] * spec["n"]
    fmt_list = list(r.permutation(fmt_list))
    fmt_list.remove("Superstore")
    fmt_list = ["Superstore"] + fmt_list           # store 0001 is the flagship superstore
    codes = [c for c, _, _ in REGIONS]
    shares = np.array([s for _, _, s in REGIONS])
    region_of = r.choice(len(codes), size=len(fmt_list), p=shares / shares.sum())
    region_of[0] = 0                               # flagship is in London
    used = {}
    for i, fmt in enumerate(fmt_list):
        reg = codes[region_of[i]]
        town, area = (("Kensington", "W8") if i == 0 else TOWNS[reg][r.integers(len(TOWNS[reg]))])
        base = f"Kestrel {town} {fmt}"
        used[base] = used.get(base, 0) + 1
        name = base if used[base] == 1 else f"{base} {used[base]}"
        spec = FORMATS[fmt]
        rows.append(dict(
            store_id=f"{sid:04d}", store_name=name, format=fmt, region_code=reg,
            region_name=dict((c, n) for c, n, _ in REGIONS)[reg], town=town,
            postcode=f"{area} {r.integers(1, 10)}{chr(65 + r.integers(26))}{chr(65 + r.integers(26))}",
            open_date=(dt.date(1998, 1, 1) + dt.timedelta(days=int(r.integers(0, 10200)))).isoformat(),
            sqft=int(r.integers(*spec["sqft"]) // 100 * 100),
            is_24h="Y" if (fmt == "Superstore" and r.random() < 0.25) else "N",
        ))
        sid += 1
    rows[0]["open_date"] = "2004-06-18"
    rows[0]["is_24h"] = "N"
    rows.append(dict(store_id=NEW_STORE, store_name="Kestrel Solihull Local", format="Local",
                     region_code="MID", region_name="Midlands", town="Solihull", postcode="B91 3QW",
                     open_date=NEW_STORE_OPENS.isoformat(), sqft=4200, is_24h="N"))
    return pd.DataFrame(rows)


def build_products():
    r = rng(2)
    shares = np.array([c[1] for c in CATEGORIES])
    cat_idx = r.choice(len(CATEGORIES), size=N_PRODUCTS, p=shares / shares.sum())
    skus = r.permutation(np.arange(100001, 100001 + 90000))[:N_PRODUCTS]
    rows = []
    seen = set()
    for i in range(N_PRODUCTS):
        name_, _, (lo, hi), vat = CATEGORIES[cat_idx[i]]
        brand = BRANDS[r.integers(len(BRANDS))]
        item = ITEMS[name_][r.integers(len(ITEMS[name_]))]
        pack = PACKS[r.integers(len(PACKS))]
        pname = f"{brand} {item} {pack}"
        k = 2
        while pname in seen:
            pname = f"{brand} {item} {pack} v{k}"; k += 1
        seen.add(pname)
        price = float(retail_price(np.exp(r.uniform(np.log(lo), np.log(hi)))))
        rows.append(dict(
            sku=str(skus[i]), product_name=pname, category=name_, brand=brand,
            is_own_brand="Y" if brand.startswith("Kestrel") else "N", pack_size=pack,
            unit_cost=round(price * r.uniform(0.55, 0.75), 2), list_price=price, vat_rate=vat,
            launched_date=(dt.date(2015, 1, 1) + dt.timedelta(days=int(r.integers(0, 4000)))).isoformat(),
            is_active="Y",
        ))
    df = pd.DataFrame(rows)
    # popularity: a steep power law, so a few hundred lines dominate baskets
    pop = 1.0 / np.power(np.arange(1, N_PRODUCTS + 1), 0.9)
    df["popularity"] = r.permutation(pop)
    return df


def price_changes(products):
    r = rng(3)
    idx = r.choice(len(products), size=N_PRICE_CHANGES, replace=False)
    new = products.copy()
    factor = r.uniform(0.88, 1.18, size=N_PRICE_CHANGES)
    old = new["list_price"].values[idx]
    changed = retail_price(old * factor)
    same = changed == old
    changed[same] = np.round(old[same] + 0.10, 2)   # every one of the 300 really changes
    new.loc[new.index[idx], "list_price"] = changed
    return new


def product_file(df):
    return df.drop(columns=["popularity"])


def build_promotions(products):
    r = rng(4)
    rows = []
    cand = products.sort_values("popularity", ascending=False).head(1500)
    picks = r.choice(cand.index.values, size=250, replace=False)
    for n, ix in enumerate(picks, start=1):
        start = dt.date(2026, 9, 1) + dt.timedelta(days=int(r.integers(0, 22)))
        rows.append(dict(promo_id=f"P{n:04d}", sku=products.at[ix, "sku"],
                         promo_type=["PRICE_CUT", "MULTIBUY"][int(r.integers(2))],
                         discount_pct=[0.10, 0.20, 0.25, 0.33][int(r.integers(4))],
                         start_date=start.isoformat(),
                         end_date=(start + dt.timedelta(days=int(r.integers(7, 15)))).isoformat()))
    # quirk 20: 40 SKUs get a second promotion that overlaps the first
    for k, row in enumerate(rows[:40], start=251):
        s = dt.date.fromisoformat(row["start_date"]) + dt.timedelta(days=3)
        rows.append(dict(promo_id=f"P{k:04d}", sku=row["sku"], promo_type="PRICE_CUT",
                         discount_pct=0.15, start_date=s.isoformat(),
                         end_date=(s + dt.timedelta(days=10)).isoformat()))
    return pd.DataFrame(rows)


def build_members(stores):
    r = rng(5)
    n = N_MEMBERS
    member_id = np.arange(FIRST_MEMBER_ID, FIRST_MEMBER_ID + n)
    card = 63400000000000 + r.choice(9_999_999_999, size=n, replace=False)
    first = np.array(FIRST_NAMES)[r.integers(len(FIRST_NAMES), size=n)]
    last = np.array(LAST_NAMES)[r.integers(len(LAST_NAMES), size=n)]
    trading = stores[stores["format"] != "Dark"].iloc[:412]
    weight = trading["format"].map({"Superstore": 100, "Local": 30, "Express": 15}).values.astype(float)
    weight[trading["store_id"].values == FLAGSHIP] = FLAGSHIP_BASKETS
    home = trading["store_id"].values[r.choice(len(trading), size=n, p=weight / weight.sum())]
    area = trading.set_index("store_id")["postcode"].str.split(" ").str[0]
    postcode = area.loc[home].values + " " + r.integers(1, 10, size=n).astype(str) + \
        np.array(list("ABDEFGHJLNPQRSTUWXYZ"))[r.integers(20, size=n)] + \
        np.array(list("ABDEFGHJLNPQRSTUWXYZ"))[r.integers(20, size=n)]
    num = r.integers(1, 999, size=n).astype(str)
    email = (pd.Series(first).str.lower() + "." + pd.Series(last).str.lower() + num + "@" +
             pd.Series(np.array(EMAIL_DOMAINS)[r.integers(len(EMAIL_DOMAINS), size=n)])).values
    phone = "07" + pd.Series(r.integers(100000000, 999999999, size=n)).astype(str).values
    dob = pd.to_datetime("1940-01-01") + pd.to_timedelta(r.integers(0, 29000, size=n), unit="D")
    joined = pd.to_datetime("2012-03-01") + pd.to_timedelta(r.integers(0, 5280, size=n), unit="D")
    return pd.DataFrame(dict(
        member_id=member_id, card_no=card.astype(str), first_name=first, last_name=last,
        email=email, phone=phone, postcode=postcode, home_store_id=home,
        tier=r.choice(TIERS[0], size=n, p=TIERS[1]),
        opt_in_marketing=np.where(r.random(n) < 0.46, "Y", "N"),
        date_of_birth=dob.strftime("%Y-%m-%d"), joined_date=joined.strftime("%Y-%m-%d"),
    ))

# COMMAND ----------

# MAGIC %md ## Till (POS) transactions

# COMMAND ----------

def trading_stores(stores, d):
    t = stores[(stores["format"] != "Dark")]
    return t[pd.to_datetime(t["open_date"]).dt.date <= d]


def prices_on(products, changed, d):
    return (changed if d >= PRICE_CHANGE_DATE else products).set_index("sku")["list_price"]


def best_discount(promos, d):
    ds = d.isoformat()
    live = promos[(promos["start_date"] <= ds) & (promos["end_date"] >= ds)]
    best = live.sort_values("discount_pct").groupby("sku").tail(1)
    return best.set_index("sku")[["promo_id", "discount_pct"]]


def pos_lines(d, stores, products, changed, promos, members):
    r = rng(10, dkey(d))
    st = trading_stores(stores, d).reset_index(drop=True)
    fmt = st["format"].values
    base = np.array([FORMATS[f]["baskets"] for f in fmt], dtype=float)
    base[st["store_id"].values == FLAGSHIP] = FLAGSHIP_BASKETS
    nb = r.poisson(base * DOW[d.weekday()])
    b_store = np.repeat(np.arange(len(st)), nb)
    B = len(b_store)
    b_fmt = fmt[b_store]
    lam = np.array([FORMATS[f]["lines"] for f in b_fmt])
    lam[st["store_id"].values[b_store] == FLAGSHIP] = 4.0
    b_lines = 1 + r.poisson(lam)
    # time of day: opening hours with a lunchtime and an evening peak
    open_h = np.array([FORMATS[f]["hours"][0] for f in b_fmt], dtype=float)
    close_h = np.array([FORMATS[f]["hours"][1] for f in b_fmt], dtype=float)
    is24 = st["is_24h"].values[b_store] == "Y"
    open_h[is24], close_h[is24] = 0.0, 24.0
    u = np.clip(np.where(r.random(B) < 0.5, r.normal(0.35, 0.12, B), r.normal(0.72, 0.13, B)), 0, 0.9999)
    secs = ((open_h + u * (close_h - open_h)) * 3600).astype(int)
    order = np.lexsort((secs, b_store))
    b_store, b_fmt, b_lines, secs = b_store[order], b_fmt[order], b_lines[order], secs[order]
    tills = np.array([FORMATS[f]["tills"] for f in b_fmt])
    till = 1 + (r.random(B) * tills).astype(int)
    seq = pd.Series(b_store).groupby(b_store).cumcount().values + 1
    sid = st["store_id"].values[b_store]
    ts = pd.Timestamp(d) + pd.to_timedelta(secs, unit="s")
    txn_id = pd.Series(sid) + "-" + d.strftime("%Y%m%d") + "-" + pd.Series(till).map("{:02d}".format) + \
        "-" + pd.Series(seq).map("{:05d}".format)
    is_return = r.random(B) < 0.008                                   # quirk 7
    pay = r.choice(["CONTACTLESS", "CARD", "MOBILE", "CASH", "VOUCHER"], size=B, p=[0.48, 0.27, 0.12, 0.11, 0.02])
    # loyalty: 55% of baskets, 80% of those by a member whose home store this is
    has_card = r.random(B) < 0.55
    members_sorted = members.sort_values("home_store_id")
    counts = members_sorted.groupby("home_store_id").size()
    starts = counts.cumsum() - counts
    cards = members_sorted["card_no"].values
    home_start = starts.reindex(sid).fillna(0).values.astype(int)
    home_cnt = counts.reindex(sid).fillna(0).values.astype(int)
    local = (r.random(B) < 0.8) & (home_cnt > 0)
    pick = np.where(local, home_start + (r.random(B) * np.maximum(home_cnt, 1)).astype(int),
                    r.integers(0, len(cards), size=B))
    card = np.where(has_card, cards[pick], "")
    spaced = has_card & (r.random(B) < 0.35)                           # quirk 8
    card = np.where(spaced, pd.Series(card).str.replace(r"^(\d{4})(\d{4})(\d{4})(\d{2})$", r"\1 \2 \3 \4", regex=True).values, card)
    # lines
    L = int(b_lines.sum())
    l_b = np.repeat(np.arange(B), b_lines)
    l_fmt = b_fmt[l_b]
    ranked = products.sort_values("popularity", ascending=False)
    sku = np.empty(L, dtype=object)
    for f in ("Superstore", "Local", "Express"):
        m = l_fmt == f
        if m.any():
            rng_skus = ranked.head(RANGE[f])
            p = rng_skus["popularity"].values
            sku[m] = r.choice(rng_skus["sku"].values, size=int(m.sum()), p=p / p.sum())
    unknown = r.random(L) < 0.0005                                     # quirk 19
    qty = np.where(r.random(L) < 0.82, 1, 1 + r.geometric(0.5, size=L))
    price = prices_on(products, changed, d).reindex(sku).values.astype(float)
    price = np.where(np.isnan(price), 1.00, price)
    sku = np.where(unknown, "000000", sku)
    disc = best_discount(promos, d)
    pct = disc["discount_pct"].reindex(sku).fillna(0).values
    promo_code = disc["promo_id"].reindex(sku).fillna("").values
    ret = is_return[l_b]
    qty = np.where(ret, -qty, qty)
    gross = np.round(price * qty, 2)
    discount = np.round(np.abs(gross) * pct, 2) * np.sign(qty)
    void = r.random(L) < 0.015                                         # quirk 7
    df = pd.DataFrame(dict(
        txn_id=txn_id.values[l_b], store_id=sid[l_b], till_id=till[l_b],
        txn_ts=ts[l_b].strftime("%d/%m/%Y %H:%M:%S"),                   # quirk 2: UK format, local time
        txn_type=np.where(ret, "RETURN", "SALE"), loyalty_card_no=card[l_b],
        sku=sku, qty=qty, unit_price=price, discount_amt=discount,
        line_total=np.round(gross - discount, 2), payment_type=pay[l_b],
        is_void=np.where(void, "Y", "N"), region_code=st["region_code"].values[b_store][l_b],
    ))
    if d >= PROMO_CODE_FROM:
        df["promo_code"] = promo_code
    if d >= TILL_UPGRADE_FROM:                                        # live event 1
        r2 = rng(11, dkey(d))                                         # separate stream: other columns unchanged
        self_share = np.array([{"Superstore": 0.35, "Local": 0.45, "Express": 0.60}[f] for f in b_fmt])
        checkout = np.where(r2.random(B) < self_share, "SELF", "STAFFED")
        df.insert(df.columns.get_loc("till_id") + 1, "checkout_type", checkout[l_b])
    return df


def pos_files_for_delivery(D, ctx):
    """POS files delivered on date D: normally yesterday's trading, plus planted exceptions."""
    out = []
    biz = D - dt.timedelta(days=1)
    if biz >= FIRST_BUSINESS:
        for reg, _, _ in REGIONS:
            if (reg, biz) == LATE_FILE[:2]:
                continue
            out.append((reg, biz, ""))
    if D == LATE_FILE[2]:
        out.append((LATE_FILE[0], LATE_FILE[1], ""))
    if D == RESENT_FILE[2]:
        out.append((RESENT_FILE[0], RESENT_FILE[1], "_resend"))
    return out


def write_pos(D, ctx, cache):
    written = []
    for reg, biz, suffix in pos_files_for_delivery(D, ctx):
        if biz not in cache:
            cache[biz] = pos_lines(biz, ctx["stores"], ctx["products"], ctx["changed"], ctx["promos"], ctx["members"])
        df = cache[biz]
        part = df[df["region_code"] == reg].drop(columns=["region_code"])
        target = path("landing", "pos", "transactions", f"delivered={D}", f"pos_{reg}_{biz}{suffix}.csv")
        text = part.to_csv(index=False, float_format="%.2f", lineterminator="\n")
        if (reg, biz) == HEADER_IN_MIDDLE:                            # quirk 22
            lines = text.split("\n")
            mid = len(lines) // 2
            lines.insert(mid, lines[0])
            text = "\n".join(lines)
        write_text_atomic(target, text)
        written.append((target, len(part)))
    return written

# COMMAND ----------

# MAGIC %md ## Web order events

# COMMAND ----------

def orders_created_on(d, ctx):
    r = rng(20, dkey(d))
    n = int(r.poisson(ECOM_ORDERS_PER_DAY * DOW[d.weekday()]))
    stores, members, products = ctx["stores"], ctx["members"], ctx["products"]
    fulfil = stores[stores["format"].isin(["Superstore", "Dark"]) & (stores["store_id"] != NEW_STORE)]["store_id"].values
    ranked = products.sort_values("popularity", ascending=False).head(4000)
    p = ranked["popularity"].values / ranked["popularity"].values.sum()
    price = prices_on(products, ctx["changed"], d)
    orders = []
    for k in range(n):
        created = pd.Timestamp(d) + pd.Timedelta(seconds=int(r.integers(0, 86400)), milliseconds=int(r.integers(0, 1000)))
        channel = "app" if r.random() < 0.55 else "web"
        version = None
        if channel == "app":
            version = "5.2" if (d >= WEB_PRICE_STRING_FROM and r.random() < 0.30) else "5.1"
        m = members.iloc[int(r.integers(0, len(members)))]
        n_items = int(np.clip(r.poisson(17), 1, 60))
        skus = r.choice(ranked["sku"].values, size=n_items, replace=False, p=p)
        items = []
        for s in skus:
            q = 1 if r.random() < 0.7 else int(r.integers(2, 6))
            up = round(float(price.get(s, 1.0)), 2)
            items.append({"sku": str(s), "qty": q, "unit_price": (f"{up:.2f}" if version == "5.2" else up)})
        total = round(sum(i["qty"] * float(i["unit_price"]) for i in items), 2)
        home = r.random() < 0.7
        slot = (created + pd.Timedelta(hours=int(r.integers(20, 60)))).floor("h")
        cancelled = r.random() < 0.04                                  # quirk 10
        picked = created + pd.Timedelta(minutes=int(r.integers(120, 1800)))
        picked = min(picked, slot - pd.Timedelta(minutes=30))   # v1.0.1: never picked after the slot
        final = slot + pd.Timedelta(minutes=int(r.integers(5, 55)))
        orders.append(dict(
            order_id=f"W{d.strftime('%Y%m%d')}{k + 1:05d}", created=created, channel=channel, app_version=version,
            customer={"loyalty_id": (int(m["member_id"]) if r.random() < 0.8 else None),
                      "email": m["email"], "postcode": m["postcode"]},
            items=items,
            delivery={"type": "HOME" if home else "CLICK_COLLECT",
                      "store_id": str(fulfil[int(r.integers(len(fulfil)))]),
                      "slot_start": slot.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "slot_end": (slot + pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")},
            payment={"method": ["CARD", "PAYPAL", "APPLE_PAY"][int(r.integers(3))], "amount": total},
            picked=picked, final=(created + pd.Timedelta(minutes=int(r.integers(10, 600)))) if cancelled else final,
            final_status="CANCELLED" if cancelled else "DELIVERED",
        ))
    return orders


def ecom_events_on(d, ctx, cache):
    """Every event whose UTC timestamp falls on date d (quirk 9: several events per order)."""
    events = []
    for back in (0, 1, 2, 3):
        cd = d - dt.timedelta(days=back)
        if cd < FIRST_BUSINESS:
            continue
        if cd not in cache:
            cache[cd] = orders_created_on(cd, ctx)
        for o in cache[cd]:
            stages = [("CREATED", o["created"])]
            if o["final_status"] == "DELIVERED":
                stages += [("PICKED", o["picked"]), ("DELIVERED", o["final"])]
            else:
                stages += [("CANCELLED", o["final"])]
            for i, (etype, ets) in enumerate(stages):
                if ets.date() != d:
                    continue
                events.append({
                    "event_id": f"{o['order_id']}-{i + 1}", "event_type": etype,
                    "event_ts": ets.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ets.microsecond // 1000:03d}Z",
                    "order_id": o["order_id"], "order_status": etype, "channel": o["channel"],
                    "app_version": o["app_version"], "customer": o["customer"],
                    "items": [] if etype == "CANCELLED" else o["items"],
                    "delivery": o["delivery"], "payment": o["payment"],
                })
    return sorted(events, key=lambda e: e["event_ts"])


def write_ecom(D, ctx, cache):
    d = D - dt.timedelta(days=1)
    if d < FIRST_BUSINESS:
        return []
    events = ecom_events_on(d, ctx, cache)
    written = []
    by_hour = {}
    for e in events:
        by_hour.setdefault(e["event_ts"][11:13], []).append(e)
    for hh, evs in sorted(by_hour.items()):
        target = path("landing", "ecom", "order_events", f"delivered={D}", f"events_{d}_{hh}.jsonl")
        write_text_atomic(target, "\n".join(json.dumps(e) for e in evs) + "\n")
        written.append((target, len(evs)))
    return written

# COMMAND ----------

# MAGIC %md ## Loyalty CRM change feed

# COMMAND ----------

def crm_plan(d):
    """How many creates, updates and deletes happen on business date d, and where they start."""
    counts = {}
    cur = FIRST_BUSINESS
    new_id = FIRST_MEMBER_ID + N_MEMBERS
    upd_off, del_off = 0, 0
    while cur <= d:
        r = rng(30, dkey(cur))
        total = int(r.poisson(CRM_CHANGES_PER_DAY * DOW[cur.weekday()]))
        n_del = int(r.poisson(20))
        n_new = int(total * 0.25)
        n_upd = total - n_new - n_del
        counts[cur] = dict(n_new=n_new, n_upd=n_upd, n_del=n_del, new_start=new_id, upd_off=upd_off, del_off=del_off)
        new_id += n_new
        upd_off += n_upd
        del_off += n_del
        cur += dt.timedelta(days=1)
    return counts[d]


def crm_records_for(d, ctx):
    plan = crm_plan(d)
    r = rng(31, dkey(d))
    members = ctx["members"]
    order = rng(32).permutation(N_MEMBERS)              # fixed order: who gets updated, who gets erased
    upd_idx = order[plan["upd_off"]:plan["upd_off"] + plan["n_upd"]]
    del_idx = order[::-1][plan["del_off"]:plan["del_off"] + plan["n_del"]]
    t0 = pd.Timestamp(d) + pd.Timedelta(hours=6)
    lsn = dkey(d) * 1_000_000
    recs = []

    def rec(op, ts, after, member_id):
        nonlocal lsn
        lsn += 1
        return {"op": op, "ts_ms": int(ts.value // 1_000_000), "member_id": int(member_id),
                "after": after, "source": {"db": "loyalty", "table": "members", "lsn": lsn}}

    def image(row):
        return {k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in row.items()}

    for j, i in enumerate(upd_idx):
        base = image(members.iloc[int(i)].to_dict())
        field = ["email", "phone", "postcode", "tier", "opt_in_marketing"][int(r.integers(5))]
        after = dict(base)
        if field == "email":
            after["email"] = after["email"].replace("@", f".{int(r.integers(10, 99))}@")
        elif field == "phone":
            after["phone"] = "07" + str(int(r.integers(100000000, 999999999)))
        elif field == "postcode":
            after["postcode"] = after["postcode"][:-3] + str(int(r.integers(1, 10))) + "ZZ"
        elif field == "tier":
            after["tier"] = {"Blue": "Silver", "Silver": "Gold", "Gold": "Gold"}[after["tier"]]
        else:
            after["opt_in_marketing"] = "N" if after["opt_in_marketing"] == "Y" else "Y"
        ts = t0 + pd.Timedelta(seconds=int(r.integers(0, 15 * 3600)))
        after["updated_at"] = ts.strftime("%Y-%m-%d %H:%M:%S")
        recs.append((rec("u", ts, after, after["member_id"]), d))
        if r.random() < 0.01:                                          # quirk 14: out-of-order pair
            later = dict(after)
            later["tier"] = "Gold"
            ts2 = ts + pd.Timedelta(minutes=int(r.integers(5, 90)))
            later["updated_at"] = ts2.strftime("%Y-%m-%d %H:%M:%S")
            recs[-1] = (recs[-1][0], d + dt.timedelta(days=1))          # earlier change arrives a day late
            recs.append((rec("u", ts2, later, later["member_id"]), d))
    for k in range(plan["n_new"]):
        mid = plan["new_start"] + k
        f, l = FIRST_NAMES[int(r.integers(len(FIRST_NAMES)))], LAST_NAMES[int(r.integers(len(LAST_NAMES)))]
        ts = t0 + pd.Timedelta(seconds=int(r.integers(0, 15 * 3600)))
        home = members["home_store_id"].values[int(r.integers(N_MEMBERS))]
        after = {"member_id": int(mid), "card_no": str(63400000000000 + 9_999_999_999 + mid),
                 "first_name": f, "last_name": l,
                 "email": f"{f.lower()}.{l.lower()}{int(r.integers(1, 999))}@{EMAIL_DOMAINS[int(r.integers(len(EMAIL_DOMAINS)))]}",
                 "phone": "07" + str(int(r.integers(100000000, 999999999))),
                 "postcode": members["postcode"].values[int(r.integers(N_MEMBERS))], "home_store_id": home,
                 "tier": "Blue", "opt_in_marketing": "Y" if r.random() < 0.5 else "N",
                 "date_of_birth": (dt.date(1950, 1, 1) + dt.timedelta(days=int(r.integers(0, 20000)))).isoformat(),
                 "joined_date": d.isoformat(), "updated_at": ts.strftime("%Y-%m-%d %H:%M:%S")}
        recs.append((rec("c", ts, after, mid), d))
    for i in del_idx:                                                  # quirk 15: GDPR erasure
        ts = t0 + pd.Timedelta(seconds=int(r.integers(0, 15 * 3600)))
        recs.append((rec("d", ts, None, members["member_id"].values[int(i)]), d))
    return recs


def write_crm(D, ctx, cache):
    d = D - dt.timedelta(days=1)
    if d < FIRST_BUSINESS:
        return []
    out = []
    for day in (d - dt.timedelta(days=1), d):
        if day < FIRST_BUSINESS:
            continue
        if day not in cache:
            cache[day] = crm_records_for(day, ctx)
        out += [rec for rec, deliver_biz in cache[day] if deliver_biz == d]
    out.sort(key=lambda x: x["source"]["lsn"])
    target = path("landing", "crm", "member_changes", f"delivered={D}", f"changes_{d}.jsonl")
    write_text_atomic(target, "\n".join(json.dumps(x) for x in out) + "\n")
    return [(target, len(out))]

# COMMAND ----------

# MAGIC %md ## Warehouse stock snapshots (every Sunday, delivered Monday)

# COMMAND ----------

def write_wms(D, ctx):
    snap = D - dt.timedelta(days=1)
    if snap.weekday() != 6 or snap < FIRST_BUSINESS:
        return []
    import pyarrow as pa, pyarrow.parquet as pq
    r = rng(40, dkey(snap))
    stores = trading_stores(ctx["stores"], snap)
    stores = pd.concat([stores, ctx["stores"][ctx["stores"]["format"] == "Dark"]])
    ranked = ctx["products"].sort_values("popularity", ascending=False)
    parts = []
    for _, s in stores.iterrows():
        rs = ranked.head(RANGE[s["format"]])
        n = len(rs)
        scale = {"Superstore": 60, "Local": 12, "Express": 6, "Dark": 40}[s["format"]]
        if s["store_id"] == FLAGSHIP:
            scale = 400
        on_hand = r.poisson(rs["popularity"].values / rs["popularity"].values.max() * scale + 3)
        on_hand = np.where(r.random(n) < 0.002, -r.integers(1, 20, size=n), on_hand)     # quirk 13
        parts.append(pd.DataFrame(dict(
            snapshot_date=snap, store_id=np.int32(int(s["store_id"])),                   # quirk 1: an integer here
            sku=rs["sku"].values, on_hand=on_hand.astype("int32"),
            on_order=r.poisson(4, size=n).astype("int32"),
            reorder_point=np.maximum(2, (on_hand * 0.3).astype("int32")),
            last_counted_at=pd.Timestamp(snap) + pd.Timedelta(hours=22) + pd.to_timedelta(r.integers(0, 7200, size=n), unit="s"),
        )))
    df = pd.concat(parts, ignore_index=True)
    target = path("landing", "wms", "stock_snapshots", f"delivered={D}", f"stock_{snap}.parquet")
    ensure_dir(os.path.dirname(target))
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, target, coerce_timestamps="us")    # serverless can't read Parquet nanoseconds
    return [(target, len(df))]

# COMMAND ----------

# MAGIC %md ## Reference files and the CRM full export

# COMMAND ----------

def write_reference(D, ctx):
    out = []
    ref = lambda *p: path("landing", "reference", *p)
    if D == FIRST_DELIVERY:
        st = ctx["stores"][ctx["stores"]["store_id"] != NEW_STORE]
        write_csv(st, ref("stores", f"stores_2026-08-31.csv")); out.append((ref("stores", "stores_2026-08-31.csv"), len(st)))
        pf = product_file(ctx["products"])
        write_csv(pf, ref("products", "products_2026-08-31.csv")); out.append((ref("products", "products_2026-08-31.csv"), len(pf)))
        write_csv(ctx["promos"], ref("promotions", "promotions_2026-08-31.csv")); out.append((ref("promotions", "promotions_2026-08-31.csv"), len(ctx["promos"])))
        target = path("landing", "crm", "members_full", "members_export_2026-08-31.csv")
        write_csv(ctx["members"], target); out.append((target, len(ctx["members"])))
    if D == PRICE_CHANGE_DATE:
        pf = product_file(ctx["changed"])
        write_csv(pf, ref("products", f"products_{D}.csv")); out.append((ref("products", f"products_{D}.csv"), len(pf)))
    if D == NEW_STORE_REF_DELIVERY:
        write_csv(ctx["stores"], ref("stores", f"stores_{D}.csv")); out.append((ref("stores", f"stores_{D}.csv"), len(ctx["stores"])))
    return out

# COMMAND ----------

# MAGIC %md ## Running a delivery day

# COMMAND ----------

STATE_FILE = lambda: path("ops", "sim", "state.json")

def load_state():
    try:
        with open(STATE_FILE(), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"sim_version": SIM_VERSION, "seed": SEED, "delivered": []}

def save_state(s):
    write_text_atomic(STATE_FILE(), json.dumps(s, indent=2))

def build_context():
    stores = build_stores()
    products = build_products()
    return dict(stores=stores, products=products, changed=price_changes(products),
                promos=build_promotions(products), members=build_members(stores))

def deliver(D, ctx, caches, state):
    if D.isoformat() in state["delivered"]:
        print(f"{D}  already delivered, skipped")
        return
    w = []
    w += write_reference(D, ctx)
    w += write_pos(D, ctx, caches["pos"])
    w += write_ecom(D, ctx, caches["ecom"])
    w += write_crm(D, ctx, caches["crm"])
    w += write_wms(D, ctx)
    state["delivered"].append(D.isoformat())
    state["last_delivery"] = D.isoformat()
    save_state(state)
    print(f"{D}  {len(w):3d} files  {sum(n for _, n in w):>10,} rows")

def setup():
    if not IN_DATABRICKS:
        for v in LANDING_VOLUMES:
            ensure_dir(path("landing", v))
        ensure_dir(path("ops", "sim"))
        return
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG} COMMENT 'Kestrel Foods lakehouse (course)'")
    except Exception as e:
        raise RuntimeError(
            f"Could not create catalog '{CATALOG}'. Set the catalog widget to 'workspace' and run setup again.\n{e}")
    for s in SCHEMAS:
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{s}")
    for v in LANDING_VOLUMES:
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.landing.{v} COMMENT 'Raw files from the {v} source system'")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.ops.sim COMMENT 'Simulator state'")
    print(f"Catalog {CATALOG}: schemas {', '.join(SCHEMAS)}; landing volumes {', '.join(LANDING_VOLUMES)}; ops.sim")
    repair_wms()

def repair_wms():
    """Rewrite warehouse snapshots written by an older version with nanosecond timestamps. Values are unchanged."""
    import glob
    import pyarrow as pa, pyarrow.parquet as pq
    fixed = 0
    for f in sorted(glob.glob(path("landing", "wms", "stock_snapshots", "*", "*.parquet"))):
        table = pq.read_table(f)
        if any(pa.types.is_timestamp(t.type) and t.type.unit == "ns" for t in table.schema):
            schema = pa.schema([pa.field(t.name, pa.timestamp("us", t.type.tz)) if pa.types.is_timestamp(t.type) else t
                                for t in table.schema])
            pq.write_table(table.cast(schema), f, coerce_timestamps="us")
            fixed += 1
    if fixed:
        print(f"Warehouse snapshots: rewrote {fixed} file(s) with microsecond timestamps")

def status():
    s = load_state()
    days = s.get("delivered", [])
    print(f"Simulator {SIM_VERSION}, seed {SEED}")
    print(f"Deliveries made: {len(days)}" + (f"  (first {days[0]}, last {days[-1]})" if days else ""))
    for v in LANDING_VOLUMES:
        n, size = 0, 0
        for dp, _, files in os.walk(path("landing", v)):
            for f in files:
                n += 1
                size += os.path.getsize(os.path.join(dp, f))
        print(f"  landing.{v:<10} {n:6,} files  {size / 1e6:8.1f} MB")

# COMMAND ----------

# MAGIC %md ## Run

# COMMAND ----------

if MODE == "setup":
    setup()
elif MODE in ("backfill", "next_day"):
    state = load_state()
    ctx = build_context()
    caches = {"pos": {}, "ecom": {}, "crm": {}}
    if MODE == "backfill":
        D = FIRST_DELIVERY
        while D <= BACKFILL_LAST_DELIVERY:
            deliver(D, ctx, caches, state)
            D += dt.timedelta(days=1)
    else:
        last = state.get("last_delivery")
        if not last:
            raise RuntimeError("Nothing delivered yet. Run backfill first.")
        deliver(dt.date.fromisoformat(last) + dt.timedelta(days=1), ctx, caches, state)
    status()
elif MODE == "status":
    status()
elif MODE == "reset":
    if CONFIRM != "YES":
        raise RuntimeError("Reset deletes the whole catalog. Type YES in confirm_reset to proceed.")
    if IN_DATABRICKS:
        spark.sql(f"DROP CATALOG IF EXISTS {CATALOG} CASCADE")
    else:
        shutil.rmtree(ROOT, ignore_errors=True)
    print(f"Catalog {CATALOG} deleted.")
