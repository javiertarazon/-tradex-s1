"""Rutas del repositorio, resueltas siempre a partir de este fichero.

Ningún script de ``research/`` debe contener una ruta absoluta: así el
repositorio se puede clonar en cualquier carpeta o en otra máquina.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
RESULTS = os.path.join(ROOT, "results", "research")

M15_CACHE = os.path.join(DATA, "xau_m15_2022_2026.csv")

# terminal64.exe solo se usa si hay que regenerar la cache de datos.
MT5_PATH = os.environ.get("MT5_PATH", r"D:\proyectos_javier\proyectos\terminal64.exe")

os.makedirs(RESULTS, exist_ok=True)
