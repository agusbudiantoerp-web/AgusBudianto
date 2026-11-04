# Job Hub (Streamlit)

Agregator lowongan kerja & proyek freelance. Repo: github.com/<USERNAME-GITHUB-ANDA>/job-hub

## Jalankan lokal
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (GitHub -> Streamlit Community Cloud)
GitHub Pages tidak bisa menjalankan Streamlit (butuh server Python), jadi gunakan Streamlit Community Cloud (gratis):
1. Push folder ini ke repository GitHub Anda.
2. Buka https://share.streamlit.io -> **New app** -> pilih repo, branch `main`, file `app.py`.
3. Di **Advanced settings > Secrets** isi `JOOBLE_API_KEY` dan (opsional) `FREELANCER_OAUTH_TOKEN`
   (lihat `.streamlit/secrets.toml.example`).
4. Klik **Deploy**. Setiap `git push` akan otomatis memperbarui aplikasi.

## Integrasi
| Situs | Metode |
|---|---|
| Remotive, RemoteOK, Arbeitnow | API publik |
| Jooble (mencakup Indonesia) | API key gratis |
| Freelancer.com | API resmi (token opsional) |
| LinkedIn, JobStreet, Indeed, Glints, Kalibrr, Upwork, Fiverr, Google Jobs | Deep-link pencarian (tanpa scraping, sesuai ToS) |
