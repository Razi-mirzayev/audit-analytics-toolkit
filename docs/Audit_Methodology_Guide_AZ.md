# 🛡️ Müsahibə və Metodologiya Bələdçisi — Audit Analytics Toolkit (ISA 240 / 520 / 530)

Bu sənəd `audit-analytics-toolkit` layihəsini Big 4 (Deloitte, PwC, EY, KPMG), daxili audit, risk menecmenti və ya Data Analytics müsahibələrində təqdim edərkən istifadə edə biləcəyiniz metodoloji izahları və sual-cavabları ehtiva edir.

---

## 1. Layihənin Qısa Təqdimatı (Elevator Pitch — 60 saniyə)
> *"Bu layihədə mən Beynəlxalq Audit Standartlarına (ISA 240, ISA 520, ISA 530) və alış-ödəniş (P2P) daxili nəzarət mexanizmlərinə əsaslanan avtomatlaşdırılmış Audit Analitikası Alətlər Dəsti (CAATs) yaratmışam. Sistem 1,223 Baş Kitab (General Ledger) yazısını, 14 Balans hesabını və 150 satınalma sifarişini təhlil edərək Benford Qanunu testini, 6 qaydalı Jurnal Yazıları Testini (JET), çoxölçülü ML anomaliya balı hesablamasını, Pul Vahidi Seçməsini (MUS) və Üç-tərəfli Uyğunlaşdırmanı (PO-Qaimə-Ödəniş) icra edir. Sonda nəticələri həm SQLite Audit Anbarına (`audit_warehouse.db`), həm 7 vərəqli Excel işçi sənədinə (`audit_findings_report.xlsx`), həm də rəsmi PDF Audit Memosuna (`audit_memo.pdf`) çevirir."*

---

## 2. Beynəlxalq Audit Standartları (ISA) üzrə Texniki Sual-Cavab

### Sual 1: Benford Qanunu (ISA 240) auditdə nə üçündür və sizin datada hansı anomaliyanı tutdu?
- **Metodologiya:** Təbii yolla əmələ gələn maliyyə əməliyyatlarında ədədin ilk rəqəminin `1` olma ehtimalı **30.1%**, `9` olma ehtimalı isə cəmi **4.58%**-dir ($P(d) = \log_{10}(1 + 1/d)$).
- **Tapıntı:** Ümumi populyasiyada $\text{MAD} = 0.00883$ (*Qəbul edilə bilən uyğunluq*) olsa da, **9 rəqəmi ilə başlayan əməliyyatlarda kəskin sıçrayış (6.38% faktiki vs 4.58% gözlənilən, yəni +1.80% artıqlıq)** aşkarlandı. Bunun səbəbi **\$10,000** təsdiq limitindən yayınmaq üçün qəsdən **\$9,700–\$9,999** aralığında rəsmiləşdirilmiş 13 ədəd şübhəli əməliyyatdır.

### Sual 2: Pul Vahidi Seçməsi (Monetary Unit Sampling — ISA 530) adi təsadüfi seçmədən nə ilə üstündür?
- **Problem:** Sadə təsadüfi seçmədə (Simple Random Sampling) \$20-lıq xırda xərc ilə \$120,000-lıq iri müqavilənin seçilmə ehtimalı bərabərdir. Nəticədə 60 təsadüfi əməliyyat ümumi \$4.89 milyonluq dövriyyənin cəmi **4.12%**-ni əhatə edir.
- **Həll (MUS):** Pul Vahidi Seçməsində hər 1 pul vahidi lotereya bileti rolunu oynayır. Seçilmiş **55 unikal əməliyyat** bütün Baş Kitabın pul dəyərinin **41.03%**-ni (**\$2.01 milyon**) əhatə edir — yəni eyni sayda sənəd yoxlamaqla **10 dəfə daha böyük maliyyə riskini** sığortalayırıq.

### Sual 3: Üç-tərəfli Uyğunlaşdırma (Three-Way Match) hansı fırıldaqçılıq və səhv risklərini önləyir?
- Satınalma Sifarişi (`PO`), Təchizatçı Qaiməsi (`Invoice`) və Bank Ödənişi (`Payment`) üçlüyünü 2%-lik tolerantlıq həddi ilə tutuşdurduqda 150 sifarişdən **48-də (32%)** uyğunsuzluq tapıldı:
  - **17 sifarişdə** qaimə məbləği sifarişdən 3–20% yüksəkdir (artıq qiymətləndirmə / overbilling riski);
  - **13 sifarişdə** qaimə gəlib, lakin ödəniş edilməyib (kreditor borcların tam uçota alınmaması riski);
  - **18 sifarişdə** PO açılıb, lakin qaimə yoxdur (açıq öhdəlik).
