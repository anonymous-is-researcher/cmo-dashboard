import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px

# Auth check


# DB connection
db_user = st.secrets["POSTGRES_USER"]
db_pwd = st.secrets["POSTGRES_PASSWORD"]
db_name = st.secrets["POSTGRES_DB"]
db_host = st.secrets["POSTGRES_HOST"]
db_port = st.secrets["POSTGRES_PORT"]

engine = create_engine(f"postgresql://{db_user}:{db_pwd}@{db_host}:{db_port}/{db_name}")

# Page
st.set_page_config(page_title="CoffeeGo - CMO Dashboard", layout="wide")
st.title("📈 CoffeeGo — CMO Dashboard")

# Year selection
year = st.selectbox("📅 Select Year", options=[2022, 2023, 2024], index=2)

# --- Revenue by channel ---
df_ca_canal = pd.read_sql(
    """
    SELECT c.canal_name, SUM(s.amount) AS ca_sales, COUNT(DISTINCT s.id_client) AS nb_clients
    FROM f_sales s
    JOIN dim_canal c ON s.id_canal = c.id_canal
    JOIN dim_time t ON s.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY c.canal_name
    ORDER BY ca_sales DESC
    """, engine, params={"year": year}
)
st.subheader("Revenue & Clients by Channel")
fig1 = px.bar(df_ca_canal, x="canal_name", y="ca_sales", title="Sales Revenue by Channel", text_auto=".2s")
st.plotly_chart(fig1, use_container_width=True)
st.dataframe(df_ca_canal.rename(columns={"canal_name":"Channel","ca_sales":"Revenue (€)","nb_clients":"Nb Clients"}))

# --- Revenue by product ---
st.subheader("Revenue Share by Product")

ca_total = pd.read_sql(
    """
    SELECT SUM(amount) AS ca_total
    FROM f_sales s
    JOIN dim_time t ON s.id_time = t.id_time
    WHERE t.year = %(year)s
    """, engine, params={"year": year}
)['ca_total'][0] or 0

df_ca_prod = pd.read_sql(
    """
    SELECT p.product_name, SUM(s.amount) AS ca_produit
    FROM f_sales s
    JOIN dim_product p ON s.id_product = p.id_product
    JOIN dim_time t ON s.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY p.product_name
    ORDER BY ca_produit DESC
    """, engine, params={"year": year}
)

df_ca_prod["pct_CA"] = 100 * df_ca_prod["ca_produit"] / ca_total if ca_total > 0 else 0
fig_prod = px.pie(df_ca_prod, names="product_name", values="ca_produit", title="Revenue Share by Product", hole=0.3)
st.plotly_chart(fig_prod, use_container_width=True)

# --- Geographic origin of clients ---
st.subheader("Geographic Distribution of Clients")
df_client_location = pd.read_sql(
    """
    SELECT location, COUNT(*) AS nb_clients
    FROM dim_client
    GROUP BY location
    ORDER BY nb_clients DESC
    LIMIT 15
    """, engine
)
fig_geo = px.bar(df_client_location, x="location", y="nb_clients", title="Top Cities of Clients", text_auto=True)
st.plotly_chart(fig_geo, use_container_width=True)

# --- Client acquisition by channel ---
st.subheader("Client Acquisition by Channel")
df_client_origin = pd.read_sql(
    """
    SELECT d.canal_name, COUNT(DISTINCT a.id_client) AS nb_clients
    FROM f_abonnement a
    JOIN dim_time t ON a.id_time = t.id_time
    JOIN dim_canal d ON a.id_canal = d.id_canal
    WHERE t.year = %(year)s
    GROUP BY d.canal_name
    ORDER BY nb_clients DESC
    """, engine, params={"year": year}
)
fig_origin = px.bar(df_client_origin, x="canal_name", y="nb_clients", title="Clients Acquired by Channel", text_auto=True)
st.plotly_chart(fig_origin, use_container_width=True)

# --- Campaign conversions & CAC ---
df_ca_camp = pd.read_sql(
    """
    SELECT d.name AS campaign, SUM(f.conversions) AS conversions, SUM(f.cac) AS total_cac
    FROM f_campagnemarketing f
    JOIN dim_campaign d ON f.id_campaign = d.id_campaign
    JOIN dim_time t ON f.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY d.name
    ORDER BY conversions DESC
    """, engine, params={"year": year}
)
st.subheader("Campaign Conversions & Total CAC")
fig2 = px.bar(df_ca_camp, x="campaign", y="conversions", title="Conversions per Campaign", text_auto=True)
st.plotly_chart(fig2, use_container_width=True)
st.dataframe(df_ca_camp.rename(columns={"campaign":"Campaign","conversions":"Conversions","total_cac":"Total CAC (€)"}))

# --- CAC by channel ---
df_cac_canal = pd.read_sql(
    """
    SELECT c.canal_name, AVG(f.cac) AS avg_cac
    FROM f_campagnemarketing f
    JOIN dim_canal c ON f.id_canal = c.id_canal
    JOIN dim_time t ON f.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY c.canal_name
    """, engine, params={"year": year}
)
avg_cac_global = df_cac_canal["avg_cac"].mean() if not df_cac_canal.empty else 0

col1, col2 = st.columns(2)
col1.metric("Average Global CAC (€)", f"{avg_cac_global:.2f}", help="Average Customer Acquisition Cost across all channels.")
if not df_cac_canal.empty:
    col2.metric("Most Efficient Channel (CAC)", df_cac_canal.sort_values("avg_cac").iloc[0]["canal_name"])

fig3 = px.bar(df_cac_canal, x="canal_name", y="avg_cac", title="Average CAC per Channel", text_auto=".2f")
st.plotly_chart(fig3, use_container_width=True)

# --- NPS by channel ---
st.subheader("NPS per Channel")
df_nps_canal = pd.read_sql(
    """
    SELECT c.canal_name, AVG(cs.NPS) AS nps
    FROM f_clientsatisfaction cs
    JOIN dim_canal c ON cs.id_canal = c.id_canal
    JOIN dim_time t ON cs.id_time = t.id_time
    WHERE t.year = %(year)s
    GROUP BY c.canal_name
    """, engine, params={"year": year}
)
fig6 = px.bar(df_nps_canal, x="canal_name", y="nps", title="NPS by Channel", text_auto=".1f")
st.plotly_chart(fig6, use_container_width=True)

# --- Subscriber retention cohort ---
st.subheader("Subscriber Retention Cohort")
df_cohorte = pd.read_sql(
    """
    SELECT dt.month AS mois_start, COUNT(DISTINCT a.id_client) AS nb_nouveaux,
           SUM(CASE WHEN a.state = 'active' THEN 1 ELSE 0 END) AS nb_retenus
    FROM f_abonnement a
    JOIN dim_time dt ON a.id_time = dt.id_time
    WHERE dt.year = %(year)s
    GROUP BY dt.month ORDER BY dt.month
    """, engine, params={"year": year}
)
if not df_cohorte.empty:
    df_cohorte["Retention (%)"] = 100 * df_cohorte["nb_retenus"] / df_cohorte["nb_nouveaux"]
    fig_cohort = px.line(df_cohorte, x="mois_start", y="Retention (%)", title="Monthly Subscriber Retention Rate", markers=True)
    st.plotly_chart(fig_cohort, use_container_width=True)
    st.dataframe(df_cohorte.rename(columns={"mois_start":"Start Month", "nb_nouveaux":"New Subscribers", "nb_retenus":"Retained Subscribers", "Retention (%)":"Retention (%)"}))
else:
    st.info("No cohort data available for the selected year.")

# Footer
st.caption("CMO Dashboard — CoffeeGo DSS Simulation ©️")
