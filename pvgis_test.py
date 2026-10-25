
from pvlib.iotools import get_pvgis_hourly

# K Blok koordinatlari
enlem = 40.995997
boylam = 29.065936

print("PVGIS'e baglaniliyor...")

# PVGIS'ten 2023 yilinin saatlik verilerini cek
veriler, bilgiler = get_pvgis_hourly(
    latitude=enlem,
    longitude=boylam,
    start=2023,
    end=2023,
    components=True,
    surface_tilt=0
)

print("\nBaglanti basarili!")
print("\nGelen veri sutunlari:")
print(veriler.columns.tolist())

print("\nIlk 5 saatlik veri:")
print(veriler[veriler["solar_elevation"] > 0].head(10))

import numpy as np

# PVGIS yatay yuzey verilerinden GHI ve DHI
veriler["GHI"] = veriler["poa_direct"] + veriler["poa_sky_diffuse"]
veriler["DHI"] = veriler["poa_sky_diffuse"]

# Yatay dogrudan isinimdan DNI hesaplama
sin_yukseklik = np.sin(np.radians(veriler["solar_elevation"]))

veriler["DNI"] = np.where(
    sin_yukseklik > 0.05,
    veriler["poa_direct"] / np.maximum(sin_yukseklik, 0.05),
    np.nan
)

print("\nGHI, DNI ve DHI (W/m2):")
print(veriler.loc[
    veriler["solar_elevation"] > 10,
    ["GHI", "DNI", "DHI"]
].head(10))

# PVGIS UTC saatlerini Turkiye saatine cevir
veriler["Turkiye_Saati"] = veriler.index.tz_convert("Europe/Istanbul")

print("\nPVGIS UTC ve Turkiye saatleri:")
print(
    veriler.loc[
        veriler["solar_elevation"] > 10,
        ["Turkiye_Saati", "GHI", "DNI", "DHI"]
    ].head(10).to_string()
)
