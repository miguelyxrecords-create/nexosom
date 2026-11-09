from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse


class SPAHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Evita cache durante o desenvolvimento local.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_head(self):
        # Serve o mesmo HTML que o Netlify usa para os Smart Links.
        if urlparse(self.path).path.startswith("/s/"):
            self.path = "/smart.html"

        return super().send_head()


print("NexoSom frontend: http://localhost:5500")

server = ThreadingHTTPServer(("localhost", 5500), SPAHandler)

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nServidor encerrado.")
