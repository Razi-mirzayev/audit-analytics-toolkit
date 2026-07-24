"""
journal_entry_testing.py
-------------------------
Jurnal Yazılarının Testi (Journal Entry Testing - JET), ISA 240-a əsasən
audit zamanı ən çox istifadə olunan fırıldaqçılıq riski proseduralarından
biridir. Bu modul aşağıdakı "qırmızı bayraqları" (red flags) avtomatik aşkar edir:

  1. Həftə sonu / qeyri-iş vaxtı yazıları
  2. Dəyirmi məbləğli yazılar (round-dollar amounts)
  3. Təsdiq həddinə yaxın (bir az aşağı) yazılar - limitdən yayınma
  4. Dövr sonuna yaxın (son 3 gün) qeydə alınan yazılar
  5. Tam identik təkrarlanan yazılar (dublikat risk)
  6. Menecer səviyyəsində qeyri-adi tezlikdə yazı aparan istifadəçilər
"""

import pandas as pd


APPROVAL_THRESHOLD = 10000.0
THRESHOLD_BUFFER = 0.03  # həddin 3%-ə qədər aşağısı "şübhəli" sayılır


def flag_weekend_entries(df: pd.DataFrame) -> pd.DataFrame:
    flagged = df[df["date"].dt.weekday >= 5].copy()
    flagged["flag_reason"] = "Həftə sonu tarixli yazı"
    return flagged


def flag_round_amounts(df: pd.DataFrame, threshold: float = 1000.0) -> pd.DataFrame:
    flagged = df[(df["amount"] % threshold == 0) & (df["amount"] >= threshold)].copy()
    flagged["flag_reason"] = "Dəyirmi məbləğ (round amount)"
    return flagged


def flag_near_threshold(df: pd.DataFrame, threshold: float = APPROVAL_THRESHOLD,
                         buffer: float = THRESHOLD_BUFFER) -> pd.DataFrame:
    lower_bound = threshold * (1 - buffer)
    flagged = df[(df["amount"] >= lower_bound) & (df["amount"] < threshold)].copy()
    flagged["flag_reason"] = f"Təsdiq həddinə ({threshold:,.0f}) yaxın - yayınma riski"
    return flagged


def flag_period_end(df: pd.DataFrame, days: int = 3) -> pd.DataFrame:
    period_end = df["date"].max()
    cutoff = period_end - pd.Timedelta(days=days)
    flagged = df[df["date"] > cutoff].copy()
    flagged["flag_reason"] = "Dövr sonuna yaxın qeydiyyat"
    return flagged


def flag_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    dup_mask = df.duplicated(subset=["account_code", "amount", "date"], keep=False)
    flagged = df[dup_mask].copy()
    flagged["flag_reason"] = "Tam identik təkrarlanan yazı"
    return flagged


def flag_manager_entries(df: pd.DataFrame, manager_keyword: str = "Menecer") -> pd.DataFrame:
    flagged = df[df["user"].str.contains(manager_keyword, na=False)].copy()
    flagged["flag_reason"] = "Menecer səviyyəsində birbaşa yazı"
    return flagged


def run_all_je_tests(df: pd.DataFrame) -> dict:
    """Bütün JET testlərini icra edir və hər biri üçün nəticə DataFrame-i qaytarır."""
    tests = {
        "Həftə Sonu Yazıları": flag_weekend_entries(df),
        "Dəyirmi Məbləğlər": flag_round_amounts(df),
        "Təsdiq Həddinə Yaxın": flag_near_threshold(df),
        "Dövr Sonu Yazıları": flag_period_end(df),
        "Təkrarlanan Yazılar": flag_duplicates(df),
        "Menecer Yazıları": flag_manager_entries(df),
    }

    all_flags = pd.concat(tests.values(), ignore_index=True) if any(len(v) for v in tests.values()) else pd.DataFrame()
    summary = pd.DataFrame({
        "Test": list(tests.keys()),
        "Aşkarlanan_Yazı_Sayı": [len(v) for v in tests.values()],
    })

    return {"individual": tests, "combined": all_flags, "summary": summary}


if __name__ == "__main__":
    from data_generator import generate_journal_entries
    je = generate_journal_entries()
    results = run_all_je_tests(je)
    print(results["summary"].to_string(index=False))
    print(f"\nÜmumi unikal bayraqlı yazı sayı: {results['combined']['entry_id'].nunique()}")
