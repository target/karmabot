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
from flask import current_app
from karmabot import regex
from karmabot import settings
from karmabot.service import slack as slack_client
from pymongo import MongoClient


class BadgesController(object):

    def __init__(self):
        self.mongodb = MongoClient(current_app.config.get('MONGODB'))['karmabot']

    def handle_command(self, command):
        if not command['text']:
            return self.cmd_badge_show(command)

        args = command['text'].split()
        if args[0] == "stats":
            return self.cmd_badge_stats(command)
        if args[0] == "show":
            # /badge show @jane.doe
            # /badge show :slack:
            return self.cmd_badge_show(command)
        if args[0] == "create":
            return self.cmd_badge_create_request(command)
        if args[0] == "delete":
            return self.cmd_badge_delete_request(command)
        if args[0] == "update":
            return self.cmd_badge_update_request(command)
        if args[0] == "list":
            return self.cmd_badge_list(command)
        if regex.user_re.match(args[0]):
            # /badge @jane.doe with :slack:
            return self.cmd_badge_user(command)
        current_app.logger.info('handle_command fallthrough: didnt match any command')
        return self.cmd_badge_help(command)

    def get_badges(self, workspace_id, subject):
        collection = self.mongodb[workspace_id]
        results = collection.find({"type": "badge", "subject": subject})

        badges = []
        for r in results:
            badges.append(r['badge'])

        return badges

    def get_badge_users(self, workspace_id, badge):
        collection = self.mongodb[workspace_id]
        results = collection.find({"type": "badge", "badge": badge})

        users = []
        for r in results:
            users.append(r['subject'])

        return users

    def delete_badge(self, workspace_id, badge):
        collection = self.mongodb[workspace_id]
        collection.delete_many({
            'type': 'badge',
            'badge': badge
        })
        collection.delete_many({
            'type': 'badge_info',
            'badge': badge
        })

    def get_badge_info(self, workspace_id, badge):
        collection = self.mongodb[workspace_id]
        results = collection.find({"type": "badge_info", "badge": badge})

        for r in results:
            return r

        return None

    def can_badge(self, workspace_id, user_id, badge):
        badge = self.get_badge_info(workspace_id, badge)
        current_app.logger.debug(badge)
        if not badge:
            return False

        if user_id == badge['owner']:
            return True

        group_members = slack_client.user_group_members(workspace_id, badge['owner'])
        if not group_members['ok']:
            return False

        for user in group_members['users']:
            if user_id == user:
                return True

        return True

    def store_badge(self, workspace_id, subject, gifter, badge):
        now = datetime.datetime.utcnow()
        data = {
            'type': 'badge',
            'subject': subject,
            'badge': badge,
            'gifter': gifter,
            'date': now
        }
        collection = self.mongodb[workspace_id]
        collection.insert_one(data)

    def remove_badge(self, workspace_id, subject, badge):
        collection = self.mongodb[workspace_id]
        collection.delete_many({
            'type': 'badge',
            'badge': badge,
            'subject': subject
        })

    @staticmethod
    def cmd_badge_help(command):
        message = {
                'response_type': 'ephemeral',
                'text': 'Badge Assistance',
                'attachments': [
                    {
                        'color': settings.KARMA_COLOR,
                        "text": ("`karma` keeps track of Badges for various things\n"
                                 " - Product owners can own a badge, and award it to users\n"
                                 " - Subject Matter Experts can own a badge, too\n")
                    },
                    {
                        'color': settings.KARMA_COLOR,
                        "text": ("Available `/badge` commands:\n"
                                 "`/badge` - Show your current badges\n"
                                 "`/badge help` - Show this help message\n"
                                 "`/badge list` - List known badges\n"
                                 "`/badge show @user` - Show what badges `@user` has\n"
                                 "`/badge show :emoji:` - Show details about the badge `:emoji:`\n"
                                 "`/badge @user with :emoji:` - Give the badge :emoji: to `@user` (badge owners only)\n"
                                 "`/badge @user without :emoji:` - Take the badge :emoji: away from `@user` (badge owners only)\n"  # noqa E501
                                 "`/badge stats` - Show some interesting statstics about badges\n"
                                 "`/badge create` - Create a badge (Slack admins only)\n"
                                 "`/badge update` - Update a badge (Slack admins only)\n"
                                 "`/badge delete` - Delete a badge (Slack admins only)\n")
                    }
                ]
            }

        slack_client.command_reply(command['team_id'], command['response_url'], message)

    @staticmethod
    def cmd_badge_create_request(command):

        user_info_r = slack_client.get_userinfo(command['team_id'], command['user_id'])
        if user_info_r.status != 200:
            current_app.logger.warning(f"Got an unknown userinfo response: {user_info_r.status}")
            return

        user_info = user_info_r.json
        current_app.logger.debug(user_info)
        if not user_info['user']['is_admin']:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Only Slack admins can create badges."
                }]
            }
            slack_client.command_reply(command['team_id'], command['response_url'], message)
            return

        dialog = {
            "callback_id": "karma-badge-create-0",
            "title": "Create a badge",
            "submit_label": "Create",
            "elements": [
                {
                    "label": "Badge (emoji)",
                    "name": "badge",
                    "type": "text",
                    "placeholder": ":slack:"
                },
                {
                    "label": "Description",
                    "name": "description",
                    "type": "text",
                    "placeholder": "Designated Slack Experts"
                },
                {
                    "label": "Owner (@user or @group)",
                    "name": "owner",
                    "type": "text",
                    "placeholder": "@groupname"
                }
            ]
        }
        args = command['text'].split()
        if len(args) > 1:
            dialog['elements'][0]['value'] = args[1]
        slack_client.dialog_open(command['team_id'], command['trigger_id'], dialog)
        return

    def cmd_badge_create_complete(self, interaction):
        data = interaction['submission']
        current_app.logger.debug(f"submitted data: {interaction}")
        errors = False

        user_info_r = slack_client.get_userinfo(interaction['team']['id'], interaction['user']['id'])
        if user_info_r.status != 200:
            current_app.logger.warning(f"Got an unknown userinfo response: {user_info_r.status}")
            return

        user_info = user_info_r.json
        if not user_info['user']['is_admin']:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Only Slack admins can create badges."
                }]
            }
            slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)
            return
        current_app.logger.info("user is an admin")
        badge_info = self.get_badge_info(interaction['team']['id'], data['badge'])
        if badge_info:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": f"The badge {data['badge']} already exists."
                }]
            }
            slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)
            errors = True

        current_app.logger.info("badge is new")
        if not regex.emoji_re.match(data['badge']):
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "The badge must be an emoji."
                }]
            }
            slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)
            errors = True

        current_app.logger.info("Badge is an emoji")
        if data['owner'][0] == '@':
            data['owner'] = data['owner'][1:]

        user = slack_client.lookup_usergroup(interaction['team']['id'], data['owner'])
        owner = None
        if user:
            owner = user['id']
        else:
            user = slack_client.lookup_user(interaction['team']['id'], data['owner'])
            if user:
                owner = user['id']
            else:
                message = {
                    "response_type": "ephemeral",
                    "attachments": [{
                        "color": settings.KARMA_COLOR,
                        "text": "Please select a User or User Group only."
                    }]
                }
                slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)
                errors = True

        if errors:
            return

        now = datetime.datetime.utcnow()
        data = {
            'type': 'badge_info',
            'badge': data['badge'],
            'owner': owner,
            'owner_display': data['owner'],
            'description': data['description'],
            'date': now
        }
        collection = self.mongodb[interaction['team']['id']]
        collection.insert_one(data)

        current_app.logger.debug("data[owner] '{owner}'")
        owner_escaped = f"<!subteam^{owner}>"
        if data['owner'][0] != "S":
            owner_escaped = f"<@{owner}>"

        message = {
            'response_type': 'ephemeral',
            'text': 'Badge created',
            'attachments': [
                {
                    "color": settings.KARMA_COLOR,
                    "footer": f"Badge created <!date^{int(now.timestamp())}^{{date_pretty}}|{now}>",
                    "fields": [
                            {
                                "title": "Badge",
                                "value": data['badge'],
                                "short": True
                            },
                            {
                                "title": "Owner",
                                "value": owner_escaped,
                                "short": True
                            },
                            {
                                "title": "Description",
                                "value": data['description'],
                                "short": False
                            }
                    ]
                }
            ]
        }

        slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)

    def cmd_badge_delete_request(self, command):

        user_info_r = slack_client.get_userinfo(command['team_id'], command['user_id'])
        if user_info_r.status != 200:
            current_app.logger.warning(f"Got an unknown userinfo response: {user_info_r.status}")
            return

        user_info = user_info_r.json
        current_app.logger.debug(user_info)
        if not user_info['user']['is_admin']:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Only Slack admins can delete badges."
                }]
            }
            slack_client.command_reply(command['team_id'], command['response_url'], message)
            return

        args = command['text'].split()
        if len(args) != 2:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Usage: `/badge delete :badgename:`"
                }]
            }
            slack_client.command_reply(command['team_id'], command['response_url'], message)
            return

        badge_info = self.get_badge_info(workspace_id=command['team_id'], badge=args[1])
        if not badge_info:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": f"The badge {args[1]} is already deleted."
                }]
            }
            slack_client.command_reply(command['team_id'], command['response_url'], message)
            return

        message = {
            "text": f"Are you sure you want to delete the badge {args[1]}?",
            "color": settings.KARMA_COLOR,
            "attachments": [
                {
                    "text": f"Deleting cannot be undone, and will remove the badge {args[1]} from all users that have it.",  # noqa E501
                    "fallback": "You are unable to choose a game",
                    "callback_id": "karma-badge-delete-0",
                    "color": settings.KARMA_COLOR,
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "delete",
                            "text": "Yes",
                            "type": "button",
                            "style": "danger",
                            "value": args[1],
                            "confirm": {
                                "title": "Are you sure?",
                                "text": f"Deleting cannot be undone, and will remove the badge {args[1]} from all users that have it.",  # noqa E501
                                "ok_text": "Yes",
                                "dismiss_text": "No"
                            }
                        },
                        {
                            "name": "delete",
                            "text": "No",
                            "type": "button",
                            "value": "no"
                        }
                    ]
                }
            ]
        }
        slack_client.command_reply(command['team_id'], command['response_url'], message)
        return

    @staticmethod
    def cmd_badge_delete_complete(self, interaction):

        user_info_r = slack_client.get_userinfo(interaction['team']['id'], interaction['user']['id'])
        if user_info_r.status != 200:
            current_app.logger.warning(f"Got an unknown userinfo response: {user_info_r.status}")
            return

        user_info = user_info_r.json
        if not user_info['user']['is_admin']:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Only Slack admins can create badges."
                }]
            }
            slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)
            return

        actions = interaction['actions']
        for action in actions:
            if action['name'] == 'delete':
                badge = action['value']
                if badge == 'no':
                    return

                self.delete_badge(interaction['team']['id'], badge)

                message = {
                    "response_type": "ephemeral",
                    "attachments": [{
                        "color": settings.KARMA_COLOR,
                        "text": f"Badge {badge} deleted."
                    }]
                }
                slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)

        return

    def cmd_badge_update_request(self, command):
        user_info_r = slack_client.get_userinfo(command['team_id'], command['user_id'])
        if user_info_r.status != 200:
            current_app.logger.warning(f"Got an unknown userinfo response: {user_info_r.status}")
            return

        user_info = user_info_r.json
        if not user_info['user']['is_admin']:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Only Slack admins can create badges."
                }]
            }
            slack_client.command_reply(command['team_id'], command['response_url'], message)
            return

        errors = False
        args = command['text'].split(' ')
        current_app.logger.debug(args)
        m_emoji = regex.emoji_re.search(args[1])
        if not m_emoji:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Not a badge."
                }]
            }
            slack_client.command_reply(command['team_id'], command['response_url'], message)
            errors = True

        badge_info = self.get_badge_info(command['team_id'], m_emoji.group('emoji'))

        if not badge_info:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Not a badge."
                }]
            }
            slack_client.command_reply(command['team_id'], command['response_url'], message)
            errors = True

        if errors:
            current_app.logger.info("found errors")
            return

        dialog = {
            "callback_id": f"karma-badge-update-{badge_info['badge']}",
            "title": f"Update badge {badge_info['badge'][:12]}",
            "submit_label": "Update",
            "elements": [
                {
                    "label": "Description",
                    "name": "description",
                    "type": "text",
                    "placeholder": "Designated Slack Experts",
                    "value": badge_info['description']
                },
                {
                    "label": "Owner (@user or @group)",
                    "name": "owner",
                    "type": "text",
                    "placeholder": "@groupname",
                    "value": f"@{badge_info['owner_display']}"
                }
            ]
        }
        current_app.logger.debug(dialog)
        current_app.logger.debug(slack_client.dialog_open(command['team_id'], command['trigger_id'], dialog))
        return

    def cmd_badge_update_complete(self, interaction):
        data = interaction['submission']
        current_app.logger.debug("submitted data:", interaction)
        errors = False

        user_info_r = slack_client.get_userinfo(interaction['team']['id'], interaction['user']['id'])
        if user_info_r.status != 200:
            current_app.logger.warning(f"Got an unknown userinfo response: {user_info_r.status}")
            return

        user_info = user_info_r.json
        if not user_info['user']['is_admin']:
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Only Slack admins can create badges."
                }]
            }
            current_app.logger.debug(slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message))  # noqa 501
            return

        badge = interaction['callback_id'].replace('karma-badge-update-', '')
        badge_info = self.get_badge_info(interaction['team']['id'], badge)
        if not badge_info:
            current_app.logger.debug(f"callback_id {interaction['callback_id']}")
            message = {
                "response_type": "ephemeral",
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    "text": "Unknown badge"
                }]
            }
            slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)
            errors = True

        if data['owner'][0] == '@':
            data['owner'] = data['owner'][1:]

        user = slack_client.lookup_usergroup(interaction['team']['id'], data['owner'])
        owner = None
        if user:
            owner = user['id']
        else:
            user = slack_client.lookup_user(interaction['team']['id'], data['owner'])
            if user:
                owner = user['id']
            else:
                message = {
                    "response_type": "ephemeral",
                    "attachments": [{
                        "color": settings.KARMA_COLOR,
                        "text": "Please select a User or User Group only."
                    }]
                }
                slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)
                errors = True

        if errors:
            return

        now = datetime.datetime.utcnow()
        data = {
            'type': 'badge_info',
            'badge': badge,
            'owner': owner,
            'owner_display': data['owner'],
            'description': data['description'],
            'date': now
        }
        collection = self.mongodb[interaction['team']['id']]
        collection.replace_one({'type': 'badge_info', 'badge': badge}, data)

        owner_escaped = f"<!subgroup^{owner}>"
        if owner[0] != "S":
            owner_escaped = f"<@{data['owner']}>"

        badge_users = self.get_badge_users(interaction['team']['id'], badge)
        badge_user_list = ""
        for user in badge_users:
            badge_user_list = f"{badge_user_list}<@{user}>\n"

        message = {
            'response_type': 'ephemeral',
            'text': 'Badge updated',
            'attachments': [
                {
                    "footer": f"Badge created <!date^{int(badge_info['date'].timestamp())}^{{date_pretty}}|{badge_info['date']}>",  # noqa 501
                    "color": settings.KARMA_COLOR,
                    "fields": [
                            {
                                "title": "Badge",
                                "value": badge_info['badge'],
                                "short": True
                            },
                            {
                                "title": "Owner",
                                "value": owner_escaped,
                                "short": True
                            },
                            {
                                "title": "Description",
                                "value": data['description'],
                                "short": False
                            },
                            {
                                "title": "Badge Holders",
                                "value": badge_user_list,
                                "short": False
                            }
                    ]
                }
            ]
        }

        slack_client.command_reply(interaction['team']['id'], interaction['response_url'], message)

    def cmd_badge_list(self, command):
        collection = self.mongodb[command['team_id']]
        results = collection.find({"type": "badge_info"})

        badges = []
        for r in results:
            badges.append(r['badge'])

        message = {
            'response_type': 'ephemeral',
            "attachments": [{
                "color": settings.KARMA_COLOR,
                'text': f"Available Badges:\n{ ' '.join(badges)}"
            }]
        }

        slack_client.command_reply(command['team_id'], command['response_url'], message)
        return

    def cmd_badge_show(self, command):
        # /badge show @jane.doe
        # /badge show :emoji:
        # /badge show
        # /badge
        if command['text'] == "" or command['text'] == "show":
            badges = self.get_badges(command['team_id'], command['user_id'])

            message = {
                'response_type': 'ephemeral',
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    'text': f"You have these badges\n{' '.join(badges)}"
                }]
            }

            slack_client.command_reply(command['team_id'], command['response_url'], message)
            return

        args = command['text'].split(' ')
        if len(args) < 2:
            return self.cmd_badge_help(command)

        m_user = regex.user_re.search(args[1])
        m_emoji = regex.emoji_re.search(args[1])
        current_app.logger.debug(f"matches: {m_user} {m_emoji}")
        if m_user:
            user_id = m_user.group('user')
            badges = self.get_badges(command['team_id'], user_id)

            message = {
                'response_type': 'ephemeral',
                "attachments": [{
                    "color": settings.KARMA_COLOR,
                    'text': f"<@{user_id}> has these badges\n{ ' '.join(badges)}"
                }]
            }

            slack_client.command_reply(command['team_id'], command['response_url'], message)

        elif m_emoji:
            badge_info = self.get_badge_info(command['team_id'], m_emoji.group('emoji'))
            badge_users = self.get_badge_users(command['team_id'], m_emoji.group('emoji'))
            badge_owner = f"<@{badge_info['owner']}>"
            if badge_info['owner'][0] == 'S':
                badge_owner = f"<!subteam^{badge_info['owner']}>"
            badge_user_list = ""
            for user in badge_users:
                badge_user_list = f"{badge_user_list}<@{user}>\n"

            message = {
                'response_type': 'ephemeral',
                'channel': command['channel_id'],
                'attachments': [
                    {
                        "color": settings.KARMA_COLOR,
                        "footer": f"Badge created <!date^{int(badge_info['date'].timestamp())}^{{date_pretty}}|{badge_info['date']}>",  # noqa 501
                        "fields": [
                                {
                                    "title": "Badge",
                                    "value": badge_info['badge'],
                                    "short": True
                                },
                                {
                                    "title": "Owner",
                                    "value": badge_owner,
                                    "short": True
                                },
                                {
                                    "title": "Description",
                                    "value": badge_info['description'],
                                    "short": False
                                },
                                {
                                    "title": "Badge Holders",
                                    "value": badge_user_list,
                                    "short": False
                                }
                        ]
                    }
                ]
            }
            slack_client.command_reply(command['team_id'], command['response_url'], message)

        else:
            return self.cmd_badge_help(command)

        return

    def get_top_badges(self, workspace_id, limit):
        collection = self.mongodb[workspace_id]

        pipeline = [
            {"$match": {"type": "badge"}},
            {"$group": {"_id": "$badge", "count": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$limit": limit}
        ]
        r = collection.aggregate(pipeline)
        msg = ""
        for entry in r:
            msg = f'{msg}\n{entry["_id"]}  {entry["count"]}'
        return msg

    def cmd_badge_stats(self, command):
        workspace_id = command['team_id']
        collection = self.mongodb[workspace_id]

        badge_info_count = collection.find({"type": "badge_info"}).count()
        badge_count = collection.find({"type": "badge"}).count()
        top_badges = self.get_top_badges(command['team_id'], 5)
        message = {
            'response_type': 'ephemeral',
            'attachments': [
                {
                    "pretext": "Interesting Badge Statistics",
                    "fallback": "Interesting Badge Statistics",
                    "color": settings.KARMA_COLOR,
                    "fields": [
                            {
                                "title": "Badges",
                                "value": badge_info_count,
                                "short": True
                            },
                            {
                                "title": "Badges Awarded",
                                "value": badge_count,
                                "short": True
                            },
                            {
                                "title": "Most Awarded Badges",
                                "value": top_badges,
                                "short": False
                            }
                    ]
                }
            ]
        }

        slack_client.command_reply(command['team_id'], command['response_url'], message)

        return

    def cmd_badge_user(self, command):
        # /badge @jane.doe with :emoji:
        # /badge @jane.doe without :emoji:
        args = command['text'].split(' ')
        if len(args) != 3:
            current_app.logger.info(f"Got {len(args)} args: {args}")
            return self.cmd_badge_help(command)

        m = regex.user_re.search(args[0])
        if not m:
            current_app.logger.info('Did not match user_re')
            return self.cmd_badge_help(command)

        user_id = m.group('user')
        badge = args[2]

        if args[1] == "with":
            has_badges = self.get_badges(command['team_id'], user_id)
            if badge in has_badges:
                self.badge_error_reply(command, f"<@{user_id}> already has the {badge} badge!")
                return

            if self.can_badge(command['team_id'], command['user_id'], badge):
                self.store_badge(command['team_id'], user_id, command['user_id'], badge)
                self.badge_success_reply(command, command['user_id'], user_id, badge)
            else:
                self.badge_error_reply(command, f"You are not permitted to give the badge {badge} to users.")
        elif args[1] == "without":
            has_badges = self.get_badges(command['team_id'], user_id)
            if badge not in has_badges:
                self.badge_error_reply(command, f"<@{user_id}> does not have the {badge} badge!")
                return

            if self.can_badge(command['team_id'], command['user_id'], badge):
                self.remove_badge(command['team_id'], user_id, badge)
                self.badge_success_remove_reply(command, command['user_id'], user_id, badge)
            else:
                self.badge_error_reply(command, f"You are not permitted to take away the badge {badge} from users.")
        return

    @staticmethod
    def badge_error_reply(command, message):
        msg = {
                'response_type': 'ephemeral',
                "color": settings.KARMA_COLOR,
                'channel': command['channel_id'],
                'attachments': [
                    {
                        'fallback': message,
                        'color': settings.KARMA_COLOR,
                        "text": message
                    }
                ]

        }
        slack_client.command_reply(command['team_id'], command['response_url'], msg)

    @staticmethod
    def badge_success_reply(command, gifter, subject, badge):
        message = {
                'response_type': 'ephemeral',
                'channel': command['channel_id'],
                'attachments': [
                    {
                        'fallback': f"<@{gifter}> gave the {badge} badge to <@{subject}>",
                        'color': settings.KARMA_COLOR,
                        "text": f"<@{gifter}> gave the {badge} badge to <@{subject}>"
                    }
                ]

        }
        slack_client.command_reply(command['team_id'], command['response_url'], message)

        dim_channel = slack_client.get_direct_im_channel(command['team_id'], user_id=subject)
        if dim_channel['ok']:
            message = {
                    'as_user': False,
                    'channel': dim_channel['channel']['id'],
                    'attachments': [
                        {
                            'fallback': f"<@{gifter}> gave you the badge {badge} - Congrats!",
                            'color': settings.KARMA_COLOR,
                            "text": f"<@{gifter}> gave you the badge {badge} - Congrats!"
                        }
                    ]

            }

            slack_client.post_attachment(command['team_id'], post=message)
        else:
            current_app.logger.error(f"Unable to open Direct IM: {dim_channel}")

        return

    @staticmethod
    def badge_success_remove_reply(command, gifter, subject, badge):
        message = {
                'response_type': 'ephemeral',
                'channel': command['channel_id'],
                'attachments': [
                    {
                        'fallback': f"<@{gifter}> took the {badge} badge from <@{subject}>",
                        'color': settings.KARMA_COLOR,
                        "text": f"<@{gifter}> took the {badge} badge from <@{subject}>"
                    }
                ]

        }
        slack_client.command_reply(command['team_id'], command['response_url'], message)

        dim_channel = slack_client.get_direct_im_channel(command['team_id'], user_id=subject)
        if dim_channel['ok']:
            message = {
                    'as_user': False,
                    'channel': dim_channel['channel']['id'],
                    'attachments': [
                        {
                            'fallback': f"<@{gifter}> took away your badge {badge}",
                            'color': settings.KARMA_COLOR,
                            "text": f"<@{gifter}> took away your badge {badge}"
                        }
                    ]

            }

            slack_client.post_attachment(command['team_id'], post=message)
        else:
            current_app.logger.error(f"Unable to open Direct IM: {dim_channel}")

        return
