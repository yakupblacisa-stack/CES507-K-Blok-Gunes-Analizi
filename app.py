
import streamlit as st
import math
from datetime import timedelta
import pvlib
from pvlib.iotools import get_pvgis_hourly
import pandas as pd
import altair as alt
import numpy as np
import plotly.graph_objects as go
import io
from shapely.geometry import Polygon, Point
from shapely.affinity import translate
from shapely.ops import unary_union
import xml.etree.ElementTree as ET


# 3. Aşama - Gölge analizi için yerel koordinat dönüşümü
def koordinat_metreye(enlem, boylam):
    referans_enlem = 40.995997
    referans_boylam = 29.065936

    x = (
        (boylam - referans_boylam)
        * 111320
        * math.cos(math.radians(referans_enlem))
    )

    y = (enlem - referans_enlem) * 111320

    return x, y

# KML dosyasındaki bina sınırlarını Shapely poligonlarına dönüştür
def kml_poligonlarini_oku(dosya_yolu):
    agac = ET.parse(dosya_yolu)
    kok = agac.getroot()

    poligonlar = {}

    for yer in kok.findall(".//{*}Placemark"):
        ad = yer.find("{*}name")
        koordinatlar = yer.find(
            ".//{*}outerBoundaryIs/{*}LinearRing/{*}coordinates"
        )

        if ad is None or koordinatlar is None:
            continue

        noktalar = []

        for nokta in koordinatlar.text.strip().split():
            boylam, enlem = map(float, nokta.split(",")[:2])
            x, y = koordinat_metreye(enlem, boylam)
            noktalar.append((x, y))

        if len(noktalar) >= 3:
            poligonlar[ad.text.strip()] = Polygon(noktalar)

    return poligonlar


# K Blok ve 5 komşu binanın gerçek sınırlarını yükle
bina_poligonlari = kml_poligonlarini_oku("KBlok_Tum_Binalar_TAM.kml")

print("Yüklenen poligon sayısı:", len(bina_poligonlari))
print("Poligon isimleri:", list(bina_poligonlari.keys()))

# Bina sınırlarından zemin üzerindeki gölge alanını hesapla
def golge_alani_hesapla(bina_poligonu, bina_yuksekligi,
                       gunes_yuksekligi, golge_azimutu,
                       alici_yuksekligi=0.0):

    if gunes_yuksekligi <= 0:
        return Polygon()

    
    yukseklik_farki = bina_yuksekligi - alici_yuksekligi

    if yukseklik_farki <= 0:
        return Polygon()

    golge_uzunlugu = yukseklik_farki / math.tan(
        math.radians(gunes_yuksekligi)
    )


    dx = golge_uzunlugu * math.sin(
        math.radians(golge_azimutu)
    )
    dy = golge_uzunlugu * math.cos(
        math.radians(golge_azimutu)
    )

    kaydirilmis_poligon = translate(
        bina_poligonu, xoff=dx, yoff=dy
    )

    parcalar = [bina_poligonu, kaydirilmis_poligon]
    kose_noktalari = list(bina_poligonu.exterior.coords)

    for i in range(len(kose_noktalari) - 1):
        x1, y1 = kose_noktalari[i]
        x2, y2 = kose_noktalari[i + 1]

        golge_parcasi = Polygon([
            (x1, y1),
            (x2, y2),
            (x2 + dx, y2 + dy),
            (x1 + dx, y1 + dy)
        ])

        parcalar.append(golge_parcasi)

    return unary_union(parcalar)


# Duffie ve Beckman - Denklem 1.6.1a
def deklinasyon_hesapla(tarih):
    n = tarih.timetuple().tm_yday

    delta = 23.45 * math.sin(
        math.radians(360 * (284 + n) / 365)
    )

    return delta

    # Duffie ve Beckman - Denklem 1.5.2 ve 1.5.3
def gunes_zamani_hesapla(tarih, saat, boylam, dakika=0):
    n = tarih.timetuple().tm_yday

    B = math.radians(360 * (n - 1) / 365)

    E = 229.2 * (
        0.000075
        + 0.001868 * math.cos(B)
        - 0.032077 * math.sin(B)
        - 0.014615 * math.cos(2 * B)
        - 0.04089 * math.sin(2 * B)
    )

    # Türkiye: UTC+3, standart meridyen 45 derece doğu
    zaman_duzeltmesi = 4 * (boylam - 45) + E

    gunes_saati = saat + dakika / 60 + zaman_duzeltmesi / 60

    return gunes_saati

# Duffie ve Beckman - Saat açısı
def saat_acisi_hesapla(gunes_saati):
    omega = 15 * (gunes_saati - 12)
    return omega
# Duffie ve Beckman - Denklem 1.6.5
def zenit_acisi_hesapla(enlem, delta, omega):
    phi = math.radians(enlem)
    delta_rad = math.radians(delta)
    omega_rad = math.radians(omega)

    cos_zenit = (
        math.sin(phi) * math.sin(delta_rad)
        + math.cos(phi) * math.cos(delta_rad) * math.cos(omega_rad)
    )

    cos_zenit = max(-1, min(1, cos_zenit))

    zenit = math.degrees(math.acos(cos_zenit))

    return zenit
# pvlib ile güneş konumu hesaplama
def pvlib_gunes_konumu(tarih, saat, enlem, boylam):

    zaman = pd.DatetimeIndex([
        pd.Timestamp(tarih) + pd.Timedelta(hours=saat)
    ]).tz_localize("Europe/Istanbul")

    konum = pvlib.solarposition.get_solarposition(
        zaman,
        latitude=enlem,
        longitude=boylam
    )

    zenit = float(konum["zenith"].iloc[0])
    yukseklik = float(konum["elevation"].iloc[0])

    # pvlib: kuzey 0° → Kitap: güney 0°
    azimut = float(konum["azimuth"].iloc[0]) - 180

    return zenit, yukseklik, azimut

# Duffie ve Beckman - Güneş yüksekliği açısı
def gunes_yuksekligi_hesapla(zenit):
    alfa = 90 - zenit
    
    return alfa

# Duffie ve Beckman - Denklem 1.6.6
# Güney 0°, doğu negatif, batı pozitif

def gunes_azimutu_hesapla(enlem, delta, omega, zenit):
    phi = math.radians(enlem)
    delta_rad = math.radians(delta)
    zenit_rad = math.radians(zenit)

    pay = (
        math.cos(zenit_rad) * math.sin(phi)
        - math.sin(delta_rad)
    )

    payda = math.sin(zenit_rad) * math.cos(phi)

    if abs(payda) < 1e-10:
        return None

    oran = max(-1, min(1, pay / payda))

    aci = math.degrees(math.acos(oran))

    omega = (omega + 180) % 360 - 180

    if omega < 0:
        azimut = -aci
    else:
        azimut = aci

    return azimut

def cephe_gelis_acisi_hesapla(gunes_yuksekligi, gunes_azimutu, cephe_azimutu):
    alpha = math.radians(gunes_yuksekligi)
    gamma_s = math.radians(gunes_azimutu + 180)
    gamma_c = math.radians(cephe_azimutu)

    cos_theta = math.cos(alpha) * math.cos(gamma_s - gamma_c)
    cos_theta = max(-1.0, min(1.0, cos_theta))

    return math.degrees(math.acos(cos_theta))

# K Blok cephe yönleri (Google Earth ölçümüne göre)
cephe_yonleri = {
    "Kuzeydoğu": 23.81,
    "Güneydoğu": 114.79,
    "Güneybatı": 201.95,
    "Kuzeybatı": 291.12
}

def pvlib_cephe_gelis_acisi_hesapla(zenit, azimut, cephe_azimutu):
    return float(
        pvlib.irradiance.aoi(
            surface_tilt=90,
            surface_azimuth=cephe_azimutu,
            solar_zenith=zenit,
            solar_azimuth=azimut % 360
        )
    )

st.set_page_config(page_title="K Blok Güneş Analizi", layout="wide")
st.markdown("""
<style>
/* Genel arka plan */
.stApp {
    background-color: #0F172A;
    color: #F8FAFC;
}

/* Ana başlıklar */
h1, h2, h3 {
    color: #FACC15 !important;
}

/* Normal metinler */
p, label {
    color: #E2E8F0;
}

/* Butonlar */
.stButton > button {
    background-color: #FACC15;
    color: #0F172A !important;
    border: none;
    border-radius: 10px;
    font-weight: 700;
}
.stButton > button p {
    color: #0F172A !important;
}
.stButton > button:hover {
    background-color: #FDE047;
    color: #0F172A;
}

/* Yan menü */
[data-testid="stSidebar"] {
    background-color: #172554;
}

/* Veri tabloları */
[data-testid="stDataFrame"] {
    border: 1px solid #334155;
    border-radius: 10px;
}
/* Sekme başlıkları */
[role="tablist"] {
    display: flex !important;
    gap: 8px !important;
}

/* Sekme kutuları */
[role="tab"] {
    flex: 1 !important;
    background: #082447 !important;
    border: 1px solid #164675 !important;
    border-radius: 7px !important;
    min-height: 50px !important;
    padding: 12px 18px !important;
    color: #CBD5E1 !important;
}

/* Sekme yazıları */
[role="tab"] p {
    font-size: 18px !important;
    font-weight: 700 !important;
}

/* Aktif sekme */
[role="tab"][aria-selected="true"] {
    background: #102F4B !important;
    border: 2px solid #FACC15 !important;
    color: #FACC15 !important;
}

/* Alt çizgi */
[role="tab"] .react-aria-SelectionIndicator {
    display: none !important;
}
/* Dört cephe seçim butonu */
div[data-testid="stSegmentedControl"] [data-baseweb="button-group"] { {
    display: flex !important;
    width: 100% !important;
    gap: 8px !important;
}

div[data-testid="stSegmentedControl"] [role="radio"] {
    flex: 1 !important;
    min-height: 48px !important;
    background: #102440 !important;
    border: 1px solid #24517A !important;
    border-radius: 7px !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}

div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"] {
    background: #17354F !important;
    border: 2px solid #FACC15 !important;
    color: #FACC15 !important;
}

div[data-testid="stSegmentedControl"] [role="radio"] p {
    color: inherit !important;
    font-size: 16px !important;
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)
st.title("☀️ K Blok Güneş Enerjisi Analiz Paneli")

st.write("Güneş açısı hesaplama uygulamasına hoş geldiniz.")
st.markdown("### 📍 Konum ve Tarih Seçimi")
col1, col2, tarih_col, buton_col = st.columns([1, 1, 1.5, 1])

with col1:
    enlem = st.number_input("📍 Enlem", value=40.995997, format="%.6f")

with col2:
    boylam = st.number_input("🧭 Boylam", value=29.065936, format="%.6f")

with tarih_col:
    tarih_araligi = st.date_input(
        "📅 Hesaplama Tarih Aralığı",
        value=()
    )
    if "hesaplama_yapildi" not in st.session_state:
     st.session_state.hesaplama_yapildi = False

with buton_col:
    st.markdown("<div style='height: 27px'></div>", unsafe_allow_html=True)
    hesapla = st.button(
        "☀️ Güneş Açılarını Hesapla",
        use_container_width=True
    )
    # Ana analiz kademeleri
kademe1, kademe2,kademe3 = st.tabs([
    "☀️ 1. Kademe: Güneş Açıları",
    "📊 2. Kademe: Işınım Karşılaştırması",
    "🌳 3. Kademe: Gölge Analizi"
])

if hesapla:
    st.session_state.hesaplama_yapildi = True

if st.session_state.hesaplama_yapildi:

    if len(tarih_araligi) != 2:
        st.warning("Lütfen başlangıç ve bitiş tarihlerini seçin.")

    else:
        baslangic, bitis = tarih_araligi
        sonuclar = []
        pvgis_verileri = pd.DataFrame()
        # Secilen tarih araligi icin PVGIS verilerini al

        
        try:
            with st.spinner("PVGIS verileri aliniyor..."):

                yillik_veriler = []

                for yil in range(baslangic.year, bitis.year + 1):

                    veri, bilgi = get_pvgis_hourly(
                        latitude=enlem,
                        longitude=boylam,
                        start=yil,
                        end=yil,
                        components=True,
                        surface_tilt=0
                    )

                    yillik_veriler.append(veri)

                pvgis_verileri = pd.concat(yillik_veriler)

                # UTC saatlerini Turkiye saatine cevir
                pvgis_verileri.index = (
                    pvgis_verileri.index.tz_convert("Europe/Istanbul")
                )

                # Yalnizca secilen tarihleri tut
                pvgis_verileri = pvgis_verileri[
                    (pvgis_verileri.index.date >= baslangic)
                    & (pvgis_verileri.index.date <= bitis)
                ]

            st.success("PVGIS verileri basariyla alindi!")

        except Exception as hata:
            st.warning(f"PVGIS verileri alinamadi: {hata}")

        gun = baslangic

        while gun <= bitis:
            delta = deklinasyon_hesapla(gun)

            for saat in range(24):
                gunes_saati = gunes_zamani_hesapla(gun, saat, boylam)
                omega = saat_acisi_hesapla(gunes_saati)
                zenit = zenit_acisi_hesapla(enlem, delta, omega)
                alfa = gunes_yuksekligi_hesapla(zenit)
                azimut = gunes_azimutu_hesapla(enlem, delta, omega, zenit)
                pv_zenit, pv_yukseklik, pv_azimut = pvlib_gunes_konumu(
                gun, saat, enlem, boylam)
                if alfa > 0:
                 gunes_durumu = "☀️ Gündüz"
                elif alfa < 0:
                 gunes_durumu = "🌙 Gece"
                else:
                 gunes_durumu = "🌅 Ufukta"
                 
                cephe_acilari = {}

                for cephe_adi, cephe_azimutu in cephe_yonleri.items():
                        cephe_acilari[f"{cephe_adi} Geliş Açısı (°)"] = round(
                            cephe_gelis_acisi_hesapla(alfa, azimut, cephe_azimutu), 2
                        ) if azimut is not None and alfa > 0 else None

                        cephe_acilari[f"pvlib {cephe_adi} Geliş Açısı (°)"] = round(
                            pvlib_cephe_gelis_acisi_hesapla(
                                pv_zenit, pv_azimut + 180, cephe_azimutu
                            ), 2
                        ) if pv_yukseklik > 0 else None
                        
                        bizim_aci = cephe_acilari[f"{cephe_adi} Geliş Açısı (°)"]
                        pvlib_aci = cephe_acilari[f"pvlib {cephe_adi} Geliş Açısı (°)"]

                        cephe_acilari[f"{cephe_adi} Fark (°)"] = (
                            round(abs(bizim_aci - pvlib_aci), 2)
                            if bizim_aci is not None and pvlib_aci is not None
                            else None
                        )


                sonuclar.append({
                    "Tarih": gun,
                    "Saat (Türkiye)": f"{saat:02d}:00",
                    "Deklinasyon Açısı (δ)": round(delta, 2),
                    "Saat Açısı (ω)": round(omega, 2),
                    "Zenit Açısı (θz)": round(zenit, 2),
                    "pvlib Zenit Açısı (θz)": round(pv_zenit, 2),
                    "Zenit Farkı (°)": round(abs(zenit - pv_zenit), 2),
                    "Güneş Yüksekliği (α)": round(alfa, 2),
                    "pvlib Güneş Yüksekliği (α)": round(pv_yukseklik, 2),
                    "Yükseklik Farkı (°)": round(abs(alfa - pv_yukseklik), 2),
                    "Güneş Azimut Açısı (γs)": round(azimut, 2) if azimut is not None else None,
                    "pvlib Güneş Azimut Açısı (γs)": round(pv_azimut, 2),
                    "Azimut Farkı (°)": round(abs((azimut - pv_azimut + 180) % 360 - 180), 2) if azimut is not None else None,
                    "Güneş Durumu": gunes_durumu,
                    **cephe_acilari
                })

            gun += timedelta(days=1)

        st.success("Seçilen tarih aralığı hesaplandı!")
        with kademe1:
                    # GRAFİKLER
            st.markdown("### 📈 Güneş Açısı Grafikleri")

            tablo = pd.DataFrame(sonuclar)
            grafik_verisi = tablo.copy()

            grafik_verisi["TarihSaat"] = pd.to_datetime(
                grafik_verisi["Tarih"].astype(str)
                + " "
                + grafik_verisi["Saat (Türkiye)"]
            )

            grafik_verisi = grafik_verisi.set_index("TarihSaat")

            ortak_tab, zenit_tab, yukseklik_tab, azimut_tab = st.tabs([
                "📋 Ortak Güneş Parametreleri",
                "☀️ Zenit Açısı",
                "📈 Güneş Yüksekliği",
                "🧭 Güneş Azimutu"
            ])
            with ortak_tab:
                st.markdown("#### 📊 Ortak Güneş Parametreleri")

                ortak_tablo = tablo[[
                    "Tarih",
                    "Saat (Türkiye)",
                    "Deklinasyon Açısı (δ)",
                    "Saat Açısı (ω)"
                ]].copy()

                ortak_html = ortak_tablo.to_html(
                    index=False,
                    float_format=lambda x: f"{x:.2f}",
                    classes="gunes-tablosu"
                )

                st.markdown(
                    '<div class="tablo-alani">' + ortak_html + '</div>',
                    unsafe_allow_html=True
                )
            
            with zenit_tab:
                zenit_verisi = grafik_verisi[[
                    "Zenit Açısı (θz)",
                    "pvlib Zenit Açısı (θz)"
                ]].reset_index()

                zenit_verisi = zenit_verisi.melt(
                    id_vars="TarihSaat",
                    var_name="Kaynak",
                    value_name="Açı"
                )

                zenit_verisi["Kaynak"] = zenit_verisi["Kaynak"].replace({
                    "Zenit Açısı (θz)": "Hesaplanan Zenit Açısı (θz)",
                    "pvlib Zenit Açısı (θz)": "pvlib Zenit Açısı (θz)"
                })

                zenit_grafik = (
                    alt.Chart(zenit_verisi)
                    .mark_line()
                    .encode(
                        x=alt.X(
                            "TarihSaat:T",
                            title="Tarih / Saat",
                           axis=alt.Axis(
                                format="%d.%m",
                                labelColor="#FFFFFF",
                                tickCount="day",
                                labelAngle=0,
                                grid=False
                            )
                        ),
                        y=alt.Y(
                            "Açı:Q",
                            title="Zenit Açısı (°)",
                            axis=alt.Axis(labelColor="#FFFFFF")
                        ),
                        color=alt.Color(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Zenit Açısı (θz)", "pvlib Zenit Açısı (θz)"],
                                range=["#EF4444", "#38BDF8"]
                            ),
                            legend=alt.Legend(
                                title=None,
                                labelColor="#FFFFFF",
                                orient="bottom"
                            )
                        ),
                        strokeDash=alt.StrokeDash(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Zenit Açısı (θz)", "pvlib Zenit Açısı (θz)"],
                                range=[[1, 0], [6, 4]]
                            ),
                            legend=None
                        ),
                        size=alt.Size(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Zenit Açısı (θz)", "pvlib Zenit Açısı (θz)"],
                                range=[4, 2]
                            ),
                            legend=None
                        ),
                        tooltip=[
                            alt.Tooltip(
                                "TarihSaat:T",
                                title="Tarih",
                                format="%d.%m.%Y %H:%M"
                            ),
                            alt.Tooltip("Kaynak:N", title="Hesaplama"),
                            alt.Tooltip("Açı:Q", title="Açı (°)", format=".2f")
                        ]
                    )
                    .properties(
                        height=450,
                        background="#1E293B",
                        padding={"top": 20, "bottom": 10, "left": 10, "right": 10}
                    )
                    .configure_view(stroke=None)
                    .configure_axis(
                        titleColor="#FFFFFF",
                        gridColor="#475569",
                        domainColor="#64748B",
                        tickColor="#64748B"
                    )
                )

                st.altair_chart(zenit_grafik, use_container_width=True)
                st.markdown("#### 📊 Zenit Açısı Karşılaştırma Tablosu")

                zenit_tablo = tablo[[
                    "Tarih",
                    "Saat (Türkiye)",
                    "Zenit Açısı (θz)",
                    "pvlib Zenit Açısı (θz)",
                    "Zenit Farkı (°)"
                ]].copy()

                zenit_tablo = zenit_tablo.rename(columns={
                        "Zenit Açısı (θz)": "Hesaplanan Zenit Açısı (θz) (°)",
                        "pvlib Zenit Açısı (θz)": "pvlib Zenit Açısı (θz) (°)",
                        "Zenit Farkı (°)": "Zenit Farkı (°)"
})

                zenit_html = zenit_tablo.to_html(
                    index=False,
                    float_format=lambda x: f"{x:.2f}",
                    classes="gunes-tablosu"
                )

                st.markdown(
                    '<div class="tablo-alani">' + zenit_html + '</div>',
                    unsafe_allow_html=True
                )

            with yukseklik_tab:
                yukseklik_verisi = grafik_verisi[[
                    "Güneş Yüksekliği (α)",
                    "pvlib Güneş Yüksekliği (α)"
                ]].reset_index()

                yukseklik_verisi = yukseklik_verisi.melt(
                    id_vars="TarihSaat",
                    var_name="Kaynak",
                    value_name="Açı"
                )

                yukseklik_verisi["Kaynak"] = yukseklik_verisi["Kaynak"].replace({
                    "Güneş Yüksekliği (α)": "Hesaplanan Güneş Yüksekliği (α)",
                    "pvlib Güneş Yüksekliği (α)": "pvlib Güneş Yüksekliği (α)"
                })

                yukseklik_grafik = (
                    alt.Chart(yukseklik_verisi)
                    .mark_line()
                    .encode(
                        x=alt.X(
                            "TarihSaat:T",
                            title="Tarih / Saat",
                            axis=alt.Axis(
                                format="%d.%m",
                                labelColor="#FFFFFF",
                                tickCount="day",
                                labelAngle=0,
                                grid=False
                            )
                        ),
                        y=alt.Y(
                            "Açı:Q",
                            title="Güneş Yüksekliği (°)",
                            axis=alt.Axis(labelColor="#FFFFFF")
                        ),
                        color=alt.Color(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Güneş Yüksekliği (α)", "pvlib Güneş Yüksekliği (α)"],
                                range=["#EF4444", "#38BDF8"]
                            ),
                            legend=alt.Legend(
                                title=None,
                                labelColor="#FFFFFF",
                                orient="bottom"
                            )
                        ),
                        strokeDash=alt.StrokeDash(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Güneş Yüksekliği (α)", "pvlib Güneş Yüksekliği (α)"],
                                range=[[1, 0], [6, 4]]
                            ),
                            legend=None
                        ),
                        size=alt.Size(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Güneş Yüksekliği (α)", "pvlib Güneş Yüksekliği (α)"],
                                range=[4, 2]
                            ),
                            legend=None
                        ),
                        tooltip=[
                            alt.Tooltip(
                                "TarihSaat:T",
                                title="Tarih / Saat",
                                format="%d.%m.%Y %H:%M"
                            ),
                            alt.Tooltip("Kaynak:N", title="Hesaplama"),
                            alt.Tooltip("Açı:Q", title="Açı (°)", format=".2f")
                        ]
                    )
                    .properties(
                        height=450,
                        background="#1E293B",
                        padding={"top": 20, "bottom": 10, "left": 10, "right": 10}
                    )
                    .configure_view(stroke=None)
                    .configure_axis(
                        titleColor="#FFFFFF",
                        gridColor="#475569",
                        domainColor="#64748B",
                        tickColor="#64748B"
                    )
                )

                st.altair_chart(yukseklik_grafik, use_container_width=True)
                st.markdown("#### 📊 Güneş Yüksekliği Karşılaştırma Tablosu")

                yukseklik_tablo = tablo[[
                    "Tarih",
                    "Saat (Türkiye)",
                    "Güneş Yüksekliği (α)",
                    "pvlib Güneş Yüksekliği (α)",
                    "Yükseklik Farkı (°)",
                    "Güneş Durumu"
                ]].copy()

                yukseklik_tablo = yukseklik_tablo.rename(columns={
                    "Güneş Yüksekliği (α)": "Hesaplanan Güneş Yüksekliği (α, °)",
                    "pvlib Güneş Yüksekliği (α)": "pvlib Güneş Yüksekliği (α, °)"
                })

                yukseklik_html = yukseklik_tablo.to_html(
                    index=False,
                    float_format=lambda x: f"{x:.2f}",
                    classes="gunes-tablosu"
                )

                st.markdown(
                    '<div class="tablo-alani">' + yukseklik_html + '</div>',
                    unsafe_allow_html=True
                )

       

            with azimut_tab:
                azimut_verisi = grafik_verisi[[
                    "Güneş Azimut Açısı (γs)",
                    "pvlib Güneş Azimut Açısı (γs)"
                ]].reset_index()

                azimut_verisi = azimut_verisi.melt(
                    id_vars="TarihSaat",
                    var_name="Kaynak",
                    value_name="Açı"
                )

                azimut_verisi["Kaynak"] = azimut_verisi["Kaynak"].replace({
                    "Güneş Azimut Açısı (γs)": "Hesaplanan Güneş Azimutu (γs)",
                    "pvlib Güneş Azimut Açısı (γs)": "pvlib Güneş Azimutu (γs)"
                })

                azimut_grafik = (
                    alt.Chart(azimut_verisi)
                    .mark_line()
                    .encode(
                        x=alt.X(
                            "TarihSaat:T",
                            title="Tarih / Saat",
                            axis=alt.Axis(
                                format="%d.%m",
                                labelColor="#FFFFFF",
                                tickCount={"interval": "day", "step": 1},
                                labelAngle=0,
                                grid=False
                            )
                        ),
                        y=alt.Y(
                            "Açı:Q",
                            title="Güneş Azimut Açısı (°)",
                            scale=alt.Scale(domain=[-180, 180]),
                            axis=alt.Axis(labelColor="#FFFFFF")
                        ),
                        color=alt.Color(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Güneş Azimutu (γs)", "pvlib Güneş Azimutu (γs)"],
                                range=["#EF4444", "#38BDF8"]
                            ),
                            legend=alt.Legend(
                                title=None,
                                labelColor="#FFFFFF",
                                orient="bottom"
                            )
                        ),
                        strokeDash=alt.StrokeDash(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Güneş Azimutu (γs)", "pvlib Güneş Azimutu (γs)"],
                                range=[[1, 0], [6, 4]]
                            ),
                            legend=None
                        ),
                        size=alt.Size(
                            "Kaynak:N",
                            scale=alt.Scale(
                                domain=["Hesaplanan Güneş Azimutu (γs)", "pvlib Güneş Azimutu (γs)"],
                                range=[4, 2]
                            ),
                            legend=None
                        ),
                        tooltip=[
                            alt.Tooltip(
                                "TarihSaat:T",
                                title="Tarih / Saat",
                                format="%d.%m.%Y %H:%M"
                            ),
                            alt.Tooltip("Kaynak:N", title="Hesaplama"),
                            alt.Tooltip("Açı:Q", title="Açı (°)", format=".2f")
                        ]
                    )
                    .properties(
                        height=450,
                        background="#1E293B",
                        padding={
                            "top": 20,
                            "bottom": 10,
                            "left": 10,
                            "right": 10
                        }
                    )
                    .configure_view(stroke=None)
                    .configure_axis(
                        titleColor="#FFFFFF",
                        gridColor="#475569",
                        domainColor="#64748B",
                        tickColor="#64748B"
                    )
                )

                st.altair_chart(
                    azimut_grafik,
                    use_container_width=True
                )
                st.markdown("#### 📊 Güneş Azimutu Karşılaştırma Tablosu")

                azimut_tablo = tablo[[
                    "Tarih",
                    "Saat (Türkiye)",
                    "Güneş Azimut Açısı (γs)",
                    "pvlib Güneş Azimut Açısı (γs)",
                    "Azimut Farkı (°)"
                ]].copy()

                azimut_tablo = azimut_tablo.rename(columns={
                    "Güneş Azimut Açısı (γs)": "Hesaplanan Güneş Azimutu (γs, °)",
                    "pvlib Güneş Azimut Açısı (γs)": "pvlib Güneş Azimutu (γs, °)"
                })

                azimut_html = azimut_tablo.to_html(
                    index=False,
                    float_format=lambda x: f"{x:.2f}",
                    classes="gunes-tablosu",
                    na_rep="—"
                )

                st.markdown(
                    '<div class="tablo-alani">' + azimut_html + '</div>',
                    unsafe_allow_html=True
                )
            # 3D GÜNEŞ SİMÜLASYONU
            st.markdown("### ☀️ 3D Güneş Konumu Simülasyonu")
            st.markdown("#### 🏢 Örnek Bina Ölçüleri")

            col_b1, col_b2, col_b3 = st.columns(3)

            with col_b1:
                bina_genislik = st.number_input("Bina Genişliği (m)", value=20.58)

            with col_b2:
                bina_uzunluk = st.number_input("Bina Uzunluğu (m)", value=31.30)

            with col_b3:
                bina_yukseklik = st.number_input("Bina Yüksekliği (m)", value=21.0)
                        # Örnek binanın 3 boyutlu modeli
            x = bina_genislik / 2
            y = bina_uzunluk / 2
            h = bina_yukseklik

            fig_3d = go.Figure()

            fig_3d.add_trace(go.Mesh3d(
                x=[-x, x, x, -x, -x, x, x, -x],
                y=[-y, -y, y, y, -y, -y, y, y],
                z=[0, 0, 0, 0, h, h, h, h],
                alphahull=0,
                color="#38BDF8",
                opacity=0.8,
                name="Örnek Bina"
            ))
                    # Güneşin 3D konumunu hesapla
            gunes_verisi = tablo[
                tablo["Güneş Yüksekliği (α)"] > 0
            ].copy()

            if not gunes_verisi.empty:
                ilk = gunes_verisi.iloc[0]

                yukseklik = math.radians(
                    ilk["Güneş Yüksekliği (α)"]
                )
                azimut = math.radians(
                    ilk["Güneş Azimut Açısı (γs)"]
                )

                mesafe = max(bina_genislik, bina_uzunluk) * 3

                gunes_x = -mesafe * math.cos(yukseklik) * math.sin(azimut)
                gunes_y = -mesafe * math.cos(yukseklik) * math.cos(azimut)
                gunes_z = mesafe * math.sin(yukseklik)

                fig_3d.add_trace(go.Scatter3d(
                    x=[gunes_x],
                    y=[gunes_y],
                    z=[gunes_z],
                    mode="markers+text",
                    marker=dict(size=12, color="#FACC15"),
                    text=[
                        f'Azimut: {ilk["Güneş Azimut Açısı (γs)"]:.2f}°'
                        f'<br>Yükseklik: {ilk["Güneş Yüksekliği (α)"]:.2f}°'
                        f'<br>Zenit: {ilk["Zenit Açısı (θz)"]:.2f}°'
                    ],
                    textposition="top center",
                    name="Güneş"
                ))

            fig_3d.update_layout(
                height=550,
                paper_bgcolor="#0F172A",
                font=dict(color="white"),
                scene=dict(
                    xaxis_title="Doğu - Batı (m)",
                    yaxis_title="Kuzey - Güney (m)",
                    zaxis_title="Yükseklik (m)",
                    aspectmode="data"
                ),
                margin=dict(l=0, r=0, t=0, b=0)
            )
        

            # ANİMASYON KODU BURAYA
            # Güneşin saatlik hareket animasyonu
            if not gunes_verisi.empty:
                animasyon_kareleri = []

                for sira, satir in gunes_verisi.reset_index(drop=True).iterrows():
                    alpha = math.radians(satir["Güneş Yüksekliği (α)"])
                    gamma = math.radians(satir["Güneş Azimut Açısı (γs)"])

                    gx = -mesafe * math.cos(alpha) * math.sin(gamma)
                    gy = -mesafe * math.cos(alpha) * math.cos(gamma)
                    gz = mesafe * math.sin(alpha)

                    animasyon_kareleri.append(
                        go.Frame(
                            data=[
                                go.Scatter3d(
                                    x=[gx],
                                    y=[gy],
                                    z=[gz],
                                    mode="markers+text",
                                    marker=dict(size=12, color="#FACC15"),
                                    text=[
                                    f'Azimut: {satir["Güneş Azimut Açısı (γs)"]:.2f}°'
                                    f'<br>Yükseklik: {satir["Güneş Yüksekliği (α)"]:.2f}°'
                                    f'<br>Zenit: {satir["Zenit Açısı (θz)"]:.2f}°'
                                ],
                                textposition="top center",
                                    name="Güneş"
                                )
                            ],
                            traces=[1],
                            name=str(sira)
                        )
                    )

                fig_3d.frames = animasyon_kareleri

                fig_3d.update_layout(
                    updatemenus=[
                        dict(
                            type="buttons",
                            direction="left",
                            x=0.05,
                            y=1.1,
                            buttons=[
                                dict(
                                    label="▶ Oynat",
                                    method="animate",
                                    args=[
                                        None,
                                        {
                                            "frame": {
                                                "duration": 400,
                                                "redraw": True
                                            },
                                            "fromcurrent": True,
                                            "transition": {"duration": 0}
                                        }
                                    ]
                                ),
                                dict(
                                    label="⏸ Duraklat",
                                    method="animate",
                                    args=[
                                        [None],
                                        {
                                            "mode": "immediate",
                                            "frame": {
                                                "duration": 0,
                                                "redraw": False
                                            },
                                            "transition": {"duration": 0}
                                        }
                                    ]
                                )
                            ]
                        )
                    ]
                )
                # Tarih ve saat seçme çubuğu
                fig_3d.update_layout(
                    sliders=[
                        dict(
                            active=0,
                            currentvalue={
                                "prefix": "Seçilen Tarih / Saat: "
                            },
                            pad={"t": 50},
                            steps=[
                                dict(
                                    method="animate",
                                    label=f'{satir["Tarih"]} {satir["Saat (Türkiye)"]}',
                                    args=[
                                        [str(sira)],
                                        {
                                            "mode": "immediate",
                                            "frame": {
                                                "duration": 0,
                                                "redraw": True
                                            },
                                            "transition": {
                                                "duration": 0
                                            }
                                        }
                                    ]
                                )
                                for sira, satir in gunes_verisi.reset_index(drop=True).iterrows()
                            ]
                        )
                    ]
                )
        
            st.plotly_chart(fig_3d, use_container_width=True)
                    # 3D simülasyonda gösterilen güneş açıları
            if not gunes_verisi.empty:
                st.markdown("#### ☀️ Güneş Konumu Açıları")

                st.info(
                    "Aşağıdaki değerler animasyonun başlangıç saatine aittir. "
                    "Hareketli değerleri sonraki adımda 3D grafiğe ekleyeceğiz."
                )

                ilk = gunes_verisi.iloc[0]

                aci_col1, aci_col2, aci_col3 = st.columns(3)

                with aci_col1:
                    st.metric(
                        "🧭 Azimut (γs)",
                        f'{ilk["Güneş Azimut Açısı (γs)"]:.2f}°'
                    )

                with aci_col2:
                    st.metric(
                        "☀️ Güneş Yüksekliği (α)",
                        f'{ilk["Güneş Yüksekliği (α)"]:.2f}°'
                    )

                with aci_col3:
                    st.metric(
                        "📐 Zenit (θz)",
                        f'{ilk["Zenit Açısı (θz)"]:.2f}°'
                    )
            # SONUÇ TABLOSU
            csv_verisi = tablo.to_csv(index=False).encode("utf-8-sig")

            st.markdown("""
            <style>
            .tablo-alani {
                max-height: 600px;
                overflow: auto;
                border-radius: 10px;
                border: 1px solid #64748B;
            }

            table.gunes-tablosu {
                width: 100%;
                border-collapse: collapse;
                white-space: nowrap;
                font-size: 14px;
            }

            table.gunes-tablosu th {
                background-color: #FACC15;
                color: #000000;
                padding: 12px;
                border: 1px solid #64748B;
                position: sticky;
                top: 0;
                z-index: 1;
            }

            table.gunes-tablosu td {l
                background-color: #1E293B;
                color: #FFFFFF;
                padding: 10px;
                border: 1px solid #64748B;
            }
            </style>
            """, unsafe_allow_html=True)
        
            # CEPHE GELİŞ AÇISI TABLOSU
            cephe_sutunlari = ["Tarih", "Saat (Türkiye)"]

            for ad in cephe_yonleri:
                cephe_sutunlari.extend([
                    f"{ad} Geliş Açısı (°)",
                    f"pvlib {ad} Geliş Açısı (°)",
                    f"{ad} Fark (°)"
                ])



            cephe_tablosu = tablo[cephe_sutunlari]

        with kademe2:
            isinim_tab, gelis_tab = st.tabs([
            "☀️ Işınım Hesapları",
            "📐 Cephe Geliş Açıları"
            ])
        with isinim_tab:
                    # DORT CEPHE - BIZIM HESAPLAMAMIZ VE PVGIS KARSILASTIRMASI
            st.markdown("### ☀️ K Blok Cephelerine Gelen Toplam Güneş Işınımı Karşılaştırması")

            if not pvgis_verileri.empty:

                karsilastirma_sonuclari = []
                albedo = 0.20

                try:
                    with st.spinner("Dört cephe karşılaştırılıyor..."):

                        for cephe, cephe_azimutu in cephe_yonleri.items():

                            for yil in range(baslangic.year, bitis.year + 1):

                                pv_cephe, _ = get_pvgis_hourly(
                                    latitude=enlem,
                                    longitude=boylam,
                                    start=yil,
                                    end=yil,
                                    components=True,
                                    surface_tilt=90,
                                    surface_azimuth=cephe_azimutu
                                )

                                pv_cephe.index = pv_cephe.index.tz_convert(
                                    "Europe/Istanbul"
                                )

                                ortak_saatler = pvgis_verileri.index.intersection(
                                    pv_cephe.index
                                )

                                for zaman in ortak_saatler:

                                    yatay = pvgis_verileri.loc[zaman]
                                    dusey = pv_cephe.loc[zaman]

                                    tarih = zaman.date()
                                    saat = zaman.hour
                                    dakika = zaman.minute

                                    delta = deklinasyon_hesapla(tarih)
                                    gunes_saati = gunes_zamani_hesapla(
                                        tarih, saat, boylam, dakika
                                    )
                                    omega = saat_acisi_hesapla(gunes_saati)
                                    zenit = zenit_acisi_hesapla(
                                        enlem, delta, omega
                                    )
                                    yukseklik = 90 - zenit
                                    azimut = gunes_azimutu_hesapla(
                                        enlem, delta, omega, zenit
                                    )

                                    GHI = float(
                                        yatay["poa_direct"]
                                        + yatay["poa_sky_diffuse"]
                                    )
                                    DHI = float(yatay["poa_sky_diffuse"])

                                    pv_yukseklik = float(
                                        yatay["solar_elevation"]
                                    )

                                    if pv_yukseklik > 3:
                                        DNI = float(yatay["poa_direct"]) / math.sin(
                                            math.radians(pv_yukseklik)
                                        )
                                    else:
                                        DNI = 0.0

                                    if yukseklik > 0 and azimut is not None:
                                        cos_gelis = (
                                            math.cos(math.radians(yukseklik))
                                            * math.cos(
                                                math.radians(
                                                    azimut + 180 - cephe_azimutu
                                                )
                                            )
                                        )
                                    else:
                                        cos_gelis = 0.0

                                    bizim_dogrudan = DNI * max(0, cos_gelis)
                                    bizim_yayili = DHI / 2
                                    bizim_yansiyan = GHI * albedo / 2

                                    bizim_toplam = (
                                        bizim_dogrudan
                                        + bizim_yayili
                                        + bizim_yansiyan
                                    )

                                    pvgis_toplam = float(
                                        dusey["poa_direct"]
                                        + dusey["poa_sky_diffuse"]
                                        + dusey["poa_ground_diffuse"]
                                    )

                                    karsilastirma_sonuclari.append({
                                        "Tarih / Saat": zaman.strftime("%d.%m.%Y %H:%M"),
                                        "Cephe": cephe,

                                        "Hesaplanan Işınım (W/m²)": round(bizim_toplam, 2),
                                        "PVGIS (W/m²)": round(pvgis_toplam, 2),
                                        "Fark (W/m²)": round(pvgis_toplam - bizim_toplam, 2),

                                        "Hesaplanan Doğrudan": round(bizim_dogrudan, 2),
                                        "PVGIS Doğrudan": round(float(dusey["poa_direct"]), 2),

                                        "Hesaplanan Yayılı": round(bizim_yayili, 2),
                                        "PVGIS Yayılı": round(float(dusey["poa_sky_diffuse"]), 2),

                                        "Hesaplanan Yansıyan": round(bizim_yansiyan, 2),
                                        "PVGIS Yansıyan": round(float(dusey["poa_ground_diffuse"]), 2)
                                    })

                    karsilastirma_tablosu = pd.DataFrame(
                        karsilastirma_sonuclari
                    )

                    if not karsilastirma_tablosu.empty:
                        toplam_sutunlari = [
                            "Tarih / Saat",
                            "Cephe",
                            "Hesaplanan Işınım (W/m²)",
                            "PVGIS (W/m²)",
                            "Fark (W/m²)"
                        ]
                        cephe_sekmeleri = st.tabs([
                            "🧭 Kuzeydoğu",
                            "☀️ Güneydoğu",
                            "🌤️ Güneybatı",
                            "🧭 Kuzeybatı"
                        ])
                        for sekme, cephe_adi in zip(
                            cephe_sekmeleri,
                            ["Kuzeydoğu", "Güneydoğu", "Güneybatı", "Kuzeybatı"]
                        ):
                            with sekme:
                            
                             cephe_tablo = karsilastirma_tablosu[
                                    karsilastirma_tablosu["Cephe"] == cephe_adi
                                ][[
                                    "Tarih / Saat",
                                    "Hesaplanan Işınım (W/m²)",
                                    "PVGIS (W/m²)",
                                    "Fark (W/m²)"
                                ]].copy()

                             cephe_html = cephe_tablo.to_html(
                                        index=False,
                                        float_format=lambda x: f"{x:.2f}",
                                        classes="gunes-tablosu"
                                    )

                             st.markdown(
                                        '<div class="tablo-alani">' + cephe_html + '</div>',
                                    unsafe_allow_html=True
                                )
                                            # ISINIM BILESENLERI KARSILASTIRMA TABLOSU
                        st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)
                        st.markdown(
                            "### ☀️ K Blok Cephelerine Gelen Güneş Işınımı Bileşenleri"
                        )

                        bilesen_sonuclari = []

                        for _, kayit in karsilastirma_tablosu.iterrows():
                            for tur in ["Doğrudan", "Yayılı", "Yansıyan"]:

                                hesaplanan = kayit[f"Hesaplanan {tur}"]
                                pvgis = kayit[f"PVGIS {tur}"]

                                bilesen_sonuclari.append({
                                    "Tarih / Saat": kayit["Tarih / Saat"],
                                    "Cephe": kayit["Cephe"],
                                    "Işınım Türü": tur,
                                    "Hesaplanan (W/m²)": hesaplanan,
                                    "PVGIS (W/m²)": pvgis,
                                    "Fark (W/m²)": round(pvgis - hesaplanan, 2)
                                })

                        bilesen_tablosu = pd.DataFrame(bilesen_sonuclari)

                        bilesen_sekmeleri = st.tabs([
                            "🧭 Kuzeydoğu",
                            "☀️ Güneydoğu",
                            "🌤️ Güneybatı",
                            "🧭 Kuzeybatı"
                        ])
                        for sekme, cephe_adi in zip(
                            bilesen_sekmeleri,
                            ["Kuzeydoğu", "Güneydoğu", "Güneybatı", "Kuzeybatı"]
                        ):
                         with sekme:
                            secili_bilesen_tablo = bilesen_tablosu[
                                bilesen_tablosu["Cephe"] == cephe_adi
                            ][[
                                "Tarih / Saat",
                                "Işınım Türü",
                                "Hesaplanan (W/m²)",
                                "PVGIS (W/m²)",
                                "Fark (W/m²)"
                            ]].copy()

                            bilesen_html = secili_bilesen_tablo.to_html(
                                index=False,
                                float_format=lambda x: f"{x:.2f}",
                                classes="gunes-tablosu"
                            )

                            st.markdown(
                                '<div class="tablo-alani">' + bilesen_html + '</div>',
                                unsafe_allow_html=True
                            )
                    else:
                        st.info("Seçilen tarihler için karşılaştırma verisi yok.")

                except Exception as hata:
                    st.warning(f"Karşılaştırma yapılamadı: {hata}")

        with gelis_tab:
            st.markdown("### 📐 K Blok Cephe Geliş Açıları")

            cephe_sekmeleri = st.tabs([
                "🧭 Kuzeydoğu",
                "☀️ Güneydoğu",
                "🌤️ Güneybatı",
                "🧭 Kuzeybatı"
            ])

            for sekme, ad in zip(cephe_sekmeleri, cephe_yonleri):
                with sekme:
                    secili_tablo = cephe_tablosu[[
                        "Tarih",
                        "Saat (Türkiye)",
                        f"{ad} Geliş Açısı (°)",
                        f"pvlib {ad} Geliş Açısı (°)",
                        f"{ad} Fark (°)"
                    ]].copy()

                    secili_html = secili_tablo.to_html(
                        index=False,
                        float_format=lambda x: f"{x:.2f}",
                        classes="gunes-tablosu",
                        na_rep="—"
                    )

                    st.markdown(
                        '<div class="tablo-alani">' + secili_html + '</div>',
                        unsafe_allow_html=True
                    )
if "sonuclar" not in locals():
    st.stop()                    
with kademe3:
    st.markdown("### 🌳 K Blok – Gölge Analizi")
    st.markdown("#### 🏢 K Blok ve Çevre Binalarının Verileri")
    

    bina_verileri = pd.DataFrame([
        ["1. Batıdaki Uzun Bina", 595.53, 111.87, 6.48, 2, 6.00, 40.996039, 29.065656],
        ["2. Kırmızı Çatılı Bina", 798.17, 119.82, 43.28, 3, 9.00, 40.996331, 29.065183],
        ["3. L Biçimli Bina", 885.72, 168.33, 40.67, 2, 6.00, 40.996669, 29.065506],
        ["4. Büyük Avlulu Bina", 1909.01, 235.77, 96.82, 2, 8.00, 40.996775, 29.064589],
        ["5. Yeşil Çatılı Bina", 179.56, 54.81, 14.15, 1, 4.00, 40.996267, 29.066203],
    ], columns=[
        "Bina",
        "Çatı Alanı (m²)",
        "Çevre (m)",
        "K Blok'a Uzaklık (m)",
        "Kat Sayısı",
        "Tahmini Yükseklik (m)",
        "Enlem",
        "Boylam"
    ])

    # Komşu binaların köşe koordinatlarını ve yüksekliklerini eşleştir
    komsu_kml_adlari = [
        "komşu-1",
        "komşu 2 kırmızı çatılı bina",
        "komşu 3 l şeklinde bina",
        "komşu 4 uzak büyük bina",
        "K blok arkası 2 katlı bina"
    ]

    komsu_geometrileri = {}

    for i, kml_adi in enumerate(komsu_kml_adlari):
        komsu_geometrileri[bina_verileri.iloc[i]["Bina"]] = {
            "poligon": next(poligon for ad, poligon in bina_poligonlari.items() if ad.startswith(kml_adi[:7])),
            "yukseklik": bina_verileri.iloc[i]["Tahmini Yükseklik (m)"]
        }

    # K Blok'un dört çatı bölümünün gerçek sınırları
    kblok_cati_poligonlari = {
        "Ana Çatı": bina_poligonlari["ana çatı  üst"],
        "Arka Çıkıntılar": next(poligon for ad, poligon in bina_poligonlari.items() if ad.startswith("arka plan")),
        "Ön Alçak Kademe 1": bina_poligonlari["1 düşü ön taraf"],
        "Ön Alçak Kademe 2": bina_poligonlari["2 düşü ön taraf"]
    }

    # K Blok çatı bölümlerinin mevcut yükseklikleri
    
    kblok_cati_yukseklikleri = {
        "Ana Çatı": 15.0,
        "Arka Çıkıntılar": (18.0, 21.0),
        "Ön Alçak Kademe 1": 6.0,
        "Ön Alçak Kademe 2": 3.0
    }
        # K Blok çatı bölümlerinin birleşik geometrisi
    kblok_birlesik_geometri = unary_union(
        list(kblok_cati_poligonlari.values())
    )
    st.write("K Blok birleşik geometri türü:", kblok_birlesik_geometri.geom_type)
    st.write(
    "K Blok ayrı poligon sayısı:",
    len(kblok_birlesik_geometri.geoms)
)
        # K Blok cephe analizi için çatı sınırlarının kenarları
    kblok_cephe_kenarlari = []

    for bolum_adi, poligon in kblok_cati_poligonlari.items():
        koordinatlar = list(poligon.exterior.coords)

        for i in range(len(koordinatlar) - 1):
            baslangic = koordinatlar[i]
            bitis = koordinatlar[i + 1]

            kblok_cephe_kenarlari.append({
                "bolum": bolum_adi,
                "baslangic": baslangic,
                "bitis": bitis
            })
                # K Blok kenarlarının uzunluk ve doğrultuları
    for sira, kenar in enumerate(kblok_cephe_kenarlari, start=1):
        x1, y1 = kenar["baslangic"]
        x2, y2 = kenar["bitis"]

        dx = x2 - x1
        dy = y2 - y1

        uzunluk = math.hypot(dx, dy)
        dogrultu = math.degrees(math.atan2(dx, dy)) % 360
        poligon = kblok_cati_poligonlari[kenar["bolum"]]

        dis_azimut = (
            dogrultu + (90 if poligon.exterior.is_ccw else -90)
        ) % 360
        kenar["uzunluk"] = uzunluk
        kenar["dis_azimut"] = dis_azimut

        kenar["cephe_yonu"] = min(
        cephe_yonleri,
        key=lambda yon: abs(
            (dis_azimut - cephe_yonleri[yon] + 180) % 360 - 180
        )
    )

        print(
            f"Kenar {sira} | {kenar['bolum']} | "
            f"Uzunluk: {uzunluk:.2f} m | "
            f"Doğrultu: {dogrultu:.2f}° | Dış Azimut: {dis_azimut:.2f}°"
        )
            # Kenarları dört cephe yönüne göre gruplandır
    cephe_kenar_gruplari = {
        yon: [] for yon in cephe_yonleri
    }

    for kenar in kblok_cephe_kenarlari:
        cephe_kenar_gruplari[kenar["cephe_yonu"]].append(kenar)
            # Cephe gruplarındaki kenar numaralarını göster
    for yon, kenarlar in cephe_kenar_gruplari.items():
        numaralar = [
            kblok_cephe_kenarlari.index(kenar) + 1
            for kenar in kenarlar
        ]
        print(f"{yon}: {numaralar}")
            # Diğer çatı bölümlerine yakın kenarları belirle
    from shapely.geometry import LineString

    for sira, kenar in enumerate(kblok_cephe_kenarlari, start=1):
        cizgi = LineString([kenar["baslangic"], kenar["bitis"]])

        mesafeler = [
            cizgi.distance(poligon)
            for ad, poligon in kblok_cati_poligonlari.items()
            if ad != kenar["bolum"]
        ]

        print(f"Kenar {sira} | Diğer bölüme en yakın: {min(mesafeler):.2f} m")
            # Cephe analizinde kullanılacak yükseklikler
            # K Blok kenarlarının dış sınır kontrolü
        dis_sinir_sonuclari = []
    for sira, kenar in enumerate(kblok_cephe_kenarlari, start=1):
         cizgi = LineString([kenar["baslangic"], kenar["bitis"]])

         dis_sinir_uzunlugu = cizgi.intersection(
            kblok_birlesik_geometri.boundary
        ).length
         ic_sinir_uzunlugu = max(
            0.0,
            kenar["uzunluk"] - dis_sinir_uzunlugu
        )

         print(
            f"Kenar {sira}: "
            f"Dış sınır {dis_sinir_uzunlugu:.2f} m / "
            f"Toplam {kenar['uzunluk']:.2f} m"
        )
         dis_sinir_sonuclari.append({
            "İç Sınır (m)": round(ic_sinir_uzunlugu, 2),
            "Çatı Bölümü": kenar["bolum"],
            "Çatı Yüksekliği (m)": {
            "Ana Çatı": 15.0,
            "Arka Çıkıntılar": 15.0,
            "Ön Alçak Kademe 1": 6.0,
            "Ön Alçak Kademe 2": 3.0
        }[kenar["bolum"]],
            "Kenar No": sira,
            "Cephe Yönü": kenar["cephe_yonu"],
            "Dış Sınır (m)": round(dis_sinir_uzunlugu, 2),
            "Toplam Uzunluk (m)": round(kenar["uzunluk"], 2)
        })
    st.subheader("K Blok - 18 Kenarın Dış Sınır Kontrolü")
    st.dataframe(pd.DataFrame(dis_sinir_sonuclari), hide_index=True)
    cephe_bolum_yukseklikleri = {
        "Ana Çatı": 15.0,
        "Arka Çıkıntılar": 15.0,
        "Ön Alçak Kademe 1": 6.0,
        "Ön Alçak Kademe 2": 3.0
    }

    for kenar in kblok_cephe_kenarlari:
        kenar["yukseklik"] = cephe_bolum_yukseklikleri[kenar["bolum"]]
            # Ön kademeli cephelerin dikey yükseklik aralıkları
    on_cephe_yukseklik_araliklari = {
        2: (0.0, 15.0),
        4: (0.0, 15.0),
        5: (0.0, 15.0),
        9: (0.0, 15.0),
        10: (0.0, 15.0),
        12: (0.0, 6.0),
        13: (6.0, 15.0),
        14: (0.0, 6.0),
        15: (0.0, 3.0),
        16: (3.0, 6.0),
        17: (0.0, 3.0),
        18: (0.0, 3.0)
    }
        # Ön cephe için dikey yüzey adaylarını oluştur
    on_cephe_yuzeyleri = []

    for kenar_no, (alt, ust) in on_cephe_yukseklik_araliklari.items():
        kenar = kblok_cephe_kenarlari[kenar_no - 1]

        on_cephe_yuzeyleri.append({
            "kenar_no": kenar_no,
            "baslangic": kenar["baslangic"],
            "bitis": kenar["bitis"],
            "alt_yukseklik": alt,
            "ust_yukseklik": ust,
            "alan": kenar["uzunluk"] * (ust - alt)
        })
            # Cephedeki bir noktanın komşu bina gölgesinde kalıp kalmadığını kontrol et
    def cephe_noktasi_golgede_mi(x, y, z, gunes_yuksekligi, gunes_azimutu):
        if gunes_yuksekligi <= 0:
            return False

        gunes_yonu = math.radians((gunes_azimutu + 180) % 360)
        uzaklik = 1000.0

        isin = LineString([
            (x, y),
            (
                x + uzaklik * math.sin(gunes_yonu),
                y + uzaklik * math.cos(gunes_yonu)
            )
        ])

        for bilgi in komsu_geometrileri.values():
            kesisim = isin.intersection(bilgi["poligon"])

            if kesisim.is_empty:
                continue

            mesafe = kesisim.distance(Point(x, y))
            isin_yuksekligi = z + mesafe * math.tan(
                math.radians(gunes_yuksekligi)
            )

            if isin_yuksekligi < bilgi["yukseklik"]:
                return True

        return False
        # Ön cephe yüzeylerinde gölge kontrol noktaları
    for yuzey in on_cephe_yuzeyleri:
        x1, y1 = yuzey["baslangic"]
        x2, y2 = yuzey["bitis"]

        noktalar = []

        for i in range(5):
            t = (i + 0.5) / 5

            for j in range(5):
                z = yuzey["alt_yukseklik"] + (
                    (j + 0.5) / 5
                ) * (
                    yuzey["ust_yukseklik"] - yuzey["alt_yukseklik"]
                )

                noktalar.append((
                    x1 + t * (x2 - x1),
                    y1 + t * (y2 - y1),
                    z
                ))

        yuzey["kontrol_noktalari"] = noktalar
            # Ön cephe için örnek saatlik gölge kontrolü
    ornek_saat = next(
        (v for v in sonuclar if v["Güneş Yüksekliği (α)"] > 0),
        None
    )
    print("GÖLGE KONTROL TESTİ")
    print("Örnek saat:", ornek_saat)
    print("Ön cephe yüzey sayısı:", len(on_cephe_yuzeyleri))

    if ornek_saat is not None:
        for yuzey in on_cephe_yuzeyleri:
            golgeli_nokta = sum(
                cephe_noktasi_golgede_mi(
                    x, y, z,
                    ornek_saat["Güneş Yüksekliği (α)"],
                    ornek_saat["Güneş Azimut Açısı (γs)"]
                )
                for x, y, z in yuzey["kontrol_noktalari"]
            )

            print(
                f"Kenar {yuzey['kenar_no']}: "
                f"25 noktadan {golgeli_nokta} tanesi gölgede"
            )
    # 3. Kademe - Saatlik ön cephe gölge analizi
    saatlik_golge_sonuclari = []
    for veri in sonuclar:
     gunes_yuksekligi = veri["Güneş Yüksekliği (α)"]

     if gunes_yuksekligi <= 0:
        continue

     gunes_azimutu = veri["Güneş Azimut Açısı (γs)"]
     for yuzey in on_cephe_yuzeyleri:

        kenar = kblok_cephe_kenarlari[yuzey["kenar_no"] - 1]
        gunes_yonu = (gunes_azimutu + 180) % 360
        cephe_yonu = kenar["dis_azimut"]

        aci_farki = (gunes_yonu - cephe_yonu + 180) % 360 - 180
        gunes_aliyor_mu = abs(aci_farki) < 90

        noktalar = yuzey["kontrol_noktalari"]
        toplam_nokta = len(noktalar)
        if toplam_nokta == 0:
            continue
        golgeli_nokta = sum(
            cephe_noktasi_golgede_mi(
                x, y, z,
                gunes_yuksekligi,
                gunes_azimutu
            )
            for x, y, z in noktalar
        )
        golge_orani = 100 * golgeli_nokta / toplam_nokta
        saatlik_golge_sonuclari.append({
            "Tarih": str(veri["Tarih"]),
            "Saat": veri["Saat (Türkiye)"],
            "Kenar No": yuzey["kenar_no"],
            "Cephe Yönü": kblok_cephe_kenarlari[yuzey["kenar_no"] - 1]["cephe_yonu"],
            "Toplam Nokta": toplam_nokta,
            "Gölgeli Nokta": golgeli_nokta,
            "Gölge Oranı (%)": round(golge_orani, 2),
            "Doğrudan Güneş Alıyor mu?": "Evet" if gunes_aliyor_mu else "Hayır"

        })
    saatlik_golge_df = pd.DataFrame(saatlik_golge_sonuclari)

    st.subheader("3. Kademe - Saatlik Ön Cephe Gölge Analizi")
    st.dataframe(saatlik_golge_df, use_container_width=True)
    if "karsilastirma_tablosu" in locals() and not karsilastirma_tablosu.empty:
        st.subheader("3.3 - Gölgeli ve Gölgesiz Cephe Güneş Kazancı Karşılaştırması")
        golge_eslestirme = saatlik_golge_df.copy()

        golge_eslestirme["Tarih / Saat"] = pd.to_datetime(
            golge_eslestirme["Tarih"] + " " + golge_eslestirme["Saat"]
        ).dt.strftime("%d.%m.%Y %H:%M")
        karsilastirma_tablosu["Tarih / Saat"] = pd.to_datetime(
            karsilastirma_tablosu["Tarih / Saat"],
            format="%d.%m.%Y %H:%M"
        ).dt.strftime("%d.%m.%Y %H:00")
        birlesik_tablo = golge_eslestirme.merge(
            karsilastirma_tablosu,
            left_on=["Tarih / Saat", "Cephe Yönü"],
            right_on=["Tarih / Saat", "Cephe"],
            how="left"
        )
        birlesik_tablo["Gölgesiz Işınım (W/m²)"] = (
            birlesik_tablo["Hesaplanan Doğrudan"]
            + birlesik_tablo["Hesaplanan Yayılı"]
            + birlesik_tablo["Hesaplanan Yansıyan"]
        )

        birlesik_tablo["Gölgeli Işınım (W/m²)"] = (
            birlesik_tablo["Hesaplanan Doğrudan"]
            * (1 - birlesik_tablo["Gölge Oranı (%)"] / 100)
            + birlesik_tablo["Hesaplanan Yayılı"]
            + birlesik_tablo["Hesaplanan Yansıyan"]
        )
        birlesik_tablo["Kayıp (%)"] = (
            (
                birlesik_tablo["Gölgesiz Işınım (W/m²)"]
                - birlesik_tablo["Gölgeli Işınım (W/m²)"]
            )
            / birlesik_tablo["Gölgesiz Işınım (W/m²)"].replace(0, float("nan"))
            * 100
        ).fillna(0).round(2)
        ozet_tablo = (
            birlesik_tablo.groupby("Cephe Yönü", as_index=False)[
                ["Gölgesiz Işınım (W/m²)", "Gölgeli Işınım (W/m²)"]
            ]
            .mean()
        )

        ozet_tablo["Kayıp (%)"] = (
            100
            * (
                ozet_tablo["Gölgesiz Işınım (W/m²)"]
                - ozet_tablo["Gölgeli Işınım (W/m²)"]
            )
            / ozet_tablo["Gölgesiz Işınım (W/m²)"].replace(0, float("nan"))
        ).fillna(0).round(2)

        st.dataframe(ozet_tablo.round(2), hide_index=True, use_container_width=True)
        enerji_tablo = (
            birlesik_tablo.groupby("Cephe Yönü", as_index=False)[
                ["Gölgesiz Işınım (W/m²)", "Gölgeli Işınım (W/m²)"]
            ]
            .mean()
        )

        enerji_tablo["Gölgesiz Enerji (kWh/m²)"] = (
            enerji_tablo["Gölgesiz Işınım (W/m²)"]
            * birlesik_tablo["Tarih / Saat"].nunique()
            / 1000
        )

        enerji_tablo["Gölgeli Enerji (kWh/m²)"] = (
            enerji_tablo["Gölgeli Işınım (W/m²)"]
            * birlesik_tablo["Tarih / Saat"].nunique()
            / 1000
        )
        enerji_tablo["Kayıp (%)"] = ozet_tablo["Kayıp (%)"]

    st.subheader("Gölgeli ve Gölgesiz Güneş Enerjisi Karşılaştırması (kWh/m²)")

    st.dataframe(
        enerji_tablo[
            ["Cephe Yönü", "Gölgesiz Enerji (kWh/m²)",
             "Gölgeli Enerji (kWh/m²)", "Kayıp (%)"]
        ].round(2),
        hide_index=True,
        use_container_width=True
    )

    # Komşu binaların metre cinsinden koordinatları
    bina_verileri[["X (m)", "Y (m)"]] = bina_verileri.apply(
        lambda satir: pd.Series(
            koordinat_metreye(
                satir["Enlem"],
                satir["Boylam"]
            )
        ),
        axis=1
    )

    st.dataframe(
        bina_verileri,
        hide_index=True,
        use_container_width=True
    )


    # Binaların K Blok'a göre konum hesaplamaları
    import math

    k_blok_enlem = 40.995997
    k_blok_boylam = 29.065936

    def bina_konumu_hesapla(enlem, boylam):
        lat1 = math.radians(k_blok_enlem)
        lon1 = math.radians(k_blok_boylam)
        lat2 = math.radians(enlem)
        lon2 = math.radians(boylam)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2)
            * math.sin(dlon / 2) ** 2
        )

        mesafe = 2 * 6371000 * math.asin(
            min(1.0, math.sqrt(a))
        )

        x = math.sin(dlon) * math.cos(lat2)
        y = (
            math.cos(lat1) * math.sin(lat2)
            - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        )

        azimut = (
            math.degrees(math.atan2(x, y)) + 360
        ) % 360

        return round(mesafe, 2), round(azimut, 2)

    konum_sonuclari = bina_verileri.copy()

    konum_sonuclari[
        ["Merkezler Arası Mesafe (m)", "Konum Azimutu (°)"]
    ] = konum_sonuclari.apply(
        lambda satir: pd.Series(
            bina_konumu_hesapla(
                satir["Enlem"],
                satir["Boylam"]
            )
        ),
        axis=1
    )

    def yon_belirle(azimut):
        yonler = [
            "Kuzey", "Kuzeydoğu", "Doğu", "Güneydoğu",
            "Güney", "Güneybatı", "Batı", "Kuzeybatı"
        ]
        indeks = int((azimut + 22.5) // 45) % 8
        return yonler[indeks]

    konum_sonuclari["Yön"] = konum_sonuclari[
        "Konum Azimutu (°)"
    ].apply(yon_belirle)


    st.markdown("#### 🧭 Binaların K Blok'a Göre Konumları")

    st.dataframe(
        konum_sonuclari[[
            "Bina",
            "Merkezler Arası Mesafe (m)",
            "Konum Azimutu (°)",
            "Yön"
        ]],
        hide_index=True,
        use_container_width=True
    )


   
             
    if "sonuclar" in locals() and sonuclar:
        st.markdown("#### 🌤️ Saatlik Gölge Uzunluğu ve Yönü")

        golge_sonuclari = []

        for veri in sonuclar:
            yukseklik_acisi = veri["Güneş Yüksekliği (α)"]
            gunes_azimutu = veri["Güneş Azimut Açısı (γs)"]

            if yukseklik_acisi <= 0 or gunes_azimutu is None:
                continue

            golge_azimutu = gunes_azimutu % 360

            for _, bina in bina_verileri.iterrows():
                golge_uzunlugu = bina["Tahmini Yükseklik (m)"] / math.tan(
                    math.radians(yukseklik_acisi)
                )
                
            golge_bitis_x = (
                bina["X (m)"]
                + golge_uzunlugu * math.sin(math.radians(golge_azimutu))
            )

            golge_bitis_y = (
                bina["Y (m)"]
                + golge_uzunlugu * math.cos(math.radians(golge_azimutu))
            )
 

            golge_sonuclari.append({
                    "Tarih": veri["Tarih"],
                    "Saat": veri["Saat (Türkiye)"],
                    "Bina": bina["Bina"],
                    "Gölge Uzunluğu (m)": round(golge_uzunlugu, 2),
                    "Gölge Azimutu (°)": round(golge_azimutu, 2),
                    "Gölge Yönü": yon_belirle(golge_azimutu),
                    "Gölge Bitiş X (m)": round(golge_bitis_x, 2),
                    "Gölge Bitiş Y (m)": round(golge_bitis_y, 2)

                })

        st.dataframe(
            pd.DataFrame(golge_sonuclari),
            hide_index=True,
            use_container_width=True
        )
        
        # Komşu binaların saatlik zemin gölge izdüşümleri
        geometrik_golge_sonuclari = []

        for veri in sonuclar:
            yukseklik = veri["Güneş Yüksekliği (α)"]
            azimut = veri["Güneş Azimut Açısı (γs)"]

            if yukseklik <= 0 or azimut is None:
                continue

            golge_yonu = azimut % 360

            for bina_adi, bilgi in komsu_geometrileri.items():
                golge = golge_alani_hesapla(
                    bilgi["poligon"],
                    bilgi["yukseklik"],
                    yukseklik,
                    golge_yonu
                )

                geometrik_golge_sonuclari.append({
                    "Tarih": veri["Tarih"],
                    "Saat": veri["Saat (Türkiye)"],
                    "Bina": bina_adi,
                    "Gölge İzdüşümü (m²)": round(golge.area, 2)
                })

        st.markdown("#### Geometrik Zemin Gölge İzdüşümleri")
        st.dataframe(
            pd.DataFrame(geometrik_golge_sonuclari),
            hide_index=True,
            use_container_width=True
        )

        # K Blok çatı bölümlerine düşen saatlik komşu bina gölgeleri
        cati_golge_sonuclari = []

        for veri in sonuclar:
            gunes_yuksekligi = veri["Güneş Yüksekliği (α)"]
            gunes_azimutu = veri["Güneş Azimut Açısı (γs)"]

            if gunes_yuksekligi <= 0 or gunes_azimutu is None:
                continue

            golge_yonu = gunes_azimutu % 360

            for cati_adi, cati_poligonu in kblok_cati_poligonlari.items():
                cati_yuksekligi = kblok_cati_yukseklikleri[cati_adi]

                # Birleşik arka çıkıntılarda en düşük seviye esas alınır.
                if isinstance(cati_yuksekligi, tuple):
                    cati_yuksekligi = min(cati_yuksekligi)

                golgeler = []

                for bilgi in komsu_geometrileri.values():
                    golge = golge_alani_hesapla(
                        bilgi["poligon"],
                        bilgi["yukseklik"],
                        gunes_yuksekligi,
                        golge_yonu,
                        alici_yuksekligi=cati_yuksekligi
                    )

                    if not golge.is_empty:
                        golgeler.append(golge)

                toplam_golge = (
                    unary_union(golgeler) if golgeler else Polygon()
                )

                golgelenen_alan = cati_poligonu.intersection(
                    toplam_golge
                ).area

                # Gölge ile çatı arasındaki en kısa mesafe
                golge_mesafesi = (
                    round(cati_poligonu.distance(toplam_golge), 2)
                    if not toplam_golge.is_empty
                    else None
                )


                cati_golge_sonuclari.append({
                    "Tarih": veri["Tarih"],
                    "Saat": veri["Saat (Türkiye)"],
                    "Çatı Bölümü": cati_adi,
                    "Gölgelenen Alan (m²)": round(golgelenen_alan, 2),
                    "Gölgeye En Yakın Mesafe (m)": golge_mesafesi
                })

        st.markdown("#### K Blok Çatı Gölge Analizi")
        st.dataframe(
            pd.DataFrame(cati_golge_sonuclari),
            hide_index=True,
            use_container_width=True
        )

        # K Blok ve komşu binaların geometrik yerleşimi
        st.markdown("#### K Blok ve Komşu Binaların Yerleşimi")

        fig_binalar = go.Figure()

        for bina_adi, poligon in bina_poligonlari.items():
            x, y = poligon.exterior.xy

            fig_binalar.add_trace(go.Scatter(
                x=list(x),
                y=list(y),
                mode="lines",
                fill="toself",
                name=bina_adi
            ))
                    # K Blok kenar numaralarını grafikte göster
        for sira, kenar in enumerate(kblok_cephe_kenarlari, start=1):
            x1, y1 = kenar["baslangic"]
            x2, y2 = kenar["bitis"]

            fig_binalar.add_annotation(
                x=(x1 + x2) / 2,
                y=(y1 + y2) / 2,
                text=str(sira),
                showarrow=False,
                font=dict(size=12, color="black"),
                bgcolor="white"
            )
        fig_binalar.update_layout(
            xaxis_title="Doğu - Batı (m)",
            yaxis_title="Kuzey - Güney (m)",
            yaxis=dict(scaleanchor="x", scaleratio=1),
            height=650
        )

        # Saatlik gölge görüntüleme seçimi

        secili_tarih = st.selectbox(
            "Gölge görüntüleme tarihi",
            sorted(set(v["Tarih"] for v in sonuclar)),
            key="kblok_golge_tarihi"
        )

        secili_saat = st.selectbox(
            "Gölge görüntüleme saati",
            sorted(set(str(v["Saat (Türkiye)"]) for v in sonuclar)),
            index=3,
            key="kblok_golge_saati_harita_tek"
        )
        
        ornek_veri = next(
            (
                v for v in sonuclar
                if v["Tarih"] == secili_tarih
                and str(v["Saat (Türkiye)"]) == secili_saat
            ),
            None
        )

        if ornek_veri is not None:
            ornek_yukseklik = ornek_veri["Güneş Yüksekliği (α)"]
            ornek_azimut = ornek_veri["Güneş Azimut Açısı (γs)"]

            if ornek_yukseklik > 0 and ornek_azimut is not None:
                for bina_adi, bilgi in komsu_geometrileri.items():
                    golge = golge_alani_hesapla(
                        bilgi["poligon"],
                        bilgi["yukseklik"],
                        ornek_yukseklik,
                        ornek_azimut % 360
                    )

                    # Bina tabanını gölge çiziminden ayır
                    golge = golge.difference(bilgi["poligon"])

                    if golge.is_empty:
                        continue

                    parcalar = (
                        [golge] if golge.geom_type == "Polygon"
                        else list(golge.geoms)
                    )

                    for parca in parcalar:
                        x, y = parca.exterior.xy

                        fig_binalar.add_trace(go.Scatter(
                            x=list(x),
                            y=list(y),
                            mode="lines",
                            fill="toself",
                            fillcolor="rgba(70,70,70,0.35)",
                            line=dict(color="rgba(70,70,70,0.5)"),
                            name="Gölge - " + bina_adi,
                            showlegend=False
                        ))


        st.plotly_chart(fig_binalar, use_container_width=True)

        st.subheader("Dört Mevsim İçin Saatlik Gölge Görselleri")
        # Saatlik görseller için gölgesiz temel bina haritası
        fig_temel = go.Figure(
                data=[
                    iz for iz in fig_binalar.data
                    if not str(iz.name).startswith("Gölge - ")
                ],
                layout=fig_binalar.layout
            )
        # Dört mevsim için örnek günler
        mevsim_tarihleri = {
                "İlkbahar": "2023-03-21",
                "Yaz": "2023-06-21",
                "Sonbahar": "2023-09-23",
                "Kış": "2023-12-21"
            }
        mevsim_sekmeleri = st.tabs(list(mevsim_tarihleri.keys()))

        for sekme, (mevsim, tarih) in zip(
                mevsim_sekmeleri, mevsim_tarihleri.items()
            ):
                with sekme:
                    st.write(f"{mevsim} – {tarih}")
                    gun_mevsim = pd.Timestamp(tarih).date()
                    delta_mevsim = deklinasyon_hesapla(gun_mevsim)

                    saatlik_gunes = []

                    for saat_mevsim in range(24):
                        gunes_saati = gunes_zamani_hesapla(
                        gun_mevsim, saat_mevsim, boylam
                        )
                        omega = saat_acisi_hesapla(gunes_saati)
                        zenit = zenit_acisi_hesapla(enlem, delta_mevsim, omega)
                        alfa = gunes_yuksekligi_hesapla(zenit)
                        azimut = gunes_azimutu_hesapla(
                        enlem, delta_mevsim, omega, zenit
                        )

                        if alfa > 0 and azimut is not None:
                            saatlik_gunes.append({
                            "Saat": f"{saat_mevsim:02d}:00",
                            "Yükseklik": alfa,
                            "Azimut": azimut
                        })

                    st.write(f"Gündüz saatleri: {len(saatlik_gunes)}")
                            
                    # İlk gündüz saati için gölge görseli
                    if saatlik_gunes:
                        sutunlar = st.columns(3)
                        for i, veri in enumerate(saatlik_gunes):
                            fig_saatlik = go.Figure(fig_temel)

                            for bina_adi, bilgi in komsu_geometrileri.items():
                                golge = golge_alani_hesapla(
                                    bilgi["poligon"],
                                    bilgi["yukseklik"],
                                    veri["Yükseklik"],
                                    veri["Azimut"] % 360
                                )

                                golge = golge.difference(bilgi["poligon"])

                                if golge.is_empty:
                                    continue

                                parcalar = (
                                    [golge] if golge.geom_type == "Polygon"
                                    else list(golge.geoms)
                                )

                                for parca in parcalar:
                                    x, y = parca.exterior.xy
                                    fig_saatlik.add_trace(go.Scatter(
                                        x=list(x),
                                        y=list(y),
                                        mode="lines",
                                        fill="toself",
                                        fillcolor="rgba(70,70,70,0.35)",
                                        line=dict(color="rgba(70,70,70,0.5)"),
                                        name="Gölge - " + bina_adi,
                                        showlegend=False
                                    ))

                            fig_saatlik.update_layout(
                                height=260,
                                margin=dict(l=5, r=5, t=5, b=5),
                                showlegend=False
                            )

                            with sutunlar[i % 3]:
                                st.write(f"Saat: {veri['Saat']}")
                                st.plotly_chart(
                                    fig_saatlik,
                                    use_container_width=True,
                                    key=f"golge_{mevsim}_{i}"
                                )
