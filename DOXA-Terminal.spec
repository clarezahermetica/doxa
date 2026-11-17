from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs
from pathlib import Path
import sys

sys.path.insert(0, str(Path(SPECPATH) / 'src'))
from doxa.version import DISPLAY_VERSION, TERMINAL_BUILD, VERSION, WINDOWS_VERSION
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

windows_version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=WINDOWS_VERSION, prodvers=WINDOWS_VERSION,
                      mask=0x3f, flags=0x0a, OS=0x40004, fileType=0x1,
                      subtype=0x0, date=(0, 0)),
    kids=[StringFileInfo([StringTable('040904B0', [
        StringStruct('ProductName', 'DOXA'),
        StringStruct('FileDescription', DISPLAY_VERSION),
        StringStruct('ProductVersion', VERSION),
        StringStruct('FileVersion', VERSION),
        StringStruct('PrivateBuild', TERMINAL_BUILD),
        StringStruct('OriginalFilename', 'doxa.exe'),
    ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])],
)

a = Analysis(['scripts/terminal_entry.py'], pathex=['src'],
    datas=collect_data_files('doxa', include_py_files=True, includes=['storage/migrations/**'])
          + collect_data_files('textual')
          + collect_data_files('doxa', includes=['cli/model_catalog.json']),
    binaries=collect_dynamic_libs('moss_core'),
    hiddenimports=collect_submodules('doxa', filter=lambda name: not name.startswith('doxa.desktop'))
                  + collect_submodules('moss') + collect_submodules('moss_core')
                  + collect_submodules('textual'),
    excludes=['doxa.desktop', 'webview', 'clr', 'pythonnet', 'pytest', 'mypy', 'ruff'],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='doxa', console=True,
          version=windows_version)
coll = COLLECT(exe, a.binaries, a.datas, name='DOXA')
