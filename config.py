DEFAULT_CONFIGURATION = {
    'source': {
        'repositories': 'file://input.csv'
    },

    'docker': {
        'max_runtime': 300,  # Maximum number of seconds of each test-application to run
        'repo_volume_path': '/repo'  # Container path to mount the repo to
    },

    'git': {

    },

    'logging': {
        'level': 'DEBUG'
    }
}