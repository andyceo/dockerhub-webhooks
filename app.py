#!/usr/bin/env python

from http.server import HTTPServer
from pylibs.webserver import WebServer
import json
import logging
import sched
import subprocess
import sys
import threading


# HTTPRequestHandler class
class DockerHubWebhookWebServer(WebServer):

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
            logging.warning("Received update for '%s', but nor services nor stacks are configured to handle updates "
                            "for this image.", image)
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(bytes('Not Found\n', "utf8"))

        elif image in stacks:
            stack = stacks[image]['stack']
            filepath = stacks[image]['filepath']

            # (Re)Deploy the stack
            logging.info("Deploying %s to stack %s...", image, stack)
            sys.stdout.flush()

            res = subprocess.run(["/usr/bin/docker", "stack", "deploy", "-c", filepath, stack], capture_output=True)

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
            sys.stdout.flush()

            res = subprocess.run(["/usr/bin/docker", "service", "update", service,
                                  "-force", '-image=%s'.format(image)], capture_output=True)

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

        sys.stdout.flush()


def run():
    logging.info('Starting httpd...\n')
    server_address = ('0.0.0.0', 8130)
    httpd = HTTPServer(server_address, DockerHubWebhookWebServer)
    logging.info('Running httpd...\n')
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info('Stopping httpd...\n')


class ThreadedIntervalScheduler(threading.Thread):
    _scheduler = None
    _stop_intervals = False

    def exec_interval(self, interval, priority, cmds):
        logging.info('Executing command %s...', ' '.join(cmds))
        res = subprocess.run(cmds, capture_output=True)
        logging.info('Command %s exited with code %d', ' '.join(cmds), res.returncode)
        logging.info('STDOUT:')
        logging.info(res.stdout)
        logging.info('STDERR:')
        logging.info(res.stderr)
        sys.stdout.flush()
        if not self._stop_intervals:
            self._scheduler.enter(interval, priority, self.exec_interval, (interval, priority, cmds,))

    def start_intervals(self, scheduler, intervals):
        self._scheduler = scheduler
        _stop_intervals = False

        for i in intervals:
            cmds = i['command'].split(' ')
            self._scheduler.enter(i['interval'], i['priority'],
                                  self.exec_interval, (i['interval'], i['priority'], cmds))

        logging.info('Intervals initialized!')

    def stop_intervals(self):
        self._stop_intervals = True
        list(map(self._scheduler.cancel, self._scheduler.queue))
        logging.info('Intervals queue cleaned!')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s.%(module)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    with open('./config.json', 'r') as f:
        cfg = json.load(f)
        services = cfg['services']
        stacks = cfg['stacks']
        intervals = cfg['intervals']

    scheduler = sched.scheduler()

    t = ThreadedIntervalScheduler(target=scheduler.run)
    t.start_intervals(scheduler, intervals)
    t.start()
    run()
    t.stop_intervals()
    t.join()
