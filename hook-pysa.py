# Collect dynamic library from Python Silentarmy wrapper - it is not
# automatically detected since the library is not built as python
# extension
from PyInstaller.utils.hooks import collect_dynamic_libs
binaries = collect_dynamic_libs('pysa')
