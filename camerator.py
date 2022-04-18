#!/usr/bin/python3

from picamera2.picamera2 import *
from picamera2.encoders.jpeg_encoder import *
import io
import logging
import socketserver
from threading import Condition, Thread
from http import server
from jinja2 import Environment, FileSystemLoader, select_autoescape

WIDTH  = 2592
HEIGHT = 1944
PORT   = 8888

file_loader = FileSystemLoader('templates')
ENV = Environment(
  loader=file_loader,
  autoescape=select_autoescape()
)

template = ENV.get_template('camerator.html.jinja')
PAGE = template.render({
  'WIDTH': WIDTH,
  'HEIGHT': HEIGHT,
})

class StreamingOutput(io.BufferedIOBase):
  def __init__(self):
    self.frame = None
    self.condition = Condition()

  def write(self, buf):
    with self.condition:
      self.frame = buf
      self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
  def do_GET(self):
    if self.path == '/':
      self.send_response(301)
      self.send_header('Location', '/index.html')
      self.end_headers()
    elif self.path == '/index.html':
      content = PAGE.encode('utf-8')
      self.send_response(200)
      self.send_header('Content-Type', 'text/html')
      self.send_header('Content-Length', len(content))
      self.end_headers()
      self.wfile.write(content)
    elif self.path == '/stream.mjpg':
      self.send_response(200)
      self.send_header('Age', 0)
      self.send_header('Cache-Control', 'no-cache, private')
      self.send_header('Pragma', 'no-cache')
      self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
      self.end_headers()
      try:
        while True:
          with output.condition:
            output.condition.wait()
            frame = output.frame
          self.wfile.write(b'--FRAME\r\n')
          self.send_header('Content-Type', 'image/jpeg')
          self.send_header('Content-Length', len(frame))
          self.end_headers()
          self.wfile.write(frame)
          self.wfile.write(b'\r\n')
      except Exception as e:
        logging.warning(
          'Removed streaming client %s: %s',
          self.client_address, str(e))
    else:
      self.send_error(404)
      self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
picam2.start_preview()
picam2.configure(picam2.video_configuration(main={"size": (WIDTH, HEIGHT)}))
output = StreamingOutput()
picam2.start_recording(JpegEncoder(), output)

try:
  address = ('', PORT)
  server = StreamingServer(address, StreamingHandler)
  server.serve_forever()
finally:
  picam2.stop_recording()