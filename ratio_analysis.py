"""
ratio_analysis.py
------------------
Analitik Prosedurlar (ISA 520 - Analytical Procedures). Auditor maliyyə
məlumatları arasındakı əlaqələri qiymətləndirərək, gözlənilməz dəyişiklikləri
("qeyri-adi varyasiyaları") aşkarlayır və bunları əlavə araşdırma üçün
qeyd edir.

Bu modul balansdan (trial balance) əsas maliyyə əmsallarını hesablayır və
dövrlər arası (current vs prior) faiz dəyişikliyini analiz edir.
"""

import pandas as pd

VARIANCE_THRESHOLD = 0.15  # 15%-dən çox dəyişiklik "qeyri-adi" sayılır və araşdırılmalıdır


def _get_balance(tb: pd.DataFrame, account_type: str, period: str) -> float:
    return tb.loc[tb["account_type"] == account_type, period].sum()


def calculate_ratios(tb: pd.DataFrame) -> pd.DataFrame:
    """Balansdan likvidlik, mənfəətlilik və leverage əmsallarını hesablayır."""
    rows = []

    for period in ["balance_prior", "balance_current"]:
        assets = _get_balance(tb, "Asset", period)
        liabilities = _get_balance(tb, "Liability", period)
        equity = _get_balance(tb, "Equity", period)
        revenue = _get_balance(tb, "Revenue", period)
        expenses = _get_balance(tb, "Expense", period)
        net_income = revenue - expenses

        cash_like = tb.loc[tb["account_code"].isin(["1000", "1100"]), period].sum()

        rows.append({
            "Dövr": "Əvvəlki" if period == "balance_prior" else "Cari",
            "Aktivlərin_Cəmi": round(assets, 2),
            "Öhdəliklərin_Cəmi": round(liabilities, 2),
            "Kapital": round(equity, 2),
            "Gəlir": round(revenue, 2),
            "Xalis_Mənfəət": round(net_income, 2),
            "Cari_Likvidlik_Əmsalı": round(cash_like / liabilities, 2) if liabilities else None,
            "Maliyyə_Asılılığı (Debt/Assets)": round(liabilities / assets, 3) if assets else None,
            "Debt_to_Equity": round(liabilities / equity, 3) if equity else None,
            "Xalis_Mənfəət_Marjı (%)": round((net_income / revenue) * 100, 2) if revenue else None,
            "ROA (%)": round((net_income / assets) * 100, 2) if assets else None,
            "ROE (%)": round((net_income / equity) * 100, 2) if equity else None,
        })

    return pd.DataFrame(rows)


def analytical_variance_review(tb: pd.DataFrame, threshold: float = VARIANCE_THRESHOLD) -> pd.DataFrame:
    """Hər bir hesab üzrə dövrlər arası faiz dəyişikliyini hesablayır və həddi keçənləri bayraqlayır."""
    tb = tb.copy()
    tb["dəyişiklik"] = tb["balance_current"] - tb["balance_prior"]
    tb["dəyişiklik_faiz"] = tb.apply(
        lambda r: (r["dəyişiklik"] / r["balance_prior"]) if r["balance_prior"] != 0 else None, axis=1
    )
    tb["qeyri_adi_varyasiya"] = tb["dəyişiklik_faiz"].abs() > threshold

    result = tb[[
        "account_code", "account_name", "account_type",
        "balance_prior", "balance_current", "dəyişiklik", "dəyişiklik_faiz", "qeyri_adi_varyasiya"
    ]].copy()
    result["dəyişiklik_faiz"] = (result["dəyişiklik_faiz"] * 100).round(2)
    return result.sort_values("qeyri_adi_varyasiya", ascending=False)


if __name__ == "__main__":
    from data_generator import generate_journal_entries, generate_trial_balance
    je = generate_journal_entries()
    tb = generate_trial_balance(je)
    print(calculate_ratios(tb).to_string(index=False))
    print("\n--- Qeyri-adi Varyasiyalar ---")
    var = analytical_variance_review(tb)
    print(var[var["qeyri_adi_varyasiya"]].to_string(index=False))
