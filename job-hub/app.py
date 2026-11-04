"""Job Hub - agregator lowongan & proyek freelance (Streamlit).
Pemilik repo: Agus Budianto
Sumber data memakai API/feeds resmi + deep-link ke situs yang melarang scraping.
"""
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Job Hub", page_icon="💼", layout="wide")
TIMEOUT = 15
HEADERS = {"User-Agent": "JobHub-Streamlit/1.0"}


def secret(name: str) -> str:
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


def row(source, title, company, location, url, date="", salary="", tags=""):
    return {"Sumber": source, "Posisi": title, "Perusahaan": company, "Lokasi": location,
            "Gaji/Budget": salary, "Tanggal": date, "Tags": tags, "Link": url}


# ---------- Konektor API resmi / publik ----------
@st.cache_data(ttl=900, show_spinner=False)
def fetch_remotive(q):
    r = requests.get("https://remotive.com/api/remote-jobs", params={"search": q}, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return [row("Remotive", j["title"], j["company_name"], j.get("candidate_required_location", "Remote"),
                j["url"], j.get("publication_date", "")[:10], j.get("salary", ""), ", ".join(j.get("tags", [])[:5]))
            for j in r.json().get("jobs", [])]


@st.cache_data(ttl=900, show_spinner=False)
def fetch_remoteok(q):
    r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    ql, out = q.lower(), []
    for j in r.json()[1:]:
        blob = f"{j.get('position','')} {' '.join(j.get('tags', []))} {j.get('company','')}".lower()
        if not ql or any(w in blob for w in ql.split()):
            sal = f"${j['salary_min']:,}-${j['salary_max']:,}" if j.get("salary_min") else ""
            out.append(row("RemoteOK", j.get("position", ""), j.get("company", ""), j.get("location") or "Remote",
                           j.get("url", ""), (j.get("date") or "")[:10], sal, ", ".join(j.get("tags", [])[:5])))
    return out


@st.cache_data(ttl=900, show_spinner=False)
def fetch_arbeitnow(q):
    r = requests.get("https://www.arbeitnow.com/api/job-board-api", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    ql, out = q.lower(), []
    for j in r.json().get("data", []):
        blob = f"{j.get('title','')} {' '.join(j.get('tags', []))} {j.get('company_name','')}".lower()
        if not ql or any(w in blob for w in ql.split()):
            out.append(row("Arbeitnow", j["title"], j["company_name"], j.get("location", ""), j["url"],
                           "", "", ", ".join(j.get("tags", [])[:5])))
    return out


@st.cache_data(ttl=900, show_spinner=False)
def fetch_jooble(q, loc, key):
    r = requests.post(f"https://jooble.org/api/{key}", json={"keywords": q, "location": loc},
                      headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return [row("Jooble", j["title"], j.get("company", ""), j.get("location", ""), j["link"],
                (j.get("updated") or "")[:10], j.get("salary", ""), j.get("type", ""))
            for j in r.json().get("jobs", [])]


@st.cache_data(ttl=900, show_spinner=False)
def fetch_freelancer(q, token):
    h = dict(HEADERS)
    if token:
        h["freelancer-oauth-v1"] = token
    r = requests.get("https://www.freelancer.com/api/projects/0.1/projects/active/",
                     params={"query": q, "limit": 30, "compact": "true", "job_details": "true"},
                     headers=h, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for p in r.json().get("result", {}).get("projects", []):
        b = p.get("budget", {}) or {}
        cur = (p.get("currency") or {}).get("sign", "$")
        sal = f"{cur}{b.get('minimum','?')}-{cur}{b.get('maximum','?')}"
        out.append(row("Freelancer", p.get("title", ""), "Client", "Remote",
                       f"https://www.freelancer.com/projects/{p.get('seo_url','')}", "", sal,
                       ", ".join(j["name"] for j in p.get("jobs", [])[:5])))
    return out


# ---------- Deep link (situs tanpa API publik / melarang scraping) ----------
def deep_links(q, loc):
    k, l = quote_plus(q), quote_plus(loc)
    return {
        "LinkedIn": f"https://www.linkedin.com/jobs/search/?keywords={k}&location={l}",
        "JobStreet": f"https://id.jobstreet.com/id/{quote_plus(q.replace(' ', '-'))}-jobs" + (f"/in-{quote_plus(loc.replace(' ', '-'))}" if loc else ""),
        "Indeed": f"https://id.indeed.com/jobs?q={k}&l={l}",
        "Glints": f"https://glints.com/id/opportunities/jobs/explore?keyword={k}",
        "Kalibrr": f"https://www.kalibrr.com/job-board/te/{quote_plus(q)}",
        "Upwork": f"https://www.upwork.com/nx/search/jobs/?q={k}&sort=recency",
        "Fiverr": f"https://www.fiverr.com/search/gigs?query={k}",
        "Google Jobs": f"https://www.google.com/search?q={k}+lowongan+{l}&ibp=htl;jobs",
    }


# ---------- UI ----------
st.title("💼 Job Hub")
st.caption("Cari lowongan kerja & proyek freelance dari banyak sumber dalam satu tempat.")

with st.sidebar:
    st.header("Pencarian")
    query = st.text_input("Kata kunci", "python developer")
    location = st.text_input("Lokasi (opsional)", "Indonesia")
    sources = st.multiselect(
        "Sumber API", ["Remotive", "RemoteOK", "Arbeitnow", "Jooble", "Freelancer"],
        default=["Remotive", "RemoteOK", "Freelancer"])
    jooble_key = st.text_input("Jooble API key", secret("JOOBLE_API_KEY"), type="password")
    fl_token = st.text_input("Freelancer OAuth token (opsional)", secret("FREELANCER_OAUTH_TOKEN"), type="password")
    go = st.button("🔍 Cari", type="primary", use_container_width=True)

st.subheader("🔗 Buka langsung di situs lain")
st.caption("LinkedIn, JobStreet, Indeed & Upwork tidak menyediakan API pencarian publik dan melarang scraping, "
           "jadi tombol ini membuka hasil pencarian resmi mereka dengan kata kunci Anda.")
links = deep_links(query, location)
cols = st.columns(4)
for i, (name, url) in enumerate(links.items()):
    cols[i % 4].link_button(name, url, use_container_width=True)

st.divider()
if go:
    results, errors = [], []
    jobs = {
        "Remotive": lambda: fetch_remotive(query),
        "RemoteOK": lambda: fetch_remoteok(query),
        "Arbeitnow": lambda: fetch_arbeitnow(query),
        "Jooble": lambda: fetch_jooble(query, location, jooble_key) if jooble_key else (_ for _ in ()).throw(ValueError("API key kosong")),
        "Freelancer": lambda: fetch_freelancer(query, fl_token),
    }
    with st.spinner("Mengambil data..."):
        for s in sources:
            try:
                results += jobs[s]()
            except Exception as e:
                errors.append(f"{s}: {e}")
    st.session_state["df"] = pd.DataFrame(results)
    for e in errors:
        st.warning(e)

df = st.session_state.get("df")
if df is not None:
    if df.empty:
        st.info("Tidak ada hasil. Coba kata kunci lain atau tambah sumber.")
    else:
        c1, c2 = st.columns([3, 1])
        text_filter = c1.text_input("Filter hasil (judul / perusahaan / tags)")
        src_filter = c2.multiselect("Sumber", sorted(df["Sumber"].unique()), default=sorted(df["Sumber"].unique()))
        view = df[df["Sumber"].isin(src_filter)]
        if text_filter:
            m = view[["Posisi", "Perusahaan", "Tags"]].astype(str).apply(
                lambda c: c.str.contains(text_filter, case=False)).any(axis=1)
            view = view[m]
        st.write(f"**{len(view)}** hasil")
        st.dataframe(view, use_container_width=True, hide_index=True,
                     column_config={"Link": st.column_config.LinkColumn("Link", display_text="Buka")})
        st.download_button("⬇️ Unduh CSV", view.to_csv(index=False).encode("utf-8"),
                           "lowongan.csv", "text/csv")
else:
    st.info("Isi kata kunci di sidebar lalu klik **Cari**.")
