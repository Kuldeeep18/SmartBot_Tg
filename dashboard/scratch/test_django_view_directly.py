import os
import sys
import django

sys.path.append(r"c:\Users\mrsan\Desktop\Anjani-master\dashboard")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")
django.setup()

from control.utils.db import get_db
db = get_db()
bots = list(db.bots.find())
print("BOTS IN DB:", len(bots))
for b in bots:
    displayName = b.get('displayName', '').encode('ascii', 'ignore').decode('ascii')
    print("BOT ID:", b['_id'])
    print("  NAME:", displayName)
    print("  TYPE:", b.get('type'))
    print("  PLUGINS:", b.get('enabledPlugins'))
