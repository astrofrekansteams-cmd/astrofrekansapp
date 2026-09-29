"""Derive Android/iOS launcher icons from the existing branding asset.

This only resizes assets/branding/app_icon/app_icon.png - no new artwork.
iOS icons are flattened onto the brand night colour because the App Store
rejects icons with an alpha channel.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets/branding/app_icon/app_icon.png"
NIGHT = (5, 7, 15)

ANDROID = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

IOS = [
    ("Icon-App-20x20@1x.png", 20), ("Icon-App-20x20@2x.png", 40), ("Icon-App-20x20@3x.png", 60),
    ("Icon-App-29x29@1x.png", 29), ("Icon-App-29x29@2x.png", 58), ("Icon-App-29x29@3x.png", 87),
    ("Icon-App-40x40@1x.png", 40), ("Icon-App-40x40@2x.png", 80), ("Icon-App-40x40@3x.png", 120),
    ("Icon-App-60x60@2x.png", 120), ("Icon-App-60x60@3x.png", 180),
    ("Icon-App-76x76@1x.png", 76), ("Icon-App-76x76@2x.png", 152),
    ("Icon-App-83.5x83.5@2x.png", 167),
    ("Icon-App-1024x1024@1x.png", 1024),
]


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")

    for folder, size in ANDROID.items():
        target = ROOT / "android/app/src/main/res" / folder / "ic_launcher.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        source.resize((size, size), Image.LANCZOS).save(target)
        print("android", target.relative_to(ROOT))

    ios_dir = ROOT / "ios/Runner/Assets.xcassets/AppIcon.appiconset"
    if ios_dir.exists():
        flat = Image.new("RGB", source.size, NIGHT)
        flat.paste(source, mask=source.split()[3])
        for name, size in IOS:
            flat.resize((size, size), Image.LANCZOS).save(ios_dir / name)
            print("ios", name)


if __name__ == "__main__":
    main()
