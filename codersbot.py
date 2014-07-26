#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
import sys, os, random, re
import lxml.html
from twisted.internet import reactor, task, defer, protocol
from twisted.python import log
from twisted.words.protocols import irc
from twisted.web.client import getPage
from twisted.application import internet, service
from collections import defaultdict
HOST, PORT = 'irc.mozilla.org', 6667

WHO_AM_I = 'I am codersbot. Brought here from planet !@$%&*&&^%$@! to help you all through this channel.'
WHERE_AM_I = 'Go sleep kiddo.. You are drunk.'
WHAT_CAN_I_DO = 'Nothing much basically. Maybe keep you entertained while your master returns.'
WHERE_ARE_EVERYONE = 'Probably busy saving the world.'
WHAT_IS_CODERSJGEC = 'codersjgec is the Firefox Club of Jalpaiguri Government Engineering College. It is open source and anyone is free to join anytime they want.'
WHO_IS_INCHARGE = 'Any or all coders are incharge. There is nobody total incharge. But if you are asking for Club Lead or Club secretary. Maybe you wanna check out our website http://coders.jolites.in/'
WHO_MADE_ME = 'ani_stark did with help from his friends.'

DEFAULT = "Sorry, I don't understand your alien tone."

#-------------------------------------------------------------------------------
# Markov chain sentence generator, from
# http://eflorenzano.com/blog/2008/11/16/writing-markov-chain-irc-bot-twisted-and-python/
#-------------------------------------------------------------------------------
class MarkovGenerator(object):
    def __init__(self, stop_word='\n'):
        self.markov = defaultdict(list)
        self.stop_word = stop_word

    def train(self, msg, chain_length, write_to_file=False):
        if write_to_file:
            fp = open('file.txt', 'a')
            fp.write(msg + '\n')
            fp.close()
        buf = [self.stop_word] * chain_length
        for word in msg.split():
            # For each sliding window of length chain_length, add the following 
            # word to the list of possible words.
            self.markov[tuple(buf)].append(word)
            # slide the window:
            del buf[0]
            buf.append(word)
        self.markov[tuple(buf)].append(self.stop_word)

    def generate(self, msg, chain_length, max_words=10000):
        tmp = msg.split()
        buf = tmp[:chain_length]
        if len(tmp) > chain_length:
            message = buf[:]
        else:
            message = []
            i = chain_length
            while i:
                try:
                    message.append(
                        random.choice(
                            self.markov[random.choice(self.markov.keys())]))
                except IndexError:
                    message.append(random.choice(( 
                                                  'umm..', 
                                                  'now,', 
                                                  'look,', 
                                                  'okay,')))

                i -= 1

        ectr = 0
        for i in xrange(max_words):
            try:
                next_word = random.choice(self.markov[tuple(buf)])
            except IndexError:
                ectr += 1
                continue
            if next_word == self.stop_word:
                print('breaking off at i = %d' % i)
                break
            message.append(next_word)
            del buf[0]
            buf.append(next_word)
        print(ectr)
        return ' '.join(message)

class YIRCProtocol(irc.IRCClient):
    nickname = 'codersbot'
    mentioned_regex = re.compile(nickname + r"\s*[:,]* ?", re.I)

    def signedOn(self):
        # This is called once the server has acknowledged that we sent
        # both NICK and USER.
        for channel in self.factory.channels:
            self.join(channel)

    # Obviously, called when a PRIVMSG is received.
    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        message = message.strip()
        # Check for a mention:
        prefix = ''
        rest = message
        if self.nickname in message:
            rest = self.mentioned_regex.sub("", message).strip()
            prefix = "{0}: ".format(nick)
            if rest == 'who are you?':
                self.say(channel, prefix + WHO_AM_I)
                return
            elif rest == 'where are you?':
                self.say(channel, prefix + WHERE_AM_I)
                return
            elif rest == 'what can you do?':
                self.say(channel, prefix + WHAT_CAN_I_DO)
                return
            elif rest == 'where are everyone?':
                self.say(channel, prefix + WHERE_ARE_EVERYONE)
            elif rest == 'what is codersjgec?':
                self.say(channel, prefix + WHAT_IS_CODERSJGEC)
            elif rest == 'who is incharge?':
                self.say(channel, prefix + WHO_IS_INCHARGE)
            elif rest == 'who made you?':
                self.say(channel, prefix + WHO_MADE_ME)
            elif rest == 'hi':
                self.say(channel, prefix + 'hii')
            else:
                self.say(channel, prefix + DEFAULT)
        
        self.factory.generator.train(rest, self.factory.chain_length, True)

        if prefix or random.random() <= self.factory.chattiness:
                sentence = self.factory.generator.generate(rest,
                                                           self.factory.chain_length,
                                                           self.factory.max_words)
                if sentence:
                    self.say(channel, prefix + sentence)

        if not message.startswith('!'): # not a trigger command
            return # do nothing
        command, sep, rest = message.lstrip('!').partition(' ')
        # Get the function corresponding to the command given.
        func = getattr(self, 'command_' + command, None)
        # Or, if there was no function, ignore the message.
        if func is None:
            return
        d = defer.maybeDeferred(func, rest)
        d.addErrback(self._show_error)
        if channel == self.nickname:
            d.addCallback(self._send_message, nick)
        else:
            d.addCallback(self._send_message, channel, nick)

    def _send_message(self, msg, target, nick=None):
        if nick:
            msg = '%s, %s' % (nick, msg)
        self.msg(target, msg)

    def _show_error(self, failure):
        return failure.getErrorMessage()

    def command_ping(self, rest):
        return 'Pong.'

    def command_saylater(self, rest):
        when, sep, msg = rest.partition(' ')
        when = int(when)
        d = defer.Deferred()
        reactor.callLater(when, d.callback, msg)
        return d

    def command_title(self, url):
        d = getPage(url)
        d.addCallback(self._parse_pagetitle, url)
        return d

    def _parse_pagetitle(self, page_contents, url):
        pagetree = lxml.html.fromstring(page_contents)
        title = u' '.join(pagetree.xpath('//title/text()')).strip()
        title = title.encode('utf-8')
        return '%s -- "%s"' % (url, title)

class YIRCFactory(protocol.ReconnectingClientFactory):
    protocol = YIRCProtocol
    channels = ['#codersjgec']
    chain_length = 2
    chattiness = 0.05 # 0 to 1.0
    max_words = 10000
    generator = MarkovGenerator()

    def __init__(self):
        if os.path.exists('file.txt'):
            fp = open('file.txt', 'r')
            for line in fp:
                self.generator.train(line, self.chain_length)
            fp.close()

if __name__ == '__main__':
    reactor.connectTCP(HOST, PORT, YIRCFactory())
    log.startLogging(sys.stdout)
    reactor.run()

elif __name__ == '__builtin__':
    application = service.Application('codersbot')
    ircService = internet.TCPClient(HOST, PORT, YIRCFactory())
    ircService.setServiceParent(application)

