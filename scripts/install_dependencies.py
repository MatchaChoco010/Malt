import os, subprocess, sys, shutil, stat

current_dir = os.path.dirname(os.path.realpath(__file__))
malt_folder = os.path.join(current_dir, '..', 'Malt')
py_version = str(sys.version_info[0])+str(sys.version_info[1])
malt_dependencies_path = os.path.join(malt_folder, '.Dependencies-{}'.format(py_version))

dependencies = ['numpy', 'glfw', 'PyOpenGL', 'PyOpenGL_accelerate', 'Pyrr', 'psutil']
try:
    subprocess.check_call([sys.executable, '-m', 'venv', malt_dependencies_path])
    subprocess.check_call([os.path.join(malt_dependencies_path, 'Scripts/activate')])
    for dependency in dependencies:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', dependency])
except:
    print('ERROR: pip install {} failed.'.format(dependency))
    import traceback
    traceback.print_exc()


from distutils.dir_util import copy_tree
copy_tree(os.path.join(current_dir, 'PatchDependencies'), malt_dependencies_path)

#make sure mcpp has executable permissions
for str in ['Linux', 'Darwin']:
    mcpp = os.path.join(malt_dependencies_path, f'mcpp-{str}')
    os.chmod(mcpp, os.stat(mcpp).st_mode | stat.S_IEXEC)
