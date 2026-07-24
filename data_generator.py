"""
data_generator.py
------------------
Sintetik (uydurma) Baş Kitab (General Ledger) yazıları və Balans (Trial Balance)
məlumatları yaradır. Real audit müştərisinin datasını simulyasiya edir və
qəsdən bəzi "anomaliyalar" (fırıldaqçılıq/səhv riski daşıyan yazılar) əlavə edir ki,
sonrakı analiz modulları bunları aşkar edə bilsin.

Bu, real audit layihələrində məlumatın necə strukturlaşdığını (entry_id, tarix,
hesab, debet/kredit, istifadəçi, təsvir) əks etdirir.
"""

import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

ACCOUNTS = [
    ("1000", "Kassa və Bank", "Asset"),
    ("1100", "Debitor Borclar", "Asset"),
    ("1200", "Mal-material Ehtiyatları", "Asset"),
    ("1500", "Əsas Vəsaitlər", "Asset"),
    ("2000", "Kreditor Borclar", "Liability"),
    ("2100", "Qısamüddətli Kreditlər", "Liability"),
    ("2200", "Uzunmüddətli Öhdəliklər", "Liability"),
    ("3000", "Nizamnamə Kapitalı", "Equity"),
    ("3100", "Bölüşdürülməmiş Mənfəət", "Equity"),
    ("4000", "Satışdan Gəlir", "Revenue"),
    ("5000", "Satışın Maya Dəyəri", "Expense"),
    ("5100", "İnzibati Xərclər", "Expense"),
    ("5200", "Kommersiya Xərcləri", "Expense"),
    ("5300", "Maliyyə Xərcləri", "Expense"),
]

USERS = ["A.Məmmədov", "N.Əliyeva", "R.Hüseynov", "S.Qasımova", "T.Rəhimov (Menecer)"]

PERIOD_START = datetime(2025, 1, 1)
PERIOD_END = datetime(2025, 12, 31)


def _random_date(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def generate_journal_entries(n_entries: int = 1200) -> pd.DataFrame:
    """Sintetik jurnal yazıları yaradır, daxilində qəsdən 'qırmızı bayraq' yazıları olur."""
    rows = []
    entry_id = 100000

    for _ in range(n_entries):
        entry_id += 1
        acc_code, acc_name, acc_type = random.choice(ACCOUNTS)
        date = _random_date(PERIOD_START, PERIOD_END)
        user = random.choice(USERS)

        # Benford qanununa uyğun "təbii" məbləğ generasiyası (log-normal paylanma)
        amount = round(np.random.lognormal(mean=6.5, sigma=1.8), 2)
        amount = max(15.0, min(amount, 250000.0))

        is_debit = acc_type in ("Asset", "Expense")
        rows.append({
            "entry_id": entry_id,
            "date": date,
            "account_code": acc_code,
            "account_name": acc_name,
            "account_type": acc_type,
            "debit": amount if is_debit else 0.0,
            "credit": 0.0 if is_debit else amount,
            "amount": amount,
            "user": user,
            "description": f"{acc_name} üzrə əməliyyat #{entry_id}",
            "is_anomaly_seed": False,
        })

    df = pd.DataFrame(rows)

    # ---- Qəsdən əlavə olunan risk yazıları (auditor tərəfindən tapılmalı) ----
    anomalies = []

    # 1) Dəyirmi rəqəmli, dövr sonuna yaxın böyük yazılar (mənfəətin manipulyasiyası riski)
    for i in range(6):
        entry_id += 1
        d = PERIOD_END - timedelta(days=random.randint(0, 2))
        anomalies.append({
            "entry_id": entry_id, "date": d, "account_code": "4000",
            "account_name": "Satışdan Gəlir", "account_type": "Revenue",
            "debit": 0.0, "credit": round(random.choice([50000, 75000, 100000, 120000]), 2),
            "amount": round(random.choice([50000, 75000, 100000, 120000]), 2),
            "user": "T.Rəhimov (Menecer)",
            "description": "İlin sonu düzəliş yazısı", "is_anomaly_seed": True,
        })

    # 2) Həftə sonu (şənbə/bazar) tarixli yazılar
    for i in range(8):
        entry_id += 1
        d = _random_date(PERIOD_START, PERIOD_END)
        while d.weekday() < 5:
            d += timedelta(days=1)
        acc_code, acc_name, acc_type = random.choice(ACCOUNTS)
        amt = round(random.uniform(2000, 30000), 2)
        anomalies.append({
            "entry_id": entry_id, "date": d, "account_code": acc_code,
            "account_name": acc_name, "account_type": acc_type,
            "debit": amt, "credit": 0.0, "amount": amt,
            "user": random.choice(USERS),
            "description": "Həftə sonu qeydiyyatı", "is_anomaly_seed": True,
        })

    # 3) Təsdiq həddindən (10,000) bir az aşağı olan yazılar (limitdən yayınma riski)
    for i in range(7):
        entry_id += 1
        d = _random_date(PERIOD_START, PERIOD_END)
        amt = round(random.uniform(9700, 9999), 2)
        anomalies.append({
            "entry_id": entry_id, "date": d, "account_code": "5100",
            "account_name": "İnzibati Xərclər", "account_type": "Expense",
            "debit": amt, "credit": 0.0, "amount": amt,
            "user": random.choice(USERS),
            "description": "Xərc ödənişi", "is_anomaly_seed": True,
        })

    # 4) Tam identik təkrarlanan yazılar (ikiqat mühasibatlaşdırma riski)
    dup_amt = 14850.00
    dup_date = _random_date(PERIOD_START, PERIOD_END)
    for i in range(2):
        entry_id += 1
        anomalies.append({
            "entry_id": entry_id, "date": dup_date, "account_code": "5200",
            "account_name": "Kommersiya Xərcləri", "account_type": "Expense",
            "debit": dup_amt, "credit": 0.0, "amount": dup_amt,
            "user": "N.Əliyeva",
            "description": "Reklam xidməti ödənişi", "is_anomaly_seed": True,
        })

    df = pd.concat([df, pd.DataFrame(anomalies)], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def generate_trial_balance(je_df: pd.DataFrame) -> pd.DataFrame:
    """Jurnal yazılarından cari dövr üçün balans yaradır, əvvəlki dövrü də simulyasiya edir."""
    current = je_df.groupby(["account_code", "account_name", "account_type"]).agg(
        debit=("debit", "sum"), credit=("credit", "sum")
    ).reset_index()
    current["balance_current"] = current["debit"] - current["credit"]
    current["balance_current"] = current.apply(
        lambda r: abs(r["balance_current"]) if r["account_type"] in ("Liability", "Equity", "Revenue")
        else r["balance_current"], axis=1
    )

    # Əvvəlki dövr üçün ağlabatan (±5%-25%) fərqlə balans simulyasiyası
    rng = np.random.default_rng(7)
    variance = rng.uniform(-0.25, 0.15, size=len(current))
    current["balance_prior"] = (current["balance_current"] / (1 + variance)).round(2)

    return current[["account_code", "account_name", "account_type", "balance_prior", "balance_current"]]


if __name__ == "__main__":
    je = generate_journal_entries()
    tb = generate_trial_balance(je)
    je.to_csv("sample_journal_entries.csv", index=False)
    tb.to_csv("sample_trial_balance.csv", index=False)
    print(f"{len(je)} jurnal yazısı və {len(tb)} balans sətri yaradıldı.")
