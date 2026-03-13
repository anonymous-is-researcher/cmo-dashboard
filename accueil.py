import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px


db_user = st.secrets["POSTGRES_USER"]
db_pwd = st.secrets["POSTGRES_PASSWORD"]
db_name = st.secrets["POSTGRES_DB"]
db_host = st.secrets["POSTGRES_HOST"]
db_port = st.secrets["POSTGRES_PORT"]

engine = create_engine(f"postgresql://{db_user}:{db_pwd}@{db_host}:{db_port}/{db_name}")

st.set_page_config(page_title="CoffeeGo - COO Dashboard", layout="wide")
st.title("🚚 CoffeeGo — COO Dashboard")

# Year selection
year = st.selectbox("📅 Select Year", options=[2022, 2023, 2024], index=2)

# --- TOP KPIs ---

# Total deliveries
total_deliv = pd.read_sql(
    "SELECT COUNT(*) AS nb FROM f_deliveries d JOIN dim_time t ON d.id_time = t.id_time WHERE t.year = %(year)s",
    engine, params={"year": year}
)['nb'][0] or 1

# Avg delivery time
mean_delay = pd.read_sql(
    "SELECT AVG(delivery_time) AS mean_delay FROM f_deliveries d JOIN dim_time t ON d.id_time = t.id_time WHERE t.year = %(year)s",
    engine, params={"year": year}
)['mean_delay'][0] or 0

# Delivery status
df_deliv_status = pd.read_sql(
    "SELECT status, COUNT(*) AS nb FROM f_deliveries d JOIN dim_time t ON d.id_time = t.id_time WHERE t.year = %(year)s GROUP BY status",
    engine, params={"year": year}
)
nb_ontime = df_deliv_status[df_deliv_status["status"]=="delivered_on_time"]["nb"].sum() if "delivered_on_time" in df_deliv_status["status"].values else 0
nb_delayed = df_deliv_status[df_deliv_status["status"]=="delayed"]["nb"].sum() if "delayed" in df_deliv_status["status"].values else 0
nb_inprog = df_deliv_status[df_deliv_status["status"]=="in_progress"]["nb"].sum() if "in_progress" in df_deliv_status["status"].values else 0

pct_ontime = 100 * nb_ontime / total_deliv if total_deliv > 0 else 0
pct_delayed = 100 * nb_delayed / total_deliv if total_deliv > 0 else 0
pct_inprog = 100 * nb_inprog / total_deliv if total_deliv > 0 else 0

# Stock shortages
df_shortages = pd.read_sql(
    "SELECT SUM(shortages) AS shortages, SUM(niveau_stock) AS stock_total FROM f_stock s JOIN dim_time t ON s.id_time = t.id_time WHERE t.year = %(year)s",
    engine, params={"year": year}
)
shortages = df_shortages["shortages"][0] or 0
stock_total = df_shortages["stock_total"][0] or 1
pct_shortage = 100 * shortages / stock_total if stock_total > 0 else 0

# Stock value
valeur_stock = pd.read_sql(
    "SELECT SUM(s.niveau_stock * p.cost) AS valeur_stock FROM f_stock s JOIN dim_product p ON s.id_product = p.id_product JOIN dim_time t ON s.id_time = t.id_time WHERE t.year = %(year)s",
    engine, params={"year": year}
)['valeur_stock'][0] or 0

# KPI HEADER
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Deliveries", f"{total_deliv:,}", help="Number of delivery operations completed.")
col2.metric("Avg. Delivery Time (days)", f"{mean_delay:.2f}", help="Average number of days per delivery.")
col3.metric("On-time Deliveries (%)", f"{pct_ontime:.1f}", help="Deliveries marked as 'delivered_on_time' over total deliveries.")
col4.metric("Delayed Deliveries (%)", f"{pct_delayed:.1f}", help="Deliveries marked as 'delayed' over total deliveries.")

col1, col2, col3 = st.columns(3)
col1.metric("Deliveries In Progress (%)", f"{pct_inprog:.1f}", help="Deliveries currently in progress.")
col2.metric("Stock Shortage Rate (%)", f"{pct_shortage:.2f}", help="Shortage units over total stock units.")
col3.metric("Total Stock Value (€)", f"{valeur_stock:,.0f}", help="Total stock value calculated from stock quantities and product costs.")

# --- Monthly Stock ---
st.subheader("📦 Monthly Stock per Product")
df_stock_month = pd.read_sql(
    """
    SELECT t.month, p.product_name, SUM(s.niveau_stock) AS stock
    FROM f_stock s
    JOIN dim_time t ON s.id_time = t.id_time
    JOIN dim_product p ON s.id_product = p.id_product
    WHERE t.year = %(year)s
    GROUP BY t.month, p.product_name
    ORDER BY t.month, p.product_name
    """, engine, params={"year": year}
)
fig_stock = px.bar(
    df_stock_month, x="month", y="stock", color="product_name",
    title="Monthly Stock Level per Product", barmode="group"
)
st.plotly_chart(fig_stock, use_container_width=True)

# --- Monthly Shortages ---
df_shortages_month = pd.read_sql(
    """
    SELECT t.month, SUM(s.shortages) AS shortages
    FROM f_stock s
    JOIN dim_time t ON s.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY t.month
    ORDER BY t.month
    """, engine, params={"year": year}
)
fig_short = px.bar(df_shortages_month, x="month", y="shortages", title="Monthly Stock Shortages")
st.plotly_chart(fig_short, use_container_width=True)

# --- Deliveries per Month and Status ---
st.subheader("🚛 Deliveries per Month and Status")
df_liv = pd.read_sql(
    """
    SELECT t.month, d.status, COUNT(*) AS nb_deliveries
    FROM f_deliveries d
    JOIN dim_time t ON d.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY t.month, d.status
    ORDER BY t.month, d.status
    """, engine, params={"year": year}
)
fig_liv = px.bar(df_liv, x="month", y="nb_deliveries", color="status", barmode="group", title="Monthly Deliveries by Status")
st.plotly_chart(fig_liv, use_container_width=True)

# --- Deliveries by City ---
st.subheader("🌍 Deliveries by City")
df_volume_city = pd.read_sql(
    """
    SELECT pl.city, COUNT(*) AS nb_livraisons
    FROM f_deliveries d
    JOIN dim_place pl ON d.id_place = pl.id_place
    JOIN dim_time t ON d.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY pl.city
    ORDER BY nb_livraisons DESC
    """, engine, params={"year": year}
)
fig_city = px.bar(df_volume_city, x="city", y="nb_livraisons", title="Number of Deliveries per City")
st.plotly_chart(fig_city, use_container_width=True)

# --- Deliveries per Product ---
st.subheader("📦 Deliveries per Product")
df_liv_prod = pd.read_sql(
    """
    SELECT p.product_name, COUNT(*) AS nb_liv
    FROM f_deliveries d
    JOIN dim_product p ON d.id_product = p.id_product
    JOIN dim_time t ON d.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY p.product_name
    ORDER BY nb_liv DESC
    """, engine, params={"year": year}
)
fig_liv_prod = px.bar(df_liv_prod, x="product_name", y="nb_liv", title="Deliveries per Product")
st.plotly_chart(fig_liv_prod, use_container_width=True)

# Footer
st.caption("COO Dashboard — CoffeeGo DSS Simulation ©️")
