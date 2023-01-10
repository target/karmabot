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

import re

# karma
karma_re = re.compile(r'\s?(?P<karma>\+{2,6}|-{2,6})')
# foo++
thing_re = re.compile(r'(?P<thing>[^\s\u201c\u201d"\-+]+)')
# "foo bar"++
quoted1_thing_re = re.compile(r'"(?P<qthing1>[^\n"]+)"')
quoted2_thing_re = re.compile(r"'(?P<qthing2>[^\n']+)'")
# left/right single quote
squoted1_thing_re = re.compile(r'\u2018(?P<sqthing1>[^\n\u2019]+)\u2019')
# single low-9/high-reversed-9 quote
squoted2_thing_re = re.compile(r'\u201a(?P<sqthing2>[^\n\u201b]+)\u201b')
# left/right double quote
squoted3_thing_re = re.compile(r'\u201c(?P<sqthing3>[^\n\u201d]+)\u201d')
# double low-9/high-rev 9 quote
squoted4_thing_re = re.compile(r'\u201e(?P<sqthing4>[^\n\u201f]+)\u201f')
# @anna++ -> <@UABC1234>++ or <@UABC1234|anna>
user_re = re.compile(r'<@(?P<user>[A-Z_.0-9]+)(?:\|[^>]+)?>')
# #beth++ -> <#CDE2345|beth>++
channel_re = re.compile(r'<#(?P<channel>[A-Z_.0-9]+)\|(?:[^\s]+)>')
# @charming-admins -> <!subteam^CDE3456|charming-admins>
user_group_re = re.compile(r'<!subteam\^(?P<group>[:A-Z_.0-9]+)\|(?:[^\s]+)>')
# code-block
code_block_re = re.compile(r'```.+?```', flags=re.DOTALL)
# pre-format
pre_block_re = re.compile(r'`.+?`')
# :emoji:
emoji_re = re.compile(r'(?P<emoji>:[a-zA-Z_0-9]+:)')

big_match = r"(%s|%s|%s|%s|%s|%s|%s|%s|%s|%s)" % (
                    user_group_re.pattern,
                    channel_re.pattern,
                    user_re.pattern,
                    squoted1_thing_re.pattern,
                    squoted2_thing_re.pattern,
                    squoted3_thing_re.pattern,
                    squoted4_thing_re.pattern,
                    quoted1_thing_re.pattern,
                    quoted2_thing_re.pattern,
                    thing_re.pattern)

big_match_karma_re = re.compile(r"%s%s" % (big_match, karma_re.pattern), re.UNICODE)

big_match_re = re.compile(big_match, re.UNICODE)
