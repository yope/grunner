#!/usr/bin/env python
#
# Copyright (c) 2014 David Jander
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# vim: set tabstop=4:

from math import *
from gcode import GCode
import signal
import sys

class Move(object):
	def __init__(self, cfg, gcode):
		self.mm2steps = [float(x) for x in cfg.settings["steps_per_mm"]]
		self.dim = cfg.settings["num_motors"]
		self.motor_name = cfg.settings["motor_name"]
		self.motor_name_indexes = {}
		for i in range(len(self.motor_name)):
			self.motor_name_indexes[self.motor_name[i]] = i
		#self.plist = [[100, 80, 50, 20], [-10, -100, 50, 20], [-10, 20, 30, 40], [0, 0, 0, 0]]
		self.gcode = gcode
		if gcode is not None:
			self.start()

	def start(self):
		self.movements = self.movement_generator()

	def transform(self, gpos):
		ret = map(lambda x, y: x * y, gpos, self.mm2steps)
		return ret

	def movement_generator(self):
		#while True:
		#	for p in self.plist:
		#		yield self.transform(p)
		while True:
			try:
				obj = next(self.gcode.commands)
			except StopIteration:
				break
			if not "command" in obj:
				print "MOVE: Onknown command object:", repr(obj)
				continue
			cmd = obj["command"]
			if cmd == "position":
				pos = [0] * self.dim
				for w in obj:
					idx = self.motor_name_indexes.get(w, None)
					if idx is not None:
						pos[idx] = obj[w]
					elif w == "F":
						yield ("feedrate", obj[w])
				p = self.transform(pos)
				yield ("position", p)
		raise StopIteration

