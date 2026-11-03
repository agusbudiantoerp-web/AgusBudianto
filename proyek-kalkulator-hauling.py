#!/usr/bin/env python3
"""
Kalkulator Biaya & Margin Hauling Tambang
Rumus mengikuti lembar Excel asli.

Cara pakai:
  python kalkulator_hauling.py              -> mode interaktif (Enter = nilai default)
  python kalkulator_hauling.py --default    -> langsung hitung dengan data contoh
  python kalkulator_hauling.py --muatan 32 --jarak 45 --harga-fuel 21000
"""
import argparse
from dataclasses import dataclass, asdict


@dataclass
class Input:
    harga_fuel: float = 20_000      # Rp/liter
    muatan: float = 30.0            # ton
    jarak: float = 50.0             # km (satu arah)
    fuel_consumption: float = 18.0  # liter/jam
    waktu_pp: float = 4.0           # jam (pergi-pulang)
    cost_unit_jam: float = 270_000  # Rp/jam
    harga_kontrak: float = 2_200    # Rp/ton/km
    salary_driver_jam: float = 35_000  # Rp/jam
    fix_cost_pct: float = 12.0      # % dari revenue


@dataclass
class Hasil:
    fuel_ratio: float       # liter/ton/km
    revenue: float          # Rp/ret
    solar: float
    unit: float
    driver: float
    total_cost: float
    margin_kotor: float
    profit_kotor_pct: float  # fraksi (0.194 = 19.4%)
    fix_cost_pct: float
    profit_bersih_pct: float
    bep_harga_kontrak: float  # tambahan: Rp/ton/km titik impas
    biaya_per_ton: float      # tambahan: Rp/ton


def hitung(d: Input) -> Hasil:
    ton_km = d.muatan * d.jarak
    fuel_ratio = (d.fuel_consumption * d.waktu_pp) / ton_km
    revenue = ton_km * d.harga_kontrak
    solar = fuel_ratio * ton_km * d.harga_fuel
    unit = d.cost_unit_jam * d.waktu_pp
    driver = d.salary_driver_jam * d.waktu_pp
    total = solar + unit + driver
    margin = revenue - total
    gp = margin / revenue if revenue else 0.0
    fix = d.fix_cost_pct / 100
    np_ = gp - fix
    bep = total / (1 - fix) / ton_km if fix < 1 else float("nan")
    return Hasil(fuel_ratio, revenue, solar, unit, driver, total, margin,
                 gp, fix, np_, bep, total / d.muatan)


def rp(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def cetak(d: Input, h: Hasil) -> None:
    garis = "-" * 52
    print(f"\n{'HASIL PERHITUNGAN HAULING':^52}\n{garis}")
    print(f"{'Fuel ratio':<26}: {h.fuel_ratio:>12.4f} Liter/Ton/Km")
    print(f"{'Pendapatan/Revenue':<26}: {rp(h.revenue):>12} Rp/Ret")
    print("Pengeluaran")
    print(f"{'  Solar':<26}: {rp(h.solar):>12} Rp/Ret")
    print(f"{'  Unit':<26}: {rp(h.unit):>12} Rp/Ret")
    print(f"{'  Driver':<26}: {rp(h.driver):>12} Rp/Ret")
    print(f"{'Total Cost':<26}: {rp(h.total_cost):>12} Rp/Ret")
    print(f"{'Margin Kotor':<26}: {rp(h.margin_kotor):>12} Rp/Ret")
    print(f"{'% Profit Kotor':<26}: {h.profit_kotor_pct * 100:>11.1f}%")
    print(f"{'Fix Cost':<26}: {h.fix_cost_pct * 100:>11.0f}%")
    print(f"{'% Profit Bersih':<26}: {h.profit_bersih_pct * 100:>11.1f}%")
    print(garis)
    print(f"{'BEP harga kontrak':<26}: {rp(h.bep_harga_kontrak):>12} Rp/Ton/Km")
    print(f"{'Biaya per ton':<26}: {rp(h.biaya_per_ton):>12} Rp/Ton\n")


LABEL = {
    "harga_fuel": "Harga Fuel (Rp/liter)",
    "muatan": "Muatan (ton)",
    "jarak": "Jarak Hauling (km)",
    "fuel_consumption": "Fuel Consumption (liter/jam)",
    "waktu_pp": "Estimasi waktu tempuh PP (jam)",
    "cost_unit_jam": "Cost Unit/Jam (Rp/jam)",
    "harga_kontrak": "Harga Kontrak (Rp/ton/km)",
    "salary_driver_jam": "Salary Driver (Rp/jam)",
    "fix_cost_pct": "Fix Cost (% revenue)",
}


def interaktif() -> Input:
    d = Input()
    print("Masukkan data (tekan Enter untuk memakai nilai di dalam kurung).")
    for k, label in LABEL.items():
        while True:
            s = input(f"{label} [{getattr(d, k):g}]: ").strip()
            if not s:
                break
            try:
                setattr(d, k, float(s.replace(",", ".")))
                break
            except ValueError:
                print("  Masukkan angka yang valid.")
    return d


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--default", action="store_true", help="pakai data contoh")
    for k in LABEL:
        p.add_argument("--" + k.replace("_", "-"), type=float)
    a = p.parse_args()

    overrides = {k: getattr(a, k) for k in LABEL if getattr(a, k) is not None}
    if overrides or a.default:
        d = Input(**overrides)
    else:
        d = interaktif()

    if d.muatan <= 0 or d.jarak <= 0 or d.waktu_pp < 0:
        raise SystemExit("Muatan dan jarak harus lebih dari 0.")
    cetak(d, hitung(d))


if __name__ == "__main__":
    main()
