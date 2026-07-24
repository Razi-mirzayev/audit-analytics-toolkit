# Audit Analytics Toolkit (Python)

Bu layihə **audit assistant** vəzifəsinin iş təsvirinə uyğun olaraq hazırlanıb və
Beynəlxalq Audit Standartlarına (ISA) əsaslanan analitik audit prosedurlarını
Python vasitəsilə avtomatlaşdırır. Məqsəd — real audit komandalarının istifadə
etdiyi metodologiyanı həm nəzəri, həm də praktiki (kodlaşdırma) səviyyədə
göstərmək.

## Modullar

| Modul | ISA / Standart | Təsvir |
|---|---|---|
| `data_generator.py` | — | Real GL/Balans strukturuna bənzər sintetik test datası yaradır (qəsdən "risk" yazıları ilə) |
| `benford_analysis.py` | ISA 240 | Benford Qanunu ilə fırıldaqçılıq riski üçün ilk-rəqəm analizi, xi-kvadrat testi |
| `journal_entry_testing.py` | ISA 240 | JET: həftə sonu yazıları, dəyirmi məbləğlər, təsdiq həddindən yayınma, dövr sonu, dublikatlar, menecer yazıları |
| `ratio_analysis.py` | ISA 520 | Likvidlik/mənfəətlilik/leverage əmsalları + dövrlər arası varyasiya analizi |
| `sampling.py` | ISA 530 | Təsadüfi, Sistematik və Pul Vahidi Seçməsi (MUS) metodları |
| `three_way_match.py` | P2P nəzarəti | Sifariş (PO) – Qaimə (Invoice) – Ödəniş (Payment) uyğunlaşdırması: açıq sifarişlər, məbləğ fərqləri, təkrar ödənişlər |
| `report_generator.py` | — | Bütün tapıntıları professional formatlanmış Excel audit iş sənədinə (working paper) yığır |
| `pdf_memo.py` | — | Rəhbərlik/tərəfdaş üçün qısa PDF "Audit Tapıntıları Memosu" |
| `dashboard.py` | — | Streamlit ilə interaktiv, real-vaxt filtrlənə bilən dashboard |
| `main.py` | — | Tam pipeline-ı CLI vasitəsilə icra edir (sintetik VƏ ya real fayllarla) |

## Quraşdırma

```bash
pip install -r requirements.txt
```

## İşə salma üsulları

### 1) Sürətli demo (sintetik data ilə)
```bash
python main.py
```
Nəticədə iki fayl yaranır:
- `audit_findings_report.xlsx` — 6 vərəqli tam audit iş sənədi (Xülasə, Benford,
  JET, Əmsallar/Varyasiya, Audit Seçməsi, 3-tərəfli Uyğunlaşdırma)
- `audit_memo.pdf` — rəhbərlik üçün 1-2 səhifəlik icraçı xülasə memosu

### 2) Real Baş Kitab / Balans faylınızla
```bash
python main.py --journal my_journal_entries.csv --trial-balance my_trial_balance.xlsx
```
CSV və XLSX formatları avtomatik tanınır. Gözlənilən sütunlar:

- **Jurnal yazıları** (`--journal`): `entry_id, date, account_code, account_name,
  account_type (Asset/Liability/Equity/Revenue/Expense), debit, credit, amount, user, description`
- **Balans** (`--trial-balance`): `account_code, account_name, account_type, balance_prior, balance_current`

### 3) Digər faydalı parametrlər
```bash
python main.py --risk-level yüksək --variance-threshold 0.10 --skip-three-way-match
python main.py --n-entries 3000          # daha böyük sintetik populyasiya
python main.py --help                    # bütün parametrlərin siyahısı
```

### 4) İnteraktiv Dashboard
```bash
streamlit run dashboard.py
```
Brauzerdə açılan dashboard vasitəsilə varyasiya həddini və risk səviyyəsini
real vaxtda dəyişərək bütün analizləri (Benford qrafiki, JET bölgüsü, əmsallar,
3-tərəfli uyğunlaşdırma statusu, MUS seçməsi) canlı izləyə bilərsiniz.

## Niyə bu layihə güclüdür (müsahibə/CV üçün)

- **Maliyyə/audit bilikləri**: hər modul konkret ISA standartına istinad edir və
  real audit metodologiyasını (fırıldaqçılıq riski, analitik prosedurlar, seçmə
  metodları, alış-satış dövrü nəzarəti) düzgün əks etdirir.
- **Python bacarıqları**: pandas/numpy ilə məlumat emalı, statistik testlər
  (scipy), openpyxl ilə formatlanmış Excel hesabatı, reportlab ilə PDF memo,
  Streamlit/Plotly ilə interaktiv dashboard, argparse ilə CLI interfeysi.
- **Praktiki tətbiq**: sadəcə demo deyil — `--journal`/`--trial-balance`
  parametrləri ilə real müştəri datası üzərində birbaşa işə salına bilər.

## Fayl strukturu

```
audit_analytics_toolkit/
├── data_generator.py        # Sintetik data
├── benford_analysis.py      # ISA 240 - Benford testi
├── journal_entry_testing.py # ISA 240 - JET
├── ratio_analysis.py        # ISA 520 - Əmsallar/Varyasiya
├── sampling.py               # ISA 530 - Audit seçməsi
├── three_way_match.py        # P2P - 3-tərəfli uyğunlaşdırma
├── report_generator.py       # Excel hesabatı
├── pdf_memo.py                # PDF audit memosu
├── dashboard.py               # Streamlit dashboard
├── main.py                    # CLI - əsas icra faylı
├── requirements.txt
└── README.md
```

## Növbəti addımlar (istəyə görə əlavə oluna bilər)

- Verilənlər bazası (PostgreSQL/SQLite) ilə birbaşa inteqrasiya
- E-poçt vasitəsilə avtomatik hesabat göndərilməsi
- Machine learning əsaslı anomaliya aşkarlanması (Isolation Forest və s.)
