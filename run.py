import subprocess
import sys
import os

venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
script = os.path.join(os.path.dirname(__file__), "batch_upload_xiaohongshu.py")

sys.exit(subprocess.call([venv_python, script]))
