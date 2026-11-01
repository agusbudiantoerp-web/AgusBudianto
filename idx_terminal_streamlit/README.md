# IDX Terminal — Streamlit Cloud

Prototype publik IDX Terminal berbasis Streamlit.

## Deploy ke Streamlit Community Cloud
1. Upload `app.py` dan `requirements.txt` ke repository GitHub (root atau folder khusus).
2. Buka https://share.streamlit.io/ dan login dengan GitHub.
3. Klik **Create app** → **Yup, I have an app**.
4. Pilih repository, branch `main`, dan file `app.py`.
5. Klik **Deploy**. Tunggu proses build selesai.
6. Salin URL `https://<nama-app>.streamlit.app`.

## Catatan data
- Yahoo Finance (`.JK` dan `^JKSE`), bukan feed resmi IDX.
- Data dapat tertunda, kosong, atau terkena rate limit.
- Data di-cache selama 5 menit.
- Tidak ada API key yang perlu dimasukkan untuk prototipe ini.
- Broker summary, ownership, foreign flow, dan data fundamental terverifikasi belum tersedia otomatis.
- Aplikasi ini untuk edukasi dan riset; bukan rekomendasi investasi.

## Lokal
```bash
pip install -r requirements.txt
streamlit run app.py
```
