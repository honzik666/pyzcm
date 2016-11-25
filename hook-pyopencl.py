# We need metadata for pyopencl
from PyInstaller.utils.hooks import copy_metadata
datas = copy_metadata('pyopencl')
