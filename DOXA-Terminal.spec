from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

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
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='doxa', console=True)
coll = COLLECT(exe, a.binaries, a.datas, name='DOXA')
