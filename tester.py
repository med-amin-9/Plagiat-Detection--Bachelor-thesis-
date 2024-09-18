from __future__ import annotations

import logging
import os.path
import sys

import model
import utils
from endpoint import EndpointFactory
from config import DEFAULT_CONFIGURATION
from source import Source
from collections.abc import Mapping


class ExerciseTester(object):

    def __init__(self, config):
        """
        Create a new exercise tester and supply the application configuration
        :param config: The configuration passed by the user (may contain a list in decreasing order of priority)
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
                        if value is not None:
                            self.config[key][option] = value
                else:
                    value = c.get(key, None)
                    if value is not None:
                        self.config[key] = value

        # Setup logging
        logging.basicConfig()
        self.logger = logging.getLogger()
        self.logger.setLevel(self.config['logging']['level'])

        # Validate config
        self._read_test_config()

        # Setup endpoints
        EndpointFactory.get().register_endpoint('gitlab', EndpointFactory.TYPE_GITLAB, self.config.get('git'))
        EndpointFactory.get().register_endpoint('moodle', EndpointFactory.TYPE_MOODLE, self.config.get('moodle'))
        EndpointFactory.get().register_endpoint('local', EndpointFactory.TYPE_LOCAL, {})

        # Fetch repos
        self.repositories = self._fetch_targets()

    @property
    def working_directory(self):
        d = self.config['general']['directory']
        return os.path.abspath(d)

    def run(self) -> None:
        """
        Run the exercises from the referenced repositories in the
        configured docker containers
        """
        path = self.working_directory
        self.logger.info(f"Run tests in base directory {path}")

        for repo in self.repositories:
            self.logger.debug(f"Fetching repository {repo}")
            repo.download()

            if self.config['general']['always_run_tests'] or repo.has_update():
                # Check if we should unzip the content
                if self.config['general']['unzip_submissions'] and repo.supports_unzip:
                    repo.unzip(self.config['general']['remove_archive_after_unzip'])

                self.logger.debug(f"Repository {repo} was updated - perform a test")
                result = self._run_test(repo)

                if not self.config['general']['simulate']:
                    self.logger.debug(f"Submit grading {result.grade} for {repo}")
                    repo.submit_grade(result.grade, result.message)
                else:
                    self.logger.debug(f"Simulated Grading {result.grade} for {repo}")
                    self.logger.debug(f"Grading message {result.message}")
            else:
                self.logger.debug(f"{repo} has no updates - skipping")

    def _read_test_config(self) -> None:
        """
        Test the application test config and bail out on invalid setup parameters
        :return: None
        """
        self.preconditions = []
        if self.config.get('preconditions') is not None:
            self.logger.debug('Read test preconditions setup')
            for test_config in self.config['preconditions']:
                self.preconditions.append(model.BasicTest.from_configuration(test_config))

            self.logger.debug(f'Read {len(self.preconditions)} test preconditions')
        else:
            self.logger.debug('No test preconditions found in setup')

        # A test node is required
        if self.config.get('tests') is None:
            raise Exception("No test configuration specified")

        self.tests = []
        self.logger.debug('Read tests')
        for test_config in self.config['tests']:
            self.tests.append(model.BasicTest.from_configuration(test_config))

        self.logger.info(f'Read {len(self.tests)} tests')
        max_points = sum(map(lambda t: t.points, self.tests))
        auto_points_tests = list(filter(lambda t: t.has_auto_points, self.tests))
        if len(auto_points_tests) > 0:
            if max_points > 100:
                self.logger.error("Auto point generation requested but max points already greater 100")
                sys.exit(1)

            difference = 100 - max_points
            points_per_test = difference // len(auto_points_tests)
            for index, test in enumerate(auto_points_tests):
                if index == len(auto_points_tests) - 1:
                    test.update_points(100 - (max_points + (len(auto_points_tests) - 1) * points_per_test));
                else:
                    test.update_points(points_per_test)

            max_points = 100

        if max_points != 100:
            self.logger.info(f'Total number of points of test are {max_points} but should be 100')

    def _run_test(self, repository: model.Repository) -> model.TestResult:
        """
        Run the tests on the given repository
        :param repository: The Repository model describing the remote repository
        :return: Test result for the given repository
        """
        # Build result model
        result = model.TestResult(repository)

        # Create test result models
        for test in self.preconditions + self.tests:
            test_result = model.TestStepResult(test)
            result.tests.append(test_result)

        # Move to repo directory
        cwd = os.getcwd()
        os.chdir(repository.path)

        # Check preconditions
        preconditions_satisfied = True
        for index, test in enumerate(self.preconditions):
            self.logger.debug(f'Run precondition test {test}')
            test_result = result.tests[index]
            test_result.run()

            if not test_result.successful:
                self.logger.info(f'Precondition test {test.name} failed')
                preconditions_satisfied = False

        result.state = result.STATE_PRECONDITIONS_EXECUTED

        if preconditions_satisfied:
            for index, test in enumerate(self.tests):
                self.logger.debug(f'Run test {test}')
                test_result = result.tests[len(self.preconditions) + index]
                test_result.run()

                if not test_result.successful:
                    self.logger.info(f'Test {test.name} failed')

                    if test.terminate_on_fail:
                        break

            result.state = result.STATE_TESTS_EXECUTED
        else:
            self.logger.info(f'No grading tests are executed because the precondition tests failed')

        self.logger.debug(f'Test execution finished for {repository}')

        # Move back to origin
        os.chdir(cwd)

        return result

    def _fetch_targets(self) -> list[model.Repository]:
        """
        Fetches the list of repositories to process during execution
        :return:
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
