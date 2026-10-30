"""Simple HTTPS server for the frontend."""
import http.server
import ssl
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
CERT_FILE = sys.argv[2] if len(sys.argv) > 2 else "cert.pem"
KEY_FILE = sys.argv[3] if len(sys.argv) > 3 else "key.pem"

handler = http.server.SimpleHTTPRequestHandler
httpd = http.server.HTTPServer(("0.0.0.0", PORT), handler)

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(CERT_FILE, KEY_FILE)
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=1)

print(f"Frontend HTTPS server running on https://localhost:{PORT}")
httpd.serve_forever()