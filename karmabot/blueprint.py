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


"""
The Blueprint module for Karma
"""

import json
import time
import re

from flask import abort, current_app, g, jsonify, request, Blueprint

from karmabot.controller.karma import KarmaController
from karmabot.controller.badges import BadgesController
from karmabot import executor
from karmabot.metrics import timeit, log_metrics

health = Blueprint("health", __name__, url_prefix='/')
slack = Blueprint("slack", __name__, url_prefix='/slack_events/v1')

karma_re = re.compile(r'(\+\++|--+)(\s+|$)')


def get_karma_controller():
    """
            Get the controller from the global state, or instansiate it if needed.
    """
    if 'karma_controller' not in g:
        g.karma_controller = KarmaController()
    return g.karma_controller


def get_badges_controller():
    """
            Get the controller from the global state, or instansiate it if needed.
        """
    if 'badges_controller' not in g:
        g.badges_controller = BadgesController()
    return g.badges_controller


@health.route("/", methods=["GET"])
@health.route("/health", methods=["GET"])
def get_health():
    log_metrics("threads", None, "queue_size", executor._work_queue.qsize())
    log_metrics("threads", None, "count", len(executor._threads))
    if executor._work_queue.qsize() > (1.5 * len(executor._threads)):
        return "QUEUE FULL", 503
    return "OK", 200


@timeit('karmabot_event_requests')
@slack.route('/karmabot_dev-v1_events', methods=['POST'])
@slack.route('/karmabot-v1_events', methods=['POST'])
def slack_event():
    """
        Handle incoming Slack events.
        SLA:
         * Must respond successfully 5% of events per hour
         * Must respond within 3 seconds
    """
    eventw = request.get_json()
    eventw["rec_time"] = time.time()

    if 'token' not in eventw:
        current_app.logger.error(
            "There is no verification token in the JSON, discarding event")
        abort(401)
    if eventw['token'] != current_app.config.get('VERIFICATION_TOKEN'):
        current_app.logger.error("Wrong verification token in JSON, discarding event")
        abort(403)
    if 'challenge' in eventw:
        return jsonify({'challenge': eventw['challenge']})
    else:
        log_metrics('karmabot_events_passed', None, 'count', 1)

        if eventw['event']['type'] == "message":
            if 'subtype' in eventw['event']:
                # skip all known subtypes.  None of them are relvant to karmabot today
                return jsonify({})

            if karma_re.search(eventw['event']['text']):
                log_metrics('karmabot_events_passed', None, 'count', 1)
                eventw["rec_time"] = time.time()
                karma_controller = get_karma_controller()
                executor.submit(karma_controller.handle_event, eventw)
            else:
                current_app.logger.debug("Not match: %s" % eventw['event']['text'])
        elif eventw['event']['type'] == "app_mention":
            if not karma_re.search(eventw['event']['text']):
                # skip karma events- another event type "message" will handle it
                log_metrics('karmabot_events_passed', None, 'count', 1)
                eventw["rec_time"] = time.time()
                karma_controller = get_karma_controller()
                executor.submit(karma_controller.handle_mention, eventw)

        else:
            current_app.logger.error("Unknown event type: %s" % eventw['event']['type'])
        return jsonify({})


@timeit('karmabot_command_requests')
@slack.route('/karmabot_dev-v1_commands', methods=['POST'])
@slack.route('/karmabot-v1_commands', methods=['POST'])
def slack_command():
    """
        Handle incoming Slack commands.
    """
    command = request.form.to_dict()
    command["rec_time"] = time.time()

    if 'payload' in command:
        command = json.loads(command['payload'])

    if 'token' not in command:
        current_app.logger.error(
            "There is no verification token, discarding command")
        abort(401)
    if command['token'] != current_app.config.get('VERIFICATION_TOKEN'):
        current_app.logger.error(f"Wrong verification token {current_app.config.get('VERIFICATION_TOKEN')} {command['token']}, discarding command")  # noqa 501
        abort(403)
    else:
        log_metrics('karmabot_commands_passed', None, 'count', 1)
        current_app.logger.debug(command['command'])
        if command['command'] == '/karma':
            karma_controller = get_karma_controller()
            executor.submit(karma_controller.handle_command, command)

        elif command['command'] == '/badge':
            badges_controller = get_badges_controller()
            executor.submit(badges_controller.handle_command, command)

        else:
            current_app.logger.info(f"Ignoring unknown command {command['command']}")

        return '', 200


@timeit('karmabot_interactive_requests')
@slack.route('/karmabot_dev-v1_interactions', methods=['POST'])
@slack.route('/karmabot-v1_interactions', methods=['POST'])
def slack_interaction():
    """
        Handle incoming Slack interactions
    """
    interaction = None
    current_app.logger.error(request.form)
    if 'payload' in request.form:
        interaction = json.loads(request.form['payload'])
        interaction["rec_time"] = time.time()
    else:
        current_app.logger.error("Missing payload, ignored interaction")
        abort(401)

    if 'token' not in interaction:
        current_app.logger.error(
            "There is no verification token, discarding interaction")
        abort(401)
    if interaction['token'] != current_app.config.get('VERIFICATION_TOKEN'):
        current_app.logger.error("Wrong verification token, discarding command")
        abort(403)
    else:
        badges_controller = get_badges_controller()
        if interaction['type'] == "dialog_submission":
            if interaction['callback_id'] == 'karma-badge-create-0':
                executor.submit(badges_controller.cmd_badge_create_complete, interaction)
            elif interaction['callback_id'].startswith('karma-badge-update-'):
                executor.submit(badges_controller.cmd_badge_update_complete, interaction)
            else:
                current_app.logger.warning(f"Unknown callback_id {interaction['callback_id']}")
        elif interaction['type'] == "interactive_message":
            if interaction['callback_id'] == 'karma-badge-delete-0':
                executor.submit(badges_controller.cmd_badge_delete_complete, interaction)
            else:
                current_app.logger.warning(f"Unknown callback_id {interaction['callback_id']}")
        else:
            current_app.logger.warning(f"Unknown interaction type: {interaction['type']}")

        log_metrics('karmabot_interactions_passed', None, 'count', 1)

        return '', 200


@slack.errorhandler(Exception)
def generic_error(e):
    log_metrics('exceptions', {'name': e.__class__.__name__}, 'count', 1)
    current_app.logger.exception(f'An error occurred during a request via {e}')
    return 'An internal error occurred.', 500


@slack.errorhandler(500)
def server_error(e):
    log_metrics('exceptions', {'name': e.__class__.__name__}, 'count', 1)
    current_app.logger.exception(f'An error occurred during a request via {e}')
    return 'An internal error occurred.', 500
