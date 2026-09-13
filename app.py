from http.server import BaseHTTPRequestHandler, HTTPServer

class App(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'<h1>NEXXUS Logistica</h1><p>Aplicacao em construcao.</p>'
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    HTTPServer(('0.0.0.0',8000),App).serve_forever()
