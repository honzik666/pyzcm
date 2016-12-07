# -*- mode: python -*-
# -*- coding: utf-8 -*-
"""Spec file for pyinstaller

(c) 2016 Jan Capek (honzik666)

MIT license
"""
block_cipher = None
def Entrypoint(dist, group, name,
               scripts=None, pathex=None, hiddenimports=[],
               hookspath=None, excludes=None, runtime_hooks=None):
    """Converts an entrypoint into a temporary script for analysis by
    pyinstaller.

    The code is based on with minor modifications and cleanup for
    python 3.4:
    https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Setuptools-Entry-Point
    """
    import pkg_resources

    # get toplevel packages of distribution from metadata
    def get_toplevel(dist):
        distribution = pkg_resources.get_distribution(dist)
        if distribution.has_metadata('top_level.txt'):
            return list(distribution.get_metadata('top_level.txt').split())
        else:
            return []
    packages = []
    for distribution in hiddenimports:
        packages += get_toplevel(distribution)
    scripts = scripts or []
    pathex = pathex or []
    # get the entry point
    ep = pkg_resources.get_entry_info(dist, group, name)
    # insert path of the egg at the verify front of the search path
    pathex = [ep.dist.location] + pathex
    # script name must not be a valid module name to avoid name clashes on import
    script_path = os.path.join(workpath, name + '-pyinstaller-script.py')
    print('Creating script for entry point: {0}, {1}, {2}'.format(dist, group, name))
    with open(script_path, 'w') as fh:
        fh.write("import {0}\n".format(ep.module_name))
        fh.write("{0}.{1}()\n".format(ep.module_name, '.'.join(ep.attrs)))
        for package in packages:
            fh.write("import {0}\n".format(package))

    return Analysis([script_path] + scripts, pathex=pathex,
                    hiddenimports=hiddenimports,
                    hookspath=hookspath,
                    excludes=excludes,
                    runtime_hooks=runtime_hooks)

a = Entrypoint('pyzcm==1.0.0', 'console_scripts', 'pyzcm', hookspath=['.'])
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
# Enable this options if verbose python run is required of the binary
options = [
    #('v', None, 'OPTION'),
    #('W ignore', None, 'OPTION')
]

# One-file build settings
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='pyzcm',
          debug=False,
          strip=False,
          upx=True,
          console=True)

# One-folder build settings:
# exe = EXE(pyz,
#           a.scripts,
#           options,
#           exclude_binaries=True,
#           name='pyzcm',
#           debug=False,
#           strip=False,
#           upx=True,
#           console=True )
# coll = COLLECT(exe,
#                a.binaries,
#                a.zipfiles,
#                a.datas,
#                strip=False,
#                upx=True,
#                name='pyzcm')
