# TWIN komandas prezentācija

## Rezultāts

- 12 galvenie slaidi.
- Paredzētais runas laiks: aptuveni 19 minūtes un 40 sekundes.
- Visa redzamā informācija un runātāja piezīmes ir latviešu valodā.
- Diagrammas un teksti PowerPoint failā ir rediģējami objekti.

## Slaidu struktūra un laiks

1. **TWIN** — ievads un prezentācijas mērķis, 0:50.
2. **Datu ir daudz. Sistēmas nav.** — problēmas hipotēze, 1:40.
3. **TWIN pamatideja** — Data Hub un uzticams datu slānis, 1:30.
4. **Viena darba vide, divi attīstības horizonti** — realizētie un plānotie moduļi, 1:40.
5. **Data Hub: vairāk nekā failu imports** — datu avoti un ievades ceļi, 1:45.
6. **Viens shipment, nevis trīs nesaistīti ieraksti** — canonical data model piemērs, 1:45.
7. **Ko esam jau uzbūvējuši** — M1 līdz M4A, 1:40.
8. **Uzticamība nozīmē apstāties, kad dati nav droši** — fail-closed review princips, 1:30.
9. **No datiem līdz inteliģencei** — realizētā deterministiskā analītika, 1:45.
10. **Attīstām spējas pa līmeņiem** — produkta evolūcija un ceļa karte, 1:40.
11. **Pirmais MVP** — input, core, output un skaidras robežas, 1:50.
12. **Nākamais mērķis: pierādīt vajadzību** — tirgus izpēte un komandas lēmums, 2:05.

## Realizēts pašreizējā prototipā

- CSV/XLSX imports, kolonnu kartēšana, normalizācija un validācija.
- Review un Data Quality plūsma ar korekcijām, revalidāciju, learned mappings un audit trail.
- Invoice un Bill of Lading dokumentu klasifikācija, extraction kandidāti, confidence, evidence, review, approval un provenance.
- Canonical loģistikas modelis ar shipment, customer, container, B/L, vessel, voyage, port, invoice, cost un payment attiecībām.
- Overview un Analytics ar deterministiskiem KPI, trendiem, breakdowns, insights un drill-down līdz avotiem.

## Plānots vai ilgtermiņa vīzija

- Pilns Data Hub ar tiešiem TMS, ERP, grāmatvedības, banku, e-pasta un API savienojumiem.
- Atsevišķa Finance darba telpa, AI Analyst, FIN//TWIN simulators un plašāks automatizāciju katalogs.
- Prognozēšana, scenāriju simulācijas un predictive ML.
- Produkcijas autentifikācija, pilna administrēšana, plašs OCR pārklājums un mērogojams integrāciju slānis.

## Tirgus izpētē jāpārbauda

- Cik bieži sadrumstalotu datu problēma rodas izvēlētajā klientu segmentā.
- Kurš pain point rada vislielāko izmērāmo vērtību: dokumentu apstrāde, shipment profitability, reporti, datu konsolidācija, exception detection vai maksājumu pārredzamība.
- Kādas sistēmas un integrācijas ir obligātas, kādas ir cloud/on-prem prasības un kas pieņem pirkuma lēmumu.
- Vai uzņēmumi būtu gatavi testēt šauri definētu MVP.
- Extraction pārklājums uz dažādiem reālu klientu dokumentu izkārtojumiem.
- Reāla diferenciācija pret TMS/ERP, Document Intelligence, Data Integration, BI un logistics analytics produktiem.

Pēc tirgus izpētes visvairāk jāatjauno 2., 8., 11. un 12. slaids. Ja ir dokumentēti klientu testi, 8. slaidā var aizstāt pašreizējo prototipa drošības principa piemēru ar reāliem testa rezultātiem.

## Dati, avoti un ekrānuzņēmumi

Prezentācija balstīta tikai TWIN repozitorija informācijā:

- `README.md`;
- `docs/ARCHITECTURE.md`;
- `docs/DATA_MODEL.md`;
- `docs/IMPORT_REVIEW.md`;
- `docs/DOCUMENT_ENGINE.md`;
- `docs/BILL_OF_LADING.md`;
- `docs/ANALYTICS.md`;
- attiecīgajos backend testos un frontend moduļu struktūrā.

Ārēji tirgus dati nav izmantoti. TAM, SAM, SOM, ROI un klientu statistika nav izdomāta.

9. slaida Rīga–Roterdama skaitļi ir TWIN sintētiskā demo datu stāsta piemērs, nevis klienta vai tirgus fakti.

Īsti aplikācijas ekrānuzņēmumi prezentācijā netika izmantoti, jo laika ierobežojuma brīdī lokālā aplikācija nebija palaista. Tā vietā izmantotas rediģējamas produkta un arhitektūras diagrammas; neviens konceptuāls mockup netiek pasniegts kā strādājoša funkcionalitāte.

## Faili

- `output/TWIN_komandas_prezentacija_LV_final_v2.pptx` — rediģējamā PowerPoint prezentācija.
- `output/pdf/TWIN_komandas_prezentacija_LV_final_v2.pdf` — PDF eksports.
- `rendered/slide-01.png` līdz `rendered/slide-12.png` — slaidu vizuālās pārbaudes renderi.
- `rendered/TWIN_montage.png` — kopskata montāža.
- `.build/build_twin_deck.mjs` — reproducējams prezentācijas ģenerators.

## Kvalitātes pārbaude

- Strukturāli validēts 12 slaidu PPTX formāts, slide size, fontu politika un importējamība.
- Individuāli apskatīti visi 12 PPTX renderi; salabots pārāk šaurs teksta lauks 2. slaidā.
- PDF atkārtoti eksportēts ar `Noto Sans`, lai izvairītos no fonta aizstāšanas.
- PDF apstiprinātas 12 lapas un 16:9 izmērs; vizuāli pārbaudīta visu lapu montāža.
- Pārbaudīts, ka realizētais un plānotais ir vizuāli nošķirts un ka runātāja piezīmes ir pievienotas katram slaidam.
