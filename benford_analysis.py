"""
benford_analysis.py
--------------------
Benford Qanunu testi (ISA 240 - Fırıldaqçılığa görə maliyyə hesabatlarına
baxılmasında auditorun məsuliyyəti ilə bağlı analitik prosedur).

Təbii, manipulyasiya edilməmiş maliyyə məlumatlarında ilk rəqəmin "1" olma
ehtimalı ~30.1%, "9" olma ehtimalı isə cəmi ~4.6%-dir. Real datanın bu
paylanmadan kəskin fərqlənməsi, manipulyasiya və ya süni yaradılmış
yazıların (məs. limitə uyğunlaşdırılmış xərclər) əlaməti ola bilər.
"""

import numpy as np
import pandas as pd
from scipy import stats

# Benford Qanununa görə gözlənilən ilk rəqəm ehtimalları (1-9)
BENFORD_EXPECTED = {d: np.log10(1 + 1 / d) for d in range(1, 10)}


def _first_digit(x: float) -> int:
    x = abs(x)
    while x < 1 and x > 0:
        x *= 10
    return int(str(x).replace(".", "")[0])


def run_benford_test(amounts: pd.Series) -> dict:
    """Benford analizini icra edir və nəticələri lüğət kimi qaytarır."""
    amounts = amounts[amounts > 0]
    first_digits = amounts.apply(_first_digit)

    observed_counts = first_digits.value_counts().reindex(range(1, 10), fill_value=0)
    n = observed_counts.sum()
    observed_pct = observed_counts / n
    expected_pct = pd.Series(BENFORD_EXPECTED)
    expected_counts = expected_pct * n

    chi2_stat, p_value = stats.chisquare(observed_counts, expected_counts)

    # Meydan Fərqi (Mean Absolute Deviation) - qərarvermə üçün əlavə göstərici
    mad = (observed_pct - expected_pct).abs().mean()
    if mad < 0.006:
        mad_conclusion = "Yaxın uyğunluq (Close conformity)"
    elif mad < 0.012:
        mad_conclusion = "Qəbul edilə bilən uyğunluq (Acceptable conformity)"
    elif mad < 0.015:
        mad_conclusion = "Mümkün uyğunsuzluq (Marginally acceptable)"
    else:
        mad_conclusion = "Uyğunsuzluq - əlavə araşdırma tələb olunur (Nonconformity)"

    result_table = pd.DataFrame({
        "first_digit": range(1, 10),
        "observed_count": observed_counts.values,
        "observed_pct": (observed_pct * 100).round(2).values,
        "expected_pct": (expected_pct * 100).round(2).values,
        "difference_pct": ((observed_pct - expected_pct) * 100).round(2).values,
    })

    return {
        "table": result_table,
        "chi2_stat": round(chi2_stat, 3),
        "p_value": round(p_value, 5),
        "mad": round(mad, 5),
        "mad_conclusion": mad_conclusion,
        "significant_deviation": p_value < 0.05,
        "n_transactions": int(n),
    }


if __name__ == "__main__":
    from data_generator import generate_journal_entries
    je = generate_journal_entries()
    result = run_benford_test(je["amount"])
    print(result["table"])
    print(f"\nChi-square: {result['chi2_stat']}, p-value: {result['p_value']}")
    print(f"MAD: {result['mad']} -> {result['mad_conclusion']}")
