"""Vista local ligada a localhost, busca puerto libre; no inicia sesión ni scraper."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path
import webbrowser
root=str(Path(__file__).resolve().parents[1])
for port in range(8780,8810):
    try: server=ThreadingHTTPServer(('127.0.0.1',port),partial(SimpleHTTPRequestHandler,directory=root)); break
    except OSError: continue
else: raise SystemExit('No se encontró puerto libre entre 8780 y 8809.')
print(f'Abriendo http://127.0.0.1:{port} — Ctrl+C para cerrar.')
webbrowser.open(f'http://127.0.0.1:{port}')
try: server.serve_forever()
except KeyboardInterrupt: server.server_close()
