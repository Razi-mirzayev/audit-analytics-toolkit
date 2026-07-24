"""
report_generator.py
--------------------
Bütün analiz nəticələrini (Benford, JET, əmsallar, seçmə) bir professional
Excel audit hesabatına ("Audit Working Paper") çevirir.
"""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference

FONT_NAME = "Arial"
HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
FLAG_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
TITLE_FONT = Font(name=FONT_NAME, size=14, bold=True, color="1F4E78")
HEADER_FONT = Font(name=FONT_NAME, size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name=FONT_NAME, size=10)
THIN_BORDER = Border(*(Side(style="thin", color="D9D9D9"),) * 4)


def _write_df(ws, df: pd.DataFrame, start_row: int = 1, title: str = None, highlight_col: str = None):
    row = start_row
    if title:
        ws.cell(row=row, column=1, value=title).font = TITLE_FONT
        row += 2

    header_row = row
    for j, col in enumerate(df.columns, start=1):
        cell = ws.cell(row=header_row, column=j, value=str(col).replace("_", " "))
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER

    for i, record in enumerate(df.itertuples(index=False), start=1):
        for j, value in enumerate(record, start=1):
            cell = ws.cell(row=header_row + i, column=j, value=value)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            if isinstance(value, float):
                cell.number_format = "#,##0.00"

        if highlight_col and highlight_col in df.columns:
            col_idx = list(df.columns).index(highlight_col) + 1
            flag_val = df.iloc[i - 1][highlight_col]
            if flag_val in (True, "True") or (isinstance(flag_val, str) and flag_val):
                for j in range(1, len(df.columns) + 1):
                    ws.cell(row=header_row + i, column=j).fill = FLAG_FILL

    for j, col in enumerate(df.columns, start=1):
        max_len = max([len(str(col))] + [len(str(v)) for v in df[col].astype(str)])
        ws.column_dimensions[get_column_letter(j)].width = min(max(max_len + 3, 12), 35)

    return header_row + len(df) + 1


def build_report(benford_result: dict, je_results: dict, ratios_df: pd.DataFrame,
                  variance_df: pd.DataFrame, sample_df: pd.DataFrame,
                  match_result: pd.DataFrame = None,
                  output_path: str = "audit_findings_report.xlsx"):
    wb = Workbook()

    # ---- Summary sheet ----
    ws = wb.active
    ws.title = "Xülasə"
    ws.cell(row=1, column=1, value="AUDİT ANALİTİK PROSEDURLARI - TAPINTILAR HESABATI").font = Font(
        name=FONT_NAME, size=16, bold=True, color="1F4E78")
    ws.cell(row=2, column=1, value="ISA (Beynəlxalq Audit Standartları) əsasında hazırlanıb").font = Font(
        name=FONT_NAME, size=10, italic=True, color="595959")

    summary_rows = [
        ["Prosedur", "Standart İstinadı", "Nəticə"],
        ["Benford Qanunu Analizi", "ISA 240", benford_result["mad_conclusion"]],
        ["", "", f"Chi-kvadrat p-dəyəri: {benford_result['p_value']}"],
        ["Jurnal Yazılarının Testi (JET)", "ISA 240",
         f"{je_results['combined']['entry_id'].nunique()} unikal bayraqlı yazı aşkar edildi"],
        ["Analitik Prosedurlar / Əmsallar", "ISA 520",
         f"{int(variance_df['qeyri_adi_varyasiya'].sum())} hesabda qeyri-adi varyasiya (>15%)"],
        ["Audit Seçməsi", "ISA 530", f"{len(sample_df)} əməliyyat seçildi (MUS metodu)"],
    ]
    if match_result is not None:
        summary_rows.append([
            "Üç-tərəfli Uyğunlaşdırma (P2P)", "Alış-satış nəzarəti",
            f"{int(match_result['flag'].sum())} / {len(match_result)} əməliyyatda uyğunsuzluq"
        ])
    for i, r in enumerate(summary_rows, start=4):
        for j, v in enumerate(r, start=1):
            cell = ws.cell(row=i, column=j, value=v)
            cell.font = HEADER_FONT if i == 4 else BODY_FONT
            cell.fill = HEADER_FILL if i == 4 else PatternFill()
            cell.border = THIN_BORDER
    for j, w in enumerate([32, 20, 55], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w

    # ---- Benford sheet ----
    ws2 = wb.create_sheet("Benford Analizi")
    _write_df(ws2, benford_result["table"], title="Benford Qanunu Testi - İlk Rəqəm Paylanması")
    chart = BarChart()
    chart.title = "Müşahidə vs Gözlənilən Faiz (%)"
    chart.y_axis.title = "%"
    chart.x_axis.title = "İlk Rəqəm"
    data = Reference(ws2, min_col=3, max_col=4, min_row=3, max_row=12)
    cats = Reference(ws2, min_col=1, min_row=4, max_row=12)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    ws2.add_chart(chart, "G3")

    # ---- JET sheet ----
    ws3 = wb.create_sheet("JET Tapıntıları")
    combined = je_results["combined"].copy()
    if not combined.empty:
        combined = combined[["entry_id", "date", "account_name", "amount", "user", "flag_reason"]]
        combined["date"] = combined["date"].astype(str)
    _write_df(ws3, je_results["summary"], title="JET - Test Xülasəsi")
    _write_df(ws3, combined, start_row=len(je_results["summary"]) + 5,
              title="Bayraqlanmış Yazıların Detalları (Bütün Testlər)")

    # ---- Ratios & variance sheet ----
    ws4 = wb.create_sheet("Əmsallar və Varyasiya")
    next_row = _write_df(ws4, ratios_df, title="Əsas Maliyyə Əmsalları (Cari vs Əvvəlki Dövr)")
    variance_display = variance_df.copy()
    variance_display["qeyri_adi_varyasiya"] = variance_display["qeyri_adi_varyasiya"].map(
        {True: "BƏLI - Araşdırılmalıdır", False: "Xeyr"})
    _write_df(ws4, variance_display, start_row=next_row + 2,
              title="Hesab üzrə Dövrlər Arası Varyasiya Analizi (ISA 520)",
              highlight_col="qeyri_adi_varyasiya")

    # ---- Sampling sheet ----
    ws5 = wb.create_sheet("Audit Seçməsi")
    sample_display = sample_df[["entry_id", "date", "account_name", "amount", "user", "sampling_method"]].copy()
    sample_display["date"] = sample_display["date"].astype(str)
    _write_df(ws5, sample_display, title="Seçilmiş Əməliyyatlar - Detal Test üçün (ISA 530)")

    # ---- Three-way match sheet ----
    if match_result is not None:
        ws6 = wb.create_sheet("3-tərəfli Uyğunlaşdırma")
        match_display = match_result.copy()
        match_display["flag"] = match_display["flag"].map({True: "BƏLI", False: "Xeyr"})
        _write_df(ws6, match_display,
                   title="Sifariş (PO) - Qaimə (Invoice) - Ödəniş (Payment) Uyğunlaşdırması",
                   highlight_col="flag")

    wb.save(output_path)
    return output_path
