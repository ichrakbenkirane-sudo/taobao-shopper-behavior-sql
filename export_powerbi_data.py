"""
Export small summary tables from the full Taobao dataset for use in Power BI.

Run from the folder that contains UserBehavior.csv:
    python export_powerbi_data.py

Creates: pbi_funnel.csv, pbi_hours.csv, pbi_categories.csv, pbi_daily.csv
"""

import duckdb
import pandas as pd

RAW_FILE = "UserBehavior.csv"
START_TS = 1511539200  # 2017-11-25 00:00 China time
END_TS = 1512316800    # 2017-12-04 00:00 China time

raw = duckdb.read_csv(RAW_FILE, header=False)
events = duckdb.sql("""
    SELECT column0 AS user_id, column1 AS item_id, column2 AS category_id,
           column3 AS behavior, column4 AS ts
    FROM raw
""")
valid = duckdb.sql(f"""
    SELECT * FROM events WHERE ts >= {START_TS} AND ts < {END_TS}
""")

# 1. Funnel (actions and unique users per behavior)
funnel = duckdb.sql("""
    SELECT behavior, COUNT(*) AS actions, COUNT(DISTINCT user_id) AS users
    FROM valid GROUP BY behavior
""").df()
order = {"pv": 1, "cart": 2, "fav": 3, "buy": 4}
labels = {"pv": "View", "cart": "Add to cart", "fav": "Favorite", "buy": "Purchase"}
funnel["step_order"] = funnel["behavior"].map(order)
funnel["stage"] = funnel["behavior"].map(labels)
funnel = funnel.sort_values("step_order")[["step_order", "stage", "actions", "users"]]
funnel.to_csv("pbi_funnel.csv", index=False)
print("Saved pbi_funnel.csv")

# 2. Purchases by hour (China time)
hours = duckdb.sql("""
    SELECT CAST(((ts + 28800) % 86400) // 3600 AS INTEGER) AS hour,
           COUNT(*) AS purchases
    FROM valid WHERE behavior = 'buy' GROUP BY hour ORDER BY hour
""").df()
hours.to_csv("pbi_hours.csv", index=False)
print("Saved pbi_hours.csv")

# 3. Top categories by purchases (with 100k+ views)
cats = duckdb.sql("""
    SELECT category_id,
           CAST(SUM(CASE WHEN behavior = 'pv' THEN 1 ELSE 0 END) AS BIGINT) AS views,
           CAST(SUM(CASE WHEN behavior = 'cart' THEN 1 ELSE 0 END) AS BIGINT) AS cart_adds,
           CAST(SUM(CASE WHEN behavior = 'buy' THEN 1 ELSE 0 END) AS BIGINT) AS purchases
    FROM valid GROUP BY category_id
    HAVING views >= 100000
    ORDER BY purchases DESC LIMIT 30
""").df()
cats["purchases_per_100_views"] = (cats["purchases"] / cats["views"] * 100).round(2)
cats.to_csv("pbi_categories.csv", index=False)
print("Saved pbi_categories.csv")

# 4. Daily activity by behavior (China time)
daily = duckdb.sql("""
    SELECT CAST((ts + 28800) // 86400 AS BIGINT) AS day_number, behavior,
           COUNT(*) AS actions
    FROM valid GROUP BY day_number, behavior ORDER BY day_number
""").df()
daily["date"] = pd.to_datetime(daily["day_number"] * 86400, unit="s").dt.date
daily["stage"] = daily["behavior"].map(labels)
daily = daily[["date", "stage", "actions"]]
daily.to_csv("pbi_daily.csv", index=False)
print("Saved pbi_daily.csv")
