"""
pdf_memo.py
------------
Rəhbərlik üçün qısa Audit Tapıntıları Memosu (Executive Audit Memo) yaradır.
Excel iş sənədindən fərqli olaraq, bu sənəd audit rəhbərinə/tərəfdaşa (partner)
və ya müştəriyə təqdim ediləcək YÜKSƏK SƏVİYYƏLİ xülasədir - detallar deyil,
əsas tapıntılar və tövsiyələr əks olunur.
"""

from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

# Helvetica/Times kimi standart PDF fontları Azərbaycan hərflərini (Ə, İ, ı, Ş və s.)
# dəstəkləmir və bu hərflər qara qutu kimi göstərilir. Ona görə DejaVu Sans (tam Unicode
# dəstəkli TTF) qeydiyyatdan keçirilir və bütün mətn üçün istifadə olunur.
#
# Font faylı əvvəlcə layihənin öz `fonts/` qovluğundan axtarılır (əməliyyat sistemindən
# asılı olmayaraq işləsin deyə birbaşa layihəyə daxil edilib). Tapılmazsa, sistemdəki
# yayılmış yerlərə baxılır. Heç biri tapılmazsa, standart Helvetica-ya keçilir (bu halda
# Azərbaycana məxsus hərflər düzgün görünməyə bilər).
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

_CANDIDATE_DIRS = [
    os.path.join(_THIS_DIR, "fonts"),                       # layihənin öz qovluğu (əsas seçim)
    "/usr/share/fonts/truetype/dejavu",                      # Linux
    r"C:\Windows\Fonts",                                     # Windows (Arial fallback üçün aşağıda)
    "/System/Library/Fonts/Supplemental",                    # macOS
    "/Library/Fonts",                                        # macOS
]


def _find_font(filename: str) -> str:
    for d in _CANDIDATE_DIRS:
        candidate = os.path.join(d, filename)
        if os.path.isfile(candidate):
            return candidate
    return None


_regular_path = _find_font("DejaVuSans.ttf")
_bold_path = _find_font("DejaVuSans-Bold.ttf")
_italic_path = _find_font("DejaVuSans-Oblique.ttf")

if _regular_path and _bold_path and _italic_path:
    pdfmetrics.registerFont(TTFont("DejaVuSans", _regular_path))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", _bold_path))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Oblique", _italic_path))
    FONT_REGULAR = "DejaVuSans"
    FONT_BOLD = "DejaVuSans-Bold"
    FONT_ITALIC = "DejaVuSans-Oblique"
else:
    # Ehtiyat variant: Windows-da Arial adətən Azərbaycan hərflərini dəstəkləyir.
    _arial_path = _find_font("arial.ttf")
    _arial_bold_path = _find_font("arialbd.ttf")
    _arial_italic_path = _find_font("ariali.ttf")
    if _arial_path and _arial_bold_path:
        pdfmetrics.registerFont(TTFont("Arial", _arial_path))
        pdfmetrics.registerFont(TTFont("Arial-Bold", _arial_bold_path))
        pdfmetrics.registerFont(TTFont("Arial-Italic", _arial_italic_path or _arial_path))
        FONT_REGULAR = "Arial"
        FONT_BOLD = "Arial-Bold"
        FONT_ITALIC = "Arial-Italic"
    else:
        print("XƏBƏRDARLIQ: Unicode font tapılmadı, Helvetica istifadə olunur. "
              "Azərbaycana məxsus hərflər (Ə, İ, ı, Ş) düzgün görünməyə bilər.")
        FONT_REGULAR = "Helvetica"
        FONT_BOLD = "Helvetica-Bold"
        FONT_ITALIC = "Helvetica-Oblique"
pdfmetrics.registerFontFamily(
    FONT_REGULAR, normal=FONT_REGULAR, bold=FONT_BOLD, italic=FONT_ITALIC, boldItalic=FONT_BOLD
)

NAVY = colors.HexColor("#1F4E78")
LIGHT_GREY = colors.HexColor("#F2F2F2")
RED = colors.HexColor("#C00000")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="MemoTitle", fontSize=18, textColor=NAVY,
                               fontName=FONT_BOLD, spaceAfter=4))
    styles.add(ParagraphStyle(name="MemoSub", fontSize=10, textColor=colors.grey,
                               fontName=FONT_ITALIC, spaceAfter=14))
    styles.add(ParagraphStyle(name="SectionHeading", fontSize=13, textColor=NAVY,
                               fontName=FONT_BOLD, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="Body", fontSize=10, leading=14,
                               fontName=FONT_REGULAR, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="Flag", fontSize=10, leading=14,
                               fontName=FONT_BOLD, textColor=RED))
    return styles


def build_audit_memo(benford_result: dict, je_results: dict, variance_df,
                      match_result, sample_size: int, output_path: str = "audit_memo.pdf",
                      client_name: str = "Nümunə Müştəri MMC",
                      period: str = "01.01.2025 - 31.12.2025"):
    styles = _styles()
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                             topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    story = []

    # ---- Header ----
    story.append(Paragraph("AUDİT TAPINTILARI MEMOSU", styles["MemoTitle"]))
    story.append(Paragraph(
        f"Müştəri: {client_name} &nbsp;|&nbsp; Dövr: {period} &nbsp;|&nbsp; "
        f"Hazırlanma tarixi: {date.today().strftime('%d.%m.%Y')}",
        styles["MemoSub"]))
    story.append(HRFlowable(width="100%", color=NAVY, thickness=1))
    story.append(Spacer(1, 10))

    # ---- Executive summary ----
    story.append(Paragraph("1. İCMAL", styles["SectionHeading"]))
    n_unusual = int(variance_df["qeyri_adi_varyasiya"].sum())
    n_je_flags = je_results["combined"]["entry_id"].nunique() if not je_results["combined"].empty else 0
    n_match_flags = int(match_result["flag"].sum())

    summary_text = (
        f"Aparılmış analitik prosedurlar (ISA 240, ISA 520, ISA 530) nəticəsində "
        f"cəmi <b>{n_je_flags}</b> jurnal yazısında, <b>{n_unusual}</b> balans hesabında və "
        f"<b>{n_match_flags}</b> alış-satış əməliyyatında əlavə araşdırma tələb edən "
        f"məsələlər aşkar edilmişdir. Benford Qanunu testi üzrə nəticə: "
        f"<b>{benford_result['mad_conclusion']}</b>."
    )
    story.append(Paragraph(summary_text, styles["Body"]))
    story.append(Spacer(1, 8))

    # ---- Key metrics table ----
    table_data = [
        ["Prosedur", "Standart", "Nəticə", "Status"],
        ["Benford Qanunu Analizi", "ISA 240", benford_result["mad_conclusion"],
         "DİQQƏT" if benford_result["significant_deviation"] else "QƏNAƏTBƏXŞ"],
        ["Jurnal Yazılarının Testi", "ISA 240", f"{n_je_flags} bayraqlı yazı",
         "DİQQƏT" if n_je_flags > 0 else "QƏNAƏTBƏXŞ"],
        ["Analitik Prosedurlar", "ISA 520", f"{n_unusual} qeyri-adi varyasiya",
         "DİQQƏT" if n_unusual > 0 else "QƏNAƏTBƏXŞ"],
        ["Üç-tərəfli Uyğunlaşdırma", "P2P Nəzarəti", f"{n_match_flags} uyğunsuzluq",
         "DİQQƏT" if n_match_flags > 0 else "QƏNAƏTBƏXŞ"],
        ["Audit Seçməsi (MUS)", "ISA 530", f"{sample_size} əməliyyat seçilib", "İCRA OLUNUB"],
    ]
    t = Table(table_data, colWidths=[5.5 * cm, 3 * cm, 5.5 * cm, 3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # ---- Key findings ----
    story.append(Paragraph("2. ƏSAS TAPINTILAR", styles["SectionHeading"]))
    findings = [
        f"<b>Fırıldaqçılıq riski göstəriciləri:</b> Jurnal yazıları arasında həftə sonu "
        f"tarixli, təsdiq həddinə yaxın və dövr sonuna aid yazılar aşkar edilmişdir. "
        f"Bunlar əlavə substantiv prosedurlar tələb edir (ISA 240.32-33).",

        f"<b>Analitik dəyişikliklər:</b> {n_unusual} balans hesabında dövrlər arası "
        f"15%-dən çox varyasiya qeydə alınmışdır. Rəhbərlikdən izahat tələb olunmalı "
        f"və dəstəkləyici sənədlərlə əsaslandırılmalıdır (ISA 520.5).",

        f"<b>Alış-satış dövrü nəzarətləri:</b> Üç-tərəfli uyğunlaşdırma zamanı "
        f"{n_match_flags} əməliyyatda uyğunsuzluq (açıq sifarişlər, ödənilməmiş qaimələr "
        f"və ya məbləğ fərqləri) aşkar edilmişdir.",

        f"<b>Seçmə əsaslı test:</b> Pul Vahidi Seçməsi (MUS) metodu ilə {sample_size} "
        f"əməliyyat seçilmiş və detal testə cəlb edilmişdir (ISA 530.8-10).",
    ]
    for f in findings:
        story.append(Paragraph(f"• {f}", styles["Body"]))
        story.append(Spacer(1, 4))

    # ---- Recommendations ----
    story.append(Paragraph("3. TÖVSİYƏLƏR", styles["SectionHeading"]))
    recs = [
        "Bayraqlanmış jurnal yazıları üçün müştəridən yazılı izahat və dəstəkləyici "
        "sənədlər (təsdiq, müqavilə, ödəniş qəbzi) tələb olunsun.",
        "Qeyri-adi varyasiya olan hesablar üzrə əlavə substantiv prosedurlar "
        "(təsdiqləmə, yenidən hesablama) planlaşdırılsın.",
        "Açıq sifarişlər və ödənilməmiş qaimələr üzrə öhdəliklərin tamlığı "
        "(completeness) təsdiqlənsin.",
        "Təkrar ödəniş riski olan əməliyyatlar üzrə daxili nəzarət mühiti "
        "rəhbərliklə müzakirə edilsin.",
    ]
    for r in recs:
        story.append(Paragraph(f"• {r}", styles["Body"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", color=colors.grey, thickness=0.5))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>Qeyd: Bu memo audit komandasının daxili istifadəsi üçün hazırlanmışdır və "
        "yekun audit rəyi deyil. Tapıntılar əlavə audit prosedurları vasitəsilə "
        "təsdiqlənməlidir.</i>", styles["Body"]))

    doc.build(story)
    return output_path


if __name__ == "__main__":
    from data_generator import generate_journal_entries, generate_trial_balance
    from benford_analysis import run_benford_test
    from journal_entry_testing import run_all_je_tests
    from ratio_analysis import analytical_variance_review
    from three_way_match import generate_procurement_data, run_three_way_match

    je = generate_journal_entries()
    tb = generate_trial_balance(je)
    benford_result = run_benford_test(je["amount"])
    je_results = run_all_je_tests(je)
    variance_df = analytical_variance_review(tb)
    proc_data = generate_procurement_data()
    match_result = run_three_way_match(proc_data["po"], proc_data["invoice"], proc_data["payment"])

    path = build_audit_memo(benford_result, je_results, variance_df, match_result, sample_size=56)
    print(f"Memo yaradıldı: {path}")
