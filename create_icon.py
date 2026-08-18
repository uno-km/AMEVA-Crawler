"""
Script to ensure high quality AMEVA brand icon (ICO & PNG) assets.
"""
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

AMEVA_ASSETS_DIR = os.path.join(os.path.dirname(BASE_DIR), "ameva_assets")
PROGRAM_ICONS_DIR = os.path.join(AMEVA_ASSETS_DIR, "program_icons")

def sync_brand_icons():
    src_ico = os.path.join(PROGRAM_ICONS_DIR, "icon_harvester.ico")
    src_png = os.path.join(PROGRAM_ICONS_DIR, "icon_harvester.png")
    src_svg = os.path.join(AMEVA_ASSETS_DIR, "favicon.svg")

    dest_ico = os.path.join(ASSETS_DIR, "icon.ico")
    dest_png = os.path.join(ASSETS_DIR, "icon.png")
    dest_svg = os.path.join(ASSETS_DIR, "favicon.svg")

    if os.path.exists(src_ico):
        shutil.copy2(src_ico, dest_ico)
        print(f"[+] Synced official ICO: {dest_ico}")
    if os.path.exists(src_png):
        shutil.copy2(src_png, dest_png)
        print(f"[+] Synced official PNG: {dest_png}")
    if os.path.exists(src_svg):
        shutil.copy2(src_svg, dest_svg)
        print(f"[+] Synced official SVG: {dest_svg}")

if __name__ == "__main__":
    sync_brand_icons()
