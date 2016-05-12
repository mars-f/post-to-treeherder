# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os

here = os.path.dirname(os.path.abspath(__file__))
file_name = 'report.json'

config = {
    'version': '1.0.0',
    'treeherder': {
        'group_name': 'version-control-tools',
        'group_symbol': 'VCT',
        'job_name': 'reviewboard',
        'job_symbol': 'rb'
    },
    'logs': {
        'name': file_name,
        'results': os.path.join(here, file_name)
    },
}
