from telegram import Update, Message, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, PollAnswerHandler, CallbackQueryHandler, CallbackContext, filters
from telegram.ext._contexttypes import ContextTypes
from fastapi import Request, Response
from .utils import get_config

from . import controllers
from . import nlp
import json

DEBUG_MODE = True

blitz_config = get_config('blitz')
webserver_config = get_config('webserver')
endpoint = blitz_config['endpoint']
webhook_url = f'https://{webserver_config["ip"]}:{webserver_config["port"]}{blitz_config["endpoint"]}'
bot = controllers.app

async def command_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    start_msg_lines = [
        'Hello! My name is Blitz~',
        'Im a bill split bot who can help you to log all your expenses for a trip'
        'and make it easy to settle at the end of the trip',
        '',
        'You can type /help to see my commands!',
        '',
        'Recently, I have been trying to pick up human speech as well so you can try to invoke my functionalities'
        'with a \'Hey Blitz\' and simple sentences.',
        'Kinda like \'Hey Siri\', if you dont call my name, I cant reply you.',
        '(づ ◕‿◕ )づ Do be patient with me if I dont understand you.',
        'You can always fall back on my commands~',
        '',
        'I gotta be an admin to hear non-command messages though, so remember to promote me!',
    ]
    await update.message.chat.send_message('\n'.join(start_msg_lines))

async def command_help(update: Update, context: CallbackContext):
    help_lines = [
        'For commands, you will need to follow the syntax strictly for it to work',
        '/trip TRIP_NAME - Start a new trip!',
        '/bill AMOUNT DESC - Record a receipt that you paid for, I will later ask who you paid for',
        '/settle - Get the final amout everyone owes each other',
        '/receipts - Shows all receipts and breakdown',
        '/show - Shows the currnet trip you are on, you can reselect older trips',
        '/intro - Tell you more about myself!'
    ]
    await update.message.chat.send_message('\n'.join(help_lines))

async def command_intro(update: Update, context: CallbackContext):
    introduction = [
        "Hi there! I'm Blitz, your friendly helper bot, always eager to lend a hand!",
        "I'm pretty good at math and keeping track of receipts, especially for end-of-vacation tabulations.",
        "If you've got expenses to split, I've got you covered!",
        "In my spare time, I love chasing down bugs, it's my idea of fun!",
        "I live in a cozy Raspberry Pi, thanks to my creator, Juxarius.",
        '\n(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧',
        '\nIt was there for a while but Jux couldnt get the fan to work, so he had to shut it down before it became a fire hazard.',
        'But recently he found out that the connector pins were just wrongly inserted!\nSilly Jux ꒰(･‿･)꒱',
        "\nAnyways, feel free to reach out whenever you need some help. I'm here for you!",
    ]
    await update.message.chat.send_message(' '.join(introduction))

async def command_trip(update: Update, context: CallbackContext):
    split_msg = update.message.text.split()
    if len(split_msg) < 2:
        await update.message.reply_text(f'Did you miss out the name of your trip?\n/trip TRIP_NAME')
        return
    context.user_data['trip_name'] = ''.join(split_msg[1:])
    await controllers.new_trip(update, context)

async def command_bill(update: Update, context: CallbackContext):
    split_msg = update.message.text.split()
    if len(split_msg) < 3:
        await update.message.reply_text(f'You gotta put it in this format:\n/bill AMOUNT DESC')
        return
    try:
        amount_str = split_msg[1]
        context.user_data['amount'] = float(amount_str)
    except ValueError as e:
        await update.message.reply_text(f'I cant translate {amount_str} to a number!')
        return
    context.user_data.update({
        'amount': amount_str,
        'description': ''.join(split_msg[2:]),
    })
    await controllers.new_receipt(update, context)

async def poll_complete_bill(update: Update, context: CallbackContext):
    await controllers.complete_receipt(update, context)

async def command_settle(update: Update, context: CallbackContext):
    await controllers.settle(update, context)

async def command_show_receipts(update: Update, context: CallbackContext):
    await controllers.show_receipts(update, context)

async def command_show_trip(update: Update, context: CallbackContext):
    await controllers.show_trip(update, context)

async def command_explain(update: Update, context: CallbackContext):
    await controllers.explain(update, context)

async def callback_trip_join(update: Update, context: CallbackContext):
    await controllers.join_trip(update, context)

async def callback_trip_browse(update: Update, context: CallbackContext):
    await controllers.change_trip(update, context)

command_map = {
    'start': command_start,
    'intro': command_intro,
    'trip': command_trip,
    'bill': command_bill,
    'settle': command_settle,
    'explain': command_explain,
    'show': command_show_trip,
    'receipts': command_show_receipts,
    'help': command_help,
}

callback_map = {
    'trip_join.*': callback_trip_join,
    'trip_browse.*': callback_trip_browse,
}

async def handle_text(update: Update, context: CallbackContext):
    msg = update.message.text
    if not nlp.is_calling_blitz(msg):
        return
    command = nlp.determine_command(msg)
    if command is None:
        await update.message.reply_text(f'Sorry, I uhh... dont quite understand you ٭(•﹏•)٭')
        return
    parsing_required = {
        'trip': (nlp.parse_trip, controllers.new_trip),
        'bill': (nlp.parse_bill, controllers.new_receipt),
    }
    if command not in parsing_required:
        await command_map[command](update, context)
        return
    try:
        parsing_required[command][0](msg, context)
        await parsing_required[command][1](update, context)
    except ValueError as e:
        await update.message.reply_text(str(e))

async def setup():
    for command, func in command_map.items():
        bot.add_handler(CommandHandler(command, func))

    for callback_pattern, func in callback_map.items():
        bot.add_handler(CallbackQueryHandler(func, callback_pattern))

    poll_handlers = [
        poll_complete_bill,
    ]
    for func in poll_handlers:
        bot.add_handler(PollAnswerHandler(func))

    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    with open(webserver_config['certfile']) as certfile:
        await bot.bot.setWebhook(webhook_url, certificate=certfile)

async def process_request(request: Request):
    req = await request.json()
    if DEBUG_MODE: print(json.dumps(req, indent=2))
    update = Update.de_json(req, bot.bot)
    await bot.process_update(update)
    return Response(status_code=200)
