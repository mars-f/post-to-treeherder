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
        'rb': {
            'job_name': 'reviewboard',
            'job_symbol': 'rb',
        },
        'nd': {
            'job_name': 'no-docker',
            'job_symbol': 'nd',
        },
        'artifacts': {
            'results.txt': os.path.join(here, 'upload', 'results.txt'),
            'report.json': os.path.join(here, 'upload', 'report.json'),
            'create-test-env.log': os.path.join(here, 'upload', 'create-test-env.log'),
            'failed-tests-diffs.log': os.path.join(here, 'upload', 'failed-tests-diffs.log')
        },
    },
    'logs': {
        'results': os.path.join(here, 'upload', 'report.json')
    },
}
