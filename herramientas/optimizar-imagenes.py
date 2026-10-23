#!/usr/bin/env python3
"""Optimiza las fotos del portafolio y genera sus versiones ligeras.

Uso (desde la raíz del proyecto):  python3 herramientas/optimizar-imagenes.py

Para cada foto listada en `projects` de index.html:
  - la foto completa se limita a 1600 px y se recomprime (solo si queda más ligera);
  - assets/tarjetas/<ruta>   lado corto 800 px, para las tarjetas del portafolio;
  - assets/miniaturas/<ruta> lado corto 240 px, para círculos y miniaturas de la galería.
Las versiones existentes se omiten salvo que la foto original sea más reciente.

Requiere macOS (sips) y libjpeg-turbo (djpeg/cjpeg: `brew install jpeg-turbo`).
"""
import os
import re
import shutil
import subprocess
import tempfile

MAX_COMPLETA = 1600
LADO_TARJETA = 800
LADO_MINIATURA = 240


def fotos_del_portafolio():
    s = open('index.html', encoding='utf-8').read()
    bloque = s[s.index('const projects = ['):s.index('\n  ];')]
    return sorted(set(re.findall(r"img: '([^']+)'", bloque)))


def orientacion_exif(ruta):
    b = open(ruta, 'rb').read(65536)
    for marca, orden in ((b'\x01\x12\x00\x03', 'big'), (b'\x12\x01\x03\x00', 'little')):
        i = b.find(marca)
        if i > 0:
            return int.from_bytes(b[i + 8:i + 10], orden)
    return 1


def medidas(ruta):
    out = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', ruta],
                         capture_output=True, text=True, check=True).stdout
    w = int(re.search(r'pixelWidth: (\d+)', out).group(1))
    h = int(re.search(r'pixelHeight: (\d+)', out).group(1))
    return w, h


def sips(*args):
    subprocess.run(['sips', *args], capture_output=True, check=True)


def codificar(origen, destino, calidad):
    """Recodifica como JPEG progresivo; descarta metadatos (la rotación ya va en los píxeles)."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, 'wb') as salida:
        djpeg = subprocess.Popen(['djpeg', origen], stdout=subprocess.PIPE)
        subprocess.run(['cjpeg', '-quality', str(calidad), '-optimize', '-progressive'],
                       stdin=djpeg.stdout, stdout=salida, check=True)
        djpeg.wait()


def copia_enderezada(ruta, tmp):
    """Copia la foto con la rotación EXIF aplicada a los píxeles."""
    copia = os.path.join(tmp, 'base.jpg')
    sips('-s', 'format', 'jpeg', ruta, '--out', copia)
    giro = {3: '180', 6: '90', 8: '270'}.get(orientacion_exif(ruta))
    if giro:
        sips('-r', giro, copia)
    return copia


def reducir(base, destino_tmp, lado_corto=None, lado_largo=None):
    shutil.copy(base, destino_tmp)
    w, h = medidas(destino_tmp)
    if lado_largo and max(w, h) > lado_largo:
        sips('-Z', str(lado_largo), destino_tmp)
    if lado_corto and min(w, h) > lado_corto:
        sips('--resampleWidth' if w <= h else '--resampleHeight', str(lado_corto), destino_tmp)
    return destino_tmp


def al_dia(variante, original):
    return os.path.exists(variante) and os.path.getmtime(variante) >= os.path.getmtime(original)


def main():
    kb = lambda n: f'{n / 1024:5.0f} KB'
    for ruta in fotos_del_portafolio():
        relativa = ruta[len('assets/'):]
        tarjeta = f'assets/tarjetas/{relativa}'
        miniatura = f'assets/miniaturas/{relativa}'
        with tempfile.TemporaryDirectory() as tmp:
            base = copia_enderezada(ruta, tmp)

            completa = os.path.join(tmp, 'completa.jpg')
            codificar(reducir(base, os.path.join(tmp, 'c.jpg'), lado_largo=MAX_COMPLETA), completa, 80)
            antes = os.path.getsize(ruta)
            if os.path.getsize(completa) < antes * 0.9:
                shutil.copy(completa, ruta)
                print(f'{kb(antes)} -> {kb(os.path.getsize(ruta))}  {ruta}')
                base = copia_enderezada(ruta, tmp)

            if not al_dia(tarjeta, ruta):
                codificar(reducir(base, os.path.join(tmp, 't.jpg'), lado_corto=LADO_TARJETA), tarjeta, 78)
            if not al_dia(miniatura, ruta):
                codificar(reducir(base, os.path.join(tmp, 'm.jpg'), lado_corto=LADO_MINIATURA), miniatura, 75)


if __name__ == '__main__':
    main()
