import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram_bot.bot import run

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        # Suppress server logs to keep deployment logs clean
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    # Start web server in background thread for Render compatibility
    web_thread = threading.Thread(target=run_health_check_server, daemon=True)
    web_thread.start()
    
    # Start the Telegram bot
    run()
