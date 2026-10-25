
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
# PVGIS verilerinin tarih ve saat bilgilerini ayır
veriler["Tarih"] = veriler["Turkiye_Saati"].dt.date
veriler["Saat"] = veriler["Turkiye_Saati"].dt.hour
veriler["Dakika"] = veriler["Turkiye_Saati"].dt.minute

print("\nPVGIS tarih ve saat kontrolu:")
print(
    veriler[["Turkiye_Saati", "Tarih", "Saat", "Dakika", "GHI", "DNI", "DHI"]]
    .head(10)
    .to_string()
)
# Dakika bazli gunes zamani testi
import math

def gunes_zamani_test(tarih, saat, dakika, boylam):
    n = tarih.timetuple().tm_yday
    B = math.radians(360 * (n - 1) / 365)

    E = 229.2 * (
        0.000075
        + 0.001868 * math.cos(B)
        - 0.032077 * math.sin(B)
        - 0.014615 * math.cos(2 * B)
        - 0.04089 * math.sin(2 * B)
    )

    zaman_duzeltmesi = 4 * (boylam - 45) + E
    return saat + dakika / 60 + zaman_duzeltmesi / 60

ilk_kayit = veriler.iloc[0]

tarih = ilk_kayit["Tarih"]
saat = int(ilk_kayit["Saat"])
dakika = int(ilk_kayit["Dakika"])

print("\nDakika bazli hesaplama testi:")
print("PVGIS saati:", ilk_kayit["Turkiye_Saati"])
print("Hesaplanan gunes saati:",
      gunes_zamani_test(tarih, saat, dakika, boylam))
# PVGIS saatlerine gore zenit ve gunes yuksekligi hesabi
from datetime import date

def deklinasyon_test(tarih):
    n = tarih.timetuple().tm_yday
    return 23.45 * math.sin(math.radians(360 * (284 + n) / 365))

def zenit_test(enlem, delta, omega):
    phi = math.radians(enlem)
    delta = math.radians(delta)
    omega = math.radians(omega)

    cos_zenit = (
        math.sin(phi) * math.sin(delta)
        + math.cos(phi) * math.cos(delta) * math.cos(omega)
    )
    cos_zenit = max(-1, min(1, cos_zenit))
    return math.degrees(math.acos(cos_zenit))

# Gunesin gorundugu ilk 5 PVGIS kaydi
test_verileri = veriler[veriler["solar_elevation"] > 10].head(5)

print("\nPVGIS saatlerinde gunes acilari:")

for _, satir in test_verileri.iterrows():
    tarih = satir["Tarih"]
    saat = int(satir["Saat"])
    dakika = int(satir["Dakika"])

    gunes_saati = gunes_zamani_test(tarih, saat, dakika, boylam)
    omega = 15 * (gunes_saati - 12)
    delta = deklinasyon_test(tarih)
    zenit = zenit_test(enlem, delta, omega)
    yukseklik = 90 - zenit

    print(
        f"{saat:02d}:{dakika:02d} | "
        f"Zenit: {zenit:.2f}° | "
        f"Yukseklik: {yukseklik:.2f}° | "
        f"PVGIS yukseklik: {satir['solar_elevation']:.2f}°"
    )
# PVGIS saatlerinde gunes azimut acisi hesabi
def gunes_azimutu_test(enlem, delta, omega, zenit):
    phi = math.radians(enlem)
    delta_rad = math.radians(delta)
    zenit_rad = math.radians(zenit)

    pay = math.cos(zenit_rad) * math.sin(phi) - math.sin(delta_rad)
    payda = math.sin(zenit_rad) * math.cos(phi)

    if abs(payda) < 1e-10:
        return None

    oran = max(-1, min(1, pay / payda))
    aci = math.degrees(math.acos(oran))

    omega = (omega + 180) % 360 - 180
    return -aci if omega < 0 else aci


print("\nPVGIS saatlerinde gunes azimut acilari:")

for _, satir in test_verileri.iterrows():
    tarih = satir["Tarih"]
    saat = int(satir["Saat"])
    dakika = int(satir["Dakika"])

    gunes_saati = gunes_zamani_test(tarih, saat, dakika, boylam)
    omega = 15 * (gunes_saati - 12)
    delta = deklinasyon_test(tarih)
    zenit = zenit_test(enlem, delta, omega)

    azimut = gunes_azimutu_test(enlem, delta, omega, zenit)

    print(f"{saat:02d}:{dakika:02d} | Gunes azimutu: {azimut:.2f}°")

# K Blok dört cepheye güneş geliş açısı hesabı
cephe_yonleri = {
    "Kuzeydoğu": 23.81,
    "Güneydoğu": 114.79,
    "Güneybatı": 201.95,
    "Kuzeybatı": 291.12
}

print("\nPVGIS saatlerinde dört cephe geliş açıları:")

for _, satir in test_verileri.iterrows():
    tarih = satir["Tarih"]
    saat = int(satir["Saat"])
    dakika = int(satir["Dakika"])

    gunes_saati = gunes_zamani_test(tarih, saat, dakika, boylam)
    omega = 15 * (gunes_saati - 12)
    delta = deklinasyon_test(tarih)
    zenit = zenit_test(enlem, delta, omega)
    yukseklik = 90 - zenit
    azimut = gunes_azimutu_test(enlem, delta, omega, zenit)

    print(f"\n{saat:02d}:{dakika:02d}")

    for cephe, cephe_azimutu in cephe_yonleri.items():
        cos_gelis = (
            math.cos(math.radians(yukseklik))
            * math.cos(math.radians(azimut + 180 - cephe_azimutu))
        )
        cos_gelis = max(-1, min(1, cos_gelis))
        gelis_acisi = math.degrees(math.acos(cos_gelis))

        print(f"{cephe}: {gelis_acisi:.2f}°")
# Dört cephe için saatlik güneş ışınımı hesabı
# Duffie, Beckman ve Blair - İzotropik gökyüzü modeli

albedo = 0.20  # Zemin yansıtma katsayısı (varsayım)

print("\nPVGIS saatlerinde dört cephe ışınımı (W/m2):")

for _, satir in test_verileri.iterrows():
    tarih = satir["Tarih"]
    saat = int(satir["Saat"])
    dakika = int(satir["Dakika"])

    gunes_saati = gunes_zamani_test(tarih, saat, dakika, boylam)
    omega = 15 * (gunes_saati - 12)
    delta = deklinasyon_test(tarih)
    zenit = zenit_test(enlem, delta, omega)
    yukseklik = 90 - zenit
    azimut = gunes_azimutu_test(enlem, delta, omega, zenit)

    GHI = float(satir["GHI"])
    DNI = float(satir["DNI"])
    DHI = float(satir["DHI"])

    print(f"\n{saat:02d}:{dakika:02d}")

    for cephe, cephe_azimutu in cephe_yonleri.items():
        cos_gelis = (
            math.cos(math.radians(yukseklik))
            * math.cos(math.radians(azimut + 180 - cephe_azimutu))
        )

        # Doğrudan ışınım yalnızca güneşe bakan cepheye gelir
        dogrudan = DNI * max(0, cos_gelis)

        # Düşey cephe için yayılı ve yerden yansıyan ışınım
        yayili = DHI / 2
        yansiyan = GHI * albedo / 2

        toplam = dogrudan + yayili + yansiyan

        print(f"{cephe}: {toplam:.2f} W/m2")
# PVGIS ile guneydogu cephe isinimi karsilastirma testi
pvgis_guneydogu, bilgi_guneydogu = get_pvgis_hourly(
    latitude=enlem,
    longitude=boylam,
    start=2023,
    end=2023,
    components=True,
    surface_tilt=90,
    surface_azimuth=114.79
)

pvgis_guneydogu["Toplam_Isinim"] = (
    pvgis_guneydogu["poa_direct"]
    + pvgis_guneydogu["poa_sky_diffuse"]
    + pvgis_guneydogu["poa_ground_diffuse"]
)

print("\nPVGIS guneydogu cephe isinimi (W/m2):")

print(
    pvgis_guneydogu.loc[
        pvgis_guneydogu.index.isin(test_verileri.index),
        ["Toplam_Isinim"]
    ].to_string()
)
# Guneydogu cephesi isinim bilesenlerini karsilastir
satir = test_verileri.iloc[1]  # 11:10 Turkiye saati
zaman = satir.name

tarih = satir["Tarih"]
saat = int(satir["Saat"])
dakika = int(satir["Dakika"])

gunes_saati = gunes_zamani_test(tarih, saat, dakika, boylam)
omega = 15 * (gunes_saati - 12)
delta = deklinasyon_test(tarih)
zenit = zenit_test(enlem, delta, omega)
yukseklik = 90 - zenit
azimut = gunes_azimutu_test(enlem, delta, omega, zenit)

cos_gelis = (
    math.cos(math.radians(yukseklik))
    * math.cos(math.radians(azimut + 180 - 114.79))
)

bizim_dogrudan = float(satir["DNI"]) * max(0, cos_gelis)
bizim_yayili = float(satir["DHI"]) / 2
bizim_yansiyan = float(satir["GHI"]) * 0.20 / 2

pv = pvgis_guneydogu.loc[zaman]

print("\n11:10 Guneydogu bilesen karsilastirmasi (W/m2)")
print("Bilesen       Bizim      PVGIS")
print(f"Dogrudan      {bizim_dogrudan:.2f}      {pv['poa_direct']:.2f}")
print(f"Yayili        {bizim_yayili:.2f}      {pv['poa_sky_diffuse']:.2f}")
print(f"Yansiyan      {bizim_yansiyan:.2f}      {pv['poa_ground_diffuse']:.2f}")
# Kuzeydogu cephesi - PVGIS karsilastirmasi
pvgis_kuzeydogu, bilgi_kuzeydogu = get_pvgis_hourly(
    latitude=enlem,
    longitude=boylam,
    start=2023,
    end=2023,
    components=True,
    surface_tilt=90,
    surface_azimuth=23.81
)

pvgis_kuzeydogu["Toplam_Isinim"] = (
    pvgis_kuzeydogu["poa_direct"]
    + pvgis_kuzeydogu["poa_sky_diffuse"]
    + pvgis_kuzeydogu["poa_ground_diffuse"]
)

print("\nPVGIS Kuzeydogu cephe isinimi (W/m2):")

print(
    pvgis_kuzeydogu.loc[
        pvgis_kuzeydogu.index.isin(test_verileri.index),
        ["Toplam_Isinim"]
    ].to_string()
)
# Guneybati cephesi - PVGIS karsilastirmasi
pvgis_guneybati, bilgi_guneybati = get_pvgis_hourly(
    latitude=enlem,
    longitude=boylam,
    start=2023,
    end=2023,
    components=True,
    surface_tilt=90,
    surface_azimuth=201.95
)

pvgis_guneybati["Toplam_Isinim"] = (
    pvgis_guneybati["poa_direct"]
    + pvgis_guneybati["poa_sky_diffuse"]
    + pvgis_guneybati["poa_ground_diffuse"]
)

print("\nPVGIS Guneybati cephe isinimi (W/m2):")

print(
    pvgis_guneybati.loc[
        pvgis_guneybati.index.isin(test_verileri.index),
        ["Toplam_Isinim"]
    ].to_string()
)
# Kuzeybati cephesi - PVGIS karsilastirmasi
pvgis_kuzeybati, bilgi_kuzeybati = get_pvgis_hourly(
    latitude=enlem,
    longitude=boylam,
    start=2023,
    end=2023,
    components=True,
    surface_tilt=90,
    surface_azimuth=291.12
)

pvgis_kuzeybati["Toplam_Isinim"] = (
    pvgis_kuzeybati["poa_direct"]
    + pvgis_kuzeybati["poa_sky_diffuse"]
    + pvgis_kuzeybati["poa_ground_diffuse"]
)

print("\nPVGIS Kuzeybati cephe isinimi (W/m2):")

print(
    pvgis_kuzeybati.loc[
        pvgis_kuzeybati.index.isin(test_verileri.index),
        ["Toplam_Isinim"]
    ].to_string()
)
# Kuzey cephelerinde yansiyan isinim farkini incele

satir = test_verileri.iloc[1]  # 11:10

GHI = float(satir["GHI"])
DHI = float(satir["DHI"])

pv_kd = pvgis_kuzeydogu.loc[satir.name]
pv_kb = pvgis_kuzeybati.loc[satir.name]

print("\nYANSIYAN ISINIM KONTROLU - 11:10")
print(f"GHI: {GHI:.2f} W/m2")
print(f"DHI: {DHI:.2f} W/m2")

print(f"Bizim GHI tabanli hesabimiz: {GHI * 0.20 / 2:.2f}")
print(f"DHI tabanli kontrol degeri: {DHI * 0.20 / 2:.2f}")

print(f"PVGIS Kuzeydogu: {pv_kd['poa_ground_diffuse']:.2f}")
print(f"PVGIS Kuzeybati: {pv_kb['poa_ground_diffuse']:.2f}")
print("\nKUZEY CEPHELERI YANSIMA KONTROLU")

for _, satir in test_verileri.iterrows():
    saat = int(satir["Saat"])
    dakika = int(satir["Dakika"])

    dhi_kontrol = float(satir["DHI"]) * 0.20 / 2
    pv_yansiyan = float(
        pvgis_kuzeydogu.loc[satir.name, "poa_ground_diffuse"]
    )

    print(
        f"{saat:02d}:{dakika:02d} | "
        f"DHI kontrol: {dhi_kontrol:.2f} | "
        f"PVGIS: {pv_yansiyan:.2f}"
    )