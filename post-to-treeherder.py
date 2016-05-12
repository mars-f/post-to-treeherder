#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Original source:
# https://github.com/mozilla/mozmill-ci/blob/master/jenkins-master/jobs/scripts/workspace/submission.py

import argparse
import os
import re
import socket
from urlparse import urljoin, urlparse
import uuid
import json

from config import config
from lib import utils

import logging
logging.basicConfig()

here = os.path.dirname(os.path.abspath(__file__))

RESULTSET_FRAGMENT = 'api/project/{repository}/resultset/?revision={revision}'
JOB_FRAGMENT = '/#/jobs?repo={repository}&revision={revision}'

BUILD_STATES = ['running', 'completed']


class TestResultParser(object):

    BUSTED = 'busted'
    SUCCESS = 'success'
    TESTFAILED = 'testfailed'
    UNKNOWN = 'unknown'

    def __init__(self, retval, log_file):
        self.retval = retval
        self.log_file = log_file
        self.failures = []
        self.result_line = []
        self.parse_results()

    def parse_results(self):
        # if already failed (busted) no point in looking for logs
        if self.retval == 1:
            print('Test was reported as busted (--test-busted)')
            return

        # ensure results file exists, parse it
        try:
            with open(self.log_file, 'r') as results_file:
                results_data = results_file.read()
                # get rid of 'testreport =' at top of file as not valid json
                if results_data[:12] == 'testreport =':
                    results_data = results_data[12:]
                results_json = json.loads(results_data)

        except IOError:
            print('Test busted, missing log file: {}'.format(self.log_file))
            self.retval = 1

        except ValueError:
            print('Test busted, unable to parse log file: {}'.format(self.log_file))
            self.retval = 1

        if self.retval == 1 or self.failures:
            return

        # results file found and parsed, so now check the actual results themselves
        print("******* TODO: parse results_json now")

    @property
    def status(self):
        status = self.UNKNOWN

        if self.retval is None or (self.retval and not self.failures):
            status = self.BUSTED

        elif not self.failures:
            status = self.SUCCESS

        elif self.failures:
            status = self.TESTFAILED

        return status

    def failures_as_json(self):
        failures = {'all_errors': [], 'errors_truncated': True}

        for failure in self.failures:
            failures['all_errors'].append({'line': failure, 'linenumber': 1})

        return failures


class Submission(object):

    def __init__(self, repository, revision, settings, start_time, finish_time, 
                 test_busted=0, treeherder_url=None, treeherder_client_id=None, treeherder_secret=None):
        self.repository = repository
        self.revision = revision
        self.start_time = start_time
        self.finish_time = finish_time
        self.settings = settings
        self._job_details = []

        self.url = treeherder_url
        self.client_id = treeherder_client_id
        self.secret = treeherder_secret

        if test_busted == '0' or test_busted == '1':
            self.test_busted = int(test_busted)
        else:
            self.test_busted = 0

        if not self.client_id or not self.secret:
            raise ValueError('The client_id and secret for Treeherder must be set.')

    def get_treeherder_platform(self):
        platform = None

        info = mozinfo.info

        if info['os'] == 'linux':
            platform = ('linux', '%s%s' % (info['os'], info['bits']), '%s' % info['processor'])

        elif info['os'] == 'mac':
            platform = ('mac', 'osx-%s' % info['os_version'].replace('.', '-'), info['processor'])

        elif info['os'] == 'win':
            versions = {'5.1': 'xp', '6.1': '7', '6.2': '8'}
            bits = ('-%s' % info['bits']) if info['os_version'] != '5.1' else ''
            platform = ('win', 'windows%s%s' % (versions[info['os_version']], '%s' % bits),
                        info['processor'],
                        )

        return platform

    def create_job(self, guid, **kwargs):
        job = TreeherderJob()

        job.add_job_guid(guid)

        job.add_product_name('mozreview')

        job.add_project(self.repository)
        job.add_revision(self.revision)

        # Add platform and build information
        job.add_machine(socket.getfqdn())
        platform = self.get_treeherder_platform()

        job.add_machine_info(*platform)
        job.add_build_info(*platform)

        # TODO debug or others?
        job.add_option_collection({'opt': True})

        # TODO: Add e10s group once we run those tests
        job.add_group_name(self.settings['treeherder']['group_name'].format(**kwargs))
        job.add_group_symbol(self.settings['treeherder']['group_symbol'].format(**kwargs))

        # Bug 1174973 - for now we need unique job names even in different groups
        job.add_job_name(self.settings['treeherder']['job_name'].format(**kwargs))
        job.add_job_symbol(self.settings['treeherder']['job_symbol'].format(**kwargs))

        # request time and start time same is fine
        job.add_submit_timestamp(int(self.start_time))

        # test start time for that paraticular app is set in jenkins job itself
        job.add_start_timestamp(int(self.start_time))

        # Bug 1175559 - Workaround for HTTP Error
        job.add_end_timestamp(0)

        return job

    def retrieve_revision_hash(self):
        if not self.url:
            raise ValueError('URL for Treeherder is missing.')

        lookup_url = urljoin(self.url,
                             RESULTSET_FRAGMENT.format(repository=self.repository,
                                                       revision=self.revision))

        print('Getting revision hash from: {}'.format(lookup_url))
        response = requests.get(lookup_url)
        response.raise_for_status()

        if not response.json():
            raise ValueError('Unable to determine revision hash for {}. '
                             'Perhaps it has not been ingested by '
                             'Treeherder?'.format(self.revision))

        return response.json()['results'][0]['revision_hash']

    def submit(self, job, logs=None):
        logs = logs or []

        # We can only submit job info once, so it has to be done in completed
        if self._job_details:
            job.add_artifact('Job Info', 'json', {'job_details': self._job_details})

        job_collection = TreeherderJobCollection()
        job_collection.add(job)

        print('Sending results to Treeherder: {}'.format(job_collection.to_json()))
        url = urlparse(self.url)
       
        #client = TreeherderClient(protocol=url.scheme, host=url.hostname,
        #                          client_id=self.client_id, secret=self.secret)
        #client.post_collection(self.repository, job_collection)

        #print('Results are available to view at: {}'.format(
        #    urljoin(self.url,
        #            JOB_FRAGMENT.format(repository=self.repository, revision=self.revision))))

    def submit_running_job(self, job):
        job.add_state('running')
        self.submit(job)

    def build_results_url(self, parser_retval):
        if self.test_busted == 0 and parser_retval == 0:
            results_url = 'Make link to test results here'
        else:
            results_url = "Test busted! See Jenkins buid log!"

        print('Link to results: %s' % results_url)
        return results_url

    def submit_completed_job(self, job, retval):
        """Update the status of a job to completed.
        """

        # Parse results log
        parser = TestResultParser(retval, self.settings['logs']['results'].format(**kwargs))
        job.add_result(parser.status)

        # If the Jenkins BUILD_URL environment variable is present add it as artifact
        if os.environ.get('BUILD_URL'):
            self._job_details.append({
                'title': 'Inspect Jenkins Build',
                'value': os.environ['BUILD_URL'],
                'content_type': 'link',
                'url': os.environ['BUILD_URL']
            })

        # Add link to results
        results_url = self.build_results_url(parser.retval)
        self._job_details.append({
            'title': 'Results link',
            'value': results_url,
            'content_type': 'link',
            'url': results_url
        })

        job.add_state('completed')
        job.add_end_timestamp(int(self.finish_time))

        self.submit(job)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-time',
                        required=True,
                        help='The time (epoch) that the test started at.')
    parser.add_argument('--finish-time',
                        help='The time (epoch) that the test finished at.')
    parser.add_argument('--test-busted',
                        help='(Bool) Set to 1 if the test failed to run on Jenkins (busted).')
    parser.add_argument('--repository',
                        required=True,
                        help='The repository name the build was created from.')
    parser.add_argument('--revision',
                        required=True,
                        help='Revision of the build that is being tested.')
    parser.add_argument('--build-state',
                        choices=BUILD_STATES,
                        required=True,
                        help='The state of the build')

    aws_group = parser.add_argument_group('AWS', 'Arguments for Amazon S3')
    aws_group.add_argument('--aws-bucket',
                           default=os.environ.get('AWS_BUCKET'),
                           help='The S3 bucket name.')
    aws_group.add_argument('--aws-key',
                           default=os.environ.get('AWS_ACCESS_KEY_ID'),
                           help='Access key for Amazon S3.')
    aws_group.add_argument('--aws-secret',
                           default=os.environ.get('AWS_SECRET_ACCESS_KEY'),
                           help='Access secret for Amazon S3.')

    treeherder_group = parser.add_argument_group('treeherder', 'Arguments for Treeherder')
    treeherder_group.add_argument('--treeherder-url',
                                  default=os.environ.get('TREEHERDER_URL'),
                                  help='URL to the Treeherder server.')
    treeherder_group.add_argument('--treeherder-client-id',
                                  default=os.environ.get('RAPTOR_TREEHERDER_CLIENT_ID'),
                                  help='Client ID for submission to Treeherder.')
    treeherder_group.add_argument('--treeherder-secret',
                                  default=os.environ.get('RAPTOR_TREEHERDER_SECRET'),
                                  help='Secret for submission to Treeherder.')

    return vars(parser.parse_args())


if __name__ == '__main__':
    print('Raptor Treeherder Submission Script Version %s' % config['version'])
    kwargs = parse_args()

    # Can only be imported after the environment has been activated
    import mozinfo
    import requests

    from thclient import TreeherderClient, TreeherderJob, TreeherderJobCollection

    th = Submission(kwargs['repository'],
                    treeherder_url=kwargs['treeherder_url'],
                    treeherder_client_id=kwargs['treeherder_client_id'],
                    treeherder_secret=kwargs['treeherder_secret'],
                    revision=kwargs['revision'][:12],
                    settings=config,
                    start_time=kwargs['start_time'],
                    finish_time=kwargs['finish_time'],
                    test_busted=kwargs['test_busted'])

    # State 'running'
    if kwargs['build_state'] == BUILD_STATES[0]:
        job_guid = str(uuid.uuid4())
        job = th.create_job(job_guid, **kwargs)
        th.submit_running_job(job)
        with file('job_guid.txt', 'w') as f:
            f.write(job_guid)

    # State 'completed'
    elif kwargs['build_state'] == BUILD_STATES[1]:
        # Read in job guid to update the report
        try:
            with file('job_guid.txt', 'r') as f:
                job_guid = f.read()
        except:
            job_guid = str(uuid.uuid4())

        # return value from jenkins test (--test-busted) indicates if busted
        retval = 0
        if kwargs['test_busted'] != None:
            if int(kwargs['test_busted']) != 0:
                retval = 1

        job = th.create_job(job_guid, **kwargs)

        th.submit_completed_job(job, retval)
