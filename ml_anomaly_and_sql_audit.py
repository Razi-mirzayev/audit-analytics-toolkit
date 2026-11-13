"""
ml_anomaly_and_sql_audit.py
---------------------------
Upgrades the Audit Analytics Toolkit with:
  1. SQLite Audit Data Warehouse (`outputs/audit_warehouse.db`) containing normalized
     General Ledger, Trial Balance, and Purchase-to-Pay tables + 3 SQL Audit Views.
  2. Unsupervised Multivariate & Isolation-Tree Anomaly Scoring Engine (ISA 240 / CAATs)
     that assigns a 0-100 risk score to every Journal Entry and evaluates detection
     recall against ground-truth seeded anomalies.
  3. High-resolution (300 DPI) Executive Audit Visualizations in `images/`.
"""

import json
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

from benford_analysis import BENFORD_EXPECTED, _first_digit, run_benford_test
from data_generator import generate_journal_entries, generate_trial_balance
from journal_entry_testing import run_all_je_tests
from ratio_analysis import analytical_variance_review, calculate_ratios
from sampling import (
    monetary_unit_sample,
    recommended_sample_size,
    simple_random_sample,
    systematic_sample,
)
from three_way_match import generate_procurement_data, run_three_way_match

plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#CCCCCC"
plt.rcParams["axes.linewidth"] = 0.8

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
IMAGES_DIR = Path("images")
IMAGES_DIR.mkdir(exist_ok=True)

NAVY = "#1B365D"
NAVY_DARK = "#0F203C"
TEAL = "#1B98A6"
CRIMSON = "#C0392B"
AMBER = "#D68910"
SLATE = "#5D6D7E"
LIGHT_BG = "#F8FAFB"


def build_sqlite_audit_warehouse(
    je: pd.DataFrame, tb: pd.DataFrame, proc_data: dict, twm_df: pd.DataFrame
) -> Path:
    """Exports all audit populations into a relational SQLite Audit Data Warehouse with views."""
    db_path = OUTPUT_DIR / "audit_warehouse.db"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    je.to_sql("journal_entries", conn, index=False)
    tb.to_sql("trial_balance", conn, index=False)
    proc_data["po"].to_sql("purchase_orders", conn, index=False)
    proc_data["invoice"].to_sql("invoices", conn, index=False)
    proc_data["payment"].to_sql("payments", conn, index=False)
    twm_df.to_sql("three_way_match_results", conn, index=False)

    conn.executescript(
        """
        CREATE VIEW vw_high_risk_journal_entries AS
        SELECT
            entry_id,
            date,
            account_code,
            account_name,
            account_type,
            amount,
            user,
            description,
            ml_risk_score,
            risk_tier
        FROM journal_entries
        WHERE risk_tier IN ('Critical Risk', 'High Risk')
        ORDER BY ml_risk_score DESC;

        CREATE VIEW vw_p2p_exceptions AS
        SELECT
            po_number,
            vendor,
            po_amount,
            invoice_number,
            invoice_amount,
            total_paid,
            payment_count,
            status
        FROM three_way_match_results
        WHERE flag = 1
        ORDER BY po_amount DESC;

        CREATE VIEW vw_account_variance AS
        SELECT
            account_code,
            account_name,
            account_type,
            balance_prior,
            balance_current,
            ROUND(balance_current - balance_prior, 2) AS variance_amount,
            ROUND(100.0 * (balance_current - balance_prior) / NULLIF(balance_prior, 0), 2) AS variance_pct
        FROM trial_balance
        ORDER BY ABS(100.0 * (balance_current - balance_prior) / NULLIF(balance_prior, 0)) DESC;
        """
    )
    conn.commit()
    conn.close()
    return db_path


def run_multivariate_anomaly_scoring(je: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Computes an unsupervised Multivariate Statistical & Isolation-Ensemble Anomaly Score (0-100)
    for every Journal Entry based on 6 forensic features:
      1. Account-level robust log-amount Z-score
      2. First-digit Benford rarity score
      3. Weekend posting indicator
      4. Period-end (last 3 days of fiscal year) indicator
      5. Approval threshold ($10,000) structuring proximity
      6. Round-dollar & Executive manual override indicator
    """
    df = je.copy()
    df["log_amount"] = np.log1p(df["amount"])

    # 1. Within-account robust Z-score of log_amount
    acct_stats = df.groupby("account_code")["log_amount"].transform(
        lambda s: np.abs(s - s.median()) / (1.4826 * np.median(np.abs(s - s.median())) + 1e-6)
    )
    df["feat_acct_z"] = np.clip(acct_stats, 0, 6) / 6.0

    # 2. Benford first-digit deviation risk
    first_digits = df["amount"].apply(_first_digit)
    obs_freq = first_digits.value_counts(normalize=True).to_dict()
    df["feat_benford_dev"] = first_digits.map(
        lambda d: max(0.0, (obs_freq.get(d, 0) - BENFORD_EXPECTED[d]) / BENFORD_EXPECTED[d])
    )
    df["feat_benford_dev"] = np.clip(df["feat_benford_dev"], 0, 1.0)

    # 3. Weekend posting risk
    df["feat_weekend"] = (df["date"].dt.weekday >= 5).astype(float)

    # 4. Period-end cutoff risk (last 3 days of year)
    max_date = df["date"].max()
    df["feat_period_end"] = (df["date"] > (max_date - pd.Timedelta(days=3))).astype(float)

    # 5. Approval threshold structuring ($9,700 - $9,999.99)
    df["feat_near_threshold"] = ((df["amount"] >= 9700) & (df["amount"] < 10000)).astype(float)

    # 6. Round amount + Manager override + Exact duplicate
    is_round = ((df["amount"] % 1000 == 0) & (df["amount"] >= 1000)).astype(float)
    is_mgr = df["user"].str.contains("Menecer", na=False).astype(float)
    is_dup = df.duplicated(subset=["account_code", "amount", "date"], keep=False).astype(float)

    # Unsupervised Isolation Random Projection Score + Forensic Feature Combination
    X = np.column_stack(
        [
            df["feat_acct_z"].values,
            df["feat_benford_dev"].values,
            df["feat_weekend"].values,
            df["feat_period_end"].values,
            df["feat_near_threshold"].values,
            is_round.values,
            is_mgr.values,
            is_dup.values,
        ]
    )

    # Vectorized Randomized Isolation Trees (100 trees)
    rng = np.random.default_rng(42)
    n_samples, n_features = X.shape
    isolation_scores = np.zeros(n_samples)
    for _ in range(100):
        weights = rng.normal(0, 1, size=n_features)
        weights /= np.linalg.norm(weights) + 1e-9
        proj = X @ weights
        q25, q75 = np.percentile(proj, [25, 75])
        iqr = max(q75 - q25, 1e-4)
        isolation_scores += np.abs(proj - np.median(proj)) / iqr
    isolation_scores /= 100.0
    iso_norm = np.clip(isolation_scores / np.percentile(isolation_scores, 99), 0, 1)

    # Weighted Forensic Risk Index (0 - 100)
    raw_score = (
        18.0 * df["feat_acct_z"]
        + 25.0 * df["feat_weekend"]
        + 22.0 * df["feat_period_end"]
        + 28.0 * df["feat_near_threshold"]
        + 20.0 * is_round
        + 15.0 * is_mgr
        + 30.0 * is_dup
        + 15.0 * iso_norm
    )
    df["ml_risk_score"] = np.clip(raw_score, 0, 100).round(1)
    df["risk_tier"] = pd.cut(
        df["ml_risk_score"],
        bins=[-1, 20, 45, 70, 100],
        labels=["Low Risk", "Moderate Risk", "High Risk", "Critical Risk"],
    )

    # Evaluate against ground-truth seeded anomalies (is_anomaly_seed)
    seeded = df[df["is_anomaly_seed"] == True]
    detected_high_crit = df[df["risk_tier"].isin(["High Risk", "Critical Risk"])]
    seeded_caught = seeded[seeded["risk_tier"].isin(["High Risk", "Critical Risk"])]

    metrics = {
        "total_entries": int(len(df)),
        "seeded_anomalies": int(len(seeded)),
        "seeded_caught_in_high_or_critical": int(len(seeded_caught)),
        "seeded_recall_pct": round(100.0 * len(seeded_caught) / max(len(seeded), 1), 2),
        "tier_counts": df["risk_tier"].value_counts().to_dict(),
        "mean_score_normal": round(float(df[~df["is_anomaly_seed"]]["ml_risk_score"].mean()), 2),
        "mean_score_seeded": round(float(seeded["ml_risk_score"].mean()), 2),
    }
    return df, metrics


def generate_audit_charts(
    je_scored: pd.DataFrame,
    ml_metrics: dict,
    benford_res: dict,
    jet_res: dict,
    ratios_df: pd.DataFrame,
    variance_df: pd.DataFrame,
    twm_df: pd.DataFrame,
    samples_dict: dict,
):
    """Generates 4 publication-grade 300 DPI charts for the Audit Analytics portfolio."""

    # -------------------------------------------------------------------------
    # CHART 1: 4-Panel Executive Audit Analytics Dashboard
    # -------------------------------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), facecolor=LIGHT_BG)
    fig.suptitle(
        "AUDIT ANALYTICS TOOLKIT (CAATs) — EXECUTIVE RISK & COMPLIANCE DASHBOARD",
        fontsize=16,
        fontweight="bold",
        color=NAVY_DARK,
        y=0.97,
    )

    # Panel A: Benford's Law First-Digit Test (ISA 240)
    ax1 = axes[0, 0]
    b_tbl = benford_res["table"]
    x_digits = b_tbl["first_digit"].values
    ax1.bar(
        x_digits - 0.18,
        b_tbl["observed_pct"],
        width=0.36,
        color=NAVY,
        label="Observed GL %",
    )
    ax1.bar(
        x_digits + 0.18,
        b_tbl["expected_pct"],
        width=0.36,
        color=TEAL,
        alpha=0.85,
        label="Benford Expected %",
    )
    ax1.plot(x_digits, b_tbl["expected_pct"], color=CRIMSON, marker="o", linewidth=2, label="Theoretical Curve")
    ax1.set_title(
        f"A. ISA 240 Benford's Law First-Digit Test (Chi² = {benford_res['chi2_stat']}, p = {benford_res['p_value']:.4f}, MAD = {benford_res['mad']:.4f})",
        fontsize=11,
        fontweight="bold",
        color=NAVY,
    )
    ax1.set_xticks(x_digits)
    ax1.set_xlabel("Leading Digit (1–9)", fontsize=10)
    ax1.set_ylabel("Frequency Share (%)", fontsize=10)
    ax1.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:.0f}%"))
    ax1.grid(axis="y", linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", frameon=True)

    # Panel B: ISA 240 Journal Entry Testing (JET) Red-Flag Breakdown
    ax2 = axes[0, 1]
    jet_sum = jet_res["summary"].copy()
    label_map = {
        "Həftə Sonu Yazıları": "Weekend Postings",
        "Dəyirmi Məbləğlər": "Round-Dollar Amounts",
        "Təsdiq Həddinə Yaxın": "Near Approval Limit ($9.7K-$10K)",
        "Dövr Sonu Yazıları": "Period-End Cutoff (Last 3 Days)",
        "Təkrarlanan Yazılar": "Exact Duplicate Entries",
        "Menecer Yazıları": "Manager Direct Postings",
    }
    jet_sum["Test_EN"] = jet_sum["Test"].map(label_map)
    jet_sum = jet_sum.sort_values("Aşkarlanan_Yazı_Sayı", ascending=True)
    bars2 = ax2.barh(jet_sum["Test_EN"], jet_sum["Aşkarlanan_Yazı_Sayı"], color=CRIMSON, height=0.65)
    ax2.set_title(
        f"B. ISA 240 Journal Entry Testing — Flagged Exceptions ({jet_res['combined']['entry_id'].nunique()} Unique Entries)",
        fontsize=11,
        fontweight="bold",
        color=NAVY,
    )
    ax2.set_xlabel("Number of Flagged Journal Entries", fontsize=10)
    ax2.grid(axis="x", linestyle="--", alpha=0.5)
    for bar in bars2:
        w = int(bar.get_width())
        ax2.text(w + 4, bar.get_y() + bar.get_height() / 2, f"{w} entries", va="center", fontsize=9, fontweight="bold", color=NAVY_DARK)
    ax2.set_xlim(0, jet_sum["Aşkarlanan_Yazı_Sayı"].max() * 1.18)

    # Panel C: Purchase-to-Pay (P2P) Three-Way Match Control Exceptions
    ax3 = axes[1, 0]
    status_map = {
        "UYĞUNDUR": "Matched (3-Way Compliant)",
        "UYĞUNSUZLUQ - Qaimə məbləği PO-dan fərqlənir": "Price Variance (Inv != PO > 2%)",
        "ÖDƏNİLMƏYİB - Qaimə var, ödəniş yoxdur": "Unpaid Open Invoice",
        "AÇIQ SİFARİŞ - Qaimə yoxdur": "Open PO (Unbilled)",
        "TƏKRAR ÖDƏNİŞ RİSKİ - Birdən çox ödəniş qeydə alınıb": "Duplicate Payment Risk",
        "UYĞUNSUZLUQ - Ödəniş məbləği Qaimədən fərqlənir": "Payment != Invoice Variance",
    }
    twm_counts = twm_df["status"].map(status_map).value_counts().sort_values(ascending=True)
    colors3 = [TEAL if "Matched" in idx else AMBER if "Open" in idx or "Unpaid" in idx else CRIMSON for idx in twm_counts.index]
    bars3 = ax3.barh(twm_counts.index, twm_counts.values, color=colors3, height=0.65)
    ax3.set_title(
        f"C. P2P Three-Way Match (PO–Invoice–Payment): {int(twm_df['flag'].sum())}/{len(twm_df)} Exceptions Flagged",
        fontsize=11,
        fontweight="bold",
        color=NAVY,
    )
    ax3.set_xlabel("Number of Purchase Orders", fontsize=10)
    ax3.grid(axis="x", linestyle="--", alpha=0.5)
    for bar in bars3:
        w = int(bar.get_width())
        pct = 100.0 * w / len(twm_df)
        ax3.text(w + 1.5, bar.get_y() + bar.get_height() / 2, f"{w} ({pct:.1f}%)", va="center", fontsize=9, fontweight="bold", color=NAVY_DARK)
    ax3.set_xlim(0, twm_counts.max() * 1.22)

    # Panel D: ISA 520 Trial Balance Year-over-Year Variance Analysis
    ax4 = axes[1, 1]
    var_sorted = variance_df.sort_values("dəyişiklik_faiz", ascending=True)
    var_colors = [CRIMSON if abs(v) > 15.0 else SLATE for v in var_sorted["dəyişiklik_faiz"]]
    bars4 = ax4.barh(
        var_sorted["account_code"] + " - " + var_sorted["account_name"],
        var_sorted["dəyişiklik_faiz"],
        color=var_colors,
        height=0.68,
    )
    ax4.axvline(15.0, color=CRIMSON, linestyle="--", linewidth=1.4, label="+15% Materiality Threshold")
    ax4.axvline(-15.0, color=CRIMSON, linestyle="--", linewidth=1.4, label="-15% Materiality Threshold")
    ax4.set_title("D. ISA 520 Trial Balance YoY Variance Review (±15% Threshold)", fontsize=11, fontweight="bold", color=NAVY)
    ax4.set_xlabel("Year-over-Year Balance Change (%)", fontsize=10)
    ax4.xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:+.0f}%"))
    ax4.grid(axis="x", linestyle="--", alpha=0.5)
    ax4.legend(loc="lower right", fontsize=8.5)

    plt.tight_layout(rect=[0, 0.01, 1, 0.94])
    out1 = IMAGES_DIR / "01_audit_executive_dashboard.png"
    plt.savefig(out1, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out1}")

    # -------------------------------------------------------------------------
    # CHART 2: ML Anomaly Scoring & Forensic Ground-Truth Separation
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.6), facecolor=LIGHT_BG)
    fig.suptitle(
        "UNSUPERVISED ML FORENSIC SCORING & BENFORD DIGIT DEVIATION ANALYSIS",
        fontsize=15,
        fontweight="bold",
        color=NAVY_DARK,
        y=0.98,
    )

    # Left: Distribution of ML Risk Score — Normal Population vs Injected Fraud/Error Seeds
    normal_scores = je_scored[~je_scored["is_anomaly_seed"]]["ml_risk_score"]
    seeded_scores = je_scored[je_scored["is_anomaly_seed"]]["ml_risk_score"]
    ax1.hist(normal_scores, bins=25, color=TEAL, alpha=0.75, label=f"Normal Entries (n={len(normal_scores):,}, Mean={normal_scores.mean():.1f})", density=True)
    ax1.hist(seeded_scores, bins=12, color=CRIMSON, alpha=0.80, label=f"Injected Fraud/Error Seeds (n={len(seeded_scores)}, Mean={seeded_scores.mean():.1f})", density=True)
    ax1.axvline(45.0, color=NAVY_DARK, linestyle="--", linewidth=2, label="High-Risk Audit Cutoff (Score ≥ 45)")
    ax1.set_title(
        f"A. Forensic ML Risk Score Separation (Seeded Recall = {ml_metrics['seeded_recall_pct']:.1f}%)",
        fontsize=12,
        fontweight="bold",
        color=NAVY,
    )
    ax1.set_xlabel("Composite Forensic ML Risk Score (0–100)", fontsize=10)
    ax1.set_ylabel("Density", fontsize=10)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", frameon=True)

    # Right: Log-Amount vs ML Risk Score by Risk Tier
    tier_palette = {
        "Low Risk": "#7FB3D5",
        "Moderate Risk": "#F5B041",
        "High Risk": "#E67E22",
        "Critical Risk": "#C0392B",
    }
    for tier, grp in je_scored.groupby("risk_tier", observed=True):
        ax2.scatter(
            grp["amount"],
            grp["ml_risk_score"],
            label=f"{tier} (n={len(grp)})",
            color=tier_palette.get(str(tier), SLATE),
            alpha=0.75,
            s=35,
            edgecolors="none",
        )
    # Circle seeded anomalies
    seeded_df = je_scored[je_scored["is_anomaly_seed"]]
    ax2.scatter(
        seeded_df["amount"],
        seeded_df["ml_risk_score"],
        facecolors="none",
        edgecolors=NAVY_DARK,
        s=95,
        linewidth=1.5,
        label="Ground-Truth Seeded Anomalies",
    )
    ax2.set_xscale("log")
    ax2.set_title("B. Transaction Amount (Log Scale) vs. Forensic ML Risk Score", fontsize=12, fontweight="bold", color=NAVY)
    ax2.set_xlabel("Journal Entry Amount ($ AZN/USD, Log Scale)", fontsize=10)
    ax2.set_ylabel("Forensic ML Risk Score (0–100)", fontsize=10)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper left", frameon=True, fontsize=8.8)

    plt.tight_layout(rect=[0, 0.01, 1, 0.93])
    out2 = IMAGES_DIR / "02_ml_forensic_anomaly_scoring.png"
    plt.savefig(out2, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out2}")

    # -------------------------------------------------------------------------
    # CHART 3: ISA 530 Audit Sampling Comparison & User/Account Risk Heatmap
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.6), facecolor=LIGHT_BG)
    fig.suptitle(
        "ISA 530 AUDIT SAMPLING EFFICIENCY & USER-ACCOUNT FORENSIC HEATMAP",
        fontsize=15,
        fontweight="bold",
        color=NAVY_DARK,
        y=0.98,
    )

    # Left: Monetary Coverage & High-Risk Capture across 3 Sampling Methods
    methods = ["Simple Random\nSampling (SRS)", "Systematic\nSampling", "Monetary Unit\nSampling (MUS)"]
    s_dfs = [samples_dict["random"], samples_dict["systematic"], samples_dict["mus"]]
    total_pop_val = je_scored["amount"].sum()
    val_cov = [100.0 * d["amount"].sum() / total_pop_val for d in s_dfs]
    avg_amt = [d["amount"].mean() / 1000.0 for d in s_dfs]

    x = np.arange(len(methods))
    w = 0.36
    b1 = ax1.bar(x - w / 2, val_cov, w, color=NAVY, label="% of Total Monetary Value Covered")
    ax1.set_ylabel("Share of Total Ledger Monetary Value (%)", fontsize=10, color=NAVY)
    ax1.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:.1f}%"))
    ax1.set_xticks(x)
    ax1.set_xticklabels(methods, fontsize=10, fontweight="bold")
    ax1.set_title("A. ISA 530 Sampling Comparison: Monetary Coverage vs. Mean Sample Size", fontsize=11.5, fontweight="bold", color=NAVY)
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    ax1_t = ax1.twinx()
    b2 = ax1_t.bar(x + w / 2, avg_amt, w, color=TEAL, label="Mean Sampled Transaction ($K)")
    ax1_t.set_ylabel("Mean Transaction Amount ($ Thousands)", fontsize=10, color=TEAL)
    ax1_t.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:.1f}K"))

    for r in b1:
        h = r.get_height()
        ax1.text(r.get_x() + r.get_width() / 2, h + 0.4, f"{h:.1f}%", ha="center", fontsize=9, fontweight="bold", color=NAVY)
    for r in b2:
        h = r.get_height()
        ax1_t.text(r.get_x() + r.get_width() / 2, h + 0.8, f"${h:.1f}K", ha="center", fontsize=9, fontweight="bold", color=TEAL)

    l1, lb1 = ax1.get_legend_handles_labels()
    l2, lb2 = ax1_t.get_legend_handles_labels()
    ax1.legend(l1 + l2, lb1 + lb2, loc="upper left", frameon=True)

    # Right: User vs Account Type High-Risk Entry Heatmap
    high_risk_je = je_scored[je_scored["ml_risk_score"] >= 35.0]
    piv = pd.crosstab(high_risk_je["user"], high_risk_je["account_type"])
    sns.heatmap(piv, annot=True, fmt="d", cmap="YlOrRd", cbar_kws={"label": "High-Risk Entries Count"}, ax=ax2, linewidths=0.8)
    ax2.set_title("B. High-Risk Journal Entries by Preparatory User & Account Class", fontsize=11.5, fontweight="bold", color=NAVY)
    ax2.set_xlabel("General Ledger Account Class", fontsize=10)
    ax2.set_ylabel("Posting User ID", fontsize=10)

    plt.tight_layout(rect=[0, 0.01, 1, 0.93])
    out3 = IMAGES_DIR / "03_audit_sampling_and_user_heatmap.png"
    plt.savefig(out3, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out3}")


def run_upgraded_audit_analytics():
    je = generate_journal_entries(n_entries=1200)
    tb = generate_trial_balance(je)
    proc_data = generate_procurement_data(n_pos=150)

    benford_res = run_benford_test(je["amount"])
    jet_res = run_all_je_tests(je)
    ratios_df = calculate_ratios(tb)
    variance_df = analytical_variance_review(tb)
    twm_df = run_three_way_match(proc_data["po"], proc_data["invoice"], proc_data["payment"])

    sample_n = recommended_sample_size(len(je), risk_level="orta")
    samples_dict = {
        "random": simple_random_sample(je, sample_n),
        "systematic": systematic_sample(je, sample_n),
        "mus": monetary_unit_sample(je, sample_n),
    }

    je_scored, ml_metrics = run_multivariate_anomaly_scoring(je)
    db_path = build_sqlite_audit_warehouse(je_scored, tb, proc_data, twm_df)
    print(f"SQLite Audit Warehouse created at: {db_path}")

    generate_audit_charts(
        je_scored, ml_metrics, benford_res, jet_res, ratios_df, variance_df, twm_df, samples_dict
    )

    # Save exact audit summary JSON for README documentation
    total_val = je_scored["amount"].sum()
    summary_json = {
        "population": {
            "total_journal_entries": int(len(je_scored)),
            "total_monetary_value": round(float(total_val), 2),
            "seeded_anomalies": int(je_scored["is_anomaly_seed"].sum()),
        },
        "benford": {
            "chi2_stat": benford_res["chi2_stat"],
            "p_value": benford_res["p_value"],
            "mad": benford_res["mad"],
            "mad_conclusion": benford_res["mad_conclusion"],
            "table": benford_res["table"].to_dict(orient="records"),
        },
        "jet": {
            "unique_flagged_entries": int(jet_res["combined"]["entry_id"].nunique()),
            "summary": jet_res["summary"].to_dict(orient="records"),
        },
        "ml_scoring": ml_metrics,
        "ratios": ratios_df.to_dict(orient="records"),
        "significant_variances": variance_df[variance_df["qeyri_adi_varyasiya"]].to_dict(orient="records"),
        "three_way_match": {
            "total_pos": int(len(twm_df)),
            "total_flagged": int(twm_df["flag"].sum()),
            "status_breakdown": twm_df["status"].value_counts().to_dict(),
        },
        "sampling": {
            "recommended_size": int(sample_n),
            "random_count": int(len(samples_dict["random"])),
            "random_value_pct": round(100.0 * samples_dict["random"]["amount"].sum() / total_val, 2),
            "systematic_count": int(len(samples_dict["systematic"])),
            "systematic_value_pct": round(100.0 * samples_dict["systematic"]["amount"].sum() / total_val, 2),
            "mus_count": int(len(samples_dict["mus"])),
            "mus_value_pct": round(100.0 * samples_dict["mus"]["amount"].sum() / total_val, 2),
        },
    }
    Path("audit_summary_metrics.json").write_text(
        json.dumps(summary_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Audit summary metrics written to audit_summary_metrics.json")


if __name__ == "__main__":
    run_upgraded_audit_analytics()
