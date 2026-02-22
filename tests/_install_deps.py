"""Install conform tool dependencies into bundled Blender Python."""
import subprocess, sys
subprocess.run([sys.executable, '-m', 'pip', 'install',
    'opentimelineio', 'pycmx', 'pyaaf2', 'timecode'],
    check=True)
