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
        'service': 'moodle_mobile_app',  # Name of the service to use when fetching auth tokens
    },

    'logging': {
        'level': 'DEBUG'
    },

    'preconditions': [],
    'tests': []
}