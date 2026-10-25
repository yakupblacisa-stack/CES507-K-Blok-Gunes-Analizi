# ☀️ CES507 – K Blok Güneş Enerjisi Analizi

## 📌 Proje Hakkında

Bu proje, İstanbul Medeniyet Üniversitesi CES507 Rüzgâr, Güneş ve Jeotermal Enerji Sistemleri dersi kapsamında geliştirilmiştir.

Çalışmanın amacı, İstanbul Medeniyet Üniversitesi Kuzey Kampüs K Blok binasının güneş geometrisini analiz etmek, bina cephelerine güneş ışınlarının geliş açılarını hesaplamak ve elde edilen sonuçları bilimsel hesaplama araçlarıyla karşılaştırmaktır.

Proje, kullanıcı tarafından seçilen tarih aralığında saatlik hesaplamalar gerçekleştirebilen interaktif bir güneş enerjisi analiz paneli olarak geliştirilmektedir.

## ✅ 1. Aşama – Güneş Geometrisi ve Cephe Analizi

Bu aşama kapsamında aşağıdaki çalışmalar tamamlanmıştır:

- Seçilen tarih aralığı için saatlik güneş konumu hesaplamaları
- Güneş deklinasyon açısı (δ) hesaplaması
- Güneş saat açısı (ω) hesaplaması
- Güneş zenit açısı (θz) hesaplaması
- Güneş yükseklik açısı (α) hesaplaması
- Güneş azimut açısı (γs) hesaplaması
- Güneş konumu sonuçlarının pvlib ile karşılaştırılması
- K Blok binasının dört cephe yönünün belirlenmesi
- Dört cepheye güneş ışınlarının geliş açılarının hesaplanması
- Cephe geliş açılarının pvlib sonuçlarıyla karşılaştırılması
- İki hesaplama yöntemi arasındaki açısal farkların belirlenmesi
- İnteraktif güneş açısı grafikleri ve saatlik sonuç tablolarının oluşturulması
- Cephe analizi sonuçlarının Excel formatında dışa aktarılması

## 📍 K Blok Konum Bilgileri

**Bina:** İstanbul Medeniyet Üniversitesi Kuzey Kampüs K Blok

- **Enlem:** 40.996320° Kuzey
- **Boylam:** 29.065165° Doğu

Binanın coğrafi koordinatları, güneşin saatlik konumunun hesaplanmasında esas alınmıştır.

## 🏢 K Blok Cephe Yönleri ve Azimut Açıları

K Blok binasının cephe yönleri, Google Earth Pro üzerinden yapılan uydu görüntüsü incelemeleri ve bina doğrultusu ölçümleri esas alınarak belirlenmiştir.

Cephelerin azimut açıları, coğrafi kuzey referans alınarak saat yönünde 0°–360° arasında tanımlanmıştır.

| Cephe | Yön | Azimut Açısı |
|---|---|---|
| 1. Cephe | Kuzeydoğuya bakan cephe | 23,70° |
| 2. Cephe | Güneydoğuya bakan cephe | 113,70° |
| 3. Cephe | Güneybatıya bakan cephe | 203,70° |
| 4. Cephe | Kuzeybatıya bakan cephe | 293,70° |

### 1. Kuzeydoğu Cephesi – 23,70°

Bu cephe, coğrafi kuzey yönünden saat yönünde 23,70° doğuya dönüktür.

Kuzey ile kuzeydoğu arasında yer almakta olup kuzey yönüne daha yakındır.

### 2. Güneydoğu Cephesi – 113,70°

Bu cephe, coğrafi kuzey yönünden saat yönünde 113,70° açısına sahiptir.

Doğu yönünden güneye doğru 23,70° dönük olup doğu ile güney arasında konumlanmaktadır.

### 3. Güneybatı Cephesi – 203,70°

Bu cephe, coğrafi kuzey yönünden saat yönünde 203,70° açısına sahiptir.

Güney yönünden batıya doğru 23,70° dönük olup güney ile batı arasında konumlanmaktadır.

### 4. Kuzeybatı Cephesi – 293,70°

Bu cephe, coğrafi kuzey yönünden saat yönünde 293,70° açısına sahiptir.

Batı yönünden kuzeye doğru 23,70° dönük olup batı ile kuzey arasında konumlanmaktadır.

**Not:** Cephe adları genel yönleri ifade etmektedir. Hesaplamalarda esas alınan değerler, Google Earth Pro ölçümlerinden belirlenen sayısal azimut açılarıdır.

## 📐 Güneş Geometrisi Hesaplama Yöntemi

Saatlik güneş geometrisi hesaplamalarında, *Solar Engineering of Thermal Processes* kitabında yer alan güneş geometrisi bağıntıları esas alınmıştır.

Seçilen tarih ve coğrafi konuma bağlı olarak güneşin deklinasyon, saat, zenit, yükseklik ve azimut açıları hesaplanmıştır.

Kendi hesaplama yöntemimizde güneş azimut açısı güney referanslı olarak tanımlanmıştır:

- Güney: 0°
- Doğu: −90°
- Batı: +90°

pvlib karşılaştırmalarında ise kullanılan açı referansları arasında gerekli matematiksel dönüşümler uygulanmıştır.

Hesaplanan saatlik güneş konumu sonuçları pvlib verileriyle karşılaştırılmış ve iki yöntem arasındaki açısal farklar belirlenmiştir.

## ☀️ Cephelere Güneş Geliş Açısı Analizi

K Blok binasının dört cephesi için güneş ışınlarının geliş açıları hesaplanmıştır.

Bina cepheleri düşey yüzeyler olarak değerlendirilmiş ve yüzey eğim açıları **90°** kabul edilmiştir.

Her cephe için hesaplamalarda şu bilgiler kullanılmıştır:

- Güneşin saatlik yükseklik açısı
- Güneşin saatlik azimut açısı
- Cephenin azimut açısı
- Cephenin yüzey eğim açısı

Her saat için elde edilen geliş açıları pvlib sonuçlarıyla karşılaştırılmıştır.

Karşılaştırma tablolarında her cephe için üç değer yan yana gösterilmektedir:

1. Kendi hesaplamamızla bulunan geliş açısı
2. pvlib ile hesaplanan geliş açısı
3. İki hesaplama arasındaki mutlak açısal fark

Güneşin ufkun altında bulunduğu gece saatleri, saatlik sonuç tablolarında korunmuştur. Ancak bu saatlerde doğrudan güneş ışınımı bulunmadığından cephe geliş açısı alanları boş bırakılmıştır.

90°'den büyük geliş açıları, güneşin ilgili cephenin arka tarafında bulunduğunu ifade etmektedir.

## 📊 Analiz Paneli ve Sonuçların Dışa Aktarılması

Geliştirilen analiz paneli üzerinden kullanıcılar:

- Binanın coğrafi koordinatlarını belirleyebilir.
- İstenilen tarih aralığını seçebilir.
- Saatlik güneş konumu hesaplamalarını gerçekleştirebilir.
- Kendi hesaplamaları ile pvlib sonuçlarını karşılaştırabilir.
- Dört cephenin geliş açılarını inceleyebilir.
- İki hesaplama yöntemi arasındaki farkları değerlendirebilir.
- Sonuçları tablo ve grafikler üzerinden görüntüleyebilir.
- Cephe analizi sonuçlarını Excel formatında indirebilir.

## 📋 Sonraki Aşamalar

Projenin devamında aşağıdaki çalışmaların gerçekleştirilmesi planlanmaktadır:

- PVGIS üzerinden saatlik güneş ışınımı verilerinin analizi
- K Blok ve çevresindeki yapıların gölgeleme analizi
- Gölgeli ve gölgesiz cephe güneş kazançlarının karşılaştırılması
- Çatı üzeri güneş enerjisi üretim potansiyelinin değerlendirilmesi
- Enerji ve CO₂ azaltım analizleri
- Ekonomik geri ödeme süresinin hesaplanması

## 📚 Kaynakça

Duffie, J. A., Beckman, W. A. & Blair, N. – *Solar Engineering of Thermal Processes*, 5. Baskı, 2020.
