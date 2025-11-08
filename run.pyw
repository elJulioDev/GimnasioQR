import subprocess
import os

# Cambia el directorio al lugar donde está manage.py
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Ejecuta el comando
subprocess.run(["py", "manage.py", "makemigrations"])
subprocess.run(["py", "manage.py", "migrate"])
subprocess.run(["py", "manage.py", "runserver"])
