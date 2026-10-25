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
- K Blok binasının dört ana cephe yönünün belirlenmesi
- Dört cepheye güneş ışınlarının geliş açılarının hesaplanması
- Cephe geliş açılarının pvlib sonuçlarıyla karşılaştırılması
- İki hesaplama yöntemi arasındaki açısal farkların belirlenmesi
- İnteraktif güneş açısı grafikleri ve saatlik sonuç tablolarının oluşturulması
- Cephe analizi sonuçlarının Excel formatında dışa aktarılması

## 📍 K Blok Konum Bilgileri

**Bina:** İstanbul Medeniyet Üniversitesi Kuzey Kampüs K Blok

- **Enlem:** 40.995997° Kuzey
- **Boylam:** 29.065936° Doğu

Binanın coğrafi koordinatları, güneşin saatlik konumunun hesaplanmasında esas alınmıştır.

## 📐 K Blok Bina Ölçüleri

K Blok binasının yaklaşık yatay boyutları Google Earth üzerinden yapılan ölçümler kullanılarak belirlenmiştir.

| Özellik | Değer |
|---|---|
| Bina genişliği | 20,58 m |
| Bina uzunluğu | 31,30 m |
| Kat sayısı | 6 kat (model kabulü) |
| Kat yüksekliği | 3,50 m (varsayım) |
| Toplam bina yüksekliği | 21,00 m (tahmini) |

**Google Earth üzerinden ölçülen bina kenarları:**

| Kenar | Ölçülen uzunluk | Kenar doğrultusu |
|---|---|---|
| Üst kenar | 20,58 m | 113,81° |
| Sağ kenar | 31,30 m | 204,79° |
| Alt kenar | 18,85 m | 111,95° |
| Sol kenar | 31,98 m | 201,12° |

**Not:** Bina yüksekliği doğrudan ölçülmemiştir. Altı kat ve kat başına 3,50 metre kabul edilerek yaklaşık 21 metre hesaplanmıştır. Mevcut 3B gösterimde bina, dikdörtgen ana gövdeyle temsil edilmektedir. Gerçek binanın kademeli bölümleri, girinti ve çıkıntıları ile kavisli cephesi henüz ayrıntılı olarak modellenmemiştir.

## 🏢 K Blok Cephe Yönleri ve Azimut Açıları

K Blok binasının cephe yönleri, Google Earth üzerinden yapılan uydu görüntüsü incelemeleri ve bina kenarlarının doğrultu ölçümleri esas alınarak belirlenmiştir.

Cephelerin dışa bakan normal doğrultuları, ölçülen kenar doğrultularına 90° eklenerek veya çıkarılarak yaklaşık olarak hesaplanmıştır.

Cephe azimut açıları coğrafi kuzey referans alınarak saat yönünde 0°–360° arasında tanımlanmıştır.

| Cephe | Yön | Azimut açısı |
|---|---|---|
| 1. Cephe | Kuzey-kuzeydoğuya bakan cephe | 23,81° |
| 2. Cephe | Doğu-güneydoğuya bakan cephe | 114,79° |
| 3. Cephe | Güney-güneybatıya bakan cephe | 201,95° |
| 4. Cephe | Batı-kuzeybatıya bakan cephe | 291,12° |

### 1. Kuzeydoğu Cephesi – 23,81°

Bu cephe, coğrafi kuzey yönünden saat yönünde 23,81° doğuya dönüktür.

Kuzey ile kuzeydoğu arasında yer almakta olup kuzey yönüne daha yakındır.

### 2. Güneydoğu Cephesi – 114,79°

Bu cephe, coğrafi kuzey yönünden saat yönünde 114,79° açısına sahiptir.

Doğu yönünden güneye doğru 24,79° dönüktür.

### 3. Güneybatı Cephesi – 201,95°

Bu cephe, coğrafi kuzey yönünden saat yönünde 201,95° açısına sahiptir.

Güney yönünden batıya doğru 21,95° dönüktür.

### 4. Kuzeybatı Cephesi – 291,12°

Bu cephe, coğrafi kuzey yönünden saat yönünde 291,12° açısına sahiptir.

Batı yönünden kuzeye doğru 21,12° dönüktür.

**Not:** Cephe adları genel yön gruplarını ifade etmektedir. Sayısal hesaplamalarda Google Earth ölçümlerinden türetilen yaklaşık azimut açıları kullanılmaktadır. Bunlar mimari projeden alınmış kesin cephe yönleri değildir.

## 📐 Güneş Geometrisi Hesaplama Yöntemi

Saatlik güneş geometrisi hesaplamalarında, *Solar Engineering of Thermal Processes, Photovoltaics and Wind* kitabında yer alan güneş geometrisi bağıntıları esas alınmıştır.

Seçilen tarih ve coğrafi konuma bağlı olarak güneşin deklinasyon, saat, zenit, yükseklik ve azimut açıları hesaplanmıştır.

Kendi hesaplama yöntemimizde güneş azimut açısı güney referanslı olarak tanımlanmıştır:

- Güney: 0°
- Doğu: −90°
- Batı: +90°

pvlib karşılaştırmalarında ise kullanılan açı referansları arasında gerekli matematiksel dönüşümler uygulanmıştır.

Hesaplanan saatlik güneş konumu sonuçları pvlib verileriyle karşılaştırılabilecek şekilde tablolaştırılmıştır.

## ☀️ Cephelere Güneş Geliş Açısı Analizi

K Blok binasının dört ana cephesi için güneş ışınlarının geliş açıları hesaplanmaktadır.

Bina cepheleri düşey yüzeyler olarak değerlendirilmiş ve yüzey eğim açıları **90°** kabul edilmiştir.

Her cephe için hesaplamalarda şu bilgiler kullanılmaktadır:

- Güneşin saatlik yükseklik açısı
- Güneşin saatlik azimut açısı
- Cephenin azimut açısı
- Cephenin yüzey eğim açısı

Düşey yüzeyler için kullanılan bağıntı:

**cos(θ) = cos(α) × cos(A_güneş − A_cephe)**

Her saat için elde edilen geliş açıları pvlib AOI hesaplamalarıyla karşılaştırılmaktadır.

Karşılaştırma tablolarında her cephe için üç değer yan yana gösterilmektedir:

1. Kendi hesaplamamızla bulunan geliş açısı
2. pvlib ile hesaplanan geliş açısı
3. İki hesaplama arasındaki mutlak açısal fark

Güneşin ufkun altında bulunduğu gece saatleri, saatlik sonuç tablolarında korunmaktadır. Ancak bu saatlerde cephe geliş açısı alanları boş bırakılmaktadır.

90°'den büyük geliş açıları, güneşin ilgili cephenin arka tarafında bulunduğunu ifade etmektedir.

**Not:** Yeni K Blok koordinatları ve cephe yönleri yazılıma aktarılmıştır. Yeni bina için pvlib karşılaştırma sonuçlarının sayısal kontrolü henüz tamamlanmamıştır. Önceki binaya ait örnek karşılaştırma değerleri kullanılmamaktadır.

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
- Yaklaşık bina ölçüleriyle oluşturulan 3B güneş konumu simülasyonunu görüntüleyebilir.

Mevcut 3B gösterim, ayrıntılı bina ve çevre yapı gölgeleme modeli değildir.

## 📋 Sonraki Aşamalar

Projenin devamında aşağıdaki çalışmaların gerçekleştirilmesi planlanmaktadır:

- Yeni K Blok koordinatlarıyla saatlik güneş açısı sonuçlarının kontrol edilmesi
- PVGIS üzerinden saatlik güneş ışınımı verilerinin analizi
- K Blok ve çevresindeki yapıların gölgeleme analizi
- Dört mevsimden örnek günler için saatlik gölge görsellerinin hazırlanması
- Gölgeli ve gölgesiz cephe güneş kazançlarının karşılaştırılması
- Çatı üzeri güneş enerjisi üretim potansiyelinin değerlendirilmesi
- Enerji ve CO₂ azaltım analizleri
- Ekonomik geri ödeme süresinin hesaplanması

## 📚 Kaynakça

Duffie, J. A., Beckman, W. A. ve Blair, N. (2020). *Solar Engineering of Thermal Processes, Photovoltaics and Wind* (5. baskı). Wiley.