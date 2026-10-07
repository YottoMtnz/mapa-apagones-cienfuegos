"""Publicar solo web y datos de Cienfuegos; nunca sesión, caché, estudios o código servidor."""
from pathlib import Path
import shutil
base=Path(__file__).resolve().parents[1]
out=base/'_site'
if out.exists(): shutil.rmtree(out)
(out/'data').mkdir(parents=True)
for name in ('index.html','admin.html','config.js'):
    shutil.copy2(base/name,out/name)
if (base/'assets').exists(): shutil.copytree(base/'assets',out/'assets')
for name in ('circuitos_cienfuegos.json','estado_cienfuegos.json','limite_cienfuegos.geojson'):
    shutil.copy2(base/'data'/name,out/'data'/name)
(out/'.nojekyll').write_text('')
print('Web preparada: solo Cienfuegos.')
