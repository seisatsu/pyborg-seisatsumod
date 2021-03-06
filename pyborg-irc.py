#! /usr/bin/env python
#
# PyBorg IRC module
#
# Copyright (c) 2000, 2006 Tom Morton, Sebastien Dailly
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#        
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#

import sys
import re

try:
	from ircbot import *
	from irclib import *
except:
	print "ERROR !!!!\nircbot.py and irclib.py not found, please install them\n( http://python-irclib.sourceforge.net/ )"
	sys.exit(1)

#overide irclib function
def my_remove_connection(self, connection):
	if self.fn_to_remove_socket:
		self.fn_to_remove_socket(connection._get_socket())

IRC._remove_connection = my_remove_connection

import os
import pyborg
import cfgfile
import random
import time
import traceback
import thread

def get_time():
	"""
	Return time as a nice yummy string
	"""
	return time.strftime("%H:%M:%S", time.localtime(time.time()))

def replace_insensitive(string, target, replacement):
    no_case = string.lower()
    index = no_case.find(target.lower())
    if index >= 0:
        result = string[:index] + replacement + string[index + len(target):]
        return result
    else: # no results so return the original string
        return string

class ModIRC(SingleServerIRCBot):
	"""
	Module to interface IRC input and output with the PyBorg learn
	and reply modules.
	"""
	# The bot recieves a standard message on join. The standard part
	# message is only used if the user doesn't have a part message.
	join_msg = "%s"# is here"
	part_msg = "%s"# has left"

	# For security the owner's host mask is stored
	# DON'T CHANGE THIS
	owner_mask = []


	# Command list for this module
	commandlist =   "IRC Module Commands:\n!chans, !ignore, \
!join, !rejoin, !nick, !part, !quit, !quitmsg, !reply2ignored, !replyrate, !shutup, \
!stealth, !unignore, !logging, !notify, !wakeup, !talk, !owner"
	# Detailed command description dictionary
	commanddict = {
		"shutup": "Owner command. Usage: !shutup\nStop the bot from talking",
		"wakeup": "Owner command. Usage: !wakeup\nAllow the bot to talk",
		"join": "Owner command. Usage: !join #chan1 [#chan2 [...]]\nJoin one or more channels",
		"rejoin": "Owner command. Usage: !rejoin [on|off]\nEnable or disable rejoining a channel after being kicked. Without arguments shows the current setting",
		"part": "Owner command. Usage: !part #chan1 [#chan2 [...]]\nLeave one or more channels",
		"chans": "Owner command. Usage: !chans\nList channels currently joined",
		"nick": "Owner command. Usage: !nick nickname\nChange nickname",
		"ignore": "Owner command. Usage: !ignore [nick1 [nick2 [...]]]\nIgnore one or more nicknames. Without arguments it lists ignored nicknames",
		"unignore": "Owner command. Usage: !unignore nick1 [nick2 [...]]\nUnignores one or more nicknames",
		"logging": "Owner command. Usage: !logging [on|off]\nEnables or disables writing to a logfile",
		"notify": "Owner command. Usage: !notify [on|off]\nEnables or disables private message and CTCP notifications to owners",
		"replyrate": "Owner command. Usage: !replyrate [rate%]\nSet rate of bot replies to rate%. Without arguments (not an owner-only command) shows the current reply rate",
		"reply2ignored": "Owner command. Usage: !reply2ignored [on|off]\nAllow/disallow replying to ignored users. Without arguments shows the current setting",
		"stealth": "Owner command. Usage: !stealth [on|off]\nTurn stealth mode on or off (disable non-owner commands and don't return CTCP VERSION). Without arguments shows the current setting",
		"quitmsg": "Owner command. Usage: !quitmsg [message]\nSet the quit message. Without arguments show the current quit message",
		"talk": "Owner command. Usage !talk nick message\nmake the bot send the sentence 'message' to 'nick'",
		"quit": "Owner command. Usage: !quit\nMake the bot quit IRC",
		"owner": "Usage: !owner password\nAllow to become owner of the bot"
	}

	def __init__(self, my_pyborg, args):
		"""
		Args will be sys.argv (command prompt arguments)
		"""
		# PyBorg
		self.pyborg = my_pyborg
		# load settings
		
		self.settings = cfgfile.cfgset()
		self.settings.load("pyborg-irc.cfg",
			{ "myname": ("The bot's nickname", "PyBorg"),
			  "realname": ("Reported 'real name'", "Pyborg"),
			  "owners": ("Owner(s) nickname", [ "OwnerNick" ]),
			  "servers": ("IRC Server to connect to (server, port [,password])", [("irc.starchat.net", 6667)]),
			  "chans": ("Channels to auto-join", ["#test"]),
			  "rejoin_kick": ("Rejoin channel when kicked out", 0),
			  "logging": ("Enable or disable writing to a logfile", 0),
			  "notify" : ("Enable or disable private message and CTCP notifications to owners", 1),
			  "logfile": ("If logging is enabled, name of logfile", "log.txt"),
			  "speaking": ("Allow the bot to talk on channels", 1),
			  "stealth": ("Hide the fact we are a bot", 0),
			  "ignorelist": ("Ignore these nicknames:", []),
			  "reply2ignored": ("Reply to ignored people", 0),
			  "reply_chance": ("Chance of reply (%) per message", 33),
			  "quitmsg": ("IRC quit message", "Bye :-("),
			  "password": ("password to control the bot (Edit manually !)", "")
			} )

		self.owners = self.settings.owners[:]
		self.chans = self.settings.chans[:]

		# Parse command prompt parameters
		
		for x in xrange(1, len(args)):
			# Specify servers
			if args[x] == "-s":
				self.settings.servers = []
				# Read list of servers
				for y in xrange(x+1, len(args)):
					if args[y][0] == "-":
						break
					server = args[y].split(":")
					# Default port if none specified
					if len(server) == 1:
						server.append("6667")
					self.settings.servers.append( (server[0], int(server[1])) )
			# Channels
			if args[x] == "-c":
				self.settings.chans = []
				# Read list of channels
				for y in xrange(x+1, len(args)):
					if args[y][0] == "-":
						break
					self.settings.chans.append("#"+args[y])
			# Nickname
			if args[x] == "-n":
				try:
					self.settings.myname = args[x+1]
				except IndexError:
					pass

	def our_start(self):
		print "Connecting to server..."
		SingleServerIRCBot.__init__(self, self.settings.servers, self.settings.myname, self.settings.realname, 2)

		self.start()

	def on_welcome(self, c, e):
		print self.chans
		for i in self.chans:
			c.join(i)

	def shutdown(self):
		try:
			self.die() # disconnect from server
		except AttributeError, e:
			# already disconnected probably (pingout or whatever)
			pass

	def get_version(self):
		if self.settings.stealth:
			# stealth mode. we shall be a windows luser today
			return "VERSION mIRC32 v5.6 K.Mardam-Bey"
		else:
			return self.pyborg.ver_string

	def on_kick(self, c, e):
		"""
		Process leaving
		"""
		# Parse Nickname!username@host.mask.net to Nickname
		kicked = e.arguments()[0]
		kicker = e.source().split("!")[0]
		target = e.target() #channel
		if len(e.arguments()) >= 2:
			reason = e.arguments()[1]
		else:
			reason = ""

		if kicked == self.settings.myname:
			if self.settings.rejoin_kick:
				print "[%s] <--  %s was kicked off %s by %s (%s) (REJOINING)" % (get_time(), kicked, target, kicker, reason)
				c.join(target)
			else:
				print "[%s] <--  %s was kicked off %s by %s (%s)" % (get_time(), kicked, target, kicker, reason)

	def on_privmsg(self, c, e):
		self.on_msg(c, e)
	
	def on_pubmsg(self, c, e):
		self.on_msg(c, e)

	def on_ctcp(self, c, e):
		ctcptype = e.arguments()[0]
		if ctcptype == "ACTION":
			self.on_msg(c, e)
		else:
			SingleServerIRCBot.on_ctcp(self, c, e)

	def _on_disconnect(self, c, e):
#	        self.channels = IRCDict()
		print "deconnection"
		self.connection.execute_delayed(self.reconnection_interval, self._connected_checker)


	def on_msg(self, c, e):
		"""
		Process messages.
		"""
		# Parse Nickname!username@host.mask.net to Nickname
		source = e.source().split("!")[0]
		target = e.target()

		learn = 1

		# First message from owner 'locks' the owner host mask
		# se people can't change to the owner nick and do horrible
		# stuff like '!unlearn the' :-)
		if not e.source() in self.owner_mask and source in self.owners:
			self.owner_mask.append(e.source())
			print "Locked owner as %s" % e.source()

		# Message text
		if len(e.arguments()) == 1:
			# Normal message
			body = e.arguments()[0]
		else:
			# A CTCP thing
			if e.arguments()[0] == "ACTION":
				body = source + " " + e.arguments()[1]
			else:
				# Ignore all the other CTCPs
				return

		color_char = 0 #Remove IRC color strings
		while "\x03" in body:
			color_char = body.rfind("\x03")
			x = 0
			i = 0
			if color_char + 5 < len(body):
				while i < 5:
					if body[color_char+1].isdigit() or body[color_char+1] == ',':
						body = body[:color_char+1] + body[color_char+2:]
					else:
						body = body[:color_char] + body[color_char+1:]
						break
					i += 1
			elif color_char + 1 < len(body):
				j = color_char+1
				while j < len(body):
					if body[color_char+1].isdigit() or body[color_char+1] == ',':
						body = body[:color_char+1] + body[color_char+2:]
					else:
						body = body[:color_char] + body[color_char+1:]
						break
					j += 1
			else:
				body = body[:color_char] + body[color_char+1:]

		#remove special irc fonts chars
		body = body.replace("\x02", "")
		body = body.replace("\x1F", "")
		body = body.replace("\x16", "")
		body = body.replace("\x0F", "")
		body = body.replace("\xa0", "")

		# Ignore self.
		if source == self.settings.myname: return

		# Completely ignore lines beginning with ``
		if body.startswith("``"):
			print "Line ignored"
			return

		# We want replies reply_chance%, if speaking is on
		replyrate = self.settings.speaking * self.settings.reply_chance

		# Always reply to private messages
		if e.eventtype() == "privmsg":
			replyrate = 100

		# double reply chance if the text contains our nickname :-)
		if body.lower().find(self.settings.myname.lower() ) != -1:
			replyrate = replyrate * 2

		# Replace nicknames with "#nick", but don't mangle normal body text.
		if e.eventtype() == "pubmsg":
			for x in self.channels[target].users():
				if len(x) > 2: # Don't bother with tiny words
					if x.startswith(('&', '@', '%', '+', '~')): # Strip usermode symbols
						x = x[1:]
					body = replace_insensitive(body, ' ' + x + ' ', ' #nick ')
					tupunc = 0
					while tupunc < len(string.punctuation):
						puncind = tuple(string.punctuation)[tupunc]
						body = replace_insensitive(body, ' ' + x + puncind, ' #nick' + puncind)
						body = replace_insensitive(body, puncind + x + ' ', puncind + '#nick ')
						if body.lower().startswith(x.lower() + puncind):
							body = '#nick' + puncind + body[len(x)+1:]
						tupunc += 1
					if body.lower() == x.lower():
						body = '#nick'
					if body.lower().startswith(x.lower() + ' '):
						body = '#nick ' + body[len(x)+1:]
					if body.lower().endswith(' ' + x.lower()):
						body = body[:(len(body))-(len(x)+1)] + ' #nick'

		print "[%s] <%s> > %s> %s" % ( get_time(), source, target, body)

		# Ignore selected nicks
		if self.settings.ignorelist.count(source.lower()) > 0 \
			and self.settings.reply2ignored == 1:
			print "Nolearn from %s" % source
			learn = 0
		elif self.settings.ignorelist.count(source.lower()) > 0:
			print "Ignoring %s" % source
			return

		# Stealth mode. disable commands for non owners
		if (not source in self.owners) and self.settings.stealth:
			while body[:1] == "!":
				body = body[1:]

		if body == "":
			return

		# If logging is on, write body to logfile
		if self.settings.logging:
			loghandle = open(self.settings.logfile, 'a')
			loghandle.write("[%s] <%s> > %s> %s\n" % ( get_time(), source, target, body))

		# Ignore quoted messages
		if body[0] == "<" or body[0:1] == "\"" or body[0:1] == " <":
			print "Ignoring quoted text"
			return

		# Parse ModIRC commands
		if body[0] == "!":
			if self.irc_commands(body, source, target, c, e) == 1:return

		# Pass message onto pyborg
		if source in self.owners and e.source() in self.owner_mask:
			self.pyborg.process_msg(self, body, replyrate, learn, (body, source, target, c, e), owner=1)
		else:
			#start a new thread
			thread.start_new_thread(self.pyborg.process_msg, (self, body, replyrate, learn, (body, source, target, c, e)))

	def irc_commands(self, body, source, target, c, e):
		"""
		Special IRC commands.
		"""
		msg = ""

		command_list = body.split()
		command_list[0] = command_list[0].lower()

		### User commands
		# Query replyrate
		if command_list[0] == "!replyrate" and len(command_list)==1:
			msg = "Reply rate is "+`self.settings.reply_chance`+"%."

		if command_list[0] == "!owner" and len(command_list) > 1 and source not in self.owners:
			if command_list[1] == self.settings.password:
				self.owners.append(source)
				self.output("You've been added to owners list", ("", source, target, c, e))
			else:
				self.output("Try again", ("", source, target, c, e))

		### Owner commands
		if source in self.owners and e.source() in self.owner_mask:

			# Change nick
			if command_list[0] == "!nick":
				try:
					self.connection.nick(command_list[1])
					self.settings.myname = command_list[1]
				except:
					pass
			# stealth mode
			elif command_list[0] == "!stealth":
				msg = "Stealth mode "
				if len(command_list) == 1:
					if self.settings.stealth == 0:
						msg = msg + "off"
					else:
						msg = msg + "on"
				else:
					toggle = command_list[1].lower()
					if toggle == "on":
						msg = msg + "on"
						self.settings.stealth = 1
					else:
						msg = msg + "off"
						self.settings.stealth = 0

			# Enable/disable logging
			elif command_list[0] == "!logging":
				msg = "Logging "
				if len(command_list) == 1:
					if self.settings.logging == 0:
						msg = msg + "off"
					else:
						msg = msg + "on"
				else:
					toggle = command_list[1].lower()
					if toggle == "on":
						msg = msg + "on"
						self.settings.logging = 1
					else:
						msg = msg + "off"
						self.settings.logging = 0

			# Enable/disable notifications
			elif command_list[0] == "!notify":
				msg = "Notifications "
				if len(command_list) == 1:
					if self.settings.notify == 0:
						msg = msg + "off"
					else:
						msg = msg + "on"
				else:
					toggle = command_list[1].lower()
					if toggle == "on":
						msg = msg + "on"
						self.settings.notify = 1
					else:
						msg = msg + "off"
						self.settings.notify = 0

			# Enable/disable rejoin on kick
			elif command_list[0] == "!rejoin":
				msg = "Rejoin setting "
				if len(command_list) == 1:
					if self.settings.rejoin_kick == 0:
						msg = msg + "off"
					else:
						msg = msg + "on"
				else:
					toggle = command_list[1].lower()
					if toggle == "on":
						msg = msg + "on"
						self.settings.rejoin_kick = 1
					else:
						msg = msg + "off"
						self.settings.rejoin_kick = 0

			# filter mirc colours out?
			elif command_list[0] == "!nocolor" or command_list[0] == "!nocolour":
				msg = "obsolete command "

			# Allow/disallow replying to ignored nicks
			# (they will never be learnt from)
			elif command_list[0] == "!reply2ignored":
				msg = "Replying to ignored users "
				if len(command_list) == 1:
					if self.settings.reply2ignored == 0:
						msg = msg + "off"
					else:
						msg = msg + "on"
				else:
					toggle = command_list[1]
					if toggle == "on":
						msg = msg + "on"
						self.settings.reply2ignored = 1
					else:
						msg = msg + "off"
						self.settings.reply2ignored = 0
			# Stop talking
			elif command_list[0] == "!shutup":
				if self.settings.speaking == 1:
					msg = "I'll be quiet :-("
					self.settings.speaking = 0
				else:
					msg = ":-x"
			# Wake up again
			elif command_list[0] == "!wakeup":
				if self.settings.speaking == 0:
					self.settings.speaking = 1
					msg = "Whoohoo!"
				else:
					msg = "But i'm already awake..."
						
			# Join a channel or list of channels
			elif command_list[0] == "!join":
				for x in xrange(1, len(command_list)):
					if not command_list[x] in self.chans:
						msg = "Attempting to join channel %s" % command_list[x]
						self.chans.append(command_list[x])
						c.join(command_list[x])

			# Part a channel or list of channels
			elif command_list[0] == "!part":
				for x in xrange(1, len(command_list)):
					if command_list[x] in self.chans:
						msg = "Leaving channel %s" % command_list[x]
						self.chans.remove(command_list[x])
						c.part(command_list[x])

			# List channels currently on
			elif command_list[0] == "!chans":
				if len(self.channels.keys())==0:
					msg = "I'm currently on no channels"
				else:
					msg = "I'm currently on "
					channels = self.channels.keys()
					for x in xrange(0, len(channels)):
						msg = msg+channels[x]+" "
			# add someone to the ignore list
			elif command_list[0] == "!ignore":
				# if no arguments are given say who we are
				# ignoring
				if len(command_list) == 1:
					msg = "I'm ignoring "
					if len(self.settings.ignorelist) == 0:
						msg = msg + "nobody"
					else:
						for x in xrange(0, len(self.settings.ignorelist)):
							msg = msg + self.settings.ignorelist[x] + " "
				# Add everyone listed to the ignore list
				# eg !ignore tom dick harry
				else:
					for x in xrange(1, len(command_list)):
						self.settings.ignorelist.append(command_list[x].lower())
						msg = "done"
			# remove someone from the ignore list
			elif command_list[0] == "!unignore":
				# Remove everyone listed from the ignore list
				# eg !unignore tom dick harry
				for x in xrange(1, len(command_list)):
					try:
						self.settings.ignorelist.remove(command_list[x].lower())
						msg = "done"
					except:
						pass
			# set the quit message
			elif command_list[0] == "!quitmsg":
				if len(command_list) > 1:
					self.settings.quitmsg = body.split(" ", 1)[1]
					msg = "New quit message is \"%s\"" % self.settings.quitmsg
				else:
					msg = "Quit message is \"%s\"" % self.settings.quitmsg
			# make the pyborg quit
			elif command_list[0] == "!quit":
				sys.exit()
			# Change reply rate
			elif command_list[0] == "!replyrate":
				try:
					if int(command_list[1]) > 100:
						self.settings.reply_chance = 100
					else:
						self.settings.reply_chance = int(command_list[1])
					msg = "Now replying to %d%% of messages." % self.settings.reply_chance
				except:
					msg = "Reply rate is %d%%." % self.settings.reply_chance
			#make the bot talk
			elif command_list[0] == "!talk":
				if len(command_list) >= 2:
					phrase=""
					for x in xrange (2, len (command_list)):
						phrase = phrase + str(command_list[x]) + " "
					self.output(phrase, ("", command_list[1], "", c, e))
			# Save changes
			self.pyborg.settings.save()
			self.settings.save()
	
		if msg == "":
			return 0
		else:
			self.output(msg, ("<none>", source, target, c, e))
			return 1
			
	def output(self, message, args):
		"""
		Output a line of text. args = (body, source, target, c, e)
		"""
		if not self.connection.is_connected():
			print "Can't send reply : not connected to server"
			return

		# Unwrap arguments
		body, source, target, c, e = args

		# replace by the good nickname
		message = message.replace("#nick", source)

		# Decide. should we do a ctcp action?
		if message.find(self.settings.myname.lower()+" ") == 0:
			action = 1
			message = message[len(self.settings.myname)+1:]
		else:
			action = 0

		# Joins replies and public messages
		if e.eventtype() == "join" or e.eventtype() == "quit" or e.eventtype() == "part" or e.eventtype() == "pubmsg":
			if action == 0:
				print "[%s] <%s> > %s> %s" % ( get_time(), self.settings.myname, target, message)
				c.privmsg(target, message)
			else:
				print "[%s] <%s> > %s> /me %s" % ( get_time(), self.settings.myname, target, message)
				c.action(target, message)
		# Private messages
		elif e.eventtype() == "privmsg":
			# normal private msg
			if action == 0:
				print "[%s] <%s> > %s> %s" % ( get_time(), self.settings.myname, source, message)
				c.privmsg(source, message)
				# send copy to owner
				if not source in self.owners:
					if self.settings.notify:
						c.privmsg(','.join(self.owners), "(From "+source+") "+body)
						c.privmsg(','.join(self.owners), "(To   "+source+") "+message)
			# ctcp action priv msg
			else:
				print "[%s] <%s> > %s> /me %s" % ( get_time(), self.settings.myname, target, message)
				c.action(source, message)
				# send copy to owner
				if not source in self.owners:
					if self.settings.notify:
						map ( ( lambda x: c.action(x, "(From "+source+") "+body) ), self.owners)
						map ( ( lambda x: c.action(x, "(To   "+source+") "+message) ), self.owners)

if __name__ == "__main__":
	
	if "--help" in sys.argv:
		print "Pyborg irc bot. Usage:"
		print " pyborg-irc.py [options]"
		print " -s   server:port"
		print " -c   channel"
		print " -n   nickname"
		print "Defaults stored in pyborg-irc.cfg"
		print
		sys.exit(0)
	# start the pyborg
	my_pyborg = pyborg.pyborg()
	bot = ModIRC(my_pyborg, sys.argv)
	try:
		bot.our_start()
	except KeyboardInterrupt, e:
		pass
	except SystemExit, e:
		pass
	except:
		traceback.print_exc()
		c = raw_input("Ooops! It looks like Pyborg has crashed. Would you like to save its dictionary? (y/n) ")
		if c.lower()[:1] == 'n':
			sys.exit(0)
	bot.disconnect(bot.settings.quitmsg)
	my_pyborg.save_all()
	del my_pyborg
