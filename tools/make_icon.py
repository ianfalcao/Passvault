"""Gera a marca do PassVault em alta resolução para Tk e Windows."""

from pathlib import Path

from PIL import Image, ImageDraw


def principal() -> None:
    pasta = Path(__file__).resolve().parents[1] / "passvault" / "assets"
    pasta.mkdir(exist_ok=True)
    img = Image.new("RGBA", (512, 512))
    d = ImageDraw.Draw(img)
    d.polygon([(256, 20), (452, 94), (440, 271), (409, 352), (350, 419),
               (256, 486), (162, 419), (103, 352), (72, 271), (60, 94)], fill="#2964D9")
    d.polygon([(256, 49), (419, 113), (409, 259), (383, 333), (327, 399),
               (256, 449)], fill="#1E52BD")
    d.ellipse((206, 154, 306, 254), fill="white")
    d.polygon([(242, 231), (270, 231), (285, 333), (227, 333)], fill="white")
    for nome, tamanho in (("passvault.png", 256), ("logo.png", 64)):
        img.resize((tamanho, tamanho), Image.Resampling.LANCZOS).save(pasta / nome)
    img.save(pasta / "passvault.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])


if __name__ == "__main__":
    principal()
