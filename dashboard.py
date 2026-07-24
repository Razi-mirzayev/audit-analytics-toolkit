"""
dashboard.py
-------------
İnteraktiv Streamlit Audit Dashboard.

İşə salmaq üçün:
    pip install streamlit plotly
    streamlit run dashboard.py

Dashboard real vaxtda aşağıdakıları göstərir:
  - Benford Qanunu qrafiki
  - JET tapıntılarının bölgüsü
  - Maliyyə əmsalları və varyasiya analizi
  - Üç-tərəfli uyğunlaşdırma statusu
  - Audit seçməsi nəticələri

Öz CSV/Excel faylınızı yükləməklə real data üzərində də işlədə bilərsiniz
(gözlənilən sütunlar üçün main.py --help-ə baxın).
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data_generator import generate_journal_entries, generate_trial_balance
from benford_analysis import run_benford_test
from journal_entry_testing import run_all_je_tests
from ratio_analysis import calculate_ratios, analytical_variance_review
from sampling import monetary_unit_sample, recommended_sample_size
from three_way_match import generate_procurement_data, run_three_way_match

st.set_page_config(page_title="Audit Analytics Dashboard", layout="wide", page_icon="📊")

st.title("📊 Audit Analytics Dashboard")
st.caption("ISA (Beynəlxalq Audit Standartları) əsasında analitik audit prosedurları")


@st.cache_data
def load_data():
    je = generate_journal_entries(n_entries=1200)
    tb = generate_trial_balance(je)
    proc = generate_procurement_data()
    return je, tb, proc


with st.sidebar:
    st.header("⚙️ Parametrlər")
    variance_threshold = st.slider("Varyasiya həddi (%)", 5, 50, 15) / 100
    risk_level = st.selectbox("Audit riski səviyyəsi", ["aşağı", "orta", "yüksək"], index=1)
    st.markdown("---")
    st.markdown(
        "**Modul xəritəsi**\n"
        "- Benford → ISA 240\n"
        "- JET → ISA 240\n"
        "- Əmsallar → ISA 520\n"
        "- Seçmə → ISA 530\n"
        "- 3-tərəfli uyğunlaşdırma → P2P nəzarəti"
    )

je, tb, proc = load_data()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔢 Benford Analizi", "🚩 JET Tapıntıları", "📈 Əmsallar & Varyasiya",
    "🔗 3-tərəfli Uyğunlaşdırma", "🎯 Audit Seçməsi"
])

# ---- Tab 1: Benford ----
with tab1:
    result = run_benford_test(je["amount"])
    col1, col2, col3 = st.columns(3)
    col1.metric("Chi-kvadrat", result["chi2_stat"])
    col2.metric("p-dəyəri", result["p_value"])
    col3.metric("MAD Nəticəsi", result["mad_conclusion"])

    fig = go.Figure()
    fig.add_trace(go.Bar(x=result["table"]["first_digit"], y=result["table"]["observed_pct"],
                          name="Müşahidə olunan"))
    fig.add_trace(go.Scatter(x=result["table"]["first_digit"], y=result["table"]["expected_pct"],
                              name="Benford (gözlənilən)", mode="lines+markers"))
    fig.update_layout(title="İlk Rəqəm Paylanması: Müşahidə vs Benford Qanunu",
                       xaxis_title="İlk Rəqəm", yaxis_title="Faiz (%)")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(result["table"], use_container_width=True)

# ---- Tab 2: JET ----
with tab2:
    je_results = run_all_je_tests(je)
    st.dataframe(je_results["summary"], use_container_width=True)
    fig2 = px.bar(je_results["summary"], x="Test", y="Aşkarlanan_Yazı_Sayı",
                   color="Aşkarlanan_Yazı_Sayı", color_continuous_scale="Reds",
                   title="Test Növünə görə Aşkarlanan Yazı Sayı")
    st.plotly_chart(fig2, use_container_width=True)
    with st.expander("Bayraqlanmış yazıların detalları"):
        st.dataframe(je_results["combined"], use_container_width=True)

# ---- Tab 3: Ratios & variance ----
with tab3:
    ratios_df = calculate_ratios(tb)
    st.subheader("Əsas Maliyyə Əmsalları")
    st.dataframe(ratios_df, use_container_width=True)

    variance_df = analytical_variance_review(tb, threshold=variance_threshold)
    st.subheader(f"Hesab üzrə Varyasiya Analizi (hədd: {int(variance_threshold*100)}%)")
    flagged = variance_df[variance_df["qeyri_adi_varyasiya"]]
    st.metric("Qeyri-adi varyasiyalı hesab sayı", len(flagged))
    fig3 = px.bar(variance_df, x="account_name", y="dəyişiklik_faiz",
                   color="qeyri_adi_varyasiya", color_discrete_map={True: "#C00000", False: "#1F4E78"},
                   title="Hesab üzrə Dövrlər Arası Dəyişiklik (%)")
    st.plotly_chart(fig3, use_container_width=True)
    st.dataframe(variance_df, use_container_width=True)

# ---- Tab 4: Three-way match ----
with tab4:
    match_result = run_three_way_match(proc["po"], proc["invoice"], proc["payment"])
    status_counts = match_result["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Say"]
    fig4 = px.pie(status_counts, names="Status", values="Say", hole=0.4,
                   title="PO – Qaimə – Ödəniş Uyğunlaşdırma Statusu")
    st.plotly_chart(fig4, use_container_width=True)
    st.dataframe(match_result, use_container_width=True)

# ---- Tab 5: Sampling ----
with tab5:
    sample_size = recommended_sample_size(len(je), risk_level=risk_level)
    st.metric("Tövsiyə olunan seçmə həcmi", sample_size)
    sample_df = monetary_unit_sample(je, sample_size)
    fig5 = px.scatter(sample_df, x="date", y="amount", color="account_name",
                        title="Seçilmiş Əməliyyatlar (Pul Vahidi Seçməsi - MUS)")
    st.plotly_chart(fig5, use_container_width=True)
    st.dataframe(sample_df[["entry_id", "date", "account_name", "amount", "user"]],
                 use_container_width=True)

st.markdown("---")
st.caption("Bu dashboard sintetik məlumat üzərində qurulub və nümayiş məqsədi daşıyır.")
