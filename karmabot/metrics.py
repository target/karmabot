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

from functools import wraps
from urllib.parse import urlparse
from influxdb.line_protocol import make_lines
import time
import socket
import os

METRICS_URI = os.environ.get('METRICS_URI', 'tcp://localhost:8094')
METRICS_HOST = urlparse(METRICS_URI).hostname
METRICS_PORT = urlparse(METRICS_URI).port


class timeit(object):
    def __init__(self, measurement, tags=None, field="time_elapsed"):
        self.measurement = measurement
        self.tags = tags
        self.field = field

    def __call__(self, f):

        @wraps(f)
        def timed(*args, **kwargs):
            ts = time.time()
            result = f(*args, **kwargs)
            te = time.time()
            value = int((te - ts) * 1000)
            log_metrics(self.measurement, self.tags, self.field, value)

            return result
        return timed


def _get_connection():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((METRICS_HOST, METRICS_PORT))
    return s


def log_metrics(measurement, tags, field, value):
    json_body = {'points': [
        {
            'measurement': measurement,
            'tags': tags,
            'fields': {
                field: value
            }
        }
    ]}
    output = make_lines(json_body, None)
    s = _get_connection()
    s.send(output.encode())
    s.close()
