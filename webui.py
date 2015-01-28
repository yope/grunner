#!/usr/bin/env python
#
# vim: set tabstop=4:
#
# Copyright (c) 2015 David Jander
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# Add external modules paths to sys.path...
import os
import sys
pwd = os.getcwd()
sys.path.append(os.path.join(pwd, "aiohttp"))
sys.path.append(os.path.join(pwd, "websockets"))

import monkeypatch
import asyncio
from aiohttp import web
import websockets
import json
from collections import deque

import random
random.seed()

class WsHanlder(object):
	def __init__(self, websock, webui):
		self.webui = webui
		self.ws_acked = True
		self.ws_queue = []
		self.websock = websock
		self.queue = deque()
		self.webui.add_websocket(self)

	@asyncio.coroutine
	def send_message(self, obj):
		txt = json.dumps(obj)
		yield from self.websock.send(txt)

	@asyncio.coroutine
	def coro_queue(self):
		while self.queue:
			obj = self.queue.popleft()
			yield from self.send_message(obj)

	def queue_message(self, obj):
		start = not self.queue
		self.queue.append(obj)
		if start:
			asyncio.async(self.coro_queue())

	@asyncio.coroutine
	def coro_recieve(self):
		while True:
			msg = yield from self.websock.recv()
			if msg is None:
				break
			yield from self.on_message(msg)
		self.on_disconnect()

	@asyncio.coroutine
	def on_message(self, message):
		if isinstance(message, bytes):
			message = message.decode('iso8859-1')
		try:
			obj = json.loads(message)
		except ValueError:
			# Garbage or nothing received, close the connection.
			self.on_disconnect()
			self.websock.close()
		else:
			yield from self.parse_object(obj)

	@asyncio.coroutine
	def parse_object(self, obj):
		print("WS: received:", repr(obj))
		p = self.webui.printer
		cmd = obj.get("command", None)
		if cmd == "runfile":
			yield from p.print_file(obj["filename"])
		elif cmd == "gcode":
			yield from p.execute_gcode(obj["code"])
		elif cmd == "no_extrusion":
			p.gcode.set_zero_extruder(obj["value"])
		elif cmd == "speed_scale":
			p.sc.set_speed_scale(obj["value"])
		elif cmd == "pause":
			p.set_pause(obj["value"])
		elif cmd == "stop":
			yield from p.stop()
		elif cmd == "heater":
			p.set_setpoint("bed", obj["bed_setpoint"])
			p.set_setpoint("ext", obj["extruder_setpoint"])
		elif cmd == "heater_policy":
			p.set_heater_enable_mcodes(obj["enable_mcodes"])
			p.set_heater_disable_eof(obj["diable_at_eof"])

	def on_disconnect(self):
		print("WS: disconnect")
		self.webui.del_websocket(self)

class WebUi(object):
	def __init__(self, printer):
		print("Starting web server...")
		self.printer = printer
		self.httpd = web.Application()
		self.httpd.router.add_static('/', './html/')
		self.loop = asyncio.get_event_loop()
		f = self.loop.create_server(self.httpd.make_handler(), '0.0.0.0', 8888)
		self.server = self.loop.run_until_complete(f)
		self.wsockets = []
		start = websockets.serve(self.websocket_handler, '0.0.0.0', 9999)
		self.websockd = self.loop.run_until_complete(start)
		print("...done")
		#asyncio.async(self.sim_temperature())
		#asyncio.async(self.simulate())
		asyncio.async(self.coro_temperature())

	@asyncio.coroutine
	def websocket_handler(self, websock, path):
		h = WsHanlder(websock, self)
		yield from h.coro_recieve()

	@asyncio.coroutine
	def simulate(self):
		x, y, z = 0, 0, 0
		while True:
			yield from asyncio.sleep(random.randrange(20, 200)/1000.0)
			x += random.randrange(-30, 30)
			y += random.randrange(-30, 30)
			if x > 195: x = 195
			if x < 0: x = 0
			if y > 185: y = 185
			if y < 0: y = 0
			if random.randrange(100) > 97:
				z += 0.2
			if z > 20.0: z = 0
			self.queue_move(x, y, z, 0)

	@asyncio.coroutine
	def coro_temperature(self):
		while True:
			yield from asyncio.sleep(1)
			t_ext = self.printer.get_temperature("ext")
			t_bed = self.printer.get_temperature("bed")
			self.queue({"id": "temperature", "extruder": t_ext, "bed": t_bed})

	@asyncio.coroutine
	def sim_temperature(self):
		while True:
			yield from asyncio.sleep(1)
			t_ext = random.randrange(20, 50)
			t_bed = random.randrange(20, 50)
			self.queue({"id": "temperature", "extruder": t_ext, "bed": t_bed})

	def add_websocket(self, wsock):
		print("add_websocket")
		self.wsockets.append(wsock)
		self.printer.update_status()

	def del_websocket(self, wsock):
		try:
			self.wsockets.remove(wsock)
		except ValueError:
			pass

	@asyncio.coroutine
	def send(self, obj):
		for ws in self.wsockets:
			yield from ws.send_message(obj)

	def queue(self, obj):
		for ws in self.wsockets:
			ws.queue_message(obj)

	def queue_move(self, x, y, z, e):
		self.queue({"id": "move", "x": x, "y": y, "z": z, "e": e})

	def queue_status(self, motors, extruder, bed):
		self.queue({"id": "status", "motors": motors, "extruder": extruder, "bed": bed});

# Test function
if __name__ == "__main__":
	w = WebUi()
	asyncio.get_event_loop().run_forever()
