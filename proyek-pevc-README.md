# PE/VC Investment Analysis Engine — Integrated V2

Aplikasi analisis investasi berbasis Python + Excel + Streamlit. Gunakan untuk analisis awal; bukan pengganti model transaksi yang direview independen.

## Jalankan di Windows
1. Ekstrak ZIP ke folder kerja.
2. Pastikan Python 3.10 atau lebih baru sudah terpasang.
3. Jalankan `run_windows.bat`.
4. Browser biasanya membuka `http://localhost:8501`.
5. Upload workbook `.xlsx` melalui uploader di bagian atas dashboard.

## Penting untuk upload Excel
- Dashboard membaca ulang file yang diunggah ketika file berubah dan menampilkan nama sumber, SHA-256, serta fingerprint data.
- Jika Anda mengunggah workbook bawaan yang persis sama, angka tidak berubah karena inputnya identik. Ubah nilai di Excel, simpan, lalu upload kembali.
- Workbook harus memiliki sheet `Company_Financials`. Format yang didukung adalah layout metric-vertikal pada workbook contoh atau tabel datar dengan kolom `Year, Revenue, EBITDA_Margin, D&A, Capex, NWC`.
- Pastikan formula Excel telah dihitung oleh Excel desktop sebelum upload. Pembacaan memakai nilai tersimpan dari workbook, bukan menjalankan kalkulasi formula Excel.

## Modul yang tersedia
1. Data validation: kolom wajib, tipe angka, nilai kosong, duplikasi, margin, tahun, WACC/growth, dan pajak.
2. Audit trail: nama file sumber, waktu pemuatan UTC, ukuran file, SHA-256 dan fingerprint input.
3. DCF + sensitivity: FCFF, terminal value, EV/equity value, sensitivitas WACC/growth.
4. LBO: entry/exit sensitivity dan debt schedule tahunan dengan mandatory amortization, cash sweep, leverage covenant, dan interest coverage covenant.
5. VC: multi-round priced-round cap table dan liquidation preference sederhana (participating/non-participating).
6. Monte Carlo: distribusi MOIC dan IRR, percentile P5/P25/median/P75/P95, serta probabilitas rugi.
7. Due diligence: editable finding register, severity, status, evidence/source dan mitigasi.
8. Investment memo: memo teks dan formatted DOCX yang menggabungkan valuasi, debt schedule, simulasi return, kualitas data, audit trail dan due diligence.

## Batasan yang harus diketahui
- Angka dalam workbook contoh bersifat ilustratif.
- LBO adalah model tahunan yang disederhanakan. Belum mencakup revolver, PIK, cash minimum dinamis, cash sweep yang mengikuti semua definisi legal, tax loss carryforward, dan semua debt covenant khusus.
- VC cap table mendukung priced rounds sederhana. SAFE, convertible note, option pool refresh, anti-dilution, seniority beberapa kelas, dan legal waterfall kompleks belum dimodelkan.
- Monte Carlo menggunakan distribusi lognormal yang ditentukan pengguna; hasilnya sangat tergantung asumsi dan bukan prediksi.
- Due diligence findings perlu dimasukkan dan didukung bukti oleh analis. Aplikasi tidak membaca otomatis dokumen hukum/keuangan dalam versi ini.
- Audit trail ini adalah identifikasi sumber file dan input, belum merupakan immutable enterprise audit log dengan user access control.

## Verifikasi teknis
Tes engine: `python -m pytest -q` dari folder proyek.
