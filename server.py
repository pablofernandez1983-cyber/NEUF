import http.server, webbrowser, os, threading

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = 8585
handler = http.server.SimpleHTTPRequestHandler

def open_browser():
    webbrowser.open(f'http://localhost:{PORT}')

threading.Timer(0.8, open_browser).start()
print(f"NEUF BBS Reader -> http://localhost:{PORT}")
print("Ctrl+C para salir")
with http.server.HTTPServer(('', PORT), handler) as httpd:
    httpd.serve_forever()
