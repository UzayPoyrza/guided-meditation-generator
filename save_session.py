import os
import sys
import http.server
import webbrowser
import urllib.parse

PORT = 8765
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HTML = """<!DOCTYPE html>
<html><head><title>Save Session</title>
<style>
body { font-family: sans-serif; max-width: 700px; margin: 40px auto; padding: 20px; }
textarea { width: 100%%; height: 300px; font-size: 14px; padding: 10px; }
input { font-size: 18px; padding: 5px; width: 80px; }
button { font-size: 18px; padding: 8px 24px; margin-top: 10px; cursor: pointer; }
</style></head><body>
<h2>Save Session to Batch</h2>
<label>Batch number: <input type="number" id="batch" min="1" max="22" value="1"></label><br><br>
<textarea id="text" placeholder="Paste your text here (Cmd+V)..."></textarea><br>
<button onclick="save()">Save</button>
<p id="msg"></p>
<script>
function save() {
    fetch('/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'batch=' + document.getElementById('batch').value +
              '&text=' + encodeURIComponent(document.getElementById('text').value)
    }).then(r => r.text()).then(t => {
        document.getElementById('msg').innerText = t;
    });
}
</script>
</body></html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        data = urllib.parse.parse_qs(self.rfile.read(length).decode())
        batch = data.get('batch', [''])[0].strip()
        text = data.get('text', [''])[0]

        folder = os.path.join(BASE_DIR, f"batch{batch}")
        if not os.path.isdir(folder):
            msg = f"Error: batch{batch} folder does not exist."
        elif not text.strip():
            msg = "Error: text is empty."
        else:
            filepath = os.path.join(folder, f"session_batch_{batch}.txt")
            with open(filepath, "w") as f:
                f.write(text)
            msg = f"Saved to {filepath}"

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(msg.encode())

    def log_message(self, format, *args):
        pass

print(f"Opening browser at http://localhost:{PORT}")
print("Press Ctrl+C to stop.")
webbrowser.open(f"http://localhost:{PORT}")
http.server.HTTPServer(('', PORT), Handler).serve_forever()
