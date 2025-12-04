import logging
import os
from typing import Mapping

import model
import utils
from endpoint import EndpointFactory
from source import Source

DEFAULT_CONFIGURATION = {
    'general': {
        'repositories': 'file://input.csv',
        'directory': '/tmp/exercise-runner',  # Run in the local working directory
        'always_run_tests': False,  # Ignore any cached results and always run tests
        'simulate': True,  # Do not submit results
        'unzip_submissions': False,  # If the submission consists of a single .zip file then extract it if set to True
        'remove_archive_after_unzip': False,  # Set to true to remove any zip files after auto unzipping took place
        'valid_until': None, # Timestamp until the tests should be executed
        'not_valid_before': None, # Earliest timestamp since when the tests should be executed
        'repo_filter': [], # Explicit filters for repositories
        'always_update_grades': True # Always publish grades on updated projects even if the grade worsens or is empty
    },

    'docker': {
        'max_runtime': 300,  # Maximum number of seconds of each test-application to run
        'repo_volume_path': '/repo',  # Container path to mount the repo to
        'image': None  # Name of the container image to run the tests
    },

    'git': {
        'uri': None,       # URI to use as base for requests
        'username': None,  # Username to use for authentication when pulling from the repo
        'password': None,  # Password to use if username is given
        'report_file': 'AutoReviewResults.md',  # Name of the file where the generated test report is written to
        'commit_message_request_marker': 'AUSWERTUNG',  # Text to look for in commit messages to detect
                                                        # commits requested for testing
        'commit_message_feedback_marker': 'FEEDBACK',  # Text to look for in commit messages to detect
                                                       # generated feedback commits
        'feedback_commit_message': 'FEEDBACK zum Commit {commit.hexsha}',  # Message to use as commit message when
                                                                           # publishing results (commit=git.Commit-obj)
        'grading_file_template': 'BEWERTUNG: {grade}\n\n{message}',  # Grading file content (grade is an integer and
                                                                     # message a string)
        'page_size': 25
    },

    'moodle': {
        'uri': None,       # URI to use as base for requests
        'username': None,  # Username to use for authentication at the moodle instance
        'password': None,  # Password to use for username
        'token': None,     # Token to use instead of username / password authentication
        'service': 'moodle_mobile_app',  # Name of the service to use when fetching auth tokens
        'use_previous_attempt_for_reopened_submissions': True
    },

    'logging': {
        'level': 'DEBUG'
    },

    'plagiarism_detection': {
        'enabled': False,  # Is plagiarism detection enabled
        'files': [],       # List of files and globs to include in the detection process
        'exclude_files': ["**/.DS_Store", "**/.*"], # List of files or file patterns to ignore
        'normalize_pattern': r"\s|(//.*)|(/\*(\s\S)*\*/)" # Pattern to run over input file to normalize input characters
    },

    'preconditions': [],
    'tests': []
}

class ConfigurationBasedObject(object):
    def __init__(self, config, environment = 'prod'):
        """
        Create a new configuration based object and supply the application configuration
        :param config: The configuration passed by the user (may contain a list in decreasing order of priority)
        :param environment: Runtime environment to use as optional suffix to configuration parameters
        """
        # Set default config as config parameters
        self.config = {}
        for key in DEFAULT_CONFIGURATION.keys():
            self.config[key] = DEFAULT_CONFIGURATION[key].copy()

        config = utils.ensure_list(config)
        for c in config[::-1]:
            for key in self.config:
                if isinstance(self.config[key], Mapping):
                    for option in self.config[key]:
                        value = c.get(key, {}).get(option, None)
                        environment_value = c.get(key, {}).get(f'{option}_{environment}', None)
                        if environment_value is not None:
                            self.config[key][option] = environment_value
                        elif value is not None:
                            self.config[key][option] = value
                else:
                    value = c.get(key, None)
                    environment_value = c.get(f'{key}_{environment}', None)
                    if environment_value is not None:
                        self.config[key] = environment_value
                    elif value is not None:
                        self.config[key] = value

        # Setup logging
        logging.basicConfig(level=logging.DEBUG)  # Ensure debug logs are captured
        self.logger = logging.getLogger()
        self.logger.setLevel(self.config['logging']['level'])

        # Setup endpoints
        #EndpointFactory.get().register_endpoint('gitlab', EndpointFactory.TYPE_GITLAB, self.config.get('git'))
        #EndpointFactory.get().register_endpoint('moodle', EndpointFactory.TYPE_MOODLE, self.config.get('moodle'))
        EndpointFactory.get().register_endpoint('local', EndpointFactory.TYPE_LOCAL, {})

        # Fetch repos
        self.repositories = self.fetch_targets()

    @property
    def working_directory(self):
        d = self.config['general']['directory']
        return os.path.abspath(d)

    def fetch_targets(self) -> list[model.Repository]:
        """
        Fetches the list of repositories to process during execution
        :return: List of repositories to process
        """
        source_urls = utils.ensure_list(self.config['general']['repositories'])
        if len(source_urls) == 0:
            raise Exception("No repository sources configured in general->repositories")

        d = self.config['general']['directory']
        path = os.path.abspath(d)
        submissions = []
        for source_url in source_urls:
            self.logger.debug(f"Processing source: {source_url}")
            source = Source(source_url, path)
            submissions += source.submissions

        self.logger.debug(f"Found {len(submissions)} repositories: {submissions}")
        return submissions
