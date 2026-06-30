# RetailIQ — DAX Measures Reference
## Class 4 | Power BI

All measures go into a single empty table called `_Measures`.
This keeps your model view clean — no measures scattered across tables.

### How to Create the Measures Table
1. Home → Enter Data → Name the table `_Measures` → Load
2. Delete the default Column1 by right-clicking → Remove Column in Power Query
3. Close & Apply
4. Now create all measures inside `_Measures` using New Measure

---

## SECTION 1: Date Table (Create BEFORE any measures)

Create this table first. Without a proper date table, all time intelligence
functions (MTD, YTD, SAMEPERIODLASTYEAR) will fail silently.

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
    "YearMonth",   FORMAT([Date], "YYYY-MM"),      -- used for sorting charts
    "IsWeekend",   IF(WEEKDAY([Date], 2) >= 6, 1, 0)
)
```

After creating: right-click DateTable in the model → Mark as Date Table → select Date column.

Then create this relationship:
- fact_orders[order_purchase_date]  →  DateTable[Date]  (Many-to-one, Single direction)

---

## SECTION 2: Basic Aggregation Measures

```dax
-- Total revenue from completed orders
Total Revenue =
CALCULATE(
    SUM(fact_orders[revenue]),
    fact_orders[is_delivered] = 1
)
```

```dax
-- Total orders (distinct count handles any duplicates)
Total Orders =
DISTINCTCOUNT(fact_orders[order_id])
```

```dax
-- Average order value
AOV =
DIVIDE([Total Revenue], [Total Orders])
```

```dax
-- Total unique customers who placed at least one order
Total Customers =
DISTINCTCOUNT(fact_orders[customer_id])
```

```dax
-- Total items sold (sum of item_count per order)
Total Items Sold =
SUM(fact_orders[item_count])
```

```dax
-- Average items per order
Avg Items Per Order =
DIVIDE([Total Items Sold], [Total Orders])
```

```dax
-- Average review score (only where score exists)
Avg Review Score =
CALCULATE(
    AVERAGE(fact_orders[review_score]),
    NOT ISBLANK(fact_orders[review_score])
)
```

```dax
-- Late delivery rate as a percentage
Late Delivery Rate % =
DIVIDE(
    CALCULATE(COUNTROWS(fact_orders), fact_orders[was_late] = 1, fact_orders[is_delivered] = 1),
    CALCULATE(COUNTROWS(fact_orders), fact_orders[is_delivered] = 1)
) * 100
```

```dax
-- Average delivery days (only delivered orders)
Avg Delivery Days =
CALCULATE(
    AVERAGE(fact_orders[delivery_days]),
    fact_orders[is_delivered] = 1,
    fact_orders[delivery_days] > 0
)
```

```dax
-- Total freight value
Total Freight =
SUM(fact_orders[freight_value])
```

```dax
-- Freight as a % of revenue
Freight as % of Revenue =
DIVIDE([Total Freight], [Total Revenue]) * 100
```

---

## SECTION 3: Time Intelligence Measures

These all require the DateTable to be marked as a Date Table.
The relationship must be: fact_orders[order_purchase_date] → DateTable[Date]

```dax
-- Revenue same period last year
Revenue LY =
CALCULATE(
    [Total Revenue],
    SAMEPERIODLASTYEAR(DateTable[Date])
)
```

```dax
-- Year-over-year growth percentage
Revenue YoY % =
DIVIDE(
    [Total Revenue] - [Revenue LY],
    [Revenue LY]
) * 100
```

```dax
-- Revenue in the previous month
Revenue PM =
CALCULATE(
    [Total Revenue],
    DATEADD(DateTable[Date], -1, MONTH)
)
```

```dax
-- Month-over-month growth percentage
Revenue MoM % =
DIVIDE(
    [Total Revenue] - [Revenue PM],
    [Revenue PM]
) * 100
```

```dax
-- Month-to-date revenue (resets every month)
Revenue MTD =
TOTALMTD([Total Revenue], DateTable[Date])
```

```dax
-- Year-to-date revenue (resets every year)
Revenue YTD =
TOTALYTD([Total Revenue], DateTable[Date])
```

```dax
-- Running cumulative revenue (never resets — goes from day 1 to today)
Running Revenue Total =
CALCULATE(
    [Total Revenue],
    FILTER(
        ALL(DateTable[Date]),
        DateTable[Date] <= MAX(DateTable[Date])
    )
)
```

```dax
-- 3-month rolling average (smooths out spikes in trend charts)
Revenue 3M Rolling Avg =
AVERAGEX(
    DATESINPERIOD(DateTable[Date], LASTDATE(DateTable[Date]), -3, MONTH),
    [Total Revenue]
)
```

```dax
-- Orders same period last year
Orders LY =
CALCULATE(
    [Total Orders],
    SAMEPERIODLASTYEAR(DateTable[Date])
)
```

```dax
-- Orders YoY growth
Orders YoY % =
DIVIDE([Total Orders] - [Orders LY], [Orders LY]) * 100
```

---

## SECTION 4: Customer Measures

```dax
-- Customers who ordered more than once (unique person, multiple orders)
Repeat Customers =
CALCULATE(
    DISTINCTCOUNT(fact_orders[customer_id]),
    FILTER(
        VALUES(fact_orders[customer_id]),
        CALCULATE(DISTINCTCOUNT(fact_orders[order_id])) > 1
    )
)
```

```dax
-- Repeat purchase rate
Repeat Customer Rate % =
DIVIDE([Repeat Customers], [Total Customers]) * 100
```

```dax
-- Average customer lifetime value (avg total spend per customer)
Avg Customer LTV =
DIVIDE([Total Revenue], [Total Customers])
```

---

## SECTION 5: Product / Category Measures

```dax
-- Revenue rank of a category (lower number = higher revenue)
-- Use this as a measure in a table visual with category names
Category Revenue Rank =
RANKX(
    ALL(dim_products[product_category_broad]),
    [Total Revenue],
    ,
    DESC,
    DENSE
)
```

---

## SECTION 6: Seller Measures

```dax
-- On-time delivery rate for sellers
On Time Delivery % =
DIVIDE(
    CALCULATE(
        COUNTROWS(fact_orders),
        fact_orders[was_late] = 0,
        fact_orders[is_delivered] = 1
    ),
    CALCULATE(
        COUNTROWS(fact_orders),
        fact_orders[is_delivered] = 1
    )
) * 100
```

---

## SECTION 7: Calculated Columns (add to dim_customers table)

These are columns, not measures. Right-click dim_customers → New Column.

```dax
-- RFM segment color for conditional formatting
RFM Color =
SWITCH(
    dim_customers[rfm_segment],
    "Champions",      "#27AE60",    -- green
    "Loyal Customers","#2980B9",    -- blue
    "At Risk",        "#E67E22",    -- orange
    "Needs Attention","#E74C3C",    -- red
    "Lost",           "#95A5A6",    -- grey
    "#BDC3C7"
)
```

```dax
-- Simple revenue tier label (used in tooltips)
Revenue Tier =
SWITCH(
    TRUE(),
    dim_customers[monetary] >= 500, "High Value (R$500+)",
    dim_customers[monetary] >= 200, "Mid Value (R$200-499)",
    "Entry (< R$200)"
)
```

---

## SECTION 8: Dynamic Titles (use in text boxes with DAX)

These make your report feel alive — the title changes with whatever
the user has filtered.

```dax
-- Dynamic subtitle for filtered state
Selected State Title =
IF(
    ISFILTERED(dim_customers[customer_state]),
    "Filtered: " & SELECTEDVALUE(dim_customers[customer_state], "Multiple States"),
    "All States"
)
```

```dax
-- Dynamic period label
Selected Period =
IF(
    ISFILTERED(DateTable[Year]),
    "Year: " & SELECTEDVALUE(DateTable[Year], "Multiple"),
    "All Time"
)
```

---

## SECTION 9: KPI Formatting Reference

When adding a KPI card or measure to a visual, use these formatting strings.
Set them in the Measure → Format → Format String field.

| Measure               | Format String          | Example Output   |
|-----------------------|------------------------|-----------------|
| Total Revenue         | `"R$ "#,##0.00`        | R$ 13,591,644.02|
| AOV                   | `"R$ "#,##0.00`        | R$ 154.87       |
| Revenue YoY %         | `+0.0%;-0.0%;0.0%`     | +14.2%          |
| Late Delivery Rate %  | `0.0"%"`               | 8.3%            |
| Avg Review Score      | `0.00" / 5"`           | 4.09 / 5        |
| Repeat Customer Rate% | `0.0"%"`               | 3.2%            |
| Avg Delivery Days     | `0.0" days"`           | 12.4 days       |

---

## SECTION 10: Measures Needed Per Page

### Page 1 — Executive Summary
- Total Revenue, Total Orders, AOV, Total Customers
- Revenue YoY %, Revenue MoM %
- Revenue YTD, Revenue 3M Rolling Avg
- Avg Review Score, Late Delivery Rate %

### Page 2 — Customer Intelligence
- Total Customers, Repeat Customer Rate %, Avg Customer LTV
- (RFM data comes directly from dim_customers columns, not measures)

### Page 3 — Geographic
- Total Revenue, Total Orders, Avg Delivery Days, Late Delivery Rate %
- (Filter context from the map drives these automatically)

### Page 4 — Sellers
- On Time Delivery %, Avg Review Score, Total Revenue, Total Orders
- (Filter context from the scatter drives the detail table)
