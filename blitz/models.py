from pydantic_mongo import AbstractRepository, PydanticObjectId
from pydantic import BaseModel, Field
from typing import Optional, List, Self
from datetime import datetime, timedelta

class Person(BaseModel):
    user_id: int
    user_name: str

    def __hash__(self) -> int:
        return self.user_id
    
    def __repr__(self) -> str:
        return self.user_name
    
    def __eq__(self, other: Self) -> bool:
        return self.user_id == other.user_id

class IOU(BaseModel):
    paid_by: Person
    paid_for: Person
    amount: float
    description: str

    def compound(self, other: Self) -> bool:
        if (self.paid_for, self.paid_by) == (other.paid_by, other.paid_for):
            self.amount -= other.amount
            self.description += f', {other.description}'
            self.correct_for_negative()
            return True
        elif (self.paid_for, self.paid_by) == (other.paid_for, other.paid_by):
            self.amount += other.amount
            self.description += f', {other.description}'
            self.correct_for_negative()
            return True
        return False
    
    def correct_for_negative(self) -> None:
        if self.amount < 0:
            self.reverse()

    def reverse(self) -> None:
        self.paid_by, self.paid_for = self.paid_for, self.paid_by
        self.amount = -self.amount

    def describe(self) -> str:
        return f'{self.paid_for.user_name} owes {self.paid_by.user_name} ${self.amount:.2f}'

class Receipt(BaseModel):
    paid_by: Person
    paid_for: List[Person]
    amount: float
    description: str = ""

    def break_down(self) -> List[IOU]:
        split_amount = self.amount / len(self.paid_for)
        return [IOU(paid_by=self.paid_by, paid_for=person, amount=split_amount, description=self.description) for person in self.paid_for]

    def describe(self) -> str:
        paid_for_str = ', '.join(p.user_name for p in self.paid_for)
        if len(self.paid_for) > 7:
            paid_for_str = f'{len(self.paid_for)} people'
        per_person_amount = self.amount / len(self.paid_for)
        lines = [
            f'-- {self.description} [ ${self.amount:.2f} | ${per_person_amount:.2f} each ]',
            f'{self.paid_by.user_name} paid for {paid_for_str}'
        ]
        return '\n'.join(lines)
    
    def multiply(self, amount: float) -> None:
        self.amount *= amount

class Trip(BaseModel):
    id: Optional[PydanticObjectId] = None
    chat_name: str = ""
    chat_id: int
    title: str
    created_by: Person
    created_on: datetime = Field(default_factory=datetime.now)
    last_referenced: datetime = Field(default_factory=datetime.now)
    attendees: List[Person]
    receipts: List[Receipt] = []

    def get_ious(self) -> List[IOU]:
        ious: List[IOU] = []
        for receipt in self.receipts:
            ious.extend(receipt.break_down())
        return ious

    def settle(self) -> List[IOU]:
        ious = self.get_ious()
        settled_ious: List[IOU] = []
        for iou in ious:
            for settled in settled_ious:
                if settled.compound(iou):
                    break
            else:
                settled_ious.append(iou)
        # Remove anything less than 1 cent
        return [iou for iou in settled_ious if abs(iou.amount) > 0.01 and iou.paid_by != iou.paid_for]

    def describe_settle(self) -> str:
        ious = self.settle()
        lines = [
            f'🎉 {self.title} 🎉\n',
            f'Receipts: {len(self.receipts)}\n',
        ]
        ious.sort(key=lambda iou: iou.paid_for.user_name)
        curr_oweing = ious[0].paid_for
        for iou in ious:
            if iou.paid_for != curr_oweing:
                lines.append('')
                curr_oweing = iou.paid_for
            lines.append(iou.describe())
        return '\n'.join(lines)

    def describe(self) -> str:
        attendees_str = "\n".join(p.user_name for p in self.attendees)
        lines = [
            f'🎉 {self.title} 🎉',
            f'< {self.created_on.strftime("%d %b %Y")} >',
            '',
            f'Receipts: {len(self.receipts)}',
            f'Attendees:\n{attendees_str}',
        ]
        return '\n'.join(lines)
    
    def one_liner(self) -> str:
        return f'{self.title} with {self.chat_name}\n{len(self.attendees)} people, {len(self.receipts)} receipts'

    def add_person(self, p: Person) -> bool:
        attendees = set(self.attendees)
        if p in attendees:
            return False
        self.attendees.append(p)
        return True
    
    def update_as_last_referenced(self) -> None:
        self.last_referenced = datetime.now()
    
    def show_receipts(self) -> str:
        if len(self.receipts) == 0:
            return 'No receipts recorded for this trip yet!'
        return '\n\n'.join(receipt.describe() for receipt in self.receipts)

class Trips(AbstractRepository[Trip]):
    class Meta:
        collection_name = 'trips'

def generate_expiry_date() -> datetime:
    return datetime.now() + timedelta(days=30)

class State(BaseModel):
    id: Optional[PydanticObjectId] = None
    data: dict
    expiry: datetime = Field(default_factory=generate_expiry_date)

class States(AbstractRepository[State]):
    class Meta:
        collection_name = 'states'

class Log(BaseModel):
    id: Optional[PydanticObjectId] = None
    log_level: int
    timestamp: datetime
    message: str

class Logs(AbstractRepository[Log]):
    class Meta:
        collection_name = 'logs'
