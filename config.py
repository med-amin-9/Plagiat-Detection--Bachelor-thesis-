DEFAULT_CONFIGURATION = {
    'source': {
        'repositories': 'file://input.csv',
        'directory': '/tmp/exercise-runner'  # Run in the local working directory
    },

    'docker': {
        'max_runtime': 300,  # Maximum number of seconds of each test-application to run
        'repo_volume_path': '/repo',  # Container path to mount the repo to
        'image': None  # Name of the container image to run the tests
    },

    'git': {
        'username': None,  # Username to use for authentication when pulling from the repo
        'password': None,  # Password to use if username is given
        'report_file': 'AutoReviewResults.md',  # Name of the file where the generated test report is written to
        'commit_message_request_marker': 'AUSWERTUNG',  # Text to look for in commit messages to detect
                                                        # commits requested for testing
        'commit_message_feedback_marker': 'FEEDBACK',  # Text to look for in commit messages to detect
                                                       # generated feedback commits
        'feedback_commit_message': 'FEEDBACK zum Commit {commit.hexsha}'  # Message to use as commit message when
                                                                          # publishing results (commit = git.Commit-obj)
    },

    'logging': {
        'level': 'DEBUG'
    }
}