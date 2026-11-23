# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

dados, binarios, modulos = collect_all("cryptography")
a = Analysis(["passvault/__main__.py"], pathex=[SPECPATH], binaries=binarios,
             datas=dados + [("passvault/assets", "passvault/assets")],
             hiddenimports=modulos, excludes=["PIL"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="PassVault", console=False,
          debug=False, strip=False, upx=False, icon="passvault/assets/passvault.ico",
          version="version_info.txt", manifest="app.manifest")
