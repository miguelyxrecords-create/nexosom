from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse


class SPAHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Evita cache durante o desenvolvimento local.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        url_path = urlparse(self.path).path
        local_path = Path(self.translate_path(url_path))

        # Rotas do frontend, como /s/nome-da-musica,
        # devem carregar o index.html.
        if url_path.startswith("/s/"):
            self.path = "/index.html"

        elif not local_path.exists() and "." not in Path(url_path).name:
            self.path = "/index.html"

        return super().do_GET()


print("NexoSom frontend: http://localhost:5500")

server = ThreadingHTTPServer(("localhost", 5500), SPAHandler)

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nServidor encerrado.")