#!/usr/bin/env python3
"""
Genera TG_SESSION EN TU PC (nunca en GitHub Actions).
  pip install telethon
  python3 scraper/generar_sesion.py
Pide api_id, api_hash, teléfono y el código por teclado y IMPRIME la sesión en la
terminal (no la escribe en disco). Cópiala directamente a GitHub:
  gh secret set TG_SESSION      # y pega; o Settings > Secrets and variables > Actions
Una sesión equivale a acceso total a la cuenta de Telegram: no la pegues en chats,
issues, logs ni la subas al repo. Si se filtra: Telegram > Ajustes > Dispositivos > cerrar sesión.
"""
import getpass
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("api_id: ").strip())
api_hash = getpass.getpass("api_hash (no se muestra): ").strip()
with TelegramClient(StringSession(), api_id, api_hash) as client:   # pide teléfono y código
    print("\n--- TG_SESSION (cópiala ahora, no se guarda) ---")
    print(client.session.save())
