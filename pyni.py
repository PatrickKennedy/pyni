#!/usr/bin/env python
#
#  PyNI - Python Config Management Module
#  Copyright (c) 2008, Patrick Kennedy
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#
#  - Redistributions of source code must retain the above copyright
#  notice, this list of conditions and the following disclaimer.
#
#  - Redistributions in binary form must reproduce the above copyright
#  notice, this list of conditions and the following disclaimer in the
#  documentation and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION OR
#  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
#  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
#  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
#  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import with_statement

import os

from collections import defaultdict

__version__ = '0.2.0'

class ConfigNode(defaultdict):
	def __init__(self):
		self.default_factory = type(self)
		self._comments = {}

	def __getattr__(self, attr):
		return self.__getitem__(attr)

	def __setattr__(self, attr, value):
		# We will never be setting anything other than the default factory
		# so we'll make the exception for that here. Everything else will go
		# straight to __setitem__.
		if attr in ['default_factory', '_comments', '_filename', '_encoding']:
			super(defaultdict, self).__setattr__(attr, value)
		else:
			self.__setitem__(attr, value)

	def __delattr__(self, attr):
		self.__delitem__(attr)

	def __repr__(self):
		return dict(self).__repr__()

	def _output(self, parents=None, buffer=None):
		if parents is None:
			parents = []
			buffer = []

		# True if we've already appended the parent sections
		buffered_parents = False

		# All ConfigNode children are stored here to be appended
		# after the variable assignemnts.
		sub_sections = []

		# Allows us to sort the child assignments alphabetically
		children = self.items()
		children.sort()
		for key, value in children:
			# If we're handling a dictionary
			if isinstance(value, defaultdict):
				sub_sections.append((key, value))
			# All other variables get thrown into assignments
			else:
				# Append all parent sections to the beginning of assignments.
				if not buffered_parents and parents:
					buffer.append('')
					# Attach section comments to the header.
					if '__root__' in self._comments:
						buffer.append(self._comments['__root__'])
					[buffer.append("[%s]" % parent) for parent in parents]
					buffered_parents = True

				# Attach value comments to each value.
				if key in self._comments:
					buffer.append(self._comments[key])
				buffer.append("%s = %r" % (key, value))

		# Walk through all sub-sections, appending and poping to emulate depth.
		for key, value in sub_sections:
			parents.append(key)
			value._output(parents, buffer)
			parents.pop()

		return '\n'.join(buffer)

class ConfigRoot(ConfigNode):

	def __init__(self, filename, encoding='utf-8'):
		self._filename = filename
		self._encoding = encoding
		self.default_factory = ConfigNode

	def read(self, clear=True):
		self.parse_config()

	def parse_config(self, clear=True):
		if not os.path.exists(self._filename):
			print "Creating %s" % self._filename
		with file(self._filename, 'a+') as f:
			self.parse_config_file(f, clear)

	def parse_config_list(self, list_, clear=True):
		if clear:
			self.clear()
		node = self
		# True as long as each consecutive line is in section format
		in_header = True
		# Contains all lines of a comment block. Emptied when exiting a block.
		# TODO: Implement comment reading/writing
		comment_lines = []
		# True if the comment belongs to a section rather than value
		section_comment = False

		for index, line in enumerate(list_):
			if not line:
				continue

			if line.startswith('#'):
				comment_lines.append(line)
				continue

			if line.startswith('[') and line.endswith(']'):
				if comment_lines:
					section_comment = True
				# If we've already come across a section header
				# We'll drop down to a lower level node
				if in_header:
					node = node[line[1:-1]]
				# If this is the first section header we've seen then
				# we'll assume it's a root level section.
				else:
					node = self[line[1:-1]]
					in_header = True
				continue

			in_header = False
			key, value = line.split('=', 1)
			key, value = key.strip(), value.strip()
			node[key] = eval(compile(value, self._filename + ' line: %d' % (index+1), 'eval'))
			if comment_lines:
				comment_block = '\n'.join(comment_lines)
				comment_lines[:] = []
				if section_comment:
					section_comment = False
					node._comments['__root__'] = comment_block
				else:
					node._comments[key] = comment_block

	def parse_config_string(self, str_, clear=True):
		self.parse_config_list(str_.splitlines(keepends=False), clear)

	def parse_config_file(self, file_, clear=True):
		self.parse_config_list((line.rstrip('\n') for line in file_), clear)

	def save(self):
		with file(self._filename, 'w+') as f:
			f.write(self._output())

if __name__ == '__main__':
	try:
		c = ConfigRoot('config.ini')
		print "DEBUG: Parsing File"
		c.parse_config()
	except IOError, e:
		print "DEBUG: Empty/Unknown File"
		print "DEBUG: Using Defaults"
		c.breakfast = ['bacon', 'eggs', 'pancakes', 'orange juice']
		c.x = 3.14159
		c.y = '\nThe "quick"\nbrown fox\njumps over\nthe \'lazy\' dog.\n'
		c.z = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8}
		c.server.username = 'iPal'
		c.server.password = 'ipfreely'
		c.server.ports.jabber = 5222
		c.server.ports.telnet = 23
		c.server.ports.http = 80
	#print "First Parse:\n%s\n" % c
	print "DEBUG: Saving File"
	c.save()
	print "DEBUG: Reparsing outputed file"
	c = ConfigRoot('config_out.ini')
	c.parse_config()
	#print "Second Parse:\n%s\n" % c
