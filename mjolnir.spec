# -*- mode: python -*-

block_cipher = None


a = Analysis(['bin/mjolnir'],
             pathex=['.'],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             cipher=block_cipher)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='mjolnir',
          debug=False,
          strip=False,
          upx=True,
          console=True )
