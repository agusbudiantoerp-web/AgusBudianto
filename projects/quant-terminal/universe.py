# Daftar CONTOH konstituen LQ45. Komposisi resmi direvisi IDX tiap Februari & Agustus -> sesuaikan di sini.
LQ45 = ("ACES ADRO AKRA AMMN AMRT ANTM ARTO ASII BBCA BBNI BBRI BBTN BMRI BRIS BRPT BREN BUKA CPIN CTRA EXCL "
        "ESSA GOTO HRUM ICBP INCO INDF INKP INTP ISAT ITMG JPFA KLBF MAPI MDKA MEDC MTEL PGAS PGEO PTBA SIDO "
        "SMGR TLKM TOWR UNTR UNVR").split()

# Batas auto-reject (ARA/ARB) papan reguler, dipakai simetris, berdasarkan harga penutupan sebelumnya:
# (harga < batas) -> persentase. VERIFIKASI dengan aturan IDX terbaru: persentase ini pernah berubah beberapa kali.
AR_BANDS = [(200, .35), (5000, .25), (float("inf"), .20)]

# Sektor (klasifikasi IDX-IC, PERKIRAAN dari ingatan; verifikasi dan koreksi sesuai data resmi IDX). Simbol di luar peta = "Lainnya".
SECTORS = {
    "BBCA": "Keuangan", "BBRI": "Keuangan", "BMRI": "Keuangan", "BBNI": "Keuangan", "BBTN": "Keuangan", "BRIS": "Keuangan", "ARTO": "Keuangan",
    "ADRO": "Energi", "AKRA": "Energi", "HRUM": "Energi", "ITMG": "Energi", "MEDC": "Energi", "PGAS": "Energi", "PGEO": "Energi", "PTBA": "Energi",
    "AMMN": "Bahan Baku", "ANTM": "Bahan Baku", "BRPT": "Bahan Baku", "ESSA": "Bahan Baku", "INCO": "Bahan Baku", "INKP": "Bahan Baku",
    "INTP": "Bahan Baku", "MDKA": "Bahan Baku", "SMGR": "Bahan Baku",
    "AMRT": "Konsumer Primer", "CPIN": "Konsumer Primer", "ICBP": "Konsumer Primer", "INDF": "Konsumer Primer", "JPFA": "Konsumer Primer", "UNVR": "Konsumer Primer",
    "ACES": "Konsumer Siklikal", "ASII": "Konsumer Siklikal", "MAPI": "Konsumer Siklikal",
    "KLBF": "Kesehatan", "SIDO": "Kesehatan",
    "BREN": "Infrastruktur", "EXCL": "Infrastruktur", "ISAT": "Infrastruktur", "MTEL": "Infrastruktur", "TLKM": "Infrastruktur", "TOWR": "Infrastruktur",
    "BUKA": "Teknologi", "GOTO": "Teknologi", "CTRA": "Properti", "UNTR": "Industri",
}

# Jendela krisis historis (nama, dari, sampai). TANGGAL PERKIRAAN, sesuaikan sendiri. Jendela di luar rentang data akan ditandai "di luar data".
STRESS_WINDOWS = [
    ("Taper/aksi jual Q4 2018", "2018-10-01", "2018-12-24"),
    ("Krisis COVID-19", "2020-02-19", "2020-03-24"),
    ("Pasar beruang 2022", "2022-01-03", "2022-10-12"),
    ("Guncangan pasar Mar–Apr 2025", "2025-03-10", "2025-04-09"),
]
