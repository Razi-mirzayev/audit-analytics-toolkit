"""
main.py
--------
Audit Analytics Toolkit - əsas icra faylı.

Bu skript tam audit analitik prosedurları axınını icra edir:
  1. Audit datasının əldə edilməsi (sintetik VƏ YA real fayllardan)
  2. Benford Qanunu analizi (ISA 240)
  3. Jurnal Yazılarının Testi - JET (ISA 240)
  4. Maliyyə əmsalları və analitik prosedurlar (ISA 520)
  5. Audit seçməsi - MUS (ISA 530)
  6. Üç-tərəfli uyğunlaşdırma - PO/Qaimə/Ödəniş (P2P nəzarəti)
  7. Bütün nəticələrin Excel hesabatına və PDF audit memosuna yazılması

İstifadə nümunələri:
    # Sintetik data ilə tam demo
    python main.py

    # Real Baş Kitab / Balans fayllarınızla (CSV və ya XLSX)
    python main.py --journal my_journal_entries.csv --trial-balance my_trial_balance.xlsx

Gözlənilən sütunlar:
    Jurnal yazıları (--journal):
        entry_id, date, account_code, account_name, account_type
        (Asset/Liability/Equity/Revenue/Expense), debit, credit, amount, user, description

    Balans (--trial-balance):
        account_code, account_name, account_type, balance_prior, balance_current
"""

import argparse
import sys

import pandas as pd

from data_generator import generate_journal_entries, generate_trial_balance
from benford_analysis import run_benford_test
from journal_entry_testing import run_all_je_tests
from ratio_analysis import calculate_ratios, analytical_variance_review
from sampling import monetary_unit_sample, recommended_sample_size
from three_way_match import generate_procurement_data, run_three_way_match
from report_generator import build_report
from pdf_memo import build_audit_memo


def _read_any(path: str) -> pd.DataFrame:
    """CSV və ya Excel faylını avtomatik tanıyaraq oxuyur."""
    if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def load_journal_and_tb(journal_path: str = None, tb_path: str = None, n_entries: int = 1200):
    """Real fayl verilibsə onu oxuyur, verilməyibsə sintetik data yaradır."""
    if journal_path:
        print(f"      -> Real jurnal faylı oxunur: {journal_path}")
        je = _read_any(journal_path)
        je["date"] = pd.to_datetime(je["date"])
    else:
        je = generate_journal_entries(n_entries=n_entries)

    if tb_path:
        print(f"      -> Real balans faylı oxunur: {tb_path}")
        tb = _read_any(tb_path)
    else:
        tb = generate_trial_balance(je)

    return je, tb


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit Analytics Toolkit - ISA əsaslı analitik audit prosedurları")
    parser.add_argument("--journal", type=str, default=None,
                         help="Real jurnal yazıları faylı (CSV və ya XLSX)")
    parser.add_argument("--trial-balance", type=str, default=None,
                         help="Real balans (trial balance) faylı (CSV və ya XLSX)")
    parser.add_argument("--n-entries", type=int, default=1200,
                         help="Sintetik data yaradılarkən jurnal yazısı sayı (default: 1200)")
    parser.add_argument("--risk-level", choices=["aşağı", "orta", "yüksək"], default="orta",
                         help="Audit seçməsi üçün risk səviyyəsi (default: orta)")
    parser.add_argument("--variance-threshold", type=float, default=0.15,
                         help="Analitik prosedurlarda 'qeyri-adi varyasiya' həddi (default: 0.15)")
    parser.add_argument("--output-excel", type=str, default="audit_findings_report.xlsx")
    parser.add_argument("--output-pdf", type=str, default="audit_memo.pdf")
    parser.add_argument("--skip-three-way-match", action="store_true",
                         help="Üç-tərəfli uyğunlaşdırma modulunu icra etmə")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print(" AUDIT ANALYTICS TOOLKIT ".center(60, "="))
    print("=" * 60)

    print("\n[1/7] Audit datası əldə edilir...")
    je, tb = load_journal_and_tb(args.journal, args.trial_balance, args.n_entries)
    print(f"      -> {len(je)} jurnal yazısı, {len(tb)} balans sətri.")

    print("\n[2/7] Benford Qanunu analizi (ISA 240) icra edilir...")
    benford_result = run_benford_test(je["amount"])
    print(f"      -> MAD: {benford_result['mad']} | Nəticə: {benford_result['mad_conclusion']}")

    print("\n[3/7] Jurnal Yazılarının Testi (JET) icra edilir...")
    je_results = run_all_je_tests(je)
    print(f"      -> {je_results['combined']['entry_id'].nunique()} unikal bayraqlı yazı tapıldı.")
    print(je_results["summary"].to_string(index=False))

    print("\n[4/7] Maliyyə əmsalları və analitik prosedurlar (ISA 520) hesablanır...")
    ratios_df = calculate_ratios(tb)
    variance_df = analytical_variance_review(tb, threshold=args.variance_threshold)
    n_unusual = int(variance_df["qeyri_adi_varyasiya"].sum())
    print(f"      -> {n_unusual} hesabda {int(args.variance_threshold*100)}%-dən çox qeyri-adi varyasiya aşkarlandı.")

    print("\n[5/7] Audit seçməsi (Pul Vahidi Seçməsi - MUS, ISA 530) icra edilir...")
    sample_size = recommended_sample_size(len(je), risk_level=args.risk_level)
    sample_df = monetary_unit_sample(je, sample_size)
    print(f"      -> {len(sample_df)} əməliyyat seçildi (populyasiya: {len(je)}).")

    match_result = None
    if not args.skip_three_way_match:
        print("\n[6/7] Üç-tərəfli uyğunlaşdırma (PO-Qaimə-Ödəniş) icra edilir...")
        proc_data = generate_procurement_data()
        match_result = run_three_way_match(proc_data["po"], proc_data["invoice"], proc_data["payment"])
        print(f"      -> {int(match_result['flag'].sum())} / {len(match_result)} əməliyyatda uyğunsuzluq aşkarlandı.")
    else:
        print("\n[6/7] Üç-tərəfli uyğunlaşdırma keçildi (--skip-three-way-match).")

    print("\n[7/7] Hesabatlar yaradılır (Excel + PDF)...")
    excel_path = build_report(benford_result, je_results, ratios_df, variance_df, sample_df,
                               match_result=match_result, output_path=args.output_excel)
    print(f"      -> Excel hesabatı: {excel_path}")

    pdf_path = build_audit_memo(
        benford_result, je_results, variance_df,
        match_result if match_result is not None else pd.DataFrame({"flag": []}),
        sample_size=sample_size, output_path=args.output_pdf,
    )
    print(f"      -> PDF audit memosu: {pdf_path}")

    print("\n" + "=" * 60)
    print(" TAMAMLANDI ".center(60, "="))
    print("=" * 60)
    print("\nİpucu: İnteraktiv dashboard üçün işə salın:")
    print("    streamlit run dashboard.py")


if __name__ == "__main__":
    sys.exit(main() or 0)
