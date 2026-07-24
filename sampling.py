"""
sampling.py
------------
Audit Seçməsi (ISA 530 - Audit Sampling). Auditor bütün populyasiyanı yox,
onun bir hissəsini (seçməni) test edərək populyasiya haqqında nəticə çıxarır.

Bu modul 3 əsas seçmə metodunu təqdim edir:
  1. Sadə Təsadüfi Seçmə (Simple Random Sampling)
  2. Sistematik Seçmə (Systematic Sampling)
  3. Pul Vahidi Seçməsi (Monetary Unit Sampling / MUS) - məbləği böyük
     əməliyyatların seçilmə ehtimalını artırır (auditda ən çox istifadə olunan üsul)
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(2024)


def simple_random_sample(df: pd.DataFrame, sample_size: int) -> pd.DataFrame:
    sample_size = min(sample_size, len(df))
    idx = RNG.choice(df.index, size=sample_size, replace=False)
    return df.loc[idx].assign(sampling_method="Sadə Təsadüfi").sort_index()


def systematic_sample(df: pd.DataFrame, sample_size: int) -> pd.DataFrame:
    n = len(df)
    sample_size = min(sample_size, n)
    interval = n // sample_size
    start = RNG.integers(0, interval)
    positions = [start + i * interval for i in range(sample_size) if start + i * interval < n]
    return df.iloc[positions].assign(sampling_method="Sistematik")


def monetary_unit_sample(df: pd.DataFrame, sample_size: int, amount_col: str = "amount") -> pd.DataFrame:
    """
    MUS: hər manat (pul vahidi) populyasiyada bir 'element' sayılır, ona görə
    böyük məbləğli əməliyyatların seçilmə ehtimalı daha yüksəkdir. Bu, auditda
    maddi səhvlərin aşkarlanma ehtimalını artıran ən effektiv üsullardan biridir.
    """
    total_value = df[amount_col].sum()
    sample_size = min(sample_size, len(df))
    interval = total_value / sample_size

    df_sorted = df.sort_values(amount_col, ascending=False).reset_index(drop=True)
    cumulative = df_sorted[amount_col].cumsum()

    start_point = RNG.uniform(0, interval)
    selection_points = [start_point + i * interval for i in range(sample_size)]

    selected_indices = []
    for point in selection_points:
        matches = df_sorted[cumulative >= point]
        if not matches.empty:
            selected_indices.append(matches.index[0])

    selected_indices = sorted(set(selected_indices))
    result = df_sorted.loc[selected_indices].assign(sampling_method="Pul Vahidi Seçməsi (MUS)")
    return result


def recommended_sample_size(population_size: int, risk_level: str = "orta") -> int:
    """
    Sadələşdirilmiş seçmə həcmi kalkulyatoru (illüstrativ məqsədlə).
    Real audit təcrübəsində seçmə həcmi qəbul edilə bilən risk səviyyəsi,
    əhəmiyyətlilik dərəcəsi (materiality) və gözlənilən səhv həddinə görə təyin olunur.
    """
    risk_factors = {"aşağı": 0.02, "orta": 0.05, "yüksək": 0.10}
    factor = risk_factors.get(risk_level, 0.05)
    size = int(np.ceil(population_size * factor))
    return max(15, min(size, 60))  # praktik minimum/maksimum həddlər


if __name__ == "__main__":
    from data_generator import generate_journal_entries
    je = generate_journal_entries()
    size = recommended_sample_size(len(je), risk_level="orta")
    print(f"Tövsiyə olunan seçmə həcmi: {size}")
    print("\n--- MUS Nümunəsi (ilk 5) ---")
    print(monetary_unit_sample(je, size)[["entry_id", "account_name", "amount"]].head())
