#!/usr/bin/env python

from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import json
import logging
import subprocess


with open('./config.json', 'r') as f:
    cfg = json.load(f)
    services = cfg['services']
    stacks = cfg['stacks']


# HTTPRequestHandler class
class WebServer(BaseHTTPRequestHandler):

    def do_GET(self):
        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

        # Send message back to client
        message = "Hello world!"
        # Write content as utf-8 data
        self.wfile.write(bytes(message, "utf8"))
        return

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode('utf-8'))

        if 'repository' in payload and 'repo_name' in payload['repository'] and 'push_data' in payload and 'tag' in payload['push_data']:
            image = payload['repository']['repo_name'] + ':' + payload['push_data']['tag']
        else:
            image = 'Image not detected!'

        logging.info("POST request,\nPath: %s\nHeaders:\n%s\nBody:\n%s\n",
                     str(self.path), str(self.headers), body.decode('utf-8'))

        if image not in services and image not in stacks:
            logging.warning("Received update for '%s', but nor services nor stacks are configured to handle updates for this image.", image)
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes('Not Found\n', "utf8"))

        elif image in stacks:
            stack = stacks[image]['stack']
            filepath = stacks[image]['filepath']

            # (Re)Deploy the stack
            logging.info("Deploying %s to stack %s...", image, stack)

            res = subprocess.run(["docker", "stack", "deploy", "-c", filepath, stack], capture_output=True)

            if res.returncode:
                logging.error("Failed to deploy %s to stack %s!", image, stack)
                logging.error("STDOUT:")
                logging.error(res.stdout)
                logging.error("STDERR:")
                logging.error(res.stderr)
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(bytes('Internal Server Error\n', "utf8"))
            else:
                logging.info("Deployed %s to stack %s successfully.", image, stack)
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(bytes('OK (stack)\n', "utf8"))

        elif image in services:
            service = services[image].service

            # (Re)Deploy the image and force a restart of the associated service
            logging.info("Deploying %s to service %s...", image, service)

            res = subprocess.run(["docker", "service", "update", service, "-force", '-image=%s'.format(image)], capture_output=True)

            if res.returncode:
                logging.error("Failed to deploy %s to %s!", image, service)
                logging.error("STDOUT:")
                logging.error(res.stdout)
                logging.error("STDERR:")
                logging.error(res.stderr)
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(bytes('Internal Server Error\n', "utf8"))
            else:
                logging.info("Deployed %s to service %s successfully and restarted the service.", image, service)
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(bytes('OK (service)\n', "utf8"))


def run():
    logging.basicConfig(level=logging.INFO)
    logging.info('Starting httpd...\n')
    server_address = ('127.0.0.1', 8081)
    httpd = HTTPServer(server_address, WebServer)
    logging.info('Running httpd...\n')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info('Stopping httpd...\n')

run()