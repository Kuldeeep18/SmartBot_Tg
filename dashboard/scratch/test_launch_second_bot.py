import os
import sys
import django

sys.path.append(r"c:\Users\mrsan\Desktop\Anjani-master\dashboard")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from control.utils.db import get_db
from control.utils.docker_client import launch_bot_container, decrypt

db = get_db()
bot = db.bots.find_one({'_id': '2361b437fb3c'})
if not bot:
    print("Bot 2361b437fb3c not found in DB!")
    sys.exit(1)

token = decrypt(bot['encryptedToken'])
config = {
    'ownerId': bot.get('ownerId', ''),
    'enabledPlugins': bot.get('enabledPlugins', [])
}

try:
    print("Attempting to launch bot 2361b437fb3c container...")
    res = launch_bot_container(token, 'anjani', config)
    print("SUCCESS:", res)
except Exception as e:
    print("LAUNCH FAILED WITH ERROR:", e)
    import traceback
    traceback.print_exc()
