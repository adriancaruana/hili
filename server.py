#!/usr/bin/env python
"""
Test:
curl -X POST -H "Authentication: KEY" -H "Content-Type: application/json" --data '{"foo":"bar"}' http://127.0.0.1:8888

Run with: 
python3 hili/server.py \
  ~/hili_data/annos.json \
  ~/hili_data/saved_files \
  -s <ip> \
  -p <port> \
  -k '<key>'
"""

import os
import json
import base64
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer


parser = argparse.ArgumentParser(description='A simple server to receive and save JSON data')
parser.add_argument('FILE', type=str, help='File to save received data')
parser.add_argument('UPLOAD_DIR', type=str, help='Directory to save uploaded files')
parser.add_argument('-s', '--host', type=str, dest='HOST', default='localhost', help='Hostname of server.')
parser.add_argument('-p', '--port', type=int, dest='PORT', default=8888, help='Port for server')
parser.add_argument('-k', '--key', type=str, dest='KEY', default=None, help='Secret key to authenticate clients')
args = parser.parse_args()

Path(args.FILE).parent.mkdir(exist_ok=True)
Path(args.UPLOAD_DIR).mkdir(exist_ok=True)
    

class JSONRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        auth_key = self.headers.get('Authentication')
        if args.KEY and args.KEY != auth_key:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'unauthorized')
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # Get data
        self.data_string = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.end_headers()

        data = self.data_string.decode('utf8')
        data = json.loads(data)

        # If a file is included, save it and save only the filename
        if 'file' in data:
            # Assume that data is base64 encoded
            b64 = base64.b64decode(data['file']['data'])

            # Generate file name by hashing file data
            # and extension based on specified content type
            fname = hashlib.sha1(b64).hexdigest()
            ext = data['file']['type'].split('/')[-1]
            fname = '{}.{}'.format(fname, ext)
            with open(os.path.join(args.UPLOAD_DIR, fname), 'wb') as f:
                f.write(b64)

            # Remove original data,
            # save only filename
            del data['file']['data']
            data['file']['name'] = fname

        # Save data
        with open(args.FILE, 'a') as f:
            f.write(json.dumps(data) + '\n')

        # Response
        self.wfile.write(b'ok')
        return

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        data = []
        with open(args.FILE, 'r') as f:
            for l in f.read().splitlines():
                data.append(json.loads(l))

        # Reverse chron
        html = ['''
            <html>
                <head>
                    <meta charset="utf8">
                    <style>
                        html {
                            overflow-x: hidden;
                        }
                        article {
                            margin: 4em auto;
                            max-width: 720px;
                            line-height: 1.4;
                            padding-bottom: 4em;
                            border-bottom: 2px solid black;
                            font-family: sans-serif;
                        }
                        .highlight {
                            margin: 2em 0;
                        }
                        .tags {
                            color: #888;
                            margin-top: 1em;
                            font-size: 0.8em;
                        }
                        a {
                            color: blue;
                        }
                        img {
                            max-width: 100%;
                        }
                    </style>
                </head>
                <body>''']

        grouped = defaultdict(list)
        for d in data:
            grouped[d['href']].append(d)

        for href, group in sorted(grouped.items(), key=lambda g: -max([d['time'] for d in g[1]])):
            html.append('''
                <article>
                    <h4><a href="{href}">{title}</a></h4>'''.format(href=href, title=group[0]['title']))
            for d in group:
                if 'file' in d:
                    # fname = d['file']['name']
                    html.append('''
                        <div class="highlight">
                            <img src="{src}">
                            <p>{text}</p>
                            <div class="tags"><em>{tags}</em></div>
                        </div>
                    '''.format(
                        # src=os.path.join(args.UPLOAD_DIR, fname),
                        src=d['file']['src'],
                        text=d['text'],
                        tags=', '.join(d['tags'])
                    ))
                else:
                    html.append('''
                        <div class="highlight">
                            {html}
                            <div class="tags"><em>{tags}</em></div>
                        </div>
                    '''.format(
                        html=d['html'],
                        tags=', '.join(d['tags'])
                    ))
            html.append('</article>')

        html.append('</body></html>')

        # Response
        html = '\n'.join(html).encode('utf8')
        self.wfile.write(html)


if __name__ == '__main__':
    print(f'Server running at: {args.HOST}:{args.PORT}')
    server = HTTPServer((args.HOST, args.PORT), JSONRequestHandler)
    server.serve_forever()
