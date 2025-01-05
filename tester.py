from __future__ import annotations

import os.path
import subprocess
import sys
import datetime
from zipfile import BadZipfile

import config as config_module
import model
from endpoint import EndpointFactory
from model import TestStorage


class ExerciseTester(config_module.ConfigurationBasedObject):

    def __init__(self, config, environment='prod'):
        """
        Create a new exercise tester and supply the application configuration
        :param config: The configuration passed by the user (may contain a list in decreasing order of priority)
        :param environment: Runtime environment to use as optional suffix to configuration parameters
        """
        # Set default config as config parameters
        super().__init__(config, environment)

        # Validate config
        self._read_test_config()

    def test(self) -> bool:
        """
        Perform some self-service checks if testing is available
        :return: true if testing can start, else false
        """
        # We need at least one endpoint
        factory = EndpointFactory.get()
        if factory.get_endpoint('gitlab') is None and factory.get_endpoint('moodle') is None and \
            factory.get_endpoint('local') is None:
            self.logger.error("No endpoints available to read data")
            return False

        # Validate docker availability
        docker_command = ['docker', 'info']
        try:
            result = subprocess.run(docker_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            result.check_returncode()
        except subprocess.CalledProcessError as cpe:
            self.logger.error(f"Failed to test docker availability with {cpe}")
            return False

        return True

    def run(self) -> None:
        """
        Run the exercises from the referenced repositories in the
        configured docker containers
        """
        path = self.working_directory
        self.logger.debug(f"Run tests in base directory {path}")
        os.makedirs(path, exist_ok=True)

        # Check if execution is requested now
        now = datetime.datetime.now()
        if self.config['general']['valid_until']:
            valid_until = self.config['general']['valid_until']
            if type(valid_until) is str:
                valid_until = datetime.datetime.strptime(valid_until, "%d.%m.%Y - %H:%M Uhr")
            else:
                valid_until = datetime.datetime.fromtimestamp(valid_until)

            if now > valid_until:
                self.logger.info(f"Testing is disabled because now({now}) > valid_until({valid_until})")
                return

        if self.config['general']['not_valid_before']:
            not_valid_before = self.config['general']['not_valid_before']
            if now < not_valid_before:
                self.logger.info(f"Testing is disabled because now({now}) < not_valid_before({not_valid_before})")
                return

        for repo in self.repositories:
            if self.config['general']['repo_filter'] and repo.identifier not in self.config['general']['repo_filter']:
                self.logger.info(f"Skipping because Repo {repo} not in filter list")
                continue

            if repo.is_locked():
                self.logger.warning(f"Repository {repo} already locked - Skipping test")
                continue

            try:
                # Lock repo for processing
                repo.lock()

                if repo.endpoint.require_download_before_update_check():
                    self.logger.debug(f"Fetching repository {repo}")
                    repo.download()

                always_run_tests = self.config['general']['always_run_tests']
                if always_run_tests is not False or repo.has_update():

                    if not repo.endpoint.require_download_before_update_check():
                        self.logger.debug(f"Late fetching repository {repo}")
                        repo.download()

                    # Check if we should unzip the content
                    if self.config['general']['unzip_submissions'] and repo.supports_unzip:
                        try:
                            repo.unzip(self.config['general']['remove_archive_after_unzip'])
                        except BadZipfile:
                            repo.submit_grade(0, "Abgabe ist keine gültige ZIP-Datei")

                    self.logger.debug(f"Repository {repo} was updated - perform a test")
                    try:
                        result = self._run_test(repo)
                    except Exception as e:
                        repo.submit_grade(0, f"Auswertung der Abgabe ist abgestürzt: {e}")
                        continue

                    grade_updated = repo.current_grade != False and \
                                    (repo.current_grade is None or repo.current_grade < result.grade)
                    if self.config['general']['simulate']:
                        if grade_updated:
                            self.logger.debug(f"Simulated UPDATED Grading {result.grade} for {repo}")
                        else:
                            self.logger.debug(f"Simulation resulted in same grading {result.grade} for {repo}")
                        self.logger.debug(f"Grading message {result.message}")
                    #elif always_run_tests is True or repo.current_grade is None or repo.current_grade != result.grade:
                    else:
                        if grade_updated:
                            self.logger.debug(f"Submit UPDATED Grading {result.grade} for {repo}")
                            repo.submit_grade(result.grade, result.message)
                        else:
                            self.logger.debug(f"Skip grade submission because of same grading {result.grade} for {repo}")
                else:
                    self.logger.debug(f"{repo} has no updates - skipping")
            except Exception as e:
                self.logger.warning(f"Failed to execute test for repository {repo} with error {e}")

            finally:
                # Free repo lock
                repo.unlock()

    def _read_test_config(self) -> None:
        """
        Test the application test config and bail out on invalid setup parameters
        :return: None
        """
        self.storage = TestStorage()
        self.preconditions = []
        if self.config.get('preconditions') is not None:
            self.logger.debug('Read test preconditions setup')
            for test_config in self.config['preconditions']:
                self.preconditions.append(model.BasicTest.from_configuration(test_config, self.storage))

            self.logger.debug(f'Read {len(self.preconditions)} test preconditions')
        else:
            self.logger.debug('No test preconditions found in setup')

        # A test node is required
        if self.config.get('tests') is None:
            raise Exception("No test configuration specified")

        self.tests = []
        self.logger.debug('Read tests')
        for test_config in self.config['tests']:
            self.tests.append(model.BasicTest.from_configuration(test_config, self.storage))

        self.logger.debug(f'Read {len(self.tests)} tests')
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
                    test.update_points(100 - (max_points + (len(auto_points_tests) - 1) * points_per_test))
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
