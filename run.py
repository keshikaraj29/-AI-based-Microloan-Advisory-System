"""Start the local threaded demo server with a bounded worker pool."""
import os
from waitress import serve
from app import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    print(f'PP1 Microloan Research: http://127.0.0.1:{port}', flush=True)
    serve(app, host='127.0.0.1', port=port, threads=8)
