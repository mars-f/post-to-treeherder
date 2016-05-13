# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os

here = os.path.dirname(os.path.abspath(__file__))

config = {
    'version': '2.0.0',
    'treeherder': {
        'group_name': 'MozReview',
        'group_symbol': 'MR',
        'job_name': 'reviewboard',
        'job_symbol': 'rb',
        'artifacts': {
            'report.json': os.path.join(here, 'build', 'upload', 'report.json'),
            'results.xml': os.path.join(here, 'build', 'upload', 'results.xml')
        },
    },
    'logs': {
        'results': os.path.join(here, 'report.json')
    },
}
