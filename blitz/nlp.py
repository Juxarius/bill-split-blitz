from telegram.ext import CallbackContext
from functools import cache
from typing import Sequence
import re

# All keywords must be lower case

@cache
def sanitize_msg(msg: str) -> str:
    return msg.lower()

@cache
def match_word_logic(msg: str, logic: Sequence[Sequence[Sequence[str]]]) -> bool:
    # OR - AND - OR Logic
    msg = sanitize_msg(msg)
    def and_or_logic(m: str, inner_logic: Sequence[Sequence[str]]) -> bool:
        for or_list in inner_logic:
            if not any(kw in m for kw in or_list):
                return False
        return True
    return any(and_or_logic(msg, inner_logic) for inner_logic in logic)

ATTENTION_LOGIC = (
    (('hey', 'yo', 'hello', 'hi', 'sup'), ('blitz',),),
    (('so blitz', 'blitz,'),),
)
def is_calling_blitz(msg: str) -> bool:
    return match_word_logic(msg, ATTENTION_LOGIC)

COMMAND_LOGIC_MAP = {
    'trip': (
        (('going',),),
        (('new', 'go',), ('trip', 'vacation', 'holiday',),),
    ),
    'bill': (
        (('paid', 'paying'), ('for',),),
    ),
    'settle': (
        (('settle', '结账',),),
        (('final', 'total',), ('amount',),),
    ),
    'receipts': (
        (('receipts', 'breakdown',),),
        (('break',), ('down',),),
    ),
    'show': (
        (('show',),),
        (('current',), ('trip',),),
    ),
    'help': (
        (('help',),),
        (('what',), ('command', 'commands',),),
        (('how',),),
    ),
    'intro': (
        (('about', 'where', 'who',), ('yourself', 'you', 'u',),),
    ),
    'explain': (
        (('explain',),),
    ),
}

def determine_command(msg: str) -> str:
    for command, logic in COMMAND_LOGIC_MAP.items():
        if match_word_logic(msg, logic):
            return command
    return None

def parse_trip(msg: str, context: CallbackContext) -> None:
    results = re.search(r'to (.*)', msg)
    if not results:
        raise ValueError('I couldnt find a possible trip name in there')
    context.user_data['trip_name'] = results.group(1)

def parse_bill(msg: str, context: CallbackContext) -> None:
    results = re.search(r'(\d+(?:\.\d+)?) for (.*)', msg)
    if not results:
        raise ValueError('I cant find a money value in there...')
    try:
        context.user_data['amount'] = float(results.group(1))
        context.user_data['description'] = results.group(2)
    except ValueError as e:
        raise ValueError(f'{results.group(1)} isnt really a number to represent money')

def test():
    class Context:
        user_data: dict = {}
    while True:
        msg = input("Test input: ")
        c = Context()
        parse_trip(msg, c)
        print(c.user_data)
        

if __name__ == '__main__':
    test()
