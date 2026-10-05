"""
Taobao Shopper Behavior Analysis - full dataset (about 100M rows) with SQL (DuckDB)

Run from the folder that contains UserBehavior.csv:
    pip install duckdb pandas matplotlib
    python full_analysis.py
"""

import duckdb
import matplotlib.pyplot as plt

RAW_FILE = "UserBehavior.csv"

# The dataset documentation covers 25 Nov - 3 Dec 2017 (China time, UTC+8).
# Rows with timestamps outside that window are treated as noise and removed.
START_TS = 1511539200  # 2017-11-25 00:00 China time
END_TS = 1512316800    # 2017-12-04 00:00 China time

# --- Load and clean -------------------------------------------------------
raw = duckdb.read_csv(RAW_FILE, header=False)
events = duckdb.sql("""
    SELECT column0 AS user_id, column1 AS item_id, column2 AS category_id,
           column3 AS behavior, column4 AS ts
    FROM raw
""")
valid = duckdb.sql(f"""
    SELECT * FROM events WHERE ts >= {START_TS} AND ts < {END_TS}
""")

total = duckdb.sql("SELECT COUNT(*) FROM events").fetchone()[0]
kept = duckdb.sql("SELECT COUNT(*) FROM valid").fetchone()[0]
print(f"Rows in file: {total:,}")
print(f"Rows kept after removing out-of-window timestamps: {kept:,} "
      f"({total - kept:,} removed)")

# --- 1. Funnel: actions and unique users ----------------------------------
funnel = duckdb.sql("""
    SELECT behavior, COUNT(*) AS actions, COUNT(DISTINCT user_id) AS users
    FROM valid GROUP BY behavior ORDER BY actions DESC
""").df().set_index("behavior")
print("\nFunnel:")
print(funnel)

pv, cart, buy = (funnel.loc[b, "actions"] for b in ("pv", "cart", "buy"))
print(f"Cart adds per view: {cart / pv:.1%}")
print(f"Purchases per cart add: {buy / cart:.1%}")
print(f"Purchases per 100 views: {buy / pv * 100:.1f}")
u = funnel["users"]
print(f"Users who added to cart: {u['cart'] / u['pv']:.1%} of users who viewed")
print(f"Users who bought: {u['buy'] / u['pv']:.1%} of users who viewed")

funnel.loc[["pv", "cart", "buy"], "actions"].plot(
    kind="bar", title="Shopper funnel (full dataset, actions)")
plt.tight_layout()
plt.savefig("funnel_full.png")
plt.close()

# --- 2. Purchases by hour (China time) ------------------------------------
hours = duckdb.sql("""
    SELECT ((ts + 28800) % 86400) // 3600 AS hour, COUNT(*) AS purchases
    FROM valid WHERE behavior = 'buy' GROUP BY hour ORDER BY hour
""").df().set_index("hour")
print("\nPurchases by hour (China time):")
print(hours)

hours["purchases"].plot(
    kind="bar", title="Purchases by hour of day (China time, full dataset)")
plt.tight_layout()
plt.savefig("hours_full.png")
plt.close()

# --- 3. Categories: where do purchases come from? -------------------------
cats = duckdb.sql("""
    SELECT category_id,
           SUM(CASE WHEN behavior = 'pv' THEN 1 ELSE 0 END) AS views,
           SUM(CASE WHEN behavior = 'buy' THEN 1 ELSE 0 END) AS purchases
    FROM valid GROUP BY category_id
    HAVING views >= 100000
    ORDER BY purchases DESC LIMIT 10
""").df()
cats["purchases_per_100_views"] = (cats["purchases"] / cats["views"] * 100).round(2)
print("\nTop 10 categories by purchases (categories with 100k+ views):")
print(cats)

cats.set_index("category_id")["purchases"].plot(
    kind="bar", title="Top 10 categories by purchases (category IDs are anonymized)")
plt.tight_layout()
plt.savefig("categories_full.png")
plt.close()

# --- 4. Repeat buyers -----------------------------------------------------
repeat = duckdb.sql("""
    SELECT COUNT(*) AS buyers,
           SUM(CASE WHEN n >= 2 THEN 1 ELSE 0 END) AS repeat_buyers
    FROM (SELECT user_id, COUNT(*) AS n FROM valid
          WHERE behavior = 'buy' GROUP BY user_id)
""").df()
b, r = repeat.loc[0, "buyers"], repeat.loc[0, "repeat_buyers"]
print(f"\nBuyers: {b:,}; bought 2+ times: {r:,} ({r / b:.1%})")

print("\nSaved funnel_full.png, hours_full.png, categories_full.png")
