# RetailIQ — All 5 Class Notes
## End-to-End Power BI Portfolio Project | Olist E-Commerce Dataset

---

## PROJECT OVERVIEW

**What you're building:** A 4-page interactive Power BI dashboard analysing
100,000+ real e-commerce orders from a Brazilian retailer (Olist).

**Business question you're answering:** Which customer segments are at risk,
which product categories are underperforming, and where is delivery quality
hurting repeat business?

**Stack:** Python (clean data) → MySQL (analytics layer) → Power BI (dashboards)

**Dataset:** Olist Brazilian E-Commerce — free on Kaggle
Link: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
Download the ZIP (~37MB). It contains 9 CSV files. That's your raw data.

**Files in this project:**
```
retailiq_project/
├── python/
│   ├── clean.py      ← Class 1
│   └── load.py        ← Class 2
├── sql/
│   └── setup.sql ← Class 2
├── powerbi/
│   └── dax_measures.md ← Class 4
└── notes/
    └── notes.md   ← This file
```

---

## ONE-TIME SETUP (Do this before Class 1)

### Install Python
Download from https://www.python.org/downloads/ — install Python 3.10 or higher.
During install, tick "Add Python to PATH".

Verify in terminal:
```
python --version
```

Install required libraries:
```
pip install pandas numpy pymysql sqlalchemy
```

### Install MySQL + MySQL Workbench
Download MySQL Community Installer from https://dev.mysql.com/downloads/installer/
Choose "Full" setup — it installs both MySQL Server and MySQL Workbench.
During setup, set a root password. Write it down. You'll need it in Class 2.

### Install Power BI Desktop
Download free from https://powerbi.microsoft.com/desktop
This is Windows only. If you're on Mac, use a Windows VM or a Windows machine.

Also download the MySQL Connector for Power BI:
https://dev.mysql.com/downloads/connector/net/
This is a .NET driver that lets Power BI talk to MySQL. Install it before Class 3.

### Create project folder structure
```
retailiq_project/
├── data/
│   ├── raw/      ← put all 9 Olist CSVs here
│   └── clean/    ← Python will create this automatically
├── python/       ← copy clean.py and load.py here
├── sql/          ← copy setup.sql here
└── powerbi/      ← your .pbix file will live here
```

---

## CLASS 1 — Python Data Cleaning (1 Hour)

### Objective
By end of class: 4 clean CSV files in data/clean/, ready to load into MySQL.
You'll understand every transformation decision and be able to explain it.

### The 9 Raw Files You're Working With
```
olist_orders_dataset.csv          — 99,441 orders. The spine of everything.
olist_order_items_dataset.csv     — 112,650 items. Multiple items per order.
olist_order_payments_dataset.csv  — 103,886 payment records.
olist_order_reviews_dataset.csv   — 100,000 reviews. Some orders reviewed twice.
olist_customers_dataset.csv       — 99,441 customers. Two ID types (explained below).
olist_products_dataset.csv        — 32,951 products. Category names in Portuguese.
olist_sellers_dataset.csv         — 3,095 sellers.
olist_geolocation_dataset.csv     — 1M+ geo records (not used directly — too heavy).
product_category_name_translation.csv — 71 rows. Portuguese → English mapping.
```

### Key Concept Before You Start: Two Customer IDs
The customers table has both `customer_id` and `customer_unique_id`.

- `customer_id` links to the orders table, but a customer who buys twice
  gets TWO different customer_ids. It's an order-session ID, not a person ID.
- `customer_unique_id` is the actual unique person.

This is a classic trap. If you use `customer_id` for your RFM analysis,
you'll see 0% repeat customers. The real repeat rate is ~3%.
In our fact table, we store `customer_unique_id` as the FK and call it `customer_id`
for simplicity.

### Steps

**Step 1 — Set up your working folder (5 min)**

Open terminal, navigate to your project folder:
```bash
cd retailiq_project
```

Copy `clean.py` into the `python/` subfolder.
Make sure all 9 Kaggle CSVs are in `data/raw/`.

**Step 2 — Run the cleaning script (10 min)**
```bash
cd python
python clean.py
```

Watch the output. It prints row counts, null summaries, and decisions made.
Read every line — this is your audit trail.

**Step 3 — Understand what the script did (20 min)**

Open `clean.py` and read through it section by section.
Here's what each step does and WHY:

*clean_orders():*
- Parses 5 timestamp columns to datetime. Without this they're plain strings.
- Removes cancelled/unavailable orders (~1,600 rows). Why? They have no revenue
  and their null delivery dates would make every delivery metric meaningless.
- Adds derived columns: order_year, order_month, order_quarter, delivery_days,
  was_late, is_delivered. Pre-computing these in Python is faster than doing it
  in DAX or SQL later.

*build_items_aggregated():*
- One order can have 5 items from 3 different sellers. We aggregate to one row
  per order: total price, total freight, item count.
- For the seller_id and product_id in the fact table, we pick the item with
  the highest price (the "primary item"). This is a business decision.

*clean_reviews():*
- Some orders got reviewed twice. We keep the latest review.
- 87% of reviews have no written comment. That's normal — most customers
  just give a star rating.

*clean_products():*
- Merges English category names from the translation file.
- Maps 73 Portuguese categories into 10 broad English buckets.
  This is your business logic. "bed_bath_table" → "Home & Living".

*calculate_rfm():*
- Recency: days since last order (measured from SNAPSHOT_DATE = Jan 2019)
- Frequency: number of orders placed
- Monetary: total amount spent (revenue only, not freight)
- Each scored 1–5 using pandas qcut (splits data into 5 equal groups)
- Total score 13–15 = Champions. 10–12 = Loyal. 7–9 = At Risk. etc.

*build_fact_table():*
- Joins orders + items + payments + reviews + customer ID mapping into one table.
- This is the central table your Power BI star schema is built around.

**Step 4 — Inspect the clean files (10 min)**

Open each CSV in Excel or a text editor. Check:
```
data/clean/fact_orders.csv     — Should have ~96,000 rows, 24 columns
data/clean/dim_customers.csv   — Should have ~96,000 rows, 12 columns (includes RFM)
data/clean/dim_products.csv    — Should have ~32,000 rows, 7 columns
data/clean/dim_sellers.csv     — Should have ~3,000 rows, 3 columns
```

Also check that `rfm_segment` column in dim_customers has 5 distinct values:
Champions, Loyal Customers, At Risk, Needs Attention, Lost.

**Step 5 — Checkpoint (5 min)**

Run this in a Python terminal to verify your outputs:
```python
import pandas as pd
fact = pd.read_csv('./data/clean/fact_orders.csv')
print(f"Orders: {len(fact):,}")
print(f"Revenue: R$ {fact['revenue'].sum():,.0f}")
print(f"Avg review: {fact['review_score'].mean():.2f}")
print(f"Late rate: {fact['was_late'].mean()*100:.1f}%")
```

Expected output (approximately):
```
Orders: 96,478
Revenue: R$ 13,591,000
Avg review: 4.09
Late rate: 8.1%
```

### Common Errors

**FileNotFoundError: No such file or directory 'data/raw/olist_orders_dataset.csv'**
You're running the script from the wrong folder. Make sure your terminal is
inside `retailiq_project/`, not inside `python/`. Or adjust RAW path at top of script.

**ValueError: cannot convert float NaN to integer**
A null in was_late or is_delivered. The script handles this, but if you modified
the clean_orders() function, check the line:
`df.loc[df['order_delivered_customer_date'].isna(), 'was_late'] = 0`

**MemoryError**
Your machine has less than 4GB free RAM. Close other programs and retry.
The geolocation file (~1M rows) is the heaviest — it's not used in the script,
so this shouldn't cause issues.

### Interview Talking Points
- "I made the decision to exclude cancelled orders because their null delivery
  dates would corrupt every delivery performance metric."
- "The dataset had two customer ID types — a session ID and a unique person ID.
  Using the wrong one would show 0% repeat rate. The real repeat rate is ~3%."
- "I used qcut for RFM scoring instead of arbitrary cutoffs so the segments
  are always equally sized, which prevents Champion segment from being empty
  in a small dataset."

---

## CLASS 2 — MySQL Data Warehouse (1 Hour)

### Objective
By end of class: 4 clean tables loaded into MySQL, 6 analytical views created,
all views returning correct results when queried. Power BI will consume these
views — not the raw tables.

### Why SQL Views Instead of Raw Tables?
In real data teams, the SQL layer owns business logic. The BI tool only visualises.
If a business definition changes (e.g., "late" is now >2 days late, not >0),
you update one SQL view. Every dashboard using it updates automatically.
This architecture is what separates analysts who understand data engineering
from those who just know Power BI.

### Steps

**Step 1 — Open MySQL Workbench and connect (5 min)**

Open MySQL Workbench → Local instance MySQL80 → Enter root password → Connect.
You should see a blank query editor.

**Step 2 — Run Part 1 and Part 2 of the SQL file (10 min)**

Open `setup.sql` in MySQL Workbench (File → Open SQL Script).
Highlight ONLY Part 1 (CREATE DATABASE section) and run it: Ctrl+Shift+Enter.
Then highlight ONLY Part 2 (CREATE TABLE section) and run it.

Verify: In the left panel, refresh the schema list. You should see `retailiq`
with 4 tables inside: fact_orders, dim_customers, dim_products, dim_sellers.

**Step 3 — Load data using Python (10 min)**

Open a new terminal window (keep MySQL Workbench open).
Edit `load.py` — update MYSQL_PASS with your MySQL root password.

```bash
cd retailiq_project/python
python load.py
```

Expected output:
```
Connected. MySQL version: 8.x.x
Loading clean CSVs into MySQL...
  Loading dim_customers...   Loaded: 96,096 rows into dim_customers
  Loading dim_products...    Loaded: 32,341 rows into dim_products
  Loading dim_sellers...     Loaded: 2,968 rows into dim_sellers
  Loading fact_orders...     Loaded: 96,478 rows into fact_orders
```

This takes 2–5 minutes depending on your machine. fact_orders is the biggest.

**Step 4 — Run Part 3 (verify) in MySQL Workbench (5 min)**

Highlight Part 3 and run it. You should see row counts matching above.
Then run the sanity check query below it — verify total revenue is ~R$ 13.5M.

**Step 5 — Run Part 4 (indexes) (2 min)**

Highlight Part 4 and run it. 9 indexes get created. These make Part 5 faster.

**Step 6 — Run Part 5 (create views) (15 min)**

Run each view one at a time. After each CREATE VIEW statement, run the
test SELECT below it to verify it returns data.

The 6 views:
```
vw_monthly_revenue      — Monthly revenue, orders, AOV, late %, review score
vw_category_performance — Revenue and metrics by product category
vw_rfm_segments         — One row per RFM segment with aggregate stats
vw_state_performance    — Geographic: revenue and delivery by Brazilian state
vw_seller_performance   — Seller quality: on-time %, review score, revenue
vw_payment_analysis     — Payment method breakdown
```

**Step 7 — Run Part 6 (verify all views) (5 min)**

Run the final UNION ALL query. All 6 views should return >0 rows.

### Understanding the Most Important View: vw_seller_performance

This view powers your scatter plot in Class 5 — each seller is one dot.
The X axis is on_time_pct, Y axis is avg_review_score.

The quadrant logic in the test query at the bottom:
- Top-right (high on-time %, high review score) = Top Performers
- Bottom-left (low on-time %, low review score) = Problem Sellers — these
  are the actionable insight. Show this to a recruiter and you have a story.

The `HAVING total_orders >= 10` filter removes sellers with too few orders
to judge fairly. Always explain this kind of filter in an interview.

### Understanding vw_rfm_segments

This view gives you a one-row-per-segment summary:
- customer_count: how many people are in this segment
- total_spend: total lifetime revenue from this segment
- revenue_contribution_pct: what % of all revenue they represent

Champions typically represent 5–10% of customers but 30–40% of revenue.
That gap is the entire business case for customer retention programs.

### Common Errors

**Table doesn't exist / Unknown table 'fact_orders'**
You ran Part 5 before Part 2. The views reference the tables.
Go back and make sure all 4 CREATE TABLE statements ran successfully first.

**Error Code 1366: Incorrect integer value for column 'was_late'**
The CSV has blank values for was_late. The Python script fills these with 0,
but if you re-ran cleaning with different settings it might have changed.
Open fact_orders.csv and check the was_late column for blanks.

**python load.py: Access denied for user 'root'**
Wrong password in MYSQL_PASS. Check the password you set during MySQL install.

**python load.py: ModuleNotFoundError: No module named 'pymysql'**
Run: `pip install pymysql sqlalchemy`

### Interview Talking Points
- "I built a SQL analytics layer on top of the raw tables. Power BI consumes
  views, not tables. This means if a business definition changes, I update SQL
  and every dashboard downstream updates — without touching Power BI."
- "I added 9 indexes before creating the views. Views are re-executed every
  time Power BI refreshes. Without indexes on the join and filter columns,
  queries against 96k rows would be noticeably slower."
- "The seller performance view filters to HAVING total_orders >= 10 to prevent
  misleading metrics from sellers with only 1-2 orders."

---

## CLASS 3 — Power BI: Connect, Model, Date Table (1 Hour)

### Objective
By end of class: Power BI connected to MySQL, star schema built in Model view,
Date Table created and marked. No visuals yet — this class is all architecture.

### Why This Class Matters
Most beginner Power BI dashboards are flat-file imports with one table.
A star schema with a proper Date Table is what enables:
- Time intelligence functions (MTD, YTD, YoY) — these literally don't work
  without a marked Date Table
- Cross-filtering that makes sense (dim → fact, not fact → fact)
- Performance: Power BI caches dimension tables and queries them efficiently

Do this right in Class 3 and Classes 4 and 5 become much easier.

### Steps

**Step 1 — Open Power BI Desktop and connect to MySQL (10 min)**

Home → Get Data → More → Database → MySQL Database → Connect

Fill in:
- Server: localhost
- Database: retailiq
- Data Connectivity mode: Import (not DirectQuery — Import is faster for
  a dataset this size and enables all DAX functions)

Click OK. If prompted for credentials: Database tab → username: root,
password: your MySQL password.

If you get "MySQL: Unable to connect":
- Make sure MySQL Workbench can connect first
- Make sure you installed MySQL Connector/Net (the .NET driver)
- Try "localhost" vs "127.0.0.1"

**Step 2 — Select tables and views (5 min)**

In the Navigator window, you'll see all tables and views.
Select these (tick the checkbox):
```
✓ fact_orders
✓ dim_customers
✓ dim_products
✓ dim_sellers
✓ vw_monthly_revenue
✓ vw_category_performance
✓ vw_rfm_segments
✓ vw_state_performance
✓ vw_seller_performance
✓ vw_payment_analysis
```

Click Load (not Transform Data — we'll check transformations in a moment).

**Step 3 — Quick check in Power Query (10 min)**

Home → Transform Data. This opens Power Query Editor.

Check each table:
- Click fact_orders. Top rows should show order_ids, dates, revenue values.
  Column types: order_purchase_date should be Date, revenue should be Decimal.
  If any date column shows as "ABC" (text), change it: click column header →
  Data Type → Date.

- Click dim_customers. Verify rfm_segment column has values like "Champions".

- Add one transformation as a demonstration for the portfolio:
  In dim_customers, click rfm_score column → Transform tab → Data Type → Whole Number.
  This makes Power BI store it as integer, not decimal.

Click Close & Apply.

**Step 4 — Build the star schema in Model view (15 min)**

Click the Model view icon on the left sidebar (looks like 3 connected boxes).

By default, Power BI may have auto-detected some relationships. Delete any
auto-detected ones by clicking the connecting line → Delete. Start fresh.

Now create these relationships manually.
For each: drag from the field in one table and drop onto the field in another.
After dragging, a dialog appears — set Cardinality and Cross filter direction.

```
fact_orders[customer_id]  →  dim_customers[customer_id]
  Cardinality: Many to One (*)→(1)
  Cross filter direction: Single

fact_orders[product_id]   →  dim_products[product_id]
  Cardinality: Many to One (*)→(1)
  Cross filter direction: Single

fact_orders[seller_id]    →  dim_sellers[seller_id]
  Cardinality: Many to One (*)→(1)
  Cross filter direction: Single
```

The views (vw_monthly_revenue etc.) do NOT get connected to fact_orders.
They are standalone — already pre-aggregated by SQL. Power BI just reads them.

Your model should look like a star: fact_orders in the center, 3 dimension
tables around it, views off to the side unconnected.

**Step 5 — Create the Date Table (15 min)**

Go to Report view (the top icon). Click New Table in the top ribbon.
Paste this DAX exactly (from dax_measures.md Section 1):

```dax
DateTable =
ADDCOLUMNS(
    CALENDAR(DATE(2016, 1, 1), DATE(2018, 12, 31)),
    "Year",        YEAR([Date]),
    "MonthNum",    MONTH([Date]),
    "MonthName",   FORMAT([Date], "MMMM"),
    "MonthShort",  FORMAT([Date], "MMM"),
    "Quarter",     "Q" & QUARTER([Date]),
    "QuarterNum",  QUARTER([Date]),
    "WeekNum",     WEEKNUM([Date]),
    "DayName",     FORMAT([Date], "dddd"),
    "DayNum",      DAY([Date]),
    "YearMonth",   FORMAT([Date], "YYYY-MM"),
    "IsWeekend",   IF(WEEKDAY([Date], 2) >= 6, 1, 0)
)
```

After the table is created:
- Go back to Model view
- Right-click DateTable → Mark as Date Table → select the Date column → OK
- Drag DateTable[Date] → fact_orders[order_purchase_date]
  Cardinality: One to Many (1)→(*)
  Cross filter direction: Single

**Step 6 — Save the file (2 min)**

File → Save As → save to `retailiq_project/powerbi/RetailIQ.pbix`

### Checkpoint — How to verify the star schema is correct

In Model view, you should see:
- fact_orders in the center with 4 lines coming out of it
  (to dim_customers, dim_products, dim_sellers, DateTable)
- Each line has a 1 on the dimension side and * on the fact side
- 6 views sitting separately, not connected to anything

If you see a line between two dimension tables, delete it — that's wrong.

### Common Errors

**Power BI can't find MySQL connector**
Download MySQL Connector/Net 8.0 from mysql.com. Restart Power BI after installing.

**Some relationships show as dotted lines (inactive)**
This happens if Power BI auto-detected relationships before you built yours.
Delete all auto-detected relationships first, then create manually.

**DateTable appears as "Error" after pasting DAX**
Check for copy-paste issues with quotes. Type the quotes manually if needed.
The outer quote marks in FORMAT([Date], "MMMM") must be straight quotes, not curly.

### Interview Talking Points
- "I built a proper star schema instead of importing flat data. This enables
  cross-filtering from dimensions to facts, which is how enterprise BI models work."
- "I created the Date Table in DAX using ADDCOLUMNS + CALENDAR so that all time
  intelligence functions work correctly. Without a marked Date Table, TOTALYTD
  and SAMEPERIODLASTYEAR silently return wrong results."
- "I chose Import mode over DirectQuery because the dataset is static and Import
  gives faster query response for interactive filtering."

---

## CLASS 4 — DAX Measures + Executive Summary Page (1 Hour)

### Objective
By end of class: All measures created in a clean Measures table, and a complete
Executive Summary page with KPI cards, revenue trend line, category comparison,
and time-period context. This is the page that gets seen first and judged hardest.

### Steps

**Step 1 — Create the Measures table (5 min)**

Home → Enter Data → Name it `_Measures` → Load.
In Power Query Editor, select the Column1 column → Remove Columns → Close & Apply.
You now have an empty table. All measures live here.

The underscore prefix `_Measures` makes it sort to the top of the Fields list.

**Step 2 — Create all measures (25 min)**

For each measure below: right-click `_Measures` in the Fields panel → New Measure.
Paste the DAX from `dax_measures.md`.

Create them in this exact order — some depend on others:

Group 1: Basic (create first, others depend on these)
- Total Revenue
- Total Orders
- AOV
- Total Customers
- Total Items Sold
- Avg Review Score
- Late Delivery Rate %
- Avg Delivery Days

Group 2: Time Intelligence (need DateTable marked as Date Table first)
- Revenue LY
- Revenue YoY %
- Revenue PM
- Revenue MoM %
- Revenue MTD
- Revenue YTD
- Running Revenue Total
- Revenue 3M Rolling Avg

Group 3: Customer
- Repeat Customers
- Repeat Customer Rate %
- Avg Customer LTV

After creating each measure, verify it's not showing an error. Click the measure
name in the Fields panel — the formula bar at the top should show the DAX formula.

**Step 3 — Format your measures (5 min)**

Click Total Revenue in Fields panel. In the Measure tools ribbon:
- Format: Currency → set to R$ (or use Custom: "R$ "#,##0.00)

Click Revenue YoY %. Format: Percentage, 1 decimal place.
Click Late Delivery Rate %. Format: Percentage, 1 decimal place.
Click Avg Review Score. Format: Decimal, 2 places.

**Step 4 — Build Executive Summary Page (20 min)**

Right-click on Page1 tab at the bottom → Rename → "Executive Summary".
Set the background: View → Canvas background → Color: #1A1A2E (dark navy).
This makes your dashboard look like an actual BI product, not a school project.

Layout from top to bottom:

*Row 1 — 4 KPI Cards:*
- Insert → Card visual → drag Total Revenue into Values
- Duplicate it 3 times
- Change the measure in each: Total Orders, AOV, Repeat Customer Rate %
- In each card's Format pane: 
  - Title: on, write the metric name
  - Callout value: font size 28, bold, color white
  - Background: #16213E
  - Border: on, color #0F3460

*Row 2 — Revenue Trend Line:*
- Insert → Line chart
- X axis: DateTable[YearMonth] (this gives "2016-09" style labels)
- Y axis: Total Revenue (as bars or area) + Revenue 3M Rolling Avg (as line)
  To get two lines: click the visual → Add another Y-axis series → 
  Revenue 3M Rolling Avg → Format → change to Line type, dashed
- Title: "Monthly Revenue + 3-Month Rolling Average"
- Background: #16213E, font color white

*Row 3 — Two visuals side by side:*

Left: Clustered bar chart
- Y axis: dim_products[product_category_broad]
- X axis: Total Revenue
- Sort descending by Total Revenue
- Conditional formatting on bars: Home → Format → Data colors → fx →
  Color by value, gradient from #0F3460 to #E94560
- Title: "Revenue by Category"

Right: Donut chart
- Values: Total Orders
- Legend: fact_orders[payment_methods]
- Or: use vw_payment_analysis[payment_methods] and vw_payment_analysis[order_count]
- Title: "Orders by Payment Method"

*Bottom Row — 3 KPI tiles in a row:*
Small cards for: Revenue YoY %, Revenue MoM %, Late Delivery Rate %
These give time context to the revenue number in Row 1.

**Step 5 — Add a slicer (5 min)**

Insert → Slicer → drag DateTable[Year] into it.
This lets you filter the whole page by year (2016, 2017, 2018).
Format the slicer: Style → Dropdown, so it takes minimal space.

### Design Principles for This Page
- Every visual has a title
- Font colors are white or light grey (dark background)
- No default blue Power BI colors — use a custom palette
- No visual should require reading a legend to understand what it shows
- The biggest number on the page (Total Revenue) should be visible in 2 seconds

### Common Errors

**Revenue YoY % shows BLANK instead of a number**
Your DateTable relationship is wrong or the Date Table is not marked.
Go to Model view → right-click DateTable → Mark as Date Table → Date column.
Also verify the relationship line goes from DateTable[Date] to fact_orders[order_purchase_date].

**Revenue LY shows same value as Total Revenue**
The relationship uses the wrong column. In fact_orders, the date column must
be `order_purchase_date` (a DATE type), not `order_purchase_timestamp` (a DATETIME).
Go to Power Query and verify the column type.

**Card visuals show "Error" or blank**
Check the measure formula in the formula bar for syntax errors.
Common mistake: missing closing parenthesis. DIVIDE( needs exactly 2 or 3 arguments.

**Total Revenue doesn't match what MySQL showed**
The filter `fact_orders[is_delivered] = 1` inside Total Revenue is filtering out
in-transit orders. That's intentional. If you want all orders including in-transit,
remove that filter from the measure.

### Interview Talking Points
- "I put all measures in a single dedicated table. This keeps the model clean —
  measures don't get scattered across whatever table happened to be active when I
  clicked New Measure."
- "I used Revenue 3M Rolling Avg alongside raw monthly revenue so that the trend
  line isn't obscured by individual month spikes. Averaging removes noise."
- "The Revenue YoY % uses SAMEPERIODLASTYEAR, which requires the DateTable to be
  marked as a Date Table. Without that marking, the function falls back to calendar
  year logic and returns wrong results."

---

## CLASS 5 — Customer Intelligence, Geo, Sellers + Publish (1 Hour)

### Objective
By end of class: 3 more report pages (Customer Intelligence, Geographic, Seller
Performance), bookmarks, drill-through, a published Power BI Service URL you can
share with anyone. This is your portfolio piece.

### Steps

**Step 1 — Customer Intelligence Page (20 min)**

Add a new page: click the + at the bottom → rename it "Customer Intelligence".
Same dark background: #1A1A2E.

This page tells the story: who are our customers and what segments are we losing?

*Visual A — RFM Segment Bar Chart (left half of page):*
- Clustered bar chart
- Y axis: dim_customers[rfm_segment]
- X axis: Total Revenue (or dim_customers[monetary] aggregated)
- Better yet: use vw_rfm_segments directly
  - Axis: vw_rfm_segments[rfm_segment]
  - Values: vw_rfm_segments[total_spend]
- Conditional formatting: make "Lost" red, "Champions" green
  Format → Data colors → fx → rules-based coloring by segment name
- Title: "Revenue by Customer Segment"

*Visual B — Segment KPI Table (right half):*
- Table or Matrix visual
- Rows: vw_rfm_segments[rfm_segment]
- Values: customer_count, avg_spend, total_spend, revenue_contribution_pct
- Format → Values → font size 12 → Bold header row
- This table is the "so what" — it shows Champions are 8% of customers but
  contribute 35% of revenue. That's a story.

*Visual C — Repeat Customer Rate KPI (top right corner):*
- Card visual
- Measure: Repeat Customer Rate %
- This number being ~3% is intentional and explains why RFM matters —
  most customers only buy once.

*Visual D — Customer Frequency Distribution:*
- Histogram (use a Clustered Column chart with bins)
- X axis: dim_customers[frequency] bucketed: 1, 2, 3, 4, 5+
  To bucket: add a Calculated Column to dim_customers:
  ```dax
  Frequency Bucket =
  SWITCH(
      TRUE(),
      dim_customers[frequency] = 1, "1 order",
      dim_customers[frequency] = 2, "2 orders",
      dim_customers[frequency] = 3, "3 orders",
      dim_customers[frequency] >= 4, "4+ orders",
      "Unknown"
  )
  ```
- Y axis: count of customers
- This visual shows the "long tail" of single-purchase customers — the majority.

**Step 2 — Geographic Performance Page (15 min)**

Add new page → rename "Geographic Analysis".

*Visual A — Filled Map of Brazil (main visual, large):*
Power BI has a built-in Filled Map visual.
- Location: vw_state_performance[customer_state] — must be set to Data Category: "State or Province"
  To set: click the field in vw_state_performance → Column tools tab → Data category → State or Province
  Also set the table's Country column (add a calculated column "Country = "Brazil"" if needed)
- Color saturation: vw_state_performance[total_revenue]
- Tooltips: Add avg_delivery_days, late_rate_pct, avg_review_score to tooltips field
- The map should show São Paulo (SP) as the darkest state — it's the biggest market.

*Visual B — State Comparison Bar Chart (right side):*
- Clustered bar chart (horizontal)
- Y axis: customer_state (sorted descending by total_revenue)
- X axis: total_revenue
- Add data labels: Format → Data labels → on
- This shows the same story as the map but with exact numbers.

*Visual C — Delivery vs Review Scatter (bottom):*
- Scatter chart
- X axis: vw_state_performance[avg_delivery_days]
- Y axis: vw_state_performance[avg_review_score]
- Size: vw_state_performance[total_orders]
- Details (labels): vw_state_performance[customer_state]
- This is the key insight: states with slower delivery have lower review scores.
  You can literally draw a line through the scatter and see the correlation.
- Add two constant lines (Analytics pane → X-axis constant line at 15 days,
  Y-axis constant line at 4.0 stars) to create visual quadrants.
- Title: "Delivery Speed vs Customer Satisfaction by State"

**Step 3 — Seller Performance Page (10 min)**

Add new page → rename "Seller Performance".

*Visual A — Seller Scatter Plot (main visual):*
- Scatter chart
- X axis: vw_seller_performance[on_time_pct]
- Y axis: vw_seller_performance[avg_review_score]
- Size: vw_seller_performance[total_revenue]
- Details: vw_seller_performance[seller_id] (truncated — that's fine)
- Add constant lines: X at 90%, Y at 4.0 — creates 4 quadrants
- Analytics pane → X-axis constant line: Value = 90, label "90% Benchmark"
- Analytics pane → Y-axis constant line: Value = 4.0, label "4.0★ Benchmark"
- The bottom-left quadrant (low on-time, low review) = Problem Sellers.
  This is the actionable finding on this page.
- Title: "Seller Quality: On-Time Delivery vs Review Score"

*Visual B — Top/Bottom Sellers Table:*
- Table visual: seller_state, total_orders, total_revenue, on_time_pct, avg_review_score
- Conditional formatting on on_time_pct: green above 90%, red below 85%
  Format → Conditional formatting → Background color → Rules

**Step 4 — Add Drill-Through from Seller Scatter to Seller Detail (5 min)**

Create a new page → rename "Seller Detail" → set it as a drill-through page:
- In the Filters pane on the right, drag vw_seller_performance[seller_id] into
  the "Drill through" section at the bottom of the Filters pane.
- Add a table on this page showing all orders from this seller:
  fact_orders filtered by seller_id (drill-through context handles the filter automatically)
  Columns: order_id, order_purchase_date, revenue, delivery_days, was_late, review_score

Now on the Seller Performance page: right-click any dot on the scatter →
Drill through → Seller Detail. You'll see all that seller's orders.

**Step 5 — Add Bookmarks on Executive Summary (5 min)**

Bookmarks let you toggle between views without building separate pages.
Add two bookmarks to the Executive Summary page:

View A: "This Year" — slicer set to 2018
View B: "Full Period" — slicer set to All

How to add bookmarks:
- View tab → Bookmarks pane → Add
- Set slicer to 2018 → click Add → rename bookmark "This Year"
- Set slicer to All → click Add → rename bookmark "Full Period"

Add two buttons on the page (Insert → Buttons → Blank):
- Label each button: "This Year" and "Full Period"
- Format → Action → Action type: Bookmark → select the corresponding bookmark

Now clicking the button filters the entire page. This is the kind of UX
detail that makes a recruiter say "this person has actually built dashboards before."

**Step 6 — Custom Tooltip on Revenue Trend (optional, 5 min)**

Tooltips let you show extra information when hovering over a data point.
- Create a new page → rename "Tooltip Revenue" → resize it to Tooltip size:
  Format → Page size → Type: Tooltip
- Add 3 small card visuals on this page: Total Orders, AOV, Late Delivery Rate %
- Go back to Executive Summary → click the Revenue trend chart →
  Format → Tooltips → Type: Report Page → Page: Tooltip Revenue
- Now hover over any month on the trend chart — the tooltip shows those 3 KPIs
  for that specific month.

**Step 7 — Publish to Power BI Service (5 min)**

Home → Publish → Sign in with a Microsoft account (free with Outlook/Hotmail).
Select "My workspace" → Publish.

After publishing, Power BI opens the web link. Copy this URL.
This is what goes in your portfolio and resume.

To make it shareable: File → Publish to web → Create embed code → Public.
This gives you a link anyone can open without a Power BI account.

### Final Checklist Before Sharing

- [ ] All 4 main pages have consistent dark background and white text
- [ ] Every visual has a clear title
- [ ] All KPI cards show the correct format (R$, %, days)
- [ ] Revenue YoY % shows a number, not BLANK
- [ ] The scatter charts have quadrant lines
- [ ] Bookmarks work on the Executive Summary page
- [ ] Drill-through works from Seller scatter to Seller Detail page
- [ ] Published URL opens without a sign-in

### Interview Talking Points

**On the Customer Intelligence page:**
- "The RFM segment table shows Champions represent ~8% of customers but drive
  nearly 35% of revenue. That's the business case for retention investment."
- "The repeat purchase rate is around 3%, which means acquiring new customers is
  the growth lever, but the value of retaining Champions is disproportionate."

**On the Geographic page:**
- "There's a visible correlation between delivery days and review score.
  States in the north of Brazil (PA, AM) have 20+ day delivery and sub-3.5 star
  ratings. States in the south (SP, PR) have 8-day delivery and 4.2+ stars.
  The business should look at its logistics coverage in the north."

**On the Seller page:**
- "I filtered to sellers with at least 10 orders so the scatter isn't dominated
  by noise from one-order sellers. A seller with 2 orders and 5 stars isn't
  evidence of quality — it's a small sample."

**On the overall architecture:**
- "A recruiter can open the URL, filter by year, click into any category or seller,
  and navigate without me being there. That's the bar for a real deliverable."

---

## APPENDIX: What to Write in Your Resume / Portfolio

**Project title:** RetailIQ — E-Commerce Intelligence Platform

**One-line description:**
End-to-end analytics pipeline on 100K+ real orders: Python (EDA + RFM scoring),
MySQL (star schema + analytical views), Power BI (4-page interactive dashboard
with DAX time intelligence, customer segmentation, and seller performance analysis).

**Technologies:** Python (pandas, numpy), MySQL 8.0, Power BI (DAX, Power Query),
SQLAlchemy, Git

**Key deliverables:**
- Cleaned and modelled 9-table e-commerce dataset; 96K orders, 32K products, 3K sellers
- RFM customer segmentation (5 segments) revealing Champions drive 35% of revenue
  from 8% of customers
- Identified north-south delivery gap: northern states average 22-day delivery,
  4× longer than São Paulo, with measurable review score impact
- Published interactive dashboard: [your URL here]

**GitHub link:** push all Python + SQL files to a public repo.
Add a README.md with 3 screenshots of the dashboard and the same bullet points above.
