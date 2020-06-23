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

import os
from flask import current_app
import hvac
from datetime import datetime

USE_VAULT = os.environ.get('USE_VAULT', "False").lower() in ['true', '1', 't', 'y', 'yes']
current_app.logger.debug(f"DEBUG: USE_VAULT: ({os.environ.get('USE_VAULT')},{USE_VAULT})")
vault = None
vault_base_path = None

if USE_VAULT:
    vault = hvac.Client(url=os.environ.get('VAULT_URI'), token=os.environ.get('VAULT_TOKEN'))
    vault_base_path = os.environ.get('VAULT_BASE', "secret")

VERIFICATION_TOKEN = os.environ.get('VERIFICATION_TOKEN', '')

MONGODB = os.environ.get('MONGODB', 'mongodb://localhost:27017')
FAKE_SLACK = os.environ.get('FAKE_SLACK', "False").lower() in ['true', '1', 't', 'y', 'yes']
SLACK_EVENTS_ENDPOINT = os.environ.get("SLACK_EVENTS_ENDPOINT", "/slack_events")

# Number of "gifts" per hour (note: quantity in gifts is not considered)
KARMA_RATE_LIMIT = os.environ.get('KARMA_RATE_LIMIT', 60)

# Number of days karma is good for
KARMA_TTL = os.environ.get('KARMA_TTL', 90)

# Color to use for stuff
KARMA_COLOR = os.environ.get('KARMA_COLOR', '#af8b2d')


def get_access_token(workspace):
    if USE_VAULT:
        return _vault_get_access_token(workspace)
    else:
        return _env_get_access_token(workspace)


def get_bot_token(workspace):
    if USE_VAULT:
        return _vault_get_bot_token(workspace)
    else:
        return _env_get_bot_token(workspace)


def _env_get_access_token(workspace):
    current_app.logger.debug(f"DEBUG: Got request for {workspace} workspace (env)")
    return os.environ.get(f"ACCESS_{workspace}", None)


def _env_get_bot_token(workspace):
    current_app.logger.debug(f"DEBUG: Got request for {workspace} workspace (env)")
    return os.environ.get(f"BOT_{workspace}", None)


# vault cache
_access_token_cache = {}
_bot_token_cache = {}
_vault = None
_TTL = os.environ.get('VAULT_CACHE_TTL', 300)  # Measured in seconds


def _vault_get_access_token(workspace):
    global _access_token_cache, _TTL

    current_app.logger.debug(f"DEBUG: Got request for {workspace} workspace (vault)")
    n = datetime.now().timestamp()
    (token, ts) = _access_token_cache.get(workspace, (None, 0))
    if ts + _TTL > n:
        return token

    try:
        token_data = vault.secrets.kv.v1.read_secret(f'{vault_base_path}/access_{workspace}.txt')
        token = token_data['data']['value']
        _access_token_cache[workspace] = (token, n)

        return token
    except Exception as ex:
        current_app.logger.warning(f"Had a problem getting a token for workspace {workspace}:\n{ex}")


def _vault_get_bot_token(workspace):
    global _vault, _bot_token_cache, _TTL, vault, vault_base_path

    current_app.logger.debug(f"DEBUG: Got request for {workspace} workspace (vault)")
    n = datetime.now().timestamp()
    (token, ts) = _bot_token_cache.get(workspace, (None, 0))
    if ts + _TTL > n:
        return token

    try:
        token_data = vault.secrets.kv.v1.read_secret(f'{vault_base_path}/bot_{workspace}.txt')
        token = token_data['data']['value']
        _bot_token_cache[workspace] = (token, n)

        return token

    except Exception as ex:
        current_app.logger.warning(f"Had a problem getting a token for workspace {workspace}:\n{ex}")
