"""
three_way_match.py
--------------------
Üç-tərəfli Uyğunlaşdırma (Three-Way Match). Bu, xərclər/alışlar dövrü (Purchase-
to-Pay) auditində ən çox istifadə olunan nəzarət testidir: Sifariş (PO) - Qaimə
(Invoice) - Ödəniş (Payment) sənədlərinin bir-birinə uyğun olub-olmadığını yoxlayır.

Uyğunsuzluqlar aşağıdakı riskləri göstərə bilər:
  - Sifarişsiz alış (icazəsiz xərc)
  - Qaimə məbləği ilə ödəniş məbləği arasında fərq (artıq/az ödəniş)
  - Eyni qaiməyə görə təkrar ödəniş (dublikat ödəniş)
  - Ödənişi olmayan açıq qaimələr (öhdəliklərin tam əks olunmaması riski)
"""

import numpy as np
import pandas as pd
from datetime import timedelta

RNG = np.random.default_rng(11)
TOLERANCE = 0.02  # 2%-ə qədər fərq "qəbul edilə bilən" sayılır (məs. valyuta/yuvarlaqlaşdırma)

VENDORS = ["ABC MMC", "Baku Trade Ltd", "Caspian Supplies", "Nur Logistics", "Zirvə Servis"]


def generate_procurement_data(n_pos: int = 150, period_start=None, period_end=None) -> dict:
    """Sintetik PO / Invoice / Payment məlumatlarını yaradır (bəzi uyğunsuzluqlarla)."""
    from datetime import datetime
    period_start = period_start or datetime(2025, 1, 1)
    period_end = period_end or datetime(2025, 12, 31)

    pos, invoices, payments = [], [], []

    for i in range(1, n_pos + 1):
        po_number = f"PO-{1000 + i}"
        vendor = RNG.choice(VENDORS)
        po_amount = round(float(RNG.uniform(500, 45000)), 2)
        po_date = period_start + timedelta(days=int(RNG.integers(0, (period_end - period_start).days)))
        pos.append({"po_number": po_number, "vendor": vendor, "po_amount": po_amount, "po_date": po_date})

        # ~90% PO-lar üçün qaimə mövcuddur (10% - açıq/tamamlanmamış sifariş)
        if RNG.random() < 0.90:
            invoice_amount = po_amount
            # ~12% hallarda qaimə məbləği PO-dan fərqlənir
            if RNG.random() < 0.12:
                invoice_amount = round(po_amount * float(RNG.uniform(1.03, 1.20)), 2)
            inv_date = po_date + timedelta(days=int(RNG.integers(1, 20)))
            invoices.append({
                "po_number": po_number, "invoice_number": f"INV-{2000 + i}",
                "vendor": vendor, "invoice_amount": invoice_amount, "invoice_date": inv_date,
            })

            # ~88% qaimələr ödənilib
            if RNG.random() < 0.88:
                payment_amount = invoice_amount
                pay_date = inv_date + timedelta(days=int(RNG.integers(1, 30)))
                payments.append({
                    "po_number": po_number, "invoice_number": f"INV-{2000 + i}",
                    "payment_amount": payment_amount, "payment_date": pay_date,
                })
                # ~3% hallarda təkrar (dublikat) ödəniş
                if RNG.random() < 0.03:
                    payments.append({
                        "po_number": po_number, "invoice_number": f"INV-{2000 + i}",
                        "payment_amount": payment_amount,
                        "payment_date": pay_date + timedelta(days=int(RNG.integers(1, 10))),
                    })

    return {
        "po": pd.DataFrame(pos),
        "invoice": pd.DataFrame(invoices),
        "payment": pd.DataFrame(payments),
    }


def run_three_way_match(po_df: pd.DataFrame, invoice_df: pd.DataFrame, payment_df: pd.DataFrame,
                         tolerance: float = TOLERANCE) -> pd.DataFrame:
    """PO, Invoice və Payment məlumatlarını po_number üzrə birləşdirir və uyğunsuzluqları bayraqlayır."""
    payment_agg = payment_df.groupby("po_number").agg(
        total_paid=("payment_amount", "sum"),
        payment_count=("payment_amount", "count"),
    ).reset_index()

    merged = po_df.merge(invoice_df, on=["po_number", "vendor"], how="left") \
                  .merge(payment_agg, on="po_number", how="left")

    merged["total_paid"] = merged["total_paid"].fillna(0.0)
    merged["payment_count"] = merged["payment_count"].fillna(0).astype(int)

    def determine_status(row):
        if pd.isna(row.get("invoice_amount")):
            return "AÇIQ SİFARİŞ - Qaimə yoxdur"
        if row["payment_count"] == 0:
            return "ÖDƏNİLMƏYİB - Qaimə var, ödəniş yoxdur"
        if row["payment_count"] > 1:
            return "TƏKRAR ÖDƏNİŞ RİSKİ - Birdən çox ödəniş qeydə alınıb"

        invoice_amt = row["invoice_amount"]
        po_amt = row["po_amount"]
        paid_amt = row["total_paid"]

        if abs(invoice_amt - po_amt) / po_amt > tolerance:
            return "UYĞUNSUZLUQ - Qaimə məbləği PO-dan fərqlənir"
        if abs(paid_amt - invoice_amt) / invoice_amt > tolerance:
            return "UYĞUNSUZLUQ - Ödəniş məbləği Qaimədən fərqlənir"
        return "UYĞUNDUR"

    merged["status"] = merged.apply(determine_status, axis=1)
    merged["flag"] = merged["status"] != "UYĞUNDUR"

    cols = ["po_number", "vendor", "po_amount", "invoice_number", "invoice_amount",
            "total_paid", "payment_count", "status", "flag"]
    return merged[cols].sort_values("flag", ascending=False)


if __name__ == "__main__":
    data = generate_procurement_data()
    result = run_three_way_match(data["po"], data["invoice"], data["payment"])
    print(result["status"].value_counts())
    print(f"\nÜmumi bayraqlanmış sətir: {int(result['flag'].sum())} / {len(result)}")
