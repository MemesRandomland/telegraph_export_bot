#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram.ext import Updater, MessageHandler, Filters
from telegram import MessageEntity

import export_to_telegraph
from html_telegraph_poster import TelegraphPoster
import yaml
from telegram_util import matchKey, log_on_fail, log, tryDelete
import plain_db

with open('CREDENTIALS') as f:
    CREDENTIALS = yaml.load(f, Loader=yaml.FullLoader)
tele = Updater(CREDENTIALS['bot_token'], use_context=True)

debug_group = tele.bot.get_chat(420074357)

no_auth_link_users = [-1001399998441]

no_source_link = plain_db.loadKeyOnlyDB('no_source_link')

with open('TELEGRAPH_TOKENS') as f:
	TELEGRAPH_TOKENS = {}
	for k, v in yaml.load(f, Loader=yaml.FullLoader).items():
		TELEGRAPH_TOKENS[int(k)] = v

def saveTelegraphTokens():
	with open('TELEGRAPH_TOKENS', 'w') as f:
		f.write(yaml.dump(TELEGRAPH_TOKENS, sort_keys=True, indent=2))

def getSource(msg):
	if msg.from_user:
		return msg.from_user.id, msg.from_user.first_name, msg.from_user.username
	return msg.chat_id, msg.chat.title, msg.chat.username

def msgAuthUrl(msg, p):
	r = p.get_account_info(fields=['auth_url'])
	msg.reply_text('Use this url to login in 5 minutes: ' + r['auth_url'])

def msgTelegraphToken(msg):
	source_id, shortname, longname = getSource(msg)
	if source_id in TELEGRAPH_TOKENS:
		p = TelegraphPoster(access_token = TELEGRAPH_TOKENS[source_id])
	else:
		p = TelegraphPoster()
		r = p.create_api_token(shortname, longname)
		TELEGRAPH_TOKENS[source_id] = r['access_token']
		saveTelegraphTokens()
	if source_id not in no_auth_link_users:
		msgAuthUrl(msg, p)

def getTelegraph(msg, url):
	source_id, _, _ = getSource(msg)
	if source_id not in TELEGRAPH_TOKENS:
		msgTelegraphToken(msg)
	export_to_telegraph.token = TELEGRAPH_TOKENS[source_id]
	return export_to_telegraph.export(url, throw_exception = True, 
		force = True, toSimplified = 'bot_simplify' in msg.text,
		noSourceLink = str(msg.chat_id) in no_source_link._db.items)

def exportImp(msg):
	for item in msg.entities:
		if (item["type"] == "url"):
			url = msg.text[item["offset"]:][:item["length"]]
			if not '://' in url:
				url = "https://" + url
			result = getTelegraph(msg, url)
			if str(msg.chat_id) in no_source_link._db.items:
				msg.chat.send_message(result)
			else:
				msg.chat.send_message('%s | [source](%s)' % (result, url), 
					parse_mode='Markdown')

@log_on_fail(debug_group)
def export(update, context):
	if update.edited_message or update.edited_channel_post:
		return
	msg = update.effective_message
	if '[source]' in msg.text_markdown and msg.chat_id < 0:
		return
	if msg.chat.username == 'web_record':
		if (matchKey(msg.text_markdown, ['twitter', 'weibo', 
				'douban', 't.me/']) and 
				not matchKey(msg.text_markdown, ['article', 'note'])):
			tryDelete(msg)
			return
	try:
		r = msg.chat.send_message('received')
	except:
		return
	exportImp(msg)
	r.delete()
	if msg.chat.username == 'web_record':
		tryDelete(msg)

with open('help.md') as f:
	help_message = f.read()

def toggleSourceLink(msg):
	result = no_source_link.toggle(msg.chat_id)
	if result:
		msg.reply_text('Source Link Off')
	else:
		msg.reply_text('Source Link On')

@log_on_fail(debug_group)
def command(update, context):
	msg = update.message
	if matchKey(msg.text, ['auth', 'token']):
		return msgTelegraphToken(msg)
	if matchKey(msg.text, ['toggle', 'source']):
		return toggleSourceLink(msg)
	if msg.chat_id > 0:
		msg.reply_text(help_message)

tele.dispatcher.add_handler(MessageHandler(Filters.text & 
	(Filters.entity('url') | Filters.entity(MessageEntity.TEXT_LINK)), export))
tele.dispatcher.add_handler(MessageHandler(Filters.command, command))

tele.start_polling()
tele.idle()