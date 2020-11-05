# Copyright (c) 2019 Target Brands, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import time
import re
from karmabot import regex
from karmabot import settings
from karmabot.controller.badges import BadgesController
from karmabot.metrics import log_metrics
from flask import current_app
from karmabot.service import slack as slack_client
from pymongo import MongoClient


class KarmaController(object):

    def __init__(self):
        self.mongodb = MongoClient(current_app.config.get('MONGODB'))['karmabot']
        self.badges = BadgesController()

    def handle_event(self, eventw):
        late = time.time() - float(eventw['rec_time'])
        log_metrics('karmabot_event_latency', None, 'time_elapsed', int(late * 1000))

        current_app.logger.debug(f"{eventw['event']['type']}")
        if eventw['event']['type'] != 'message':
            current_app.logger.warning("Ignoring unknown event type")
            return

        if 'user' in eventw['event']:

            if self.blacklisted(eventw['team_id'], eventw['event']['user']):
                return
            rlc = self.ratelimit_count(eventw['team_id'], eventw['event']['user'])
            if rlc > settings.KARMA_RATE_LIMIT:
                msg = f"Slow down there, partner! You only get to use karma {settings.KARMA_RATE_LIMIT} times per hour. Wait a little while and try again."  # noqa E501
                self.karma_error_reply(eventw, msg)
                return
        else:
            # Not a message from a user; ignore bots, etc
            current_app.logger.info("No user provided in the event")
            return
        self.karma_it(eventw, rlc)
        return

    def ratelimit_count(self, workspace_id, gifter):
        collection = self.mongodb[workspace_id]
        d = datetime.datetime.utcnow() + datetime.timedelta(hours=-1)
        count = collection.find(
            {
                "$and": [
                    {"date": {"$gt": d}},
                    {"gifter": {"$eq": gifter}}
                ]
            }).count()
        return count

    def handle_command(self, command):
        current_app.logger.info(command['text'])

        if not command['text']:
            log_metrics('karmabot_command', {"command": "none"}, 'count', 1)
            return self.cmd_karma(command)

        # this needs to be checked before `if args[0] == "top"`
        if ' '.join(command['text'].split()) == 'top channel members':
            return self.get_top_channel_members(command)

        args = command['text'].split()
        if args[0] == "stats":
            log_metrics('karmabot_command', {"command": "stats"}, 'count', 1)
            if len(args) > 1:
                return self.cmd_karma_subject_stats(command, command['text'][6:])
            return self.cmd_karma_stats(command)

        if args[0] == "show":
            log_metrics('karmabot_command', {"command": "show"}, 'count', 1)
            return self.cmd_karma_show(command)

        if args[0] == "top":
            log_metrics('karmabot_command', {"command": "top"}, 'count', 1)
            return self.cmd_karma_top(command)

        if args[0] == "bottom":
            log_metrics('karmabot_command', {"command": "bottom"}, 'count', 1)
            return self.cmd_karma_top(command, 1)

        if args[0] == "leave":
            log_metrics('karmabot_command', {"command": "leave"}, 'count', 1)
            return self.cmd_leave(command)

        if args[0] == "help":
            log_metrics('karmabot_command', {"command": "help"}, 'count', 1)
        else:
            log_metrics('karmabot_command', {"command": "unknown"}, 'count', 1)
        return self.cmd_karma_help(command)

    def handle_mention(self, eventw):
        command = eventw
        if 'user' in eventw['event']:
            current_app.logger.debug(f"Got a mention from {eventw['event']['user']}")
            if self.blacklisted(eventw['team_id'], eventw['event']['user']):
                return

        else:
            # Not a message from a user; ignore bots, etc
            current_app.logger.debug("Got a mention without a user. Ignoring.")
            return
        text = eventw['event']['text'].split(' ', 1)  # remove the `@user` mention
        eventw['text'] = text[1]  # Store the text to mimic the 'command' object
        args = text[1].split(' ', 1)

        if args[0] == "stats":
            log_metrics('karmabot_mention', {"command": "stats"}, 'count', 1)
            if len(args) > 1:
                return self.cmd_karma_subject_stats(command, command['text'][6:])
            return self.cmd_karma_stats(command)

        if args[0] == "show":
            log_metrics('karmabot_mention', {"command": "show"}, 'count', 1)
            return self.cmd_karma_show(command)

        if args[0] == "top":
            log_metrics('karmabot_mention', {"command": "top"}, 'count', 1)
            return self.cmd_karma_top(command)

        if args[0] == "bottom":
            log_metrics('karmabot_mention', {"command": "bottom"}, 'count', 1)
            return self.cmd_karma_top(command, 1)

        if args[0] == "help":
            log_metrics('karmabot_mention', {"command": "help"}, 'count', 1)
        else:
            log_metrics('karmabot_mention', {"command": "unknown"}, 'count', 1)
        return self.cmd_karma_help(command)

    def store_karma(self, ktype, subject, quantity, gifter, workspace_id):
        now = datetime.datetime.utcnow()
        expires = now + datetime.timedelta(days=settings.KARMA_TTL)
        data = {
            'type': ktype,
            'subject': subject,
            'quantity': quantity,
            'gifter': gifter,
            'date': now,
            'expires': expires
        }
        collection = self.mongodb[workspace_id]
        collection.insert_one(data)

    def get_karma(self, workspace_id, ktype, subject):
        if ktype == "thing" and subject == u'\u03c0':
            return "3.14159265358979323846264338327950288419716939937510582"
        if ktype == "thing" and subject == u'\u2107':
            return "2.71828182845904523536028747135266249775724709369995957"

        collection = self.mongodb[workspace_id]
        pipeline = [
            {
                "$match": {
                    "subject": subject,
                    "type": ktype
                }
            },
            {
                "$group": {
                    "_id": "subject",
                    "total": {
                        "$sum": "$quantity"
                    }
                }
            }
        ]

        results = collection.aggregate(pipeline)
        # TODO: how do we handle errors here?
        l_results = list(results)
        if len(l_results) == 0:
            return 0
        return l_results[0]['total']

    def get_type_karma(self, workspace_id, ktype):
        collection = self.mongodb[workspace_id]
        pipeline = [
            {
                "$match": {
                    "type": ktype
                }
            },
            {
                "$group": {
                    "_id": ktype,
                    "total": {
                        "$sum": "$quantity"
                    }
                }
            }
        ]

        results = collection.aggregate(pipeline)
        # TODO: how do we handle errors here?
        l_results = list(results)
        if len(l_results) == 0:
            return 0
        return l_results[0]['total']

    def get_all_karma(self, workspace_id):
        collection = self.mongodb[workspace_id]
        pipeline = [
            {
                "$group": {
                    "_id": "all",
                    "total": {
                        "$sum": "$quantity"
                    }
                }
            }
        ]

        results = collection.aggregate(pipeline)
        # TODO: how do we handle errors here?
        l_results = list(results)
        if len(l_results) == 0:
            return 0
        return l_results[0]['total']

    def get_karma_gifter_count(self, workspace_id):
        collection = self.mongodb[workspace_id]
        return len(collection.distinct("gifter"))

    def get_subject_count(self, workspace_id, ktype):
        collection = self.mongodb[workspace_id]
        pipeline = [
            {"$group": {"_id": {"type": "$type", "subject": "$subject"}}},
            {"$count": "total_subjects"}
        ]

        if ktype:
            pipeline.insert(0, {"$match": {"type": ktype}})

        results = collection.aggregate(pipeline)
        r = results.next()
        return r['total_subjects']

    @staticmethod
    def karma_error_reply(eventw, message):
        slack_client.post_message(workspace=eventw['team_id'],
                                  channel=eventw['event']['channel'],
                                  parse="full",
                                  text=message)

    def karma_success_reply(self, eventw, ktype, subject_id, subject_display, quantity):
        karma = self.get_karma(eventw['team_id'], ktype, subject_id)

        badges = ""
        if ktype == "user":
            badges = "".join(self.badges.get_badges(eventw['team_id'], subject_id))

        if karma == 42:
            badges = f"{badges}:dolphin:"

        thread_ts = None
        if 'thread_ts' in eventw['event']:
            thread_ts = eventw['event']['thread_ts']

        message = {
            'channel': eventw['event']['channel'],
            'attachments': [
                {
                    'fallback': f"{subject_display} has {karma} karma. ({ktype}) {badges}",
                    'color': settings.KARMA_COLOR,
                    "text": f"{subject_display} has {karma} karma. ({ktype}) {badges}",
                    "footer": f"<@{eventw['event']['user']}> gave {quantity} karma to the {ktype} {subject_display}"
                }
            ],
            'thread_ts': thread_ts

        }

        # slack_client.post_message(channel=eventw['event']['channel'], parse="none", text=msg, thread_ts=thread_ts)
        slack_client.post_attachment(eventw['team_id'], post=message)

        return

    def karma_it(self, eventw, rate_limit_count):
        # Ignore ``` ... ```  and ` .. ` blocks
        text = re.sub(regex.code_block_re, "", eventw['event']['text'])
        text = re.sub(regex.pre_block_re, "", text)

        current_app.logger.debug(f"final text: {text}")

        subject_list = set()

        for match in regex.big_match_karma_re.finditer(text):
            rate_limit_count += 1
            if rate_limit_count > settings.KARMA_RATE_LIMIT:
                msg = f"Slow down there, partner! You only get to use karma {settings.KARMA_RATE_LIMIT} times per hour. Wait a little while and try again."  # noqa E501
                self.karma_error_reply(eventw, msg)
                return

            karma = match.group('karma')
            if karma.startswith("+"):
                quantity = len(karma) - 1
            else:
                quantity = 0 - (len(karma) - 1)

            if match.group('thing'):
                subject = match.group('thing')
                display = subject
                ktype = "thing"

            for mg in ["qthing1", "qthing2", "sqthing1", "sqthing2", "sqthing3", "sqthing4"]:
                if match.group(mg):
                    subject = match.group(mg)
                    display = f'"{match.group(mg)}"'
                    ktype = "thing"

            if match.group('user'):
                subject = match.group('user')
                display = f"<@{match.group('user')}>"
                ktype = "user"

            if match.group('channel'):
                subject = match.group('channel')
                display = f"<#{match.group('channel')}>"
                ktype = "channel"

            if match.group('group'):
                subject = match.group('group')
                display = f"<!subteam^{match.group('group')}>"
                ktype = "group"

            # Ignore the same subject being used multiple times in the same message
            if subject in subject_list:
                continue

            subject_list.add(subject)

            if ktype == "user" and eventw['event']['user'] == subject:
                if quantity > 0:
                    self.karma_error_reply(eventw, "Don't be so vain")
                else:
                    self.karma_error_reply(eventw, "Don't be so hard on yourself")
                return

            if not (ktype == "thing" and subject == u'\u03c0'):
                self.store_karma(ktype=ktype, subject=subject, quantity=quantity, gifter=eventw['event']['user'],
                                 workspace_id=eventw['team_id'])
                current_app.logger.info(
                    f"giving {subject} {quantity} karma from {eventw['event']['user']} in {eventw['team_id']}")

            self.karma_success_reply(eventw, ktype=ktype, subject_display=display, subject_id=subject,
                                     quantity=quantity)

    def cmd_karma(self, command):
        karma = self.get_karma(command['team_id'], "user", command['user_id'])
        msg = f"Your Karma is {karma}"
        if karma == 42:
            msg = f"{msg} :dolphin:"

        message = {
            'response_type': 'ephemeral',
            'text': msg
        }
        self.respond(message, command)

    def cmd_karma_help(self, command):
        message = {
            'response_type': 'ephemeral',
            'text': 'Karma Assistance',
            'attachments': [
                {
                    'color': settings.KARMA_COLOR,
                    "text": ("`karma` keeps track of Karma gifts to various things:\n"
                             " * `@user` - Users\n"
                             " * `@group` - Groups\n"
                             " * `#channel` - Channels\n"
                             " * `thing` - \"Things\"\n"
                             " * `\"things with spaces\"` - \"Things\"")
                },
                {
                    'color': settings.KARMA_COLOR,
                    "text": ("`thing ++` - Add 1 Karma to _thing_\n"
                             "`thing +++` - Add 2 Karma to _thing_ (count(+) - 1, max 5)\n"
                             "`thing --` - Remove 1 Karma to _thing_\n"
                             "`thing ---` - Remove 2 Karma to _thing_ (count(-) - 1, max 5)\n"
                             "`\"quoted thing\" ++` - Add 1 Karma to _quoted string_\n"
                             "Note: The space after the `thing` before the pluses or minuses is optional, but tends to work better")
                    # noqa E501
                },
                {
                    'color': settings.KARMA_COLOR,
                    "text": ("Available `/karma` commands:\n"
                             "`/karma` - Show your current Karma\n"
                             "`/karma help` - Show this help message\n"
                             "`/karma leave` - Ask the bot nicely to leave the current channel\n"
                             "`/karma show thing` - Show the current Karma of _thing_\n"
                             "`/karma top` - Show the top 10 subjects\n"
                             "`/karma bottom` - Show the bottom 10 subjects\n"
                             "`/karma top users` - Show the top 10 users\n"
                             "`/karma top groups` - Show the top 10 groups\n"
                             "`/karma top channels` - Show the top 10 channels\n"
                             "`/karma top things` - Show the top 10 things\n"
                             "`/karma stats` - Show some interesting statstics about Karma\n"
                             "`/karma stats thing` - Show some interesting statstics about `thing`\n")
                }
            ]
        }

        self.respond(message, command)

    def cmd_karma_show(self, command):
        # Remove the "show " from the command text
        subject = command['text'][5:]
        subject_disp = subject
        ktype = "Thing"
        karma = 0
        badges = ""

        f = True

        current_app.logger.info(f"show karma for subject: {subject}")
        match = regex.user_re.match(subject)
        if f and match:
            user_id = match.group(1)
            karma = self.get_karma(command['team_id'], "user", user_id)
            ktype = "User"
            f = False
            badges = "".join(self.badges.get_badges(command['team_id'], user_id))

        match = regex.channel_re.match(subject)
        if f and match:
            channel_id = match.group(1)
            karma = self.get_karma(command['team_id'], "channel", channel_id)
            ktype = "Channel"

        match = regex.user_group_re.match(subject)
        if f and match:
            group_id = match.group(1)
            karma = self.get_karma(command['team_id'], "group", group_id)
            ktype = "Group"

        if f:
            karma = self.get_karma(command['team_id'], "thing", subject)

        if karma == 42:
            badges = f"{badges}:dolphin:"

        thread_ts = None
        if 'event' in command and 'thread_ts' in command['event']:
            thread_ts = command['event']['thread_ts']

        message = {
            'attachments': [
                {
                    'fallback': f"{subject_disp} has {karma} karma. ({ktype}) {badges}",
                    'color': settings.KARMA_COLOR,
                    "text": f"{subject_disp} has {karma} karma. ({ktype}) {badges}"
                }
            ],
            'thread_ts': thread_ts

        }

        self.respond(message, command)

    def cmd_karma_subject_stats(self, command, subject_display):
        workspace_id = command['team_id']
        collection = self.mongodb[workspace_id]

        ktype = "thing"
        subject = subject_display

        f = True

        match = regex.user_re.match(subject_display)
        if f and match:
            subject = match.group(1)
            ktype = "user"
            f = False

        match = regex.channel_re.match(subject_display)
        if f and match:
            subject = match.group(1)
            ktype = "channel"

        match = regex.user_group_re.match(subject_display)
        if f and match:
            subject = match.group(1)
            ktype = "group"

        match = regex.quoted1_thing_re.match(subject_display)
        if f and match:
            subject = match.group("qthing1")
            ktype = "thing"

        match = regex.quoted2_thing_re.match(subject_display)
        if f and match:
            subject = match.group("qthing2")
            ktype = "thing"

        match = regex.squoted1_thing_re.match(subject_display)
        if f and match:
            subject = match.group("sqthing1")
            ktype = "thing"

        match = regex.squoted2_thing_re.match(subject_display)
        if f and match:
            subject = match.group("sqthing2")
            ktype = "thing"

        match = regex.squoted3_thing_re.match(subject_display)
        if f and match:
            subject = match.group("sqthing3")
            ktype = "thing"

        match = regex.squoted4_thing_re.match(subject_display)
        if f and match:
            subject = match.group("sqthing4")
            ktype = "thing"

        current_app.logger.info(f"show karma stats for subject: {subject} type: {ktype}")

        karma_ops = collection.find({"subject": subject, "type": ktype}).count()

        gifters = self.get_gifters(workspace_id, ktype, subject)
        karma = self.get_karma(workspace_id, ktype, subject)
        karma_avg = (karma / karma_ops) if karma_ops != 0 else 0
        top_5_gifters = gifters[:5]

        t5g_msg = ""
        for g in top_5_gifters:
            t5g_msg = f"{t5g_msg}{g[1]} <@{g[0]}>\n"

        gifts_msg = None
        if ktype == "user":
            top_5_gifts = self.get_top_karma(workspace_id, gifter=subject, direction=-1, limit=5)
            gifts_msg = {
                'title': 'Top Karma by that user',
                'value': top_5_gifts,
                'short': False
            }

        badges_msg = None
        if ktype == "user":
            badges = self.badges.get_badges(workspace_id, subject)
            gifts_msg = {
                'title': 'Badges',
                'value': " ".join(badges),
                'short': False
            }

        message = {
            'response_type': 'ephemeral',
            'attachments': [
                {
                    "fallback": f"*Interesting Karma Stats for {subject_display} (last {settings.KARMA_TTL} days):*",
                    "color": settings.KARMA_COLOR,
                    "pretext": f"Interesting Karma Stats for {subject_display} (last {settings.KARMA_TTL} days):",
                    "fields": [
                        {
                            'title': 'Type',
                            'value': ktype,
                            'short': True
                        },
                        {
                            "title": "Avg Karma Per Op",
                            "value": karma_avg,
                            "short": True
                        },
                        {
                            "title": "Karma Value",
                            "value": karma,
                            "short": True
                        },
                        {
                            "title": "Karma Operations",
                            "value": karma_ops,
                            "short": True
                        },
                        {
                            "title": "Total Gifters",
                            "value": f"{len(gifters)}",
                            "short": True
                        },
                        {
                            "title": "Top Gifters",
                            "value": t5g_msg,
                            "short": True
                        },
                        gifts_msg,
                        badges_msg

                    ]
                }
            ]
        }

        self.respond(message, command)
        return

    def get_top_karma(self, workspace_id, gifter=None, ktype=None, direction=-1, limit=10):
        collection = self.mongodb[workspace_id]

        pipeline = [
            {"$group": {"_id": {"type": "$type", "subject": "$subject"}, "total": {"$sum": "$quantity"}}},
            {"$sort": {"total": direction}},
            {"$limit": limit}
        ]

        if not gifter and not ktype:
            pipeline.insert(0, {"$match": {"$or": [
                {"type": "thing"},
                {"type": "user"},
                {"type": "channel"},
                {"type": "group"}
            ]}})
        if gifter and not ktype:
            pipeline.insert(0, {"$match": {"gifter": gifter, "$or": [
                {"type": "thing"},
                {"type": "user"},
                {"type": "channel"},
                {"type": "group"}
            ]}})
        elif ktype and not gifter:
            pipeline.insert(0, {"$match": {"type": ktype}})
        elif ktype and gifter:
            pipeline.insert(0, {"$match": {"gifter": gifter, "type": ktype}})

        r = collection.aggregate(pipeline)

        msg = ""
        for entry in r:
            if entry["_id"]["type"] == "user":
                msg = f'{msg}\n{entry["total"]}  <@{entry["_id"]["subject"]}> (user)'
            elif entry["_id"]["type"] == "channel":
                msg = f'{msg}\n{entry["total"]}  <#{entry["_id"]["subject"]}> (channel)'
            elif entry["_id"]["type"] == "thing":
                msg = f'{msg}\n{entry["total"]}  {entry["_id"]["subject"]} (thing)'
            elif entry["_id"]["type"] == "group":
                msg = f'{msg}\n{entry["total"]}  <!subteam^{entry["_id"]["subject"]}> (group)'
            else:
                msg = f'{msg}\n{entry["total"]}  {entry["_id"]["subject"]} (?)'

        return msg

    def get_gifters(self, workspace_id, ktype, subject):
        collection = self.mongodb[workspace_id]
        gifters = []
        pipeline = [
            {"$match": {"type": ktype, "subject": subject}},
            {"$group": {"_id": "$gifter", "total": {"$sum": "$quantity"}}},
            {"$sort": {"total": -1}}
        ]
        results = collection.aggregate(pipeline)

        for result in results:
            gifters.append((result['_id'], result['total']))

        return gifters

    def cmd_karma_stats(self, command):
        workspace_id = command['team_id']
        collection = self.mongodb[workspace_id]

        total_count = collection.find({"$or": [
            {"type": "thing"},
            {"type": "user"},
            {"type": "channel"},
            {"type": "group"}
        ]}).count()
        thing_count = collection.find({"type": "thing"}).count()
        user_count = collection.find({"type": "user"}).count()
        channel_count = collection.find({"type": "channel"}).count()
        group_count = collection.find({"type": "group"}).count()

        total_karma = self.get_all_karma(workspace_id)
        thing_karma = self.get_type_karma(workspace_id, "thing")
        user_karma = self.get_type_karma(workspace_id, "user")
        channel_karma = self.get_type_karma(workspace_id, "channel")
        group_karma = self.get_type_karma(workspace_id, "group")

        total_avg = (total_karma / total_count) if total_count != 0 else 0
        thing_avg = (thing_karma / thing_count) if thing_count != 0 else 0
        user_avg = (user_karma / user_count) if user_count != 0 else 0
        channel_avg = (channel_karma / channel_count) if channel_count != 0 else 0
        group_avg = (group_karma / group_count) if group_count != 0 else 0

        gifters = self.get_karma_gifter_count(workspace_id)
        subjects = self.get_subject_count(workspace_id, None)

        message = {
            'response_type': 'ephemeral',
            'attachments': [
                {
                    "fallback": f"*Interesting Karma Stats (last {settings.KARMA_TTL} days):*",
                    "color": settings.KARMA_COLOR,
                    "pretext": f"Interesting Karma Stats (last {settings.KARMA_TTL} days):",
                    "fields": [
                        {
                            "title": "All Karma",
                            "value": f"{total_count} operations for a sum of {total_karma}\n(avg {total_avg} per operation)",
                            # noqa E501
                            "short": False
                        },
                        {
                            "title": "User Karma",
                            "value": f"{user_count} operations for a sum of {user_karma}\n(avg {user_avg} per operation)",
                            # noqa E501
                            "short": False
                        },
                        {
                            "title": "Group Karma",
                            "value": f"{group_count} operations for a sum of {group_karma}\n(avg {group_avg} per operation)",
                            # noqa E501
                            "short": False
                        },
                        {
                            "title": "Channel Karma",
                            "value": f"{channel_count} operations for a sum of {channel_karma}\n(avg {channel_avg} per operation)",
                            # noqa E501
                            "short": False
                        },
                        {
                            "title": "Thing Karma",
                            "value": f"{thing_count} operations for a sum of {thing_karma}\n(avg {thing_avg} per operation)",
                            # noqa E501
                            "short": False
                        },
                        {
                            "title": "Total Gifters",
                            "value": gifters,
                            "short": True
                        },
                        {
                            "title": "Total Subjects",
                            "value": subjects,
                            "short": True
                        }
                    ]
                }
            ]
        }
        self.respond(message, command)
        return

    def cmd_karma_top(self, command, direction=-1):

        args = command['text'].split()

        header = "Top"
        if direction == 1:
            header = "Bottom"

        ktype = None
        if len(args) > 1:
            if args[1] == "users":
                ktype = "user"
                header = f"{header} User"
            elif args[1] == "channels":
                ktype = "channel"
                header = f"{header} Channel"
            elif args[1] == "groups":
                ktype = "group"
                header = f"{header} Group"
            else:
                ktype = "thing"
                header = f"{header} Thing"
        header = f"{header} Karma Standings"

        toplist = self.get_top_karma(command['team_id'], ktype=ktype, direction=direction)

        message = {
            'response_type': 'ephemeral',
            'attachments': [
                {
                    "fallback": f"*{header}:*",
                    "color": settings.KARMA_COLOR,
                    "fields": [
                        {
                            "title": header,
                            "value": toplist,
                            "short": False
                        }
                    ]
                }
            ]
        }
        self.respond(message, command)
        return

    @staticmethod
    def cmd_leave(command):
        user = command['user_id']
        channel = command['channel_id']

        result = slack_client.leave_channel(command['team_id'], channel)
        if result['ok']:
            slack_client.post_message(command['team_id'], channel, f"Left at <@{user}>'s request.", 'none')

    @staticmethod
    def blacklisted(workspace_id, user_id):
        # Maybe someday be able to blacklist specific users
        if user_id == "USLACKBOT":
            return True

        userinfo_r = slack_client.get_userinfo(workspace_id, user_id)
        if userinfo_r.status != 200:
            return False
        userinfo = userinfo_r.json
        if userinfo['user']['is_bot']:
            return True

        return False

    @staticmethod
    def respond(message, command):
        if 'response_url' in command:
            slack_client.command_reply(command['team_id'], command['response_url'], message)
        else:
            message['channel'] = command['event']['channel']
            message['response_type'] = ''
            slack_client.post_attachment(command['team_id'], message)

    def get_top_channel_members(self, command):
        channel_members = slack_client.get_all_channel_members(command['team_id'], command['channel_id'])
        current_app.logger.debug(f"channel_members: {channel_members}")

        collection = self.mongodb[command['team_id']]
        q = [{"subject": uid} for uid in channel_members]
        pipeline = [
            {"$match": {"$or": q}},
            {"$group": {"_id": {"type": "$type", "subject": "$subject"}, "total": {"$sum": "$quantity"}}},
            {"$sort": {"total": -1}},
            {"$limit": 10}
        ]
        results = collection.aggregate(pipeline)
        top_members = []
        for u in results:
            top_members.append(f"{u['total']} <@{u['_id']['subject']}>")
        message = {
            'response_type': 'ephemeral',
            'attachments': [
                {
                    "color": settings.KARMA_COLOR,
                    "fields": [
                        {
                            "title": "Top User Karma for this Channel",
                            "value": '\n'.join(top_members),
                            "short": False
                        }
                    ]
                }
            ]
        }
        self.respond(message, command)
