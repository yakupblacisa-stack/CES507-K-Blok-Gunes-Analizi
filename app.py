
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

with buton_col:
    st.markdown("<div style='height: 27px'></div>", unsafe_allow_html=True)
    hesapla = st.button(
        "☀️ Güneş Açılarını Hesapla",
        use_container_width=True
    )
    # Ana analiz kademeleri
kademe1, kademe2 = st.tabs([
    "☀️ 1. Kademe: Güneş Açıları",
    "📊 2. Kademe: Işınım Karşılaştırması"
])

if hesapla:

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

            table.gunes-tablosu td {
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
