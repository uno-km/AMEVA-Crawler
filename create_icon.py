"""
Script to create high quality AMEVA brand icon (ICO & PNG) using standard library.
"""
import os
import struct
import zlib
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# Fetch original SVG from GitHub
svg_url = "https://raw.githubusercontent.com/uno-km/uno-km/main/assets/brand/favicon.svg"
svg_path = os.path.join(ASSETS_DIR, "favicon.svg")
try:
    with urllib.request.urlopen(svg_url, timeout=10) as resp:
        with open(svg_path, "wb") as f:
            f.write(resp.read())
except Exception as e:
    print(f"SVG download skipped: {e}")

def create_bmp_data(size):
    """
    Generate raw 32-bit ARGB BMP pixel data for AMEVA CI Icon.
    Circular dark space background with glowing aqua/cyan amoeba/node emblem.
    """
    width, height = size, size
    pixels = bytearray()
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    radius = width * 0.46

    for y in range(height): # BMP stores bottom to top
        for x in range(width):
            dx = x - center_x
            dy = (height - 1 - y) - center_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist > radius + 1.0:
                # Transparent outside circle
                pixels.extend([0, 0, 0, 0]) # B, G, R, A
            else:
                # Anti-aliasing alpha
                if dist > radius:
                    alpha = int(255 * (radius + 1.0 - dist))
                else:
                    alpha = 255

                # Core gradient colors (Dark Space background: #060A17 -> #0B132B -> #162244)
                norm_dist = dist / radius
                bg_r = int(6 + 16 * (1.0 - norm_dist))
                bg_g = int(10 + 24 * (1.0 - norm_dist))
                bg_b = int(23 + 45 * (1.0 - norm_dist))

                # Foreground Emblem: Aqua-Cyan Glowing Ring & Nodes
                # Inner glowing circle ring at 0.45 * radius to 0.75 * radius
                ring_dist = abs(dist - 0.58 * radius)
                if ring_dist < width * 0.16:
                    ring_intensity = 1.0 - (ring_dist / (width * 0.16))
                    # Cyan/Aqua gradient (#00F5D4 -> #38BDF8)
                    fg_r = int(0 * ring_intensity + bg_r * (1 - ring_intensity))
                    fg_g = int(235 * ring_intensity + bg_g * (1 - ring_intensity))
                    fg_b = int(245 * ring_intensity + bg_b * (1 - ring_intensity))
                elif dist < width * 0.22:
                    # Center Core Node (Bright Cyan White Core)
                    core_intensity = 1.0 - (dist / (width * 0.22))
                    fg_r = int(220 * core_intensity + bg_r * (1 - core_intensity))
                    fg_g = int(255 * core_intensity + bg_g * (1 - core_intensity))
                    fg_b = int(255 * core_intensity + bg_b * (1 - core_intensity))
                else:
                    fg_r, fg_g, fg_b = bg_r, bg_g, bg_b

                pixels.extend([fg_b, fg_g, fg_r, alpha]) # B, G, R, A

    return width, height, bytes(pixels)

def create_ico_file(ico_path, sizes=[16, 32, 48, 64, 128]):
    """Pack multiple resolution BMPs into standard Windows .ico file."""
    images = []
    for s in sizes:
        w, h, raw_rgba = create_bmp_data(s)
        # BITMAPINFOHEADER (40 bytes)
        bi_size = 40
        bi_width = w
        bi_height = h * 2 # In ICO, height is 2x for XOR + AND masks
        bi_planes = 1
        bi_bit_count = 32
        bi_compression = 0
        bi_size_image = len(raw_rgba)
        bi_header = struct.pack("<IIIHHIIIIII", bi_size, bi_width, bi_height, bi_planes, bi_bit_count, bi_compression, bi_size_image, 0, 0, 0, 0)
        # AND mask (1 bit per pixel, padded to 32-bit row)
        and_row_bytes = ((w + 31) // 32) * 4
        and_mask = b"\x00" * (and_row_bytes * h)
        image_data = bi_header + raw_rgba + and_mask
        images.append((w, h, image_data))

    # ICO Header
    ico_header = struct.pack("<HHH", 0, 1, len(images)) # Reserved, Type=1(Icon), Count
    entries = bytearray()
    offset = 6 + 16 * len(images)
    for w, h, data in images:
        entry = struct.pack("<BBBBHHII", w if w < 256 else 0, h if h < 256 else 0, 0, 0, 1, 32, len(data), offset)
        entries.extend(entry)
        offset += len(data)

    with open(ico_path, "wb") as f:
        f.write(ico_header)
        f.write(entries)
        for _, _, data in images:
            f.write(data)

    print(f"[+] Created AMEVA Brand ICO: {ico_path}")

if __name__ == "__main__":
    ico_file = os.path.join(ASSETS_DIR, "icon.ico")
    create_ico_file(ico_file)
