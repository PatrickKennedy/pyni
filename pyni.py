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
from StringIO import StringIO

__version__ = '0.3.4'

def sterilize_comment(comment):
	"""Sterilize all lines of a comment.

	Make sure all lines start with a comment delimiter and end with a newline.

	"""
	comments = comment.splitlines(True)
	for index, comment in enumerate(comments):
		# Make sure the comment can't be used to inject values.
		if not comment.startswith('#'):
			comment = '# ' + comment

		# Make sure the comment doesn't absorb the section.
		if not comment.endswith('\n'):
			comment += '\n'
		comments[index] = comment
	return ''.join(comments)

class ConfigNode(defaultdict):
	def __init__(self):
		self.default_factory = ConfigNode
		self._comments = defaultdict(str)

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

	def _output(self, stream=None, parents=None):
		if parents is None:
			parents = []
		if stream is None:
			stream = StringIO()

		# True if we've already appended the parent sections
		buffered_parents = False

		# All ConfigNode children are stored here to be appended
		# after the variable assignemnts.
		sub_sections = []

		# Allows us to sort the child assignments alphabetically
		children = self.items()
		children.sort()
		for key, value in children:
			# If we're handling a subsection
			if isinstance(value, ConfigNode):
				sub_sections.append((key, value))
			# All other variables get thrown into assignments
			else:
				# Append all parent sections to the beginning of assignments.
				if not buffered_parents and parents:
					stream.write('\n')
					# Attach section comments to the header.
					if '__root__' in self._comments:
						stream.write(sterilize_comment(self._comments['__root__']))
					[stream.write("[%s]\n" % parent) for parent in parents]
					buffered_parents = True

				# Attach value comments to each value.
				if key in self._comments:
					stream.write(sterilize_comment(self._comments[key]))
				stream.write("%s = %r\n" % (key, value))

		# Walk through all sub-sections, appending and poping to emulate depth.
		for key, value in sub_sections:
			parents.append(key)
			value._output(stream, parents)
			parents.pop()
			stream.flush()

		return stream

class ConfigRoot(ConfigNode):

	def __init__(self, filename, encoding='utf-8'):
		ConfigNode.__init__(self)
		self._filename = filename
		self._encoding = encoding

	def read(self, clear=True):
		if not os.path.exists(self._filename):
			print "Creating %s" % self._filename
		with open(self._filename, 'a+') as f:
			self._parse_file(f, clear)

	def save(self, filename=None):
		with file(filename or self._filename, 'w+') as f:
			self._output(stream=f)

	def parse_object(self, content, clear=True):
		"""Parse according to content type.

		Can parse:
			strings
			files (or file-like objects)
			lists

		"""
		if isinstance(content, basestring):
			self._parse_string(content, clear)
		elif hasattr(content, 'readlines'):
			self._parse_file(content, clear)
		elif hasattr(content, '__iter__'):
			self._parse_list(content, clear)
		else:
			raise TypeError("Unknown config content type: %s" % type(content))

	def _parse_list(self, list_, clear=True):
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
			# TODO: Upgrade to ast.eval_literal in Python 2.6
			node[key] = eval(compile(value, self._filename + ' line: %d' % (index+1), 'eval'))

			if comment_lines:
				comment_block = '\n'.join(comment_lines)
				comment_lines[:] = []
				if section_comment:
					section_comment = False
					node._comments['__root__'] = comment_block
				else:
					node._comments[key] = comment_block

	def _parse_string(self, str_, clear=True):
		self._parse_list(str_.splitlines(keepends=False), clear)

	def _parse_file(self, file_, clear=True):
		self._parse_list((line.rstrip('\n') for line in file_.readlines()), clear)

if __name__ == '__main__':
	import sys
	input = 'config.ini'
	output = 'config_out.ini'
	if len(sys.argv) > 1:
		input = sys.argv[1]
	if len(sys.argv) > 2:
		output = sys.argv[2]

	c = ConfigRoot(input)
	try:
		print "DEBUG: Parsing File (%s)" % input
		c.read()
	except IOError, e:
		pass
	finally:
		if not c:
			print "DEBUG: Empty/Unknown File"
			print "DEBUG: Using Defaults"
			c._comments['__root__'] = 'Configutation Options for <program_name_here>.\nDo NOT edit while program is running.'
			c._comments['log_path'] = 'Folder for logs to be stored under\n'
			c._comments['log_path'] += ''
			c.log_path = 'logs'
			c._comments['breakfast'] = 'This sounds like a lovely breakfast ^^'
			c.breakfast = ['bacon', 'eggs', 'pancakes', 'orange juice']
			c.x = 3.14159
			c._comments['y'] = "Contains every letter in the alphabet!"
			c.y = '\nThe "quick"\nbrown fox\njumps over\nthe \'lazy\' dog.\n'
			c.z = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8}
			c.server._comments['__root__'] = 'These aren\'t my real credentials, HAHAHA'
			c.server.username = 'iPal'
			c.server.password = 'ipfreely'
			c.server.ports._comments['jabber'] = 'Don\'t forget about the old 5223 jabber port.\nI believe it was used as a security port.'
			c.server.ports.jabber = 5222
			c.server.ports.telnet = 23
			c.server.ports.http = 80
	#print "First Parse:\n%s\n" % c
	print "DEBUG: Saving File (%s)" % output
	c.save(output)
	print "DEBUG: Reparsing outputed file"
	c = ConfigRoot(output)
	c.read()
	#print "Second Parse:\n%s\n" % c
