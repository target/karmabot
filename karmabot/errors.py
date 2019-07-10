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


from flask import Response
import json


class ErrorResponse(Exception):
    """
        Error to be raised when a product is not found.
    """
    def __init__(self, message, status_code=500):
        """
            Args:
                message (str): The error message
                status_code (int): HTTP Status Code
        """
        super(ErrorResponse, self).__init__(message)
        self.status_code = status_code
        self.message = message

    def to_response(self):
        """
            Converts error to response.

            Returns:
                (flask.Response)
        """
        body = json.dumps({
            "ok": False,
            "error": self.message
        })
        response = Response()
        response.status_code = self.status_code
        response.set_data(body)

        return response


class InvalidRequestError(ErrorResponse):
    """
        Error to be raised when an invalid request is made.
    """
    def __init__(self, message):
        """
            Args:
                message (str): Error message
        """
        super(InvalidRequestError, self).__init__(message, 400)


class WebhookNotFoundError(ErrorResponse):
    """
        Error to be raised when a webhook is not found.
    """
    def __init__(self, message):
        """
            Args:
                message (str): Error message
        """
        super(WebhookNotFoundError, self).__init__(message, 404)
