INTEGRASI ZAPI (zapi.ink) — panduan singkat
============================================

LANGKAH PASANG
 1. Buat akun di zapi.ink dan salin API key dari dashboard Anda.
 2. Buat file  zapi_key.txt  di folder ini (sebelah server.py). Isi: hanya key Anda, satu baris.
    (Alternatif: set variabel lingkungan ZAPI_KEY sebelum menjalankan server.)
    Key hanya dibaca server; tidak dikirim ke browser dan tidak dicatat di log.
    JANGAN menempelkan key ke chat, forum, atau repositori publik.
 3. Jalankan:  python server.py   lalu buka  http://localhost:8000  (bukan membuka index.html langsung).
 4. Di panel "Sumber data riil — Zapi": Uji koneksi -> Unduh riwayat harian LQ45 (sekali) -> Perbarui harian (tiap hari bursa).
    Setelah unduhan selesai, halaman memuat ulang dan teks di bar atas berubah menjadi "data CSV".

BIAYA REQUEST (paket gratis: 600/bulan, 100/menit)
 Uji koneksi ................ 1 (lalu di-cache 24 jam)
 Unduh riwayat LQ45 ......... ~45 (1 per saham; berkas yang masih segar < 20 jam dilewati)
 Perbarui harian ............ 1 per hari bursa yang tertinggal (satu request mengembalikan SEMUA saham), maks 31
 Order flow Zapi ............ ~4 pada segarkan pertama (orderbook + 3 halaman tape), lalu ~2 per segarkan;
                              +1 untuk broker summary (di-cache 5 menit). Cache 15 detik: segarkan ulang yang terlalu cepat gratis.
 Contoh anggaran bulanan: 45 (riwayat) + ~21 (harian) + sisanya ~530 => ~260 kali segarkan order flow per bulan.
 => Paket gratis TIDAK cukup untuk memantau order flow terus-menerus. Gunakan segarkan manual atau interval panjang.
 Terminal memakai anggaran lokal (default 500; ubah dengan variabel lingkungan ZAPI_BUDGET) dan menolak panggilan saat habis.
 Hitungan lokal hanyalah PERKIRAAN (zapi_usage.json); hitungan resmi ada di dashboard Zapi.

ENDPOINT YANG DIPAKAI  (GET https://api.zapi.ink/v1/<kategori:sumber>/<endpoint>, header x-api-key)
 finance:idx/stock-history      riwayat harian satu saham
 finance:idx/stock-summary      ringkasan semua saham pada satu tanggal
 finance:pluang/orderbook       antrean bid/ask
 finance:pluang/running-trades  cetakan transaksi dengan sisi agresor BUY/SELL
 finance:pluang/broker-summary  10 broker net beli/jual teratas
 finance:pluang/brokers         klasifikasi broker LOCAL/FOREIGN versi Pluang

KETERBATASAN YANG PERLU ANDA TAHU
 - Zapi adalah agregator pihak ketiga yang mengambil data dari sumber lain; BUKAN feed resmi bursa. Data bisa tertunda
   belasan detik atau lebih, bisa salah, dan layanan bisa berubah. Baca syarat penggunaan Zapi dan sumbernya sendiri.
 - Harga historis TIDAK disesuaikan aksi korporasi (split, dividen saham, right issue): backtest saham yang pernah split
   bisa terdistorsi oleh lonjakan harga palsu.
 - Saham dengan riwayat jauh lebih pendek (IPO baru) otomatis dilewati saat memuat data (terlihat di panel Zapi).
 - Indeks IHSG tidak ikut diunduh (tidak ada endpoint riwayat indeks yang dipakai), jadi pembanding IHSG tidak tersedia.
 - Running trade tidak memuat kode broker per cetakan; broker summary hanya 10 teratas per sisi; klasifikasi lokal/asing
   adalah versi Pluang, bukan institusi vs ritel. Order flow tetap proksi, bukan identitas pelaku.
 - Jadwal jam bursa untuk deteksi "pasar tutup" adalah perkiraan dan tidak memuat hari libur.
 - Bukan saran investasi.

KEAMANAN
 - Endpoint yang memakai kuota (uji koneksi, sinkron, order flow mode Zapi) hanya melayani halaman terminal ini sendiri:
   Host harus localhost/127.0.0.1 dan wajib membawa token acak per-proses yang disisipkan ke index.html. Situs lain di browser Anda
   tidak bisa memicu pemakaian kuota Anda. Server hanya mendengarkan 127.0.0.1.

UJI TANPA KUOTA
 python tests/test_zapi.py        # uji penuh terhadap server TIRUAN lokal (data palsu), tanpa internet
 python tests/mock_zapi.py 8899   # jalankan mock sendiri, lalu:  ZAPI_BASE=http://127.0.0.1:8899 ZAPI_KEY=testkey python server.py
