# Collect dynamic library from the solver - it is not automatically
# detected since the library is not built as python extension
from PyInstaller.utils.hooks import collect_dynamic_libs
binaries = collect_dynamic_libs('pyzceqsolver')
