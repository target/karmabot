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

import json
import urlfetch
import karmabot
from flask import current_app
from karmabot import settings


_access_token_cache = {}
_bot_token_cache = {}
_vault = None
_TTL = 300  # Measured in seconds


def post_message(workspace, channel, text, parse="full", thread_ts=None):
    json_post = {
        "channel": channel,
        "text": text,
        "parse": parse,
        "thread_ts": thread_ts
    }
    return post_attachment(workspace, json_post)


def get_userinfo(workspace, user_id):
    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None

    if current_app.config.get('FAKE_SLACK'):
        return json.loads('''{
                            "ok": true,
                            "user": {
                                "id": "W012A3CDE",
                                "team_id": "T012AB3C4",
                                "name": "spengler",
                                "deleted": false,
                                "color": "9f69e7",
                                "real_name": "Egon Spengler",
                                "tz": "America/Los_Angeles",
                                "tz_label": "Pacific Daylight Time",
                                "tz_offset": -25200,
                                "profile": {
                                    "avatar_hash": "ge3b51ca72de",
                                    "status_text": "Print is dead",
                                    "status_emoji": ":books:",
                                    "real_name": "Egon Spengler",
                                    "display_name": "spengler",
                                    "real_name_normalized": "Egon Spengler",
                                    "display_name_normalized": "spengler",
                                    "email": "spengler@ghostbusters.example.com",
                                    "image_24": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                    "image_32": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                    "image_48": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                    "image_72": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                    "image_192": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                    "image_512": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                    "team": "T012AB3C4"
                                },
                                "is_admin": true,
                                "is_owner": false,
                                "is_primary_owner": false,
                                "is_restricted": false,
                                "is_ultra_restricted": false,
                                "is_bot": false,
                                "updated": 1502138686,
                                "is_app_user": false,
                                "has_2fa": false
                            }
                        }''')

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8'
    }
    result = urlfetch.get(url="https://slack.com/api/users.info?user=%s&token=%s" % (user_id, token),
                          headers=headers)
    return result


def command_reply(workspace, url, message):
    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None
    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': 'Bearer %s' % token
    }
    if current_app.config.get('FAKE_SLACK'):
        current_app.logger.info(url)
        current_app.logger.info(str(message))
        return '{"ok": true}'

    result = urlfetch.post(url=url,
                           data=json.dumps(message),
                           headers=headers)
    return result


def post_attachment(workspace, post):
    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None
    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': 'Bearer %s' % token
    }

    if current_app.config.get('FAKE_SLACK'):
        current_app.logger.info(str(post))
        return '{"ok": true}'

    result = urlfetch.post(url="https://slack.com/api/chat.postMessage",
                           data=json.dumps(post),
                           headers=headers)
    return result


def dialog_open(workspace, trigger_id, dialog):
    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }

    json_post = {
        'trigger_id': trigger_id,
        'dialog': dialog
    }

    if current_app.config.get('FAKE_SLACK'):
        current_app.logger.info(str(json_post))
        return json.loads('''{"ok": true}''')

    result = urlfetch.post(url="https://slack.com/api/dialog.open",
                           data=json.dumps(json_post),
                           headers=headers)
    current_app.logger.debug(result.content)
    return json.loads(result.content)


def auth_test(token):

    json_post = {
        'token': token
    }

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }

    if current_app.config.get('FAKE_SLACK'):
        current_app.logger.info(str(json_post))
        return json.loads('''{
                    "ok": true,
                    "url": "https://subarachnoid.slack.com/",
                    "team": "Subarachnoid Workspace",
                    "user": "grace",
                    "team_id": "T12345678",
                    "user_id": "W12345678"
                }''')

    result = urlfetch.post(url="https://slack.com/api/auth.test",
                           data=json.dumps(json_post),
                           headers=headers)
    return json.loads(result.content)


def get_channelinfo(workspace, channel_id):
    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }

    if current_app.config.get('FAKE_SLACK'):
        return json.loads('''
                          {
                            "ok": true,
                            "channel": {
                                "id": "C1H9RESGL",
                                "name": "busting",
                                "is_channel": true,
                                "created": 1466025154,
                                "creator": "U0G9QF9C6",
                                "is_archived": false,
                                "is_general": false,
                                "name_normalized": "busting",
                                "is_shared": false,
                                "is_org_shared": false,
                                "is_member": true,
                                "is_private": false,
                                "is_mpim": false,
                                "last_read": "1503435939.000101",
                                "latest": {
                                    "text": "Containment unit is 98% full",
                                    "username": "ecto1138",
                                    "bot_id": "B19LU7CSY",
                                    "attachments": [
                                        {
                                            "text": "Don't get too attached",
                                            "id": 1,
                                            "fallback": "This is an attachment fallback"
                                        }
                                    ],
                                    "type": "message",
                                    "subtype": "bot_message",
                                    "ts": "1503435956.000247"
                                },
                                "unread_count": 1,
                                "unread_count_display": 1,
                                "members": [
                                    "U0G9QF9C6",
                                    "U1QNSQB9U"
                                ],
                                "topic": {
                                    "value": "Spiritual containment strategies",
                                    "creator": "U0G9QF9C6",
                                    "last_set": 1503435128
                                },
                                "purpose": {
                                    "value": "Discuss busting ghosts",
                                    "creator": "U0G9QF9C6",
                                    "last_set": 1503435128
                                },
                                "previous_names": [
                                    "dusting"
                                ]
                            }
                        }''')

    result = urlfetch.get(url="https://slack.com/api/channels.info?channel=%s" % channel_id,
                          headers=headers)
    return json.loads(result.content)


def get_usergroupinfo(workspace, usergroup_id):
    usergroups = get_usergroups(workspace)
    for usergroup in usergroups:
        if usergroup['id'] == usergroup_id:
            return usergroup
    return None


def leave_channel(workspace, channel_id):
    if current_app.config.get('FAKE_SLACK'):
        return json.loads('''{ "ok": true }''')

    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None
    myself = auth_test(token)
    user_id = myself['user_id']

    token = settings.get_access_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None

    json_post = {
        'channel': channel_id,
        'user': user_id
    }

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }

    result = urlfetch.post(url="https://slack.com/api/channels.kick",
                           data=json.dumps(json_post),
                           headers=headers)
    current_app.logger.debug(result.content)
    return json.loads(result.content)


def get_direct_im_channel(workspace, user_id):
    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None

    json_post = {
        'user': user_id,
        'return_im': True
    }

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }

    if current_app.config.get('FAKE_SLACK'):
        return json.loads('''{
                            "ok": true,
                            "channel": {
                                "id": "D947RLWRX"
                            }
                          }''')

    result = urlfetch.post(url="https://slack.com/api/im.open",
                           data=json.dumps(json_post),
                           headers=headers)
    current_app.logger.debug(result.content)
    return json.loads(result.content)


def user_group_members(workspace, user_group):
    token = settings.get_access_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }

    if current_app.config.get('FAKE_SLACK'):
        return json.loads('''{
                            "ok": true,
                            "users": [
                                "U060R4BJ4",
                                "W123A4BC5"
                            ]
                        }''')
    result = urlfetch.post(url=f"https://slack.com/api/usergroups.users.list?usergroup={user_group}&include_disabled=false",  # noqa 501
                           headers=headers)
    current_app.logger.debug(result.content)
    return json.loads(result.content)


def lookup_user(workspace, displayname):
    users = get_all_users(workspace)
    current_app.logger.debug(users)
    for user in users:
        if user['name'] == displayname:
            return user
    return None


def get_all_users(workspace):
    next_cursor = ""
    r = get_users(workspace, next_cursor)

    if not r['ok']:
        return []

    users = []
    users.extend(r['members'])
    next_cursor = r['response_metadata']['next_cursor']
    while next_cursor:
        r = get_users(workspace, next_cursor)
        if not r['ok']:
            return []
        users.extend(r['members'])
        next_cursor = r['response_metadata']['next_cursor']

    return users


def get_users(workspace, cursor):
    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }

    if current_app.config.get('FAKE_SLACK'):
        return json.loads('''{
                                "ok": true,
                                "members": [
                                    {
                                        "id": "W012A3CDE",
                                        "team_id": "T012AB3C4",
                                        "name": "spengler",
                                        "deleted": false,
                                        "color": "9f69e7",
                                        "real_name": "spengler",
                                        "tz": "America/Los_Angeles",
                                        "tz_label": "Pacific Daylight Time",
                                        "tz_offset": -25200,
                                        "profile": {
                                            "avatar_hash": "ge3b51ca72de",
                                            "status_text": "Print is dead",
                                            "status_emoji": ":books:",
                                            "real_name": "Egon Spengler",
                                            "display_name": "spengler",
                                            "real_name_normalized": "Egon Spengler",
                                            "display_name_normalized": "spengler",
                                            "email": "spengler@ghostbusters.example.com",
                                            "image_24": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                            "image_32": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                            "image_48": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                            "image_72": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                            "image_192": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                            "image_512": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
                                            "team": "T012AB3C4"
                                        },
                                        "is_admin": true,
                                        "is_owner": false,
                                        "is_primary_owner": false,
                                        "is_restricted": false,
                                        "is_ultra_restricted": false,
                                        "is_bot": false,
                                        "updated": 1502138686,
                                        "is_app_user": false,
                                        "has_2fa": false
                                    },
                                    {
                                        "id": "W07QCRPA4",
                                        "team_id": "T0G9PQBBK",
                                        "name": "glinda",
                                        "deleted": false,
                                        "color": "9f69e7",
                                        "real_name": "Glinda Southgood",
                                        "tz": "America/Los_Angeles",
                                        "tz_label": "Pacific Daylight Time",
                                        "tz_offset": -25200,
                                        "profile": {
                                            "avatar_hash": "8fbdd10b41c6",
                                            "image_24": "https://a.slack-edge.com...png",
                                            "image_32": "https://a.slack-edge.com...png",
                                            "image_48": "https://a.slack-edge.com...png",
                                            "image_72": "https://a.slack-edge.com...png",
                                            "image_192": "https://a.slack-edge.com...png",
                                            "image_512": "https://a.slack-edge.com...png",
                                            "image_1024": "https://a.slack-edge.com...png",
                                            "image_original": "https://a.slack-edge.com...png",
                                            "first_name": "Glinda",
                                            "last_name": "Southgood",
                                            "title": "Glinda the Good",
                                            "phone": "",
                                            "skype": "",
                                            "real_name": "Glinda Southgood",
                                            "real_name_normalized": "Glinda Southgood",
                                            "display_name": "Glinda the Fairly Good",
                                            "display_name_normalized": "Glinda the Fairly Good",
                                            "email": "glenda@south.oz.coven"
                                        },
                                        "is_admin": true,
                                        "is_owner": false,
                                        "is_primary_owner": false,
                                        "is_restricted": false,
                                        "is_ultra_restricted": false,
                                        "is_bot": false,
                                        "updated": 1480527098,
                                        "has_2fa": false
                                    }
                                ],
                                "cache_ts": 1498777272,
                                "response_metadata": {
                                    "next_cursor": "dXNlcjpVMEc5V0ZYTlo="
                                }
                            }''')
    result = urlfetch.post(url="https://slack.com/api/users.list?cursor=%s&limit=1000" % cursor,
                           headers=headers)

    # self.log.debug(result.content)
    return json.loads(result.content)


def lookup_usergroup(workspace, displayname):
    groups = get_usergroups(workspace)
    for group in groups:
        if group['handle'] == displayname:
            return group
    return None


def get_usergroups(workspace):
    token = settings.get_access_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None

    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }

    if current_app.config.get('FAKE_SLACK'):
        return json.loads('''{
                                "ok": true,
                                "usergroups": [
                                    {
                                        "id": "S0614TZR7",
                                        "team_id": "T060RNRCH",
                                        "is_usergroup": true,
                                        "name": "Team Admins",
                                        "description": "A group of all Administrators on your team.",
                                        "handle": "admins",
                                        "is_external": false,
                                        "date_create": 1446598059,
                                        "date_update": 1446670362,
                                        "date_delete": 0,
                                        "auto_type": "admin",
                                        "created_by": "USLACKBOT",
                                        "updated_by": "U060RNRCZ",
                                        "deleted_by": null,
                                        "prefs": {
                                            "channels": [],
                                            "groups": []
                                        },
                                        "user_count": "2"
                                    },
                                    {
                                        "id": "S06158AV7",
                                        "team_id": "T060RNRCH",
                                        "is_usergroup": true,
                                        "name": "Team Owners",
                                        "description": "A group of all Owners on your team.",
                                        "handle": "owners",
                                        "is_external": false,
                                        "date_create": 1446678371,
                                        "date_update": 1446678371,
                                        "date_delete": 0,
                                        "auto_type": "owner",
                                        "created_by": "USLACKBOT",
                                        "updated_by": "USLACKBOT",
                                        "deleted_by": null,
                                        "prefs": {
                                            "channels": [],
                                            "groups": []
                                        },
                                        "user_count": "1"
                                    },
                                    {
                                        "id": "S0615G0KT",
                                        "team_id": "T060RNRCH",
                                        "is_usergroup": true,
                                        "name": "Marketing Team",
                                        "description": "Marketing gurus, PR experts and product advocates.",
                                        "handle": "marketing-team",
                                        "is_external": false,
                                        "date_create": 1446746793,
                                        "date_update": 1446747767,
                                        "date_delete": 1446748865,
                                        "auto_type": null,
                                        "created_by": "U060RNRCZ",
                                        "updated_by": "U060RNRCZ",
                                        "deleted_by": null,
                                        "prefs": {
                                            "channels": [],
                                            "groups": []
                                        },
                                        "user_count": "0"
                                    }
                                ]
                            }''')
    result = urlfetch.post(url="https://slack.com/api/usergroups.list?include_count=false&include_users=false",
                           headers=headers)

    current_app.logger.debug(result.content)
    response = json.loads(result.content)
    if response['ok']:
        return response['usergroups']
    return []


def get_channel_members(workspace, channel, cursor):
    token = settings.get_bot_token(workspace)
    if not token:
        current_app.logger.warning(f"Requested token for workspace {workspace} but found none")
        return None
    headers = {
        'User-Agent': f'karmabot/{karmabot.__version__}',
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f"Bearer {token}"
    }
    result = urlfetch.post(
        url="https://slack.com/api/conversations.members?channel=%s&cursor=%s&limit=1000" % (channel, cursor),
        headers=headers
    )
    return result.json


def get_all_channel_members(workspace, channel):
    next_cursor = ""
    r = get_channel_members(workspace, channel, next_cursor)

    if not r['ok']:
        return []

    members = []
    members.extend(r['members'])
    next_cursor = r['response_metadata']['next_cursor']
    while next_cursor:
        r = get_channel_members(channel, next_cursor)
        if not r['ok']:
            return []
        members.extend(r['members'])
        next_cursor = r['response_metadata']['next_cursor']
        get_channel_members(channel, next_cursor)

    current_app.logger.debug(f"members: {members}")
    return members
