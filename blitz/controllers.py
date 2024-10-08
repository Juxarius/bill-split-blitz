from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, Application

from models import Trips, Trip, Person, Receipt, Logs, State, States
from utils import get_config
from pymongo import MongoClient
from bson import ObjectId
from typing import List, Optional

db = MongoClient(f"mongodb://{get_config('mongoDbHostname')}:{get_config('mongoDbPort')}")['blitz']
TRIPS = Trips(database=db)
LOGS = Logs(database=db)
STATES = States(database=db)

TOKEN = get_config('token')
app = (
    Application.builder()
    .updater(None)
    .token(TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)
bot = app.bot

def get_last_trip(chat_id: int) -> Optional[Trip|None]:
    chat_trips = list(TRIPS.find_by({'chat_id': chat_id}))
    if len(chat_trips) < 1: return None
    return sorted(chat_trips, key=lambda trip: trip.last_referenced)[-1]

async def new_trip(update: Update, context: CallbackContext) -> None:
    m = update.message
    initiator = Person(user_id=m.from_user.id, user_name=m.from_user.username)
    new_trip = Trip(
        chat_id=m.chat.id,
        title=context.user_data.get('trip_name'),
        created_by=initiator,
        attendees=[initiator],
    )
    trip_id: ObjectId = TRIPS.save(new_trip).inserted_id
    await bot.send_message(
        m.chat.id,
        new_trip.describe(),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Join Trip!', callback_data=f'trip_join{trip_id}')]])
    )

async def join_trip(update: Update, context: CallbackContext) -> None:
    # Returns the list of registered users
    q = update.callback_query
    trip: Trip = TRIPS.find_one_by_id(ObjectId(q.data.replace('trip_join', '')))
    person = Person(user_id=q.from_user.id, user_name=q.from_user.username)
    if not trip.add_person(person):
        return
    TRIPS.save(trip)
    await bot.edit_message_text(
        trip.describe(),
        q.message.chat.id,
        q.message.message_id,
        reply_markup=q.message.reply_markup
    )

async def show_trip(update: Update, context: CallbackContext) -> None:
    trip = get_last_trip(update.message.chat.id)
    if trip is None:
        await update.message.reply_text('There is no recent trip found in the database')
        return
    await update.message.chat.send_message(
        trip.describe(),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('Join Trip!', callback_data=f'trip_join{trip.id}')],
            [InlineKeyboardButton('Not your trip?', callback_data='trip_browse_show0')]
        ])
    )

async def change_trip(update: Update, context: CallbackContext) -> None:
    q = update.callback_query
    sub_option = q.data.replace('trip_browse_', '')
    PAGE_SIZE = 9
    if sub_option.startswith('show'):
        page = int(sub_option.replace('show', ''))
        all_trips = sorted(list(TRIPS.find_by({"chat_id": q.message.chat.id})), key=lambda trip: trip.last_referenced, reverse=True)
        start_idx = page * PAGE_SIZE
        section = all_trips[start_idx:start_idx+PAGE_SIZE]
        next_page_exists = start_idx + PAGE_SIZE < len(all_trips)
        await q.edit_message_reply_markup(InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f'{trip.title} ({trip.created_on.strftime("%b %y")})', callback_data=f'trip_browse_select{trip.id}')]
            for trip in section]
            + ([[InlineKeyboardButton('Next Page', callback_data=f'trip_browse_show{page+1}')]] if next_page_exists else [])
        ))
        return
    if sub_option.startswith('select'):
        oid = ObjectId(sub_option.replace('select', ''))
        trip = TRIPS.find_one_by_id(oid)
        trip.update_as_last_referenced()
        TRIPS.save(trip)
        await q.edit_message_text(
            trip.describe(),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('Join Trip!', callback_data=f'trip_join{trip.id}')],
                [InlineKeyboardButton('Not your trip?', callback_data='trip_browse_show0')]
            ])
        )
        return

async def new_receipt(update: Update, context: CallbackContext) -> None:
    m = update.message
    data = context.user_data
    last_trip = get_last_trip(m.chat.id)
    if last_trip is None:
        await update.message.reply_text('There is no recent trip found in the database')
        return
    options = [(p.user_id, p.user_name) for p in last_trip.attendees]
    poll_text = '\n'.join([
        f'Trip: {last_trip.title}',
        f'{data.get("description")} [ ${data.get("amount"):.2f} ]',
        f'{m.from_user.username} is paying for...',
    ])
    poll_msg = await update.message.reply_poll(
        poll_text,
        [
            'Everyone',
            'Everyone except...',
        ] + [p[1] for p in options],
        is_anonymous=False,
        allows_multiple_answers=True
    )
    state = State(data={
        'type': 'receipt',
        'paid_by': (m.from_user.id, m.from_user.username),
        'trip_id': str(last_trip.id),
        'message_id': poll_msg.message_id,
        'chat_id': poll_msg.chat.id,
        'poll_id': poll_msg.poll.id,
        'amount': data.get('amount'),
        'description': data.get('description'),
        'options': options,
    })
    STATES.save(state)

async def complete_receipt(update: Update, context: CallbackContext):
    poll = update.poll_answer
    state = STATES.find_one_by({'data.poll_id': poll.poll_id})
    if state.data['type'] != 'receipt': return
    trip = TRIPS.find_one_by_id(ObjectId(state.data['trip_id']))
    if 0 in poll.option_ids: # Everyone
        paid_for = [Person(user_id=uid, user_name=username) for uid, username in state.data['options']]
    elif 1 in poll.option_ids: # Everyone except...
        to_remove = [opt_no-2 for opt_no in poll.option_ids if opt_no != 1]
        to_add = [opt for idx, opt in enumerate(state.data['options']) if idx not in to_remove]
        paid_for = [Person(user_id=uid, user_name=username) for uid, username in to_add]
    else:
        to_add = [state.data['options'][opt_no-2] for opt_no in poll.option_ids]
        paid_for = [Person(user_id=uid, user_name=username) for uid, username in to_add]
    trip.receipts.append(Receipt(
        paid_by=Person(user_id=state.data['paid_by'][0], user_name=state.data['paid_by'][1]),
        paid_for=paid_for,
        amount=state.data['amount'],
        description=state.data['description'],
    ))
    TRIPS.save(trip)
    await bot.stop_poll(state.data['chat_id'], state.data['message_id'])

async def settle(update: Update, context: CallbackContext) -> None:
    chat_trips = list(TRIPS.find_by({'chat_id': update.message.chat.id}))
    if len(chat_trips) < 1:
        await update.message.reply_text('There is no recent trip found in the database')
        return
    last_trip = sorted(chat_trips, key=lambda trip: trip.last_referenced)[-1]
    await update.message.reply_text(last_trip.describe_settle())

async def show_receipts(update: Update, context: CallbackContext):
    trip = get_last_trip(update.message.chat.id)
    await update.message.chat.send_message(trip.show_receipts())

async def explain(update: Update, context: CallbackContext):
    pass

def test_case_1():
    db_details = get_config("mongodbDetails")
    db = MongoClient(f"mongodb://{db_details['hostname']}:{db_details['port']}")

    trips = Trips(database=db['blitz'])
    p1 = Person(user_id=1, user_name="Juxarius")
    p2 = Person(user_id=2, user_name="Chingz")
    p3 = Person(user_id=3, user_name="Capoo")
    t1 = Trip(chat_id=23156, title="Bhutan Trip 2024", created_by=p1, attendees=[p1, p2, p3])

    r1 = Receipt(paid_by=p1, paid_for=[p1, p2, p3], amount=36, description="Dinner")
    r2 = Receipt(paid_by=p2, paid_for=[p1, p2], amount=20, description="Soft Toy")
    t1.receipts.extend([r1, r2])
    print(t1.settle())

    trips.save(t1)

if __name__ == '__main__':
    test_case_1()