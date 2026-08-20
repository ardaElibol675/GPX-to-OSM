#!/usr/bin/env python3
import os
import argparse
import sys
import math
import xml.etree.ElementTree as ET
from xml.dom import minidom
import gpxpy
import pyproj
import numpy as np
from scipy.interpolate import splprep, splev

def calculate_offsets(x, y, dx, dy, width):
    length = math.hypot(dx, dy)
    if length == 0:
        return (x, y), (x, y)
    
    nx = -dy / length
    ny = dx / length
    
    half_w = width / 2.0
    left_x = x + nx * half_w
    left_y = y + ny * half_w
    right_x = x - nx * half_w
    right_y = y - ny * half_w
    
    return (left_x, left_y), (right_x, right_y)

def prettify(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def convert_gpx_to_osm(input_file, width, grid, projector, datum, chunk_size, speed_limit, resolution, smooth_factor, reverse_path, output_name):
    if output_name:
        if not output_name.endswith(".osm"):
            output_name += ".osm"
        output_file = output_name
    else:
        output_file = os.path.splitext(input_file)[0] + ".osm"
    
    with open(input_file, 'r', encoding='utf-8') as f:
        gpx = gpxpy.parse(f)
        
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append(point)
                
    if len(points) < 4:
        print("Hata: Kübik Spline (yumuşatma) için GPX dosyasında en az 4 noktaya ihtiyaç var.")
        return

    if reverse_path:
        points.reverse()
        print("Bilgi: Rota yönü tersine çevrildi (--reverse aktif).")

    try:
        utm_zone = int(grid[:2])
    except ValueError:
        # Eğer grid 9'dan küçükse (Örn: "05V") veya düzgün okunamazsa güvenli bir fallback yap
        utm_zone = int(''.join(filter(str.isdigit, grid))) if any(c.isdigit() for c in grid) else 34

    # Silesia Ring (Kuzey Yarımküre) için projeksiyon dizgesi
    # EHB / Autoware standartlarına tam uyumlu UTM projeksiyonu
    proj_string = f"+proj=utm +zone={utm_zone} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
    
    wgs84_proj = pyproj.Proj(proj='latlong', datum='WGS84')
    local_proj = pyproj.Proj(proj_string)
    
    transformer_to_local = pyproj.Transformer.from_proj(wgs84_proj, local_proj, always_xy=True)
    transformer_to_wgs84 = pyproj.Transformer.from_proj(local_proj, wgs84_proj, always_xy=True)

    raw_local_coords = []
    for p in points:
        x, y = transformer_to_local.transform(p.longitude, p.latitude)
        raw_local_coords.append((x, y, p.elevation if p.elevation else 0.0))

    local_coords = [raw_local_coords[0]]
    for i in range(1, len(raw_local_coords)):
        cx, cy, ele = raw_local_coords[i]
        px, py, _ = local_coords[-1]
        if math.hypot(cx - px, cy - py) > 0.1:
            local_coords.append((cx, cy, ele))

    if len(local_coords) < 4:
        print("Hata: Filtreleme sonrası yeterli nokta kalmadı (En az 4 gerekli).")
        return

    pts = np.array(local_coords)
    x_arr = pts[:, 0]
    y_arr = pts[:, 1]
    ele_arr = pts[:, 2]

    tck, u = splprep([x_arr, y_arr, ele_arr], s=smooth_factor)

    total_length = np.sum(np.sqrt(np.diff(x_arr)**2 + np.diff(y_arr)**2))
    num_points = max(int(total_length / resolution), 4)

    u_new = np.linspace(0, 1, num_points)
    new_points = splev(u_new, tck)

    smoothed_coords = list(zip(new_points[0], new_points[1], new_points[2]))

    center_nodes, left_nodes, right_nodes = [], [], []
    
    for i in range(len(smoothed_coords)):
        cx, cy, ele = smoothed_coords[i]
        
        if i < len(smoothed_coords) - 1:
            nx, ny, _ = smoothed_coords[i+1]
            dx, dy = nx - cx, ny - cy
        else:
            px, py, _ = smoothed_coords[i-1]
            dx, dy = cx - px, cy - py
            
        (lx, ly), (rx, ry) = calculate_offsets(cx, cy, dx, dy, width)
        
        c_lon, c_lat = transformer_to_wgs84.transform(cx, cy)
        l_lon, l_lat = transformer_to_wgs84.transform(lx, ly)
        r_lon, r_lat = transformer_to_wgs84.transform(rx, ry)
        
        center_nodes.append((c_lat, c_lon, ele))
        left_nodes.append((l_lat, l_lon, ele))
        right_nodes.append((r_lat, r_lon, ele))

    osm = ET.Element("osm", version="0.6", generator="VectorMap MGRS Generator with Spline")
    
    # ==========================================
    # --- POZİTİF ID SİSTEMİ DEĞİŞİKLİĞİ ---
    # ==========================================
    global_id = 1  # 1'den başla
    def get_id():
        nonlocal global_id
        current = global_id
        global_id += 1  # Her seferinde artır (Pozitif ID)
        return current
    # ==========================================

    c_ids = [get_id() for _ in center_nodes]
    l_ids = [get_id() for _ in left_nodes]
    r_ids = [get_id() for _ in right_nodes]

    for i in range(len(smoothed_coords)):
        node = ET.SubElement(osm, "node", id=str(c_ids[i]), lat=str(center_nodes[i][0]), lon=str(center_nodes[i][1]), version="1")
        ET.SubElement(node, "tag", k="ele", v=str(center_nodes[i][2]))
        node = ET.SubElement(osm, "node", id=str(l_ids[i]), lat=str(left_nodes[i][0]), lon=str(left_nodes[i][1]), version="1")
        ET.SubElement(node, "tag", k="ele", v=str(left_nodes[i][2]))
        node = ET.SubElement(osm, "node", id=str(r_ids[i]), lat=str(right_nodes[i][0]), lon=str(right_nodes[i][1]), version="1")
        ET.SubElement(node, "tag", k="ele", v=str(right_nodes[i][2]))

    def create_way(node_ids, way_type):
        way_id = get_id()
        way = ET.SubElement(osm, "way", id=str(way_id), version="1")
        for nid in node_ids:
            ET.SubElement(way, "nd", ref=str(nid))
        ET.SubElement(way, "tag", k="type", v=way_type)
        ET.SubElement(way, "tag", k="ProjectorType", v=projector)
        ET.SubElement(way, "tag", k="VerticalDatum", v=datum)
        ET.SubElement(way, "tag", k="MgrsGrid", v=grid)
        return way_id

    for i in range(0, len(c_ids) - 1, chunk_size):
        end_idx = min(i + chunk_size, len(c_ids) - 1)
        
        c_chunk = c_ids[i:end_idx+1]
        l_chunk = l_ids[i:end_idx+1]
        r_chunk = r_ids[i:end_idx+1]
        
        c_way_id = create_way(c_chunk, "centerline")
        l_way_id = create_way(l_chunk, "line_thin")
        r_way_id = create_way(r_chunk, "line_thin")
        
        rel_id = get_id()
        relation = ET.SubElement(osm, "relation", id=str(rel_id), version="1")
        ET.SubElement(relation, "member", type="way", ref=str(l_way_id), role="left")
        ET.SubElement(relation, "member", type="way", ref=str(r_way_id), role="right")
        ET.SubElement(relation, "tag", k="type", v="lanelet")
        ET.SubElement(relation, "tag", k="subtype", v="road")
        ET.SubElement(relation, "tag", k="one_way", v="yes")
        ET.SubElement(relation, "tag", k="speed_limit", v=str(speed_limit))

    xml_str = prettify(osm)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_str)
        
    print(f"Başarılı! {output_file} oluşturuldu.")
    print(f"Üretilen Nokta Sayısı: {num_points} (Çözünürlük: {resolution}m)")
    print(f"Parametreler -> Grid: {grid}, Hız: {speed_limit}km/h, Chunk: {chunk_size}, Smooth: {smooth_factor}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GPX dosyasını Autoware Vector Map uyumlu, Spline ile yumuşatılmış OSM dosyasına dönüştürür.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("input", help="Dönüştürülecek .gpx dosyasının yolu")
    parser.add_argument("--width", type=float, default=3.5, help="Yol genişliği (m). Varsayılan: 3.5")
    parser.add_argument("--grid", type=str, default="35TPF", help="MGRS Grid. Varsayılan: 35TPF")
    parser.add_argument("--projector", type=str, default="MGRS", help="Projeksiyon. Varsayılan: MGRS")
    parser.add_argument("--datum", type=str, default="WGS84", help="Datum. Varsayılan: WGS84")
    parser.add_argument("--chunk", type=int, default=100, help="Bir yol parçasındaki düğüm sayısı. Varsayılan: 100")
    parser.add_argument("--speed", type=int, default=30, help="Varsayılan hız limiti (km/h). Varsayılan: 30")
    parser.add_argument("--res", type=float, default=0.5, help="Eğri çözünürlüğü (m). Varsayılan: 0.5")
    parser.add_argument("--smooth", type=float, default=2.0, help="Yumuşatma toleransı. Varsayılan: 2.0")
    parser.add_argument("--reverse", action="store_true", help="Rotayı tersten oluşturur.")
    parser.add_argument("--name", type=str, default=None, help="Oluşturulacak .osm dosyasının özel adı.")
    
    if len(sys.argv) == 2 and sys.argv[1].lower() == "help":
        parser.print_help()
        sys.exit(0)
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Hata: '{args.input}' bulunamadı!")
    else:
        convert_gpx_to_osm(
            args.input, args.width, args.grid, args.projector, args.datum, 
            args.chunk, args.speed, args.res, args.smooth, args.reverse, args.name
        )