# gpx_to_osm

GPX rota dosyalarını, Autoware Vector Map ile uyumlu, kübik spline ile yumuşatılmış `.osm` (lanelet) dosyalarına dönüştüren bir komut satırı aracı.

Bir GPX izindeki noktaları alır, kübik spline ile yumuşatır, verilen yol genişliğine göre sol/sağ kenar çizgilerini hesaplar ve sonucu `centerline` + `left`/`right` lanelet ilişkileri içeren bir OSM XML dosyası olarak üretir.

## Gereksinimler

- Python 3.8+
- [requirements.txt](requirements.txt) içindeki paketler: `numpy`, `scipy`, `pyproj`, `gpxpy`

## Kurulum

```bash
git clone https://github.com/<kullanici-adi>/gpx_to_osm.git
cd gpx_to_osm
pip install -r requirements.txt
./install.sh
```

`install.sh`, `src/gpx_to_osm.py` dosyasını çalıştırılabilir yapar ve `/usr/local/bin/gpx_to_osm` altında bir sembolik link oluşturur. Bu sayede `gpx_to_osm` komutu terminalde her yerden çalışır.

Sembolik linki manuel oluşturmak isterseniz:

```bash
chmod +x src/gpx_to_osm.py
sudo ln -sf "$(pwd)/src/gpx_to_osm.py" /usr/local/bin/gpx_to_osm
```

## Kullanım

```bash
gpx_to_osm rota.gpx [seçenekler]
```

### Seçenekler

| Parametre | Varsayılan | Açıklama |
|---|---|---|
| `input` | - | Dönüştürülecek `.gpx` dosyasının yolu (zorunlu) |
| `--width` | `3.5` | Yol genişliği (m) |
| `--grid` | `35TPF` | MGRS Grid |
| `--projector` | `MGRS` | Projeksiyon tipi |
| `--datum` | `WGS84` | Dikey datum |
| `--chunk` | `100` | Bir yol parçasındaki düğüm sayısı |
| `--speed` | `30` | Hız limiti (km/h) |
| `--res` | `0.5` | Eğri çözünürlüğü (m) |
| `--smooth` | `2.0` | Spline yumuşatma toleransı |
| `--reverse` | kapalı | Rotayı ters yönde oluşturur |
| `--name` | girdi dosyasıyla aynı | Çıktı `.osm` dosyasının adı |

### Örnek

```bash
gpx_to_osm rota.gpx --width 4 --speed 50 --grid 35TPF --name rota_cikti
```

Bu komut `rota_cikti.osm` dosyasını üretir.

> Not: Kübik spline yumuşatma için GPX dosyasında en az 4 nokta bulunmalıdır.
