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
  Flask App definition for Karmabot
"""
from flask import Flask
from flask_executor import Executor

__version__ = '0.1.0'
__author__ = 'Jay Kline <jay.kline@target.com>'
__copyright__ = "Copyright (C) 2009 Target Brands, Inc."
__license__ = "Apache License, Version 2.0"

executor = Executor()

from karmabot.errors import ErrorResponse, InvalidRequestError  # noqa: E402
from karmabot.blueprint import health  # noqa: E402
from karmabot.blueprint import slack  # noqa: E402


def create_app():
    """Generate the Flask app"""

    app = Flask(__name__)

    # Gather config
    app.config.from_object('karmabot.settings')

    # Register the components
    app.register_blueprint(slack)
    app.register_blueprint(health)

    app.logger.setLevel(app.config.get("log_level", "DEBUG"))

    app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True
    executor.init_app(app)

    @app.errorhandler(ErrorResponse)
    @app.errorhandler(InvalidRequestError)
    def error_handler(error):
        """Handle any exceptions gracefully"""

        app.logger.warn(f"Got an exception: {error}")
        app.logger.exception(error)
        return error.to_response()

    return app
