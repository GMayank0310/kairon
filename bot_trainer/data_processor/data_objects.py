from datetime import datetime

from rasa.core.events import UserUttered, ActionExecuted
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, LongField, ListField, \
    ValidationError, DateTimeField, BooleanField, DictField, DynamicField
from rasa.core.slots import CategoricalSlot, FloatSlot
from bot_trainer.utils import Utility




class Entity(EmbeddedDocument):
    start = LongField(required=True)
    end = LongField(required=True)
    value = StringField(required=True)
    entity = StringField(required=True)

    def validate(self, clean=True):
        if Utility.check_empty_string(self.value) or Utility.check_empty_string(self.entity):
            raise ValidationError("Entity name and value cannot be empty or blank spaces")

class TrainingExamples(Document):
    intent = StringField(required=True)
    text = StringField(required=True)
    bot = StringField(required=True)
    entities = ListField(EmbeddedDocumentField(Entity))
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    meta = {'indexes': [{'fields': ['$text']}]}

    def validate(self, clean=True):
        if self.entities:
            for ent in self.entities:
                extracted_ent = self.text[ent.start:ent.end]
                if extracted_ent != ent.value:
                    raise ValidationError("Invalid entity: "+ent.entity+", value: "+ent.value+" does not match with the position in the text "+extracted_ent)
        elif Utility.check_empty_string(self.text) or Utility.check_empty_string(self.intent):
            raise ValidationError("Training Example name and text cannot be empty or blank spaces")

class EntitySynonyms(Document):
    bot = StringField(required=True)
    synonym = StringField(required=True)
    value = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    meta = {'indexes': [{'fields': ['$value']}]}

    def validate(self, clean=True):
        if Utility.check_empty_string(self.synonym) or Utility.check_empty_string(self.value):
            raise ValidationError("Synonym name and value cannot be empty or blank spaces")

class LookupTables(Document):
    name = StringField(required=True)
    value = StringField(required=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    meta = {'indexes': [{'fields': ['$value']}]}

    def validate(self, clean=True):
        if Utility.check_empty_string(self.name) or Utility.check_empty_string(self.value) :
            raise ValidationError("Lookup name and value cannot be empty or blank spaces")

class RegexFeatures(Document):
    name = StringField(required=True)
    pattern = StringField(required=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    meta = {'indexes': [{'fields': ['$pattern']}]}

    def validate(self, clean=True):
        if Utility.check_empty_string(self.name) or Utility.check_empty_string(self.pattern):
            raise ValidationError("Regex name and pattern cannot be empty or blank spaces")

class Intents(Document):
    name = StringField(required=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    def validate(self, clean=True):
        if Utility.check_empty_string(self.name):
            raise ValidationError("Intent Name cannot be empty or blank spaces")

class Entities(Document):
    name = StringField(required=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    def validate(self, clean=True):
        if Utility.check_empty_string(self.name):
            raise ValidationError("Entity Name cannot be empty or blank spaces")

class Forms(Document):
    name = StringField(required=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    def validate(self, clean=True):
        if Utility.check_empty_string(self.name):
            raise ValidationError("Form name cannot be empty or blank spaces")

class ResponseButton(EmbeddedDocument):
    title = StringField(required=True)
    payload = StringField(required=True)

    def validate(self, clean=True):
        if not self.title or not self.payload:
            raise ValidationError("title and payload must be present!")
        elif Utility.check_empty_string(self.title) or Utility.check_empty_string(self.payload.strip()):
            raise ValidationError("Response title and payload cannot be empty or blank spaces")

class ResponseText(EmbeddedDocument):
    text = StringField(required=True)
    image = StringField()
    channel = StringField()
    buttons = ListField(EmbeddedDocumentField(ResponseButton))

    def validate(self, clean=True):
        if Utility.check_empty_string(self.text):
            raise ValidationError("Respone text cannot be empty or blank spaces")

class ResponseCustom(EmbeddedDocument):
    blocks = DictField(required=True)

class Responses(Document):
    name = StringField(required=True)
    text = EmbeddedDocumentField(ResponseText)
    custom = EmbeddedDocumentField(ResponseCustom)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    def validate(self, clean=True):
        if not self.text and not self.custom:
            raise ValidationError("Either Text or Custom response must be present!")


class Actions(Document):
    name = StringField(required=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    def validate(self, clean=True):
        if Utility.check_empty_string(self.name):
            raise ValidationError("Action name cannot be empty or blank spaces")

class SessionConfigs(Document):
    sesssionExpirationTime = LongField(required=True, default=60)
    carryOverSlots = BooleanField(required=True, default=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)

class Slots(Document):
    name = StringField(required=True)
    type = StringField(required=True)
    initial_value = DynamicField()
    value_reset_delay = LongField()
    auto_fill = BooleanField(default=True)
    value = StringField()
    values = ListField(StringField())
    max_value = LongField()
    min_value = LongField()
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    def validate(self, clean=True):
        if Utility.check_empty_string(self.name) or Utility.check_empty_string(self.type):
            raise ValueError("Slot name and type cannot be empty or blank spaces")
        error = ''
        if self.type == FloatSlot.type_name:
            if not self.min_value and not self.max_value:
                self.min_value = 0.0
                self.max_value = 1.0
            if self.min_value < self.max_value:
                error = "FloatSlot must have min_value < max_value"
            if not isinstance(self.initial_value, int):
                if error:
                    error += "\n"
                error = "FloatSlot initial_value must be numeric value"
                ValidationError(error)
        elif self.type == CategoricalSlot.type_name:
            if not self.values:
                raise ValidationError("CategoricalSlot must have list of categories in values field")

class StoryEvents(EmbeddedDocument):
    name = StringField(required=True)
    type = StringField(required=True)

class Stories(Document):
    block_name = StringField(required=True)
    events = ListField(EmbeddedDocumentField(StoryEvents), required=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)

    def validate(self, clean=True):
        if Utility.check_empty_string(self.block_name):
            raise ValidationError("Story path name cannot be empty or blank spaces")
        if isinstance(self.events[0], UserUttered):
            raise ValidationError("Stories must start with intent")
        elif isinstance(self.events[-1], ActionExecuted):
            raise ValidationError("Stories must end with action")


class Configs(Document):
    language = StringField(required=True, default="en")
    pipeline = ListField(DictField(), required=True)
    policies = ListField(DictField(), required=True)
    bot = StringField(required=True)
    user = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)
    status = BooleanField(default=True)