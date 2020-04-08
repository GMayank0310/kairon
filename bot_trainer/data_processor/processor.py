import asyncio
import logging
import re
from collections import ChainMap
from typing import Dict
from typing import Text, List

from mongoengine.errors import DoesNotExist
from mongoengine.errors import NotUniqueError
from rasa.core.domain import InvalidDomain
from rasa.core.domain import SessionConfig
from rasa.core.slots import TextSlot, UnfeaturizedSlot, BooleanSlot, ListSlot
from rasa.core.training.structures import Checkpoint, STORY_START
from rasa.core.training.structures import StoryGraph, StoryStep
from rasa.importers import utils
from rasa.importers.rasa import Domain, StoryFileReader
from rasa.nlu.training_data import Message, TrainingData
from rasa.nlu.training_data.formats.markdown import MarkdownReader, ent_regex
from rasa.utils.io import read_config_file

from .data_objects import *


class MongoProcessor:

    def save_from_path(self, path: Text, bot: Text, user='default'):
        try:
            nlu_path = path + "/data/nlu.md"
            story_path = path + "/data/stories.md"
            nlu = utils.training_data_from_paths([nlu_path], 'en')
            domain = Domain.from_file(path + '/domain.yml')
            loop = asyncio.new_event_loop()
            story_steps = loop.run_until_complete(
                StoryFileReader. read_from_file(
                    story_path, domain))
            self.save_nlu(nlu, bot, user)
            self.save_domain(domain, bot, user)
            self.save_stories(story_steps, bot, user)
            self.__save_config(
                read_config_file(
                    path +
                    '/config.yml'),
                bot,
                user)
        except InvalidDomain as e:
            logging.info(e)
            raise Exception('''Failed to validate yaml file.
                            Please make sure the file is correct and all mandatory parameters are specified''')
        except Exception as e:
            logging.info(e)
            raise e

    def save_nlu(self, nlu: TrainingData, bot: Text, user: Text):
        self.__save_training_examples(nlu.training_examples, bot, user)
        self.__save_entity_synonyms(nlu.entity_synonyms, bot, user)
        self.__save_lookup_tables(nlu.lookup_tables, bot, user)
        self.__save_regex_features(nlu.regex_features, bot, user)

    def load_nlu(self, bot: Text) -> TrainingData:
        training_examples = self.__prepare_training_examples(bot)
        entity_synonyms = self.__prepare_training_synonyms(bot)
        lookup_tables = self.__prepare_training_lookup_tables(bot)
        regex_features = self.__prepare_training_regex_features(bot)
        return TrainingData(
            training_examples=training_examples,
            entity_synonyms=entity_synonyms,
            lookup_tables=lookup_tables,
            regex_features=regex_features)

    def save_domain(self, domain: Domain, bot: Text, user: Text):
        self.__save_intents(domain.intents, bot, user)
        self.__save_domain_entities(domain.entities, bot, user)
        self.__save_forms(domain.form_names, bot, user)
        self.__save_actions(domain.user_actions, bot, user)
        self.__save_responses(domain.templates, bot, user)
        self.__save_slots(domain.slots, bot, user)

    def load_domain(self, bot: Text) -> Domain:
        domain_dict = {
            'intents': self.__prepare_training_intents(bot),
            'actions': self.__prepare_training_actions(bot),
            'slots': self.__prepare_training_slots(bot),
            'session_config': self.__prepare_training_session_config(bot),
            'responses': self.__prepare_training_responses(bot),
            'forms': self.__prepare_training_forms(bot),
            'entities': self.__prepare_training_domain_entities(bot)
        }
        return Domain.from_dict(domain_dict)

    def save_stories(self, story_steps: Text, bot: Text, user: Text):
        self.__save_stories(story_steps, bot, user)

    def load_stories(self, bot: Text) -> StoryGraph:
        return self.__prepare_training_story(bot)

    def __save_training_examples(
            self,
            training_examples,
            bot: Text,
            user: Text):
        if training_examples:
            TrainingExamples.objects.insert(
                list(
                    self.__extract_training_examples(
                        training_examples,
                        bot,
                        user)))

    def __extract_entities(self, entities):
        for entity in entities:
            entity_data = Entity(
                start=entity['start'],
                end=entity['end'],
                value=entity['value'],
                entity=entity['entity'])
            yield entity_data

    def __extract_training_examples(
            self,
            training_examples,
            bot: Text,
            user: Text):
        for training_example in training_examples:
            training_data = TrainingExamples()
            training_data.intent = training_example.data['intent']
            training_data.text = training_example.text
            training_data.bot = bot
            training_data.user = user
            if "entities" in training_example.data:
                training_data.entities = list(
                    self.__extract_entities(
                        training_example.data['entities']))
            yield training_data

    def __extract_synonyms(self, synonyms, bot: Text, user: Text):
        for key, value in synonyms.items():
            yield EntitySynonyms(bot=bot, synonym=value, value=key, user=user)

    def __save_entity_synonyms(self, entity_synonyms, bot: Text, user: Text):
        if entity_synonyms:
            EntitySynonyms.objects.insert(
                list(
                    self.__extract_synonyms(
                        entity_synonyms,
                        bot,
                        user)))

    def fetch_synonyms(self, bot: Text, status=True):
        entitySynonyms = EntitySynonyms.objects(bot=bot, status=status)
        for entitySynonym in entitySynonyms:
            yield {entitySynonym.value: entitySynonym.synonym}

    def __prepare_training_synonyms(self, bot: Text):
        synonyms = list(self.fetch_synonyms(bot))
        return dict(ChainMap(*synonyms))

    def __prepare_entities(self, entities):
        for entity in entities:
            yield entity.to_mongo().to_dict()

    def fetch_training_examples(self, bot: Text, status=True):
        trainingExamples = TrainingExamples.objects(bot=bot, status=status)
        for trainingExample in trainingExamples:
            message = Message(trainingExample.text)
            message.data = {'intent': trainingExample.intent}
            if trainingExample.entities:
                message.data['entities'] = list(
                    self.__prepare_entities(
                        trainingExample.entities))
            yield message

    def __prepare_training_examples(self, bot: Text):
        return list(self.fetch_training_examples(bot))

    def __extract_lookup_tables(self, lookup_tables, bot: Text, user: Text):
        for lookup_table in lookup_tables:
            name = lookup_table['name']
            for element in lookup_table['elements']:
                yield LookupTables(name=name, value=element, bot=bot, user=user)

    def __save_lookup_tables(self, lookup_tables, bot: Text, user: Text):
        if lookup_tables:
            LookupTables.objects.insert(
                list(
                    self.__extract_lookup_tables(
                        lookup_tables,
                        bot,
                        user)))

    def fetch_lookup_tables(self, bot: Text, status=True):
        lookup_tables = LookupTables.objects(bot=bot, status=status).aggregate(
            [{"$group": {"_id": "$name", "elements": {"$push": "$value"}}}])
        for lookup_table in lookup_tables:
            yield {'name': lookup_table['_id'], 'elements': lookup_table['elements']}

    def __prepare_training_lookup_tables(self, bot: Text):
        return list(self.fetch_lookup_tables(bot))

    def __extract_regex_features(self, regex_features, bot: Text, user: Text):
        for regex_feature in regex_features:
            regex_data = RegexFeatures(**regex_feature)
            regex_data.bot = bot
            regex_data.user = user
            yield regex_data

    def __save_regex_features(self, regex_features, bot: Text, user: Text):
        if regex_features:
            RegexFeatures.objects.insert(
                list(
                    self.__extract_regex_features(
                        regex_features,
                        bot,
                        user)))

    def fetch_regex_features(self, bot: Text, status=True):
        regex_features = RegexFeatures.objects(bot=bot, status=status)
        for regex_feature in regex_features:
            yield {'name': regex_feature['name'], 'elements': regex_feature['pattern']}

    def __prepare_training_regex_features(self, bot: Text):
        return list(self.fetch_regex_features(bot))

    def __extract_intents(self, intents, bot: Text, user: Text):
        for intent in intents:
            yield Intents(name=intent, bot=bot, user=user)

    def __save_intents(self, intents, bot: Text, user: Text):
        if intents:
            Intents.objects.insert(
                list(
                    self.__extract_intents(
                        intents,
                        bot,
                        user)))

    def fetch_intents(self, bot: Text, status=True):
        intents = Intents.objects(bot=bot, status=status).aggregate(
            [{"$group": {"_id": "$bot", "intents": {"$push": "$name"}}}])
        return list(intents)

    def __prepare_training_intents(self, bot: Text):
        intents = self.fetch_intents(bot)
        if intents:
            return intents[0]['intents']
        else:
            return []

    def __extract_domain_entities(
            self,
            entities: List[Dict],
            bot: Text,
            user: Text):
        for entity in entities:
            yield Entities(name=entity, bot=bot, user=user)

    def __save_domain_entities(
            self,
            entities: List[Dict],
            bot: Text,
            user: Text):
        if entities:
            saved_entities = self.__prepare_training_domain_entities(bot=bot)
            new_entities = [
                entity for entity in list(
                    self.__extract_domain_entities(
                        entities,
                        bot,
                        user)) if entity.name not in saved_entities]
            if new_entities:
                Entities.objects.insert(new_entities)

    def fetch_domain_entities(self, bot: Text, status=True):
        entities = Entities.objects(bot=bot, status=status).aggregate(
            [{"$group": {"_id": "$bot", "entities": {"$push": "$name"}}}])
        return list(entities)

    def __prepare_training_domain_entities(self, bot: Text):
        entities = self.fetch_domain_entities(bot)
        if entities:
            return entities[0]['entities']
        else:
            return []

    def __extract_forms(self, forms, bot: Text, user: Text):
        for form in forms:
            yield Forms(name=form, bot=bot, user=user)

    def __save_forms(self, forms, bot: Text, user: Text):
        if forms:
            Forms.objects.insert(list(self.__extract_forms(forms, bot, user)))

    def fetch_forms(self, bot: Text, status=True):
        forms = Forms.objects(bot=bot, status=status).aggregate(
            [{"$group": {"_id": "$bot", "forms": {"$push": "$name"}}}])
        return list(forms)

    def __prepare_training_forms(self, bot: Text):
        forms = self.fetch_forms(bot)
        if forms:
            return forms[0]['forms']
        else:
            return []

    def __extract_actions(self, actions, bot: Text, user: Text):
        for action in actions:
            yield Actions(name=action, bot=bot, user=user)

    def __save_actions(self, actions, bot: Text, user: Text):
        if actions:
            Actions.objects.insert(
                list(
                    self.__extract_actions(
                        actions,
                        bot,
                        user)))

    def fetch_actions(self, bot: Text, status=True):
        actions = Actions.objects(bot=bot, status=status).aggregate(
            [{"$group": {"_id": "$bot", "actions": {"$push": "$name"}}}])
        return list(actions)

    def __prepare_training_actions(self, bot: Text):
        actions = self.fetch_actions(bot)
        if actions:
            return actions[0]['actions']
        else:
            return []

    def __extract_session_config(
            self,
            session_config: SessionConfig,
            bot: Text,
            user: Text):
        return SessionConfigs(
            sesssionExpirationTime=session_config.session_expiration_time,
            carryOverSlots=session_config.carry_over_slots,
            bot=bot,
            user=user)

    def __save_session_config(
            self,
            session_config: SessionConfig,
            bot: Text,
            user: Text):
        try:
            if session_config:
                SessionConfigs.objects.insert(
                    self.__extract_session_config(
                        session_config, bot, user))
        except NotUniqueError as e:
            logging.info(e)
            raise Exception("Session Config already exist for the bot")
        except Exception as e:
            logging.info(e)
            raise Exception("Internal Server Error")

    def fetch_session_config(self, bot: Text):
        try:
            session_config = SessionConfigs.objects.get(bot=bot)
        except DoesNotExist as e:
            logging.info(e)
            session_config = None
        return session_config

    def __prepare_training_session_config(self, bot: Text):
        session_config = self.fetch_session_config(bot)
        if session_config:
            return {
                'session_expiration_time': session_config.sesssionExpirationTime,
                'carry_over_slots': session_config.carryOverSlots}
        else:
            default_session = SessionConfig.default()
            return {
                'session_expiration_time': default_session.session_expiration_time,
                'carry_over_slots': default_session.carry_over_slots}

    def __extract_response_button(self, buttons):
        for button in buttons:
            yield ResponseButton._from_son(button)

    def __extract_response_value(self, values, key, bot: Text, user: Text):
        for value in values:
            response = Responses()
            response.name = key
            response.bot = bot
            response.user = user
            if 'text' in value:
                response_text = ResponseText()
                response_text.text = value['text']
                if 'image' in value:
                    response_text.image = value['image']
                if 'channel' in value:
                    response_text.channel = value['channel']
                if 'button' in value:
                    response_text.buttons = list(
                        self.__extract_response_button(
                            value['buttons']))
                response.text = response_text
            elif 'custom' in value:
                response.custom = ResponseCustom._from_son(value['custom'])
            yield response

    def __extract_response(self, responses, bot: Text, user: Text):
        responses_result = []
        for key, values in responses.items():
            responses_result.extend(
                list(
                    self.__extract_response_value(
                        values,
                        key,
                        bot,
                        user)))
        return responses_result

    def __save_responses(self, responses, bot: Text, user: Text):
        if responses:
            Responses.objects.insert(
                self.__extract_response(
                    responses, bot, user))

    def fetch_responses(self, bot: Text, status=True):
        responses = Responses.objects(bot=bot, status=status).aggregate(
            [{"$group": {"_id": "$name", "texts": {"$push": "$text"}, "customs": {"$push": "$custom"}}}])
        for response in responses:
            key = response['_id']
            value = response['texts']
            value.extend(response['customs'])
            yield {key: value}

    def __prepare_training_responses(self, bot: Text):
        return dict(ChainMap(*list(self.fetch_responses(bot))))

    def __fetch_slot_names(self, bot: Text):
        saved_slots = list(Slots.objects(bot=bot).aggregate(
            [{"$group": {"_id": "$bot", "slots": {"$push": "$name"}}}]))
        slots_list = []
        if saved_slots:
            slots_list = saved_slots[0]['slots']
        return slots_list

    def __extract_slots(self, slots, bot: Text, user: Text):
        slots_name_list = self.__fetch_slot_names(bot)
        for slot in slots:
            items = vars(slot)
            if items['name'] not in slots_name_list:
                items['type'] = slot.type_name
                items['value_reset_delay'] = items['_value_reset_delay']
                items.pop('_value_reset_delay')
                items['bot'] = bot
                items['user'] = user
                yield Slots._from_son(items)

    def __save_slots(self, slots, bot: Text, user: Text):
        if slots:
            new_slots = list(self.__extract_slots(slots, bot, user))
            if new_slots:
                Slots.objects.insert(new_slots)

    def fetch_slots(self, bot: Text, status=True):
        slots = Slots.objects(bot=bot, status=status)
        return list(slots)

    def __prepare_training_slots(self, bot: Text):
        slots = self.fetch_slots(bot)
        results = []
        for slot in slots:
            if slot.type == FloatSlot.type_name:
                results.append(
                    FloatSlot(
                        name=slot.name,
                        initial_value=slot.initial_value,
                        value_reset_delay=slot.value_reset_delay,
                        auto_fill=slot.auto_fill,
                        min_value=slot.min_value,
                        max_value=slot.max_value))
            elif slot.type == CategoricalSlot.type_name:
                results.append(
                    CategoricalSlot(
                        name=slot.name,
                        initial_value=slot.initial_value,
                        value_reset_delay=slot.value_reset_delay,
                        auto_fill=slot.auto_fill,
                        values=slot.values))
            elif slot.type == TextSlot.type_name:
                results.append(
                    TextSlot(
                        name=slot.name,
                        initial_value=slot.initial_value,
                        value_reset_delay=slot.value_reset_delay,
                        auto_fill=slot.auto_fill))
            elif slot.type == BooleanSlot.type_name:
                results.append(
                    BooleanSlot(
                        name=slot.name,
                        initial_value=slot.initial_value,
                        value_reset_delay=slot.value_reset_delay,
                        auto_fill=slot.auto_fill))
            elif slot.type == ListSlot.type_name:
                results.append(
                    ListSlot(
                        name=slot.name,
                        initial_value=slot.initial_value,
                        value_reset_delay=slot.value_reset_delay,
                        auto_fill=slot.auto_fill))
            elif slot.type == UnfeaturizedSlot.type_name:
                results.append(
                    UnfeaturizedSlot(
                        name=slot.name,
                        initial_value=slot.initial_value,
                        value_reset_delay=slot.value_reset_delay,
                        auto_fill=slot.auto_fill))
        return results

    def __extract_story_events(self, events):
        for event in events:
            if isinstance(event, UserUttered):
                yield StoryEvents(type=event.type_name, name=event.text)
            elif isinstance(event, ActionExecuted):
                yield StoryEvents(type=event.type_name, name=event.action_name)

    def __extract_story_step(self, story_steps, bot: Text, user: Text):
        for story_step in story_steps:
            story_events = list(self.__extract_story_events(story_step.events))
            story = Stories(
                block_name=story_step.block_name,
                events=story_events)
            story.bot = bot
            story.user = user
            yield story

    def __save_stories(self, story_steps, bot: Text, user: Text):
        if story_steps:
            Stories.objects.insert(
                list(
                    self.__extract_story_step(
                        story_steps,
                        bot,
                        user)))

    def __prepare_training_story_events(self, events, timestamp):
        for event in events:
            if event.type == 'user':
                intent = {'name': event.name, 'confidence': 1.0}
                '''
                parse_data = {
                    "intent": intent,
                    "entities": [],
                    "text": "/"+event.name,
                    "intent_ranking":[intent]
                }
                '''
                yield UserUttered(text=event.name, intent=intent, timestamp=timestamp)
            elif event.type == 'action':
                yield ActionExecuted(action_name=event.name, timestamp=timestamp)

    def fetch_stories(self, bot: Text, status=True):
        return list(Stories.objects(bot=bot, status=status))

    def __prepare_training_story_step(self, bot: Text):
        for story in Stories.objects(bot=bot, status=True):
            story_events = list(
                self.__prepare_training_story_events(
                    story.events, datetime.now().timestamp()))
            yield StoryStep(block_name=story.block_name, events=story_events, start_checkpoints=[Checkpoint(STORY_START)])

    def __prepare_training_story(self, bot: Text):
        return StoryGraph(list(self.__prepare_training_story_step(bot)))

    def __save_config(self, config: dict, bot: Text, user: Text):
        config['bot'] = bot
        config['user'] = user
        Configs.objects.insert(Configs._from_son(config))

    def fetch_configs(self, bot: Text):
        try:
            configs = Configs.objects.get(bot=bot)
        except DoesNotExist as e:
            logging.info(e)
            configs = Configs._from_son(
                read_config_file('./template/config.yml'))
        return configs

    def load_config(self, bot: Text):
        configs = self.fetch_configs(bot)
        config_dict = configs.to_mongo().to_dict()
        return {
            key: config_dict[key] for key in config_dict if key in [
                'language',
                'pipeline',
                'policies']}

    def add_intent(self, text: Text, bot: Text, user: Text):
        self.__isExist(
            Intents,
            bot=bot,
            query={
                'name': text},
            exp_message="Intent already exist!")
        Intents(name=text, bot=bot, user=user).save()

    def get_intents(self, bot: Text):
        intents = Intents.objects(bot=bot)
        return list(self.__prepare_document_list(intents, 'name'))

    def add_training_example(
            self,
            example: Text,
            intent: Text,
            bot: Text,
            user: Text):
        self.__isExist(
            TrainingExamples,
            bot=bot,
            query={
                'text': example},
            exp_message="Training Example already exist!")

        if not self.__isExist(
                Intents,
                bot=bot,
                query={
                    'name': intent},
                raise_error=False):
            Intents(name=intent, bot=bot, user=user).save()

        training_example = TrainingExamples(
            intent=intent, text=example, bot=bot, user=user)
        if not Utility.check_empty_string(example):
            entities = MarkdownReader._find_entities_in_training_example(
                example)
            if entities:
                ext_entity = [ent['entity'] for ent in entities]
                self.__save_domain_entities(ext_entity, bot=bot, user=user)
                self.__add_slots_from_entities(ext_entity, bot, user)
                training_example.text = re.sub(
                    ent_regex, lambda m: m.groupdict()["entity_text"], example)
                training_example.entities = list(
                    self.__extract_entities(entities))
        training_example.save()

    def get_training_examples(self, intent: Text, bot: Text):
        training_examples = list(
            TrainingExamples.objects(
                bot=bot, intent=intent))
        result = []
        for training_example in training_examples:
            example = training_example.to_mongo().to_dict()
            result.append({'_id': example['_id'].__str__(), 'text': Utility.prepare_nlu_text(
                example['text'], example['entities'])})
        return result

    def remove_document(self, document: Document, id: Text):
        try:
            doc = document.objects().get(id=id)
            doc.update(status=False)
        except DoesNotExist as e:
            logging.info(e)
            raise Exception('Unable to remove document')
        except Exception as e:
            logging.info(e)
            raise Exception('Unable to remove document')

    def __isExist(
            self,
            document: Document,
            bot: Text,
            query: Dict,
            exp_message: Text = '',
            raise_error=True):
        doc = document.objects(bot=bot, __raw__=query)
        if doc.__len__():
            if raise_error:
                if Utility.check_empty_string(exp_message):
                    raise Exception("Exception message cannot be empty")
                raise Exception(exp_message)
            else:
                return True
        else:
            if not raise_error:
                return False

    def __prepare_document_list(self, documents: List[Document], field: Text):
        for document in documents:
            doc_dict = document.to_mongo().to_dict()
            yield {'_id': doc_dict['_id'].__str__(), field: doc_dict[field]}

    def add_entity(self, name: Text, bot: Text, user: Text):
        self.__isExist(
            Entities,
            bot=bot,
            query={
                'name': name},
            exp_message="Entity already exist!")
        Entities(name=name, bot=bot, user=user).save()
        if not self.__isExist(
                Slots,
                bot=bot,
                query={
                    'name': name},
                raise_error=False):
            Slots(name=name, type='text', bot=bot, user=user).save()

    def get_entities(self, bot: Text):
        entities = Entities.objects(bot=bot)
        return list(self.__prepare_document_list(entities, 'name'))

    def add_action(self, name: Text, bot: Text, user: Text):
        self.__isExist(
            Actions,
            bot=bot,
            query={
                'name': name},
            exp_message="Entity already exist!")
        Actions(name=name, bot=bot, user=user).save()

    def get_actions(self, bot: Text):
        actions = Actions.objects(bot=bot)
        return list(self.__prepare_document_list(actions, 'name'))

    def __add_slots_from_entities(
            self,
            entities: List[Text],
            bot: Text,
            user: Text):
        slot_name_list = self.__fetch_slot_names(bot)
        slots = [Slots(name=entity, type='text', bot=bot, user=user)
                 for entity in entities if entity not in slot_name_list]
        if slots:
            Slots.objects.insert(slots)