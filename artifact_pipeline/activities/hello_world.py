#
# Copyright (C) 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Logic for the hello-world related activities."""

from temporalio import activity


@activity.defn
async def say_hello(name: str) -> str:
    """Format the name argument into a 'Hello, %s' message.

    :param name: name to say hello to.
    :returns: a formatted message to say hello.
    """
    return f"Hello, {name}!"
