"""
RetailIQ — Olist E-Commerce Data Cleaning Pipeline
Class 1 | Python Foundation

DATASET (free, no account needed via direct link):
  https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
  Click "Download" → ZIP (~37MB). Extract all 9 CSVs into data/raw/

INSTALL:
  pip install pandas numpy

RUN:
  python 01_olist_cleaning.py

OUTPUT:
  4 clean CSV files saved to data/clean/ — ready for MySQL loading
"""

import pandas as pd
import numpy as np
import os
import warnings
warnings.filterwarnings('ignore')

# =====================================================================
# CONFIG — only change these paths if your folder structure differs
# =====================================================================
RAW   = "./data/raw/"
CLEAN = "./data/clean/"
os.makedirs(CLEAN, exist_ok=True)

# RFM snapshot date: 3 months after last order in dataset.
# We treat this as "today" for recency calculations.
SNAPSHOT_DATE = pd.Timestamp("2019-01-01")


# =====================================================================
# STEP 1 — LOAD ALL 9 RAW CSVs
# =====================================================================
def load_raw_data():
    print("[1/7] Loading raw CSVs...")
    data = {
        'orders':       pd.read_csv(f"{RAW}olist_orders_dataset.csv"),
        'items':        pd.read_csv(f"{RAW}olist_order_items_dataset.csv"),
        'payments':     pd.read_csv(f"{RAW}olist_order_payments_dataset.csv"),
        'reviews':      pd.read_csv(f"{RAW}olist_order_reviews_dataset.csv"),
        'customers':    pd.read_csv(f"{RAW}olist_customers_dataset.csv"),
        'products':     pd.read_csv(f"{RAW}olist_products_dataset.csv"),
        'sellers':      pd.read_csv(f"{RAW}olist_sellers_dataset.csv"),
        'geo':          pd.read_csv(f"{RAW}olist_geolocation_dataset.csv"),
        'translations': pd.read_csv(f"{RAW}product_category_name_translation.csv"),
    }
    for name, df in data.items():
        print(f"   {name:<15} {df.shape[0]:>7,} rows x {df.shape[1]} cols")
    return data


# =====================================================================
# STEP 2 — CLEAN ORDERS TABLE
# =====================================================================
def clean_orders(df):
    """
    Key decisions made here:
    1. Parse all 5 timestamp columns to datetime
    2. Remove cancelled/unavailable orders — they have no revenue and
       their null delivery dates would break every delivery metric.
    3. Add derived columns that Power BI can use without complex DAX.
    """
    print("[2/7] Cleaning orders...")

    date_cols = [
        'order_purchase_timestamp', 'order_approved_at',
        'order_delivered_carrier_date', 'order_delivered_customer_date',
        'order_estimated_delivery_date'
    ]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    keep_statuses = ['delivered', 'shipped', 'approved', 'processing', 'invoiced']
    before = len(df)
    df = df[df['order_status'].isin(keep_statuses)].copy()
    print(f"   Removed {before - len(df):,} cancelled/unavailable orders")
    print(f"   Remaining: {len(df):,} orders")

    # Date parts — pre-computing these is faster than letting Power BI
    # build a date hierarchy from a single timestamp column
    df['order_purchase_date'] = df['order_purchase_timestamp'].dt.date
    df['order_year']          = df['order_purchase_timestamp'].dt.year
    df['order_month']         = df['order_purchase_timestamp'].dt.month
    df['order_quarter']       = df['order_purchase_timestamp'].dt.quarter
    df['order_day_of_week']   = df['order_purchase_timestamp'].dt.day_name()

    # Delivery performance
    df['delivery_days'] = (
        df['order_delivered_customer_date'] - df['order_purchase_timestamp']
    ).dt.days

    df['estimated_days'] = (
        df['order_estimated_delivery_date'] - df['order_purchase_timestamp']
    ).dt.days

    # was_late = 1 if delivered after the promised date
    df['was_late'] = (
        df['order_delivered_customer_date'] > df['order_estimated_delivery_date']
    ).astype(int)
    # orders not yet delivered are not late — they're in transit
    df.loc[df['order_delivered_customer_date'].isna(), 'was_late'] = 0

    df['is_delivered'] = df['order_delivered_customer_date'].notna().astype(int)

    print(f"   Delivered: {df['is_delivered'].sum():,}  |  "
          f"Late rate: {df['was_late'].mean()*100:.1f}%  |  "
          f"Avg delivery days: {df['delivery_days'].mean():.1f}")
    return df


# =====================================================================
# STEP 3 — AGGREGATE ORDER ITEMS TO ORDER LEVEL
# =====================================================================
def build_items_aggregated(df_items):
    """
    One order can have multiple items from multiple sellers.
    We sum revenue and freight, and identify the "primary" item
    (highest price) to represent the order's seller and product
    in our star schema.
    """
    print("[3/7] Aggregating order items...")

    agg = df_items.groupby('order_id').agg(
        item_count    = ('order_item_id', 'count'),
        revenue       = ('price', 'sum'),
        freight_value = ('freight_value', 'sum'),
    ).reset_index()
    agg['order_value'] = agg['revenue'] + agg['freight_value']

    # Primary item = the one with highest price in this order
    idx     = df_items.groupby('order_id')['price'].idxmax()
    primary = df_items.loc[idx, ['order_id', 'seller_id', 'product_id']].rename(
        columns={'seller_id': 'primary_seller_id', 'product_id': 'primary_product_id'}
    )
    agg = agg.merge(primary, on='order_id', how='left')

    print(f"   {len(agg):,} orders aggregated  |  "
          f"Total revenue: R$ {agg['revenue'].sum():,.0f}")
    return agg


# =====================================================================
# STEP 4 — AGGREGATE PAYMENTS TO ORDER LEVEL
# =====================================================================
def clean_payments(df_payments):
    """
    Some customers pay with two methods (credit card + voucher).
    We aggregate to one row per order: total amount + methods used.
    """
    print("[4/7] Aggregating payments...")
    agg = df_payments.groupby('order_id').agg(
        total_payment   = ('payment_value', 'sum'),
        payment_methods = ('payment_type', lambda x: '|'.join(sorted(x.unique()))),
        installments    = ('payment_installments', 'max')
    ).reset_index()
    print(f"   {len(agg):,} orders with payment data")
    return agg


# =====================================================================
# STEP 5 — CLEAN REVIEWS TABLE
# =====================================================================
def clean_reviews(df_reviews):
    """
    Some orders have two reviews (customer updated it).
    We keep the latest review per order.
    ~87% of reviews have no written comment — that is normal and expected.
    """
    print("[5/7] Cleaning reviews...")
    df_reviews['review_creation_date'] = pd.to_datetime(
        df_reviews['review_creation_date'], errors='coerce'
    )
    reviews = (df_reviews
               .sort_values('review_creation_date', ascending=False)
               .drop_duplicates(subset='order_id', keep='first'))

    reviews['has_comment'] = reviews['review_comment_message'].notna().astype(int)
    reviews = reviews[['order_id', 'review_score', 'has_comment']].copy()

    dist = reviews['review_score'].value_counts().sort_index()
    print(f"   {len(reviews):,} reviews retained")
    print(f"   Score distribution: " +
          "  ".join([f"{k}*:{v:,}" for k,v in dist.items()]))
    return reviews


# =====================================================================
# STEP 6 — CLEAN PRODUCTS TABLE + ENGLISH CATEGORY NAMES
# =====================================================================
def clean_products(df_products, df_translations):
    """
    Products have Portuguese category names.
    We merge the English translation and then group 73 detailed
    categories into 10 broad buckets — easier to filter in Power BI.
    """
    df = df_products.merge(df_translations, on='product_category_name', how='left')
    df['product_category_name_english'] = (
        df['product_category_name_english']
        .fillna(df['product_category_name'])  # fallback to Portuguese if no translation
        .fillna('unknown')
    )

    # Business decision: 73 categories → 10 buckets for executive-level filtering
    BROAD_MAP = {
        'bed_bath_table': 'Home & Living',       'furniture_decor': 'Home & Living',
        'housewares': 'Home & Living',            'home_appliances': 'Home & Living',
        'kitchen_dining_laundry_garden_furniture': 'Home & Living',
        'computers_accessories': 'Electronics',   'computers': 'Electronics',
        'electronics': 'Electronics',             'telephony': 'Electronics',
        'tablets_printing_image': 'Electronics',  'fixed_telephony': 'Electronics',
        'watches_gifts': 'Fashion & Accessories', 'fashion_bags_accessories': 'Fashion & Accessories',
        'fashion_male_clothing': 'Fashion & Accessories',
        'fashio_female_clothing': 'Fashion & Accessories',
        'fashion_shoes': 'Fashion & Accessories', 'fashion_sport': 'Fashion & Accessories',
        'fashion_underwear_beach': 'Fashion & Accessories',
        'luggage_accessories': 'Fashion & Accessories',
        'health_beauty': 'Health & Beauty',       'perfumery': 'Health & Beauty',
        'sports_leisure': 'Sports & Leisure',
        'toys': 'Toys & Baby',                    'baby': 'Toys & Baby',
        'books_general_interest': 'Books & Media','books_imported': 'Books & Media',
        'books_technical': 'Books & Media',       'cds_dvds_musicals': 'Books & Media',
        'music': 'Books & Media',                 'dvds_blu_ray': 'Books & Media',
        'auto': 'Automotive',
        'garden_tools': 'Tools & Garden',         'construction_tools_lights': 'Tools & Garden',
        'costruction_tools_garden': 'Tools & Garden',
        'food': 'Food & Drinks',                  'food_drink': 'Food & Drinks',
        'drinks': 'Food & Drinks',
    }

    def categorize(eng_name):
        name_key = str(eng_name).lower().replace(' ', '_')
        for key, bucket in BROAD_MAP.items():
            if key in name_key:
                return bucket
        return 'Other'

    df['product_category_broad'] = df['product_category_name_english'].apply(categorize)

    # Impute null physical dimensions with median — physically sensible
    for col in ['product_weight_g', 'product_length_cm', 'product_height_cm', 'product_width_cm']:
        df[col] = df[col].fillna(df[col].median())

    return df[[
        'product_id', 'product_category_name_english', 'product_category_broad',
        'product_weight_g', 'product_length_cm', 'product_height_cm', 'product_width_cm'
    ]].copy()


# =====================================================================
# STEP 7 — BUILD FACT TABLE
# =====================================================================
def build_fact_table(orders, items_agg, payments_agg, reviews_clean, customers):
    """
    Join all cleaned tables onto the orders backbone.
    The customer_id we store is customer_unique_id (the real person),
    not customer_id (which can appear multiple times for one person).
    """
    print("[6/7] Building fact_orders table...")

    id_map = customers[['customer_id', 'customer_unique_id']].drop_duplicates()

    fact = (orders
            .merge(items_agg,     on='order_id', how='left')
            .merge(payments_agg,  on='order_id', how='left')
            .merge(reviews_clean, on='order_id', how='left')
            .merge(id_map,        on='customer_id', how='left')
            .drop(columns=['customer_id'])
            .rename(columns={
                'customer_unique_id': 'customer_id',
                'primary_seller_id':  'seller_id',
                'primary_product_id': 'product_id',
            }))

    keep = [
        'order_id', 'customer_id', 'seller_id', 'product_id',
        'order_status', 'order_purchase_date', 'order_year', 'order_month',
        'order_quarter', 'order_day_of_week',
        'order_delivered_customer_date', 'delivery_days', 'estimated_days',
        'was_late', 'is_delivered',
        'item_count', 'revenue', 'freight_value', 'order_value',
        'total_payment', 'payment_methods', 'installments',
        'review_score', 'has_comment'
    ]
    fact = fact[[c for c in keep if c in fact.columns]].copy()

    print(f"   fact_orders: {len(fact):,} rows x {fact.shape[1]} cols")
    null_check = fact[['seller_id', 'product_id', 'revenue', 'review_score']].isnull().sum()
    print(f"   Null check  - seller_id: {null_check['seller_id']:,}  "
          f"product_id: {null_check['product_id']:,}  "
          f"revenue: {null_check['revenue']:,}  "
          f"review_score: {null_check['review_score']:,} (expected - not all orders reviewed)")
    return fact


# =====================================================================
# STEP 8 — RFM SCORING
# =====================================================================
def calculate_rfm(fact):
    """
    RFM: Recency / Frequency / Monetary
    - Recency   = days since last order (lower = better)
    - Frequency = number of orders placed (higher = better)
    - Monetary  = total amount spent (higher = better)

    Each scored 1–5. Champions have high F and M, low R.
    """
    delivered = fact[fact['is_delivered'] == 1].copy()
    delivered['order_purchase_date'] = pd.to_datetime(delivered['order_purchase_date'])

    rfm = delivered.groupby('customer_id').agg(
        recency_days = ('order_purchase_date', lambda x: (SNAPSHOT_DATE - x.max()).days),
        frequency    = ('order_id', 'count'),
        monetary     = ('revenue', 'sum')
    ).reset_index()

    rfm['r_score'] = pd.qcut(rfm['recency_days'],                    q=5, labels=[5,4,3,2,1], duplicates='drop').astype(int)
    rfm['f_score'] = pd.qcut(rfm['frequency'].rank(method='first'),  q=5, labels=[1,2,3,4,5]).astype(int)
    rfm['m_score'] = pd.qcut(rfm['monetary'],                        q=5, labels=[1,2,3,4,5], duplicates='drop').astype(int)
    rfm['rfm_score'] = rfm['r_score'] + rfm['f_score'] + rfm['m_score']

    def segment(score):
        if score >= 13: return 'Champions'
        elif score >= 10: return 'Loyal Customers'
        elif score >= 7:  return 'At Risk'
        elif score >= 5:  return 'Needs Attention'
        else:             return 'Lost'

    rfm['rfm_segment'] = rfm['rfm_score'].apply(segment)
    return rfm


# =====================================================================
# BUILD DIMENSION TABLES
# =====================================================================
def build_dim_customers(df_customers, fact, rfm):
    unique_custs = (df_customers
                    .drop_duplicates(subset='customer_unique_id')
                    .drop(columns=['customer_id'])
                    .rename(columns={'customer_unique_id': 'customer_id'}))
    unique_custs['customer_city']  = unique_custs['customer_city'].str.title()
    unique_custs['customer_state'] = unique_custs['customer_state'].str.upper()

    active_ids = fact['customer_id'].unique()
    dim = (unique_custs[unique_custs['customer_id'].isin(active_ids)]
           [['customer_id', 'customer_city', 'customer_state']]
           .merge(rfm, on='customer_id', how='left'))
    return dim


def build_dim_sellers(df_sellers, fact):
    s = df_sellers.copy()
    s['seller_city']  = s['seller_city'].str.title()
    s['seller_state'] = s['seller_state'].str.upper()
    active_ids = fact['seller_id'].dropna().unique()
    return s[s['seller_id'].isin(active_ids)][
        ['seller_id', 'seller_city', 'seller_state']
    ].copy()


# =====================================================================
# EXPORT + SUMMARY
# =====================================================================
def export_clean(fact, dim_customers, dim_products, dim_sellers):
    print("[7/7] Exporting clean files...")
    tables = {
        'fact_orders.csv':   fact,
        'dim_customers.csv': dim_customers,
        'dim_products.csv':  dim_products,
        'dim_sellers.csv':   dim_sellers,
    }
    for fname, df in tables.items():
        path = f"{CLEAN}{fname}"
        df.to_csv(path, index=False)
        print(f"   Saved: {fname:<25} ({len(df):,} rows x {df.shape[1]} cols)")


def print_summary(fact, dim_customers, dim_products, dim_sellers):
    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  fact_orders    : {len(fact):,} rows")
    print(f"  dim_customers  : {len(dim_customers):,} rows")
    print(f"  dim_products   : {len(dim_products):,} rows")
    print(f"  dim_sellers    : {len(dim_sellers):,} rows")
    print()
    print(f"  Total Revenue        : R$ {fact['revenue'].sum():>12,.2f}")
    print(f"  Avg Order Value      : R$ {fact['order_value'].mean():>8,.2f}")
    print(f"  Avg Review Score     :    {fact['review_score'].mean():>6.2f} / 5.0")
    print(f"  Late Delivery Rate   :    {fact['was_late'].mean()*100:>6.1f}%")
    print(f"  Avg Delivery Days    :    {fact['delivery_days'].mean():>6.1f} days")

    if 'rfm_segment' in dim_customers.columns:
        print()
        print("  RFM Segment Breakdown:")
        seg = (dim_customers.groupby('rfm_segment')
               .agg(customers=('customer_id','count'), avg_spend=('monetary','mean'))
               .sort_values('avg_spend', ascending=False))
        for seg_name, row in seg.iterrows():
            print(f"    {seg_name:<20}  {int(row['customers']):>5} customers  "
                  f"avg R$ {row['avg_spend']:>8.2f}")

    print()
    print(f"  Clean files saved to: {CLEAN}")
    print("=" * 60)
    print("  Next step: MySQL Workbench -> run 02_mysql_schema_views.sql")
    print("=" * 60)


# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  RetailIQ - Data Cleaning Pipeline")
    print("=" * 60)

    data           = load_raw_data()
    orders_clean   = clean_orders(data['orders'].copy())
    items_agg      = build_items_aggregated(data['items'])
    payments_agg   = clean_payments(data['payments'])
    reviews_clean  = clean_reviews(data['reviews'])
    products_clean = clean_products(data['products'], data['translations'])

    fact = build_fact_table(
        orders_clean, items_agg, payments_agg,
        reviews_clean, data['customers']
    )

    rfm           = calculate_rfm(fact)
    dim_customers = build_dim_customers(data['customers'], fact, rfm)
    dim_sellers   = build_dim_sellers(data['sellers'], fact)
    dim_products  = products_clean[
        products_clean['product_id'].isin(fact['product_id'].dropna().unique())
    ].copy()

    export_clean(fact, dim_customers, dim_products, dim_sellers)
    print_summary(fact, dim_customers, dim_products, dim_sellers)
