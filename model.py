import datetime
import hashlib
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping

import toml

import utils


class Repository(object):
    """
    Class reflecting a repository to test
    """

    MODIFIED_AT_METADATA_KEY = "modified_at"

    def __init__(self, endpoint, identifier: str, data):
        """
        Parse the given repo configuration
        :param endpoint: Endpoint to use to fetch this repository
        :param identifier: unique identifier for this repository
        :param data: endpoint specific repository data
        """
        self._endpoint = endpoint
        self._identifier = hashlib.md5(identifier.encode()).hexdigest()
        self._data = data
        self.working_directory = tempfile.gettempdir()
        self._metadata = None

    def download(self):
        self._endpoint.download(self)

    def has_update(self) -> bool:
        return self._endpoint.has_update(self)

    def unzip(self, remove_archive: bool):
        return self._endpoint.unzip(self, remove_archive)

    def submit_grade(self, grade: int, message: str):
        timestamp = datetime.datetime.now().timestamp()
        self._endpoint.submit_grade(self, grade, message)
        self.metadata[Repository.MODIFIED_AT_METADATA_KEY] = timestamp
        self._save_metadata()

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def identifier(self):
        return self._identifier

    @property
    def data(self):
        return self._data

    @property
    def directory(self):
        return f'repo_{self.identifier}'

    @property
    def path(self):
        return f'{self.working_directory}/repo_{self.identifier}'

    @property
    def metadata_path(self):
        return f'{self.working_directory}/repo_{self.identifier}_meta.toml'

    @property
    def metadata(self):
        if self._metadata is None:
            if os.path.isfile(self.metadata_path):
                with open(self.metadata_path, 'r') as fd:
                    self._metadata = toml.load(fd)
            else:
                self._metadata = {}

        return self._metadata

    @metadata.setter
    def metadata(self, value):
        self._metadata = value
        self._save_metadata()

    @property
    def supports_unzip(self):
        return self._endpoint.supports_unzip

    def _save_metadata(self):
        """
        Save the current metadata to disk
        :return: None
        """
        with open(self.metadata_path, 'w') as fd:
            toml.dump(self._metadata, fd)

    def __repr__(self):
        """
        String representation of the repository
        :return: Output string
        """
        return f"Repository({self.identifier} -> {self.path})"


class TestResult(object):
    """
    Test result reflecting an executed test on a repository
    """
    STATE_PREPARED = 1
    STATE_PRECONDITIONS_EXECUTED = 2
    STATE_TESTS_EXECUTED = 3

    def __init__(self, repository: Repository):
        self._repository = repository
        self.tests = []
        self.state = TestResult.STATE_PREPARED

    @property
    def repository(self):
        return self._repository

    @property
    def successful(self) -> bool:
        return all(map(lambda x: x.successful and x.state == TestStepResult.STATE_EXECUTED, self.tests))

    @property
    def grade(self) -> int:
        result = 0
        for test in self.tests:
            if test.state == TestStepResult.STATE_EXECUTED and test.successful and test.test.points > 0:
                result += test.test.points

        return result

    @property
    def points(self) -> int:
        return sum(map(lambda t: t.test.points, self.tests))

    @property
    def message(self) -> str:
        result = "# Auswertung der Abgabe\n\n"

        result += f'- Status: '
        if self.state == TestResult.STATE_PREPARED:
            result += 'nicht ausgeführt'
        elif self.state == TestResult.STATE_PRECONDITIONS_EXECUTED:
            result += 'Abbruch nach fehlgeschlagenen Voraussetzungen'
        else:
            result += 'Abgabe wurde bewertet'

        result += '\n'

        # Print total points
        result += f'- Punkte: **{self.grade}** von **{self.points}**\n\n'

        for test in self.tests:
            result += test.message

        return result


class TestStepResult(object):
    """
    Class holding the results of a single test execution
    """
    STATE_PREPARED = 1
    STATE_EXECUTED = 2
    STATE_EXCEPTED = 3

    def __init__(self, test):
        """
        Create a new container for the given test
        :param test: Test that was run
        """
        self.state = TestStepResult.STATE_PREPARED
        self.successful = False
        self.output = ""
        self.error = ""
        self.return_code = None
        self.test = test
        self.test_items = []
        self.runtime = None

    def run(self):
        """
        Execute the associated test
        :return: None
        """
        t_start = datetime.datetime.now()
        try:
            self.test.run(self)
            self.state = TestStepResult.STATE_EXECUTED
        except Exception as e:
            self.state = TestStepResult.STATE_EXCEPTED
            self.error = repr(e)
        finally:
            t_end = datetime.datetime.now()

        self.runtime = t_end - t_start

    @property
    def message(self) -> str:
        """
        Build the test evaluation string for the test case result
        :return: Result string to publish in grading receipt
        """
        result = f'### Testergebnis für {self.test.name}\n'

        # Append state line
        result += f'- Status: '
        if self.state == TestStepResult.STATE_PREPARED:
            result += 'nicht ausgeführt'
        elif self.state == TestStepResult.STATE_EXECUTED:
            result += 'ausgeführt'
        else:
            result += 'Fehler während der Ausführung'

        result += '\n'

        # Append successful state
        result += f'- Erfolgreich: {"Ja" if self.successful else "Nein"}\n'

        # Append runtime if available
        if self.runtime is not None:
            result += f'- Laufzeit: {self.runtime}\n'

        # Append grade if available
        if self.test.points:
            result += f'- Punkte: **{self.test.points if self.successful else 0}**\n'

        # Append return code if available
        if self.return_code:
            result += f'- Return-Code / Fehlercode: {self.return_code}\n'

        # Append output
        if self.test_items:
            result += f'##### Tests\n'
            for text, success in self.test_items:
                if success is True or success is False:
                    result += f'- {text}: {"OK" if success else "fehlgeschlagen"}\n'
                else:
                    result += f'- {text}: {success}\n'

            result += '\n'

        if self.output:
            result += f'##### Ausgabe\n```\n{self.output}\n```\n\n'

        if self.error:
            result += f'##### Fehlerausgabe\n```\n{self.error}\n```\n\n'

        return result


class BasicTest(object):
    """
    Basic test class all tests are derived from
    """

    def __init__(self, options):
        """
        Init the base test with options
        :param options: Test configuration options - supported parameters are:
             type: str - Base test type identifier
             name: str - Human readable name of the test
             terminate_on_fail: True|False - End execution if the test fails
             points: int - Number of points to assign if the test is successful
        """
        self.options = options
        for key in ['type', 'name']:
            if key not in self.options:
                raise KeyError(f'Missing test option: {key}')

    @staticmethod
    def from_configuration(config):
        """
        Build a test model from the given configuration
        :param config: Configuration to process
        :return: appropriate test case model
        """
        t = config.get('type')
        if t == FileTest.TYPE:
            return FileTest(config)
        elif t == CommandTest.TYPE:
            return CommandTest(config)
        elif t == DockerCommandTest.TYPE:
            return DockerCommandTest(config)
        else:
            raise Exception(f'Unknown test type "{t}"')

    @property
    def type(self):
        return self.options['type']

    @property
    def name(self):
        return self.options['name']

    @property
    def terminate_on_fail(self):
        return self.options.get('terminate_on_fail', False)

    @property
    def points(self):
        return self.options.get('points', 0)

    def run(self, result: TestStepResult) -> TestStepResult:
        """
        Execute the test
        :param result: Container to write the result of the test to
        :return: true if execution succeeded, else false
        """
        raise NotImplementedError()

    def __repr__(self):
        return f'Test {self.name} with type {self.type}'

    def __str__(self):
        return f'Test {self.name} with type {self.type}'


class FileTest(BasicTest):
    """
    Test to check the status of a file
    """
    TYPE = "file"
    MODE_EXIST = "exist"  # Check for item existence
    MODE_NOT_EXIST = "not_exist"  # Check that the given items does not exist
    MODE_CONTAINS = "contains"  # Check if the given items contains the given content
    MODE_HASH = "hash"  # Check if the given items match the given hashes

    def __init__(self, options):
        """
        Init a file based test with options
        :param options: Test configuration options - supported parameters besides BasicTest-options are:
            mode: str (Default MODE_EXIST) - Mode of operation
            items: str|list[str] - List of items to test with the given mode
            allow_other: bool (Default True) - Indicator if other items are allowed to be present
            contents: str|list[str]|dict[str, str] - File contents to match the content of files against (MODE_CONTAINS)
            hashes: str|list[str]|dict[str, str] - Hashes to test the files against (MODE_HASH)
        """
        super(FileTest, self).__init__(options)
        self.mode = self.options.get('mode', FileTest.MODE_EXIST)
        if self.mode not in [FileTest.MODE_EXIST, FileTest.MODE_HASH, FileTest.MODE_CONTAINS, FileTest.MODE_NOT_EXIST]:
            raise Exception("Invalid test mode")

        # Extract items to test
        self.items = utils.ensure_list(self.options.get('items', []))

        if self.mode == FileTest.MODE_EXIST:
            self.allow_other = self.options.get('allow_other', True)
        elif self.mode == FileTest.MODE_HASH:
            self.hashes = self.options.get('hashes', [])
            if isinstance(self.hashes, str):
                self.hashes = [self.hashes] * len(self.items)

            if len(self.hashes) != len(self.items):
                raise Exception("You need to specify a hash for each item")
        elif self.mode == FileTest.MODE_CONTAINS:
            self.contents = self.options.get('contents', [])
            if isinstance(self.contents, str):
                self.contents = [self.contents] * len(self.items)

            if len(self.contents) != len(self.items):
                raise Exception("You need to specify desired content for each item")

    def run(self, result: TestStepResult):
        """
        Execute the test
        :param result: Container to write the result of the test to
        :return: test result
        """

        if self.mode == FileTest.MODE_EXIST:
            self._run_exist_check(result, True)
        elif self.mode == FileTest.MODE_NOT_EXIST:
            self._run_exist_check(result, False)
        elif self.mode == FileTest.MODE_CONTAINS:
            self._run_contains_check(result)
        else:
            self._run_hash_check(result)

    def _run_exist_check(self, result, desired_state):
        """
        Check if the files of this check have the desired state
        :param result: test result container
        :param desired_state: desired item existence state
        :return: None
        """
        result.successful = True
        for item in self.items:
            success = os.path.exists(item) == desired_state
            message = f'{item} soll {"vorhanden" if desired_state else "nicht vorhanden"} sein'
            result.test_items.append((message, success))
            result.successful &= success

    def _run_contains_check(self, result):
        """
        Check if the files of this check have the desired content
        :param result: test result container
        :return: None
        """
        result.successful = True
        for index, item in enumerate(self.items):
            message = f'Inhalt von {item} prüfen'
            desired_content = self.contents[item] if isinstance(self.contents, Mapping) else self.contents[index]
            try:
                with open(item, 'r') as fd:
                    content = fd.read()
                    success = desired_content in content

                result.test_items.append((message, success))
                result.successful &= success

            except FileNotFoundError:
                result.test_items.append((message, 'DATEI nicht gefunden'))
                result.successful = False
            except IsADirectoryError:
                result.test_items.append((message, 'Objekt ist ein VERZEICHNIS'))
                result.successful = False
            except PermissionError:
                result.test_items.append((message, 'KEINE ZUGRIFFSBERECHTIGUNG'))
                result.successful = False

    def _run_hash_check(self, result):
        """
        Check if the files of this check have the desired has value
        :param result: test result container
        :return: None
        """
        result.successful = True
        for index, item in enumerate(self.items):
            sha1 = hashlib.sha1()
            desired_hash = self.hashes[item] if isinstance(self.hashes, Mapping) else self.hashes[index]
            message = f'Hash-Test von {item} auf {desired_hash}'
            if os.path.exists(item) and os.path.isfile(item):
                with open(item, 'rb') as f:
                    while True:
                        data = f.read(65536)
                        if not data:
                            break

                        sha1.update(data)

                h = sha1.hexdigest()
                success = desired_hash != h
                result.test_items.append((message, success))
                result.successful &= success
            else:
                result.test_items.append((message, 'Objekt NICHT GEFUNDEN'))
                result.successful = False


class CommandTest(BasicTest):
    """
    Test by executing a command
    """
    TYPE = "command"

    def __init__(self, options):
        """
        Init a command execution based test with options
        :param options: Test configuration options - supported parameters besides BasicTest-options are:
            return_code: int|list[int] - Return code or list of return codes to accept as success (optional)
            command: str|list[str] - Command to be executed with parameters
            timeout: int - Command timeout before to kill the application because of a hang
            input: str - Input to provide to the command
            output: str - Regular expression of required output (optional) - this is tested with re.search
            output_match: str - Regular expression of required output (optional) - this is tested with re.match
            error: str - Regular expression of required error output (optional) - this is tested with re.search
            error_match: str - Regular expression of required error output (optional) - this is tested with re.match
        """
        super(CommandTest, self).__init__(options)

        if 'command' not in options:
            raise Exception("Command must be supplied for the test")

        self.command = utils.ensure_list(options['command'])
        self.timeout = self.options.get('timeout', -1)

    def run(self, result: TestStepResult):
        """
        Execute the test
        :param result: Container to write the result of the test to
        :return: test result
        """

        result.successful = True
        try:
            timeout = None if self.timeout is None or self.timeout < 0 else self.timeout
            input_data = self.options.get('input', None)
            process = subprocess.run(self.command, input=input_data, capture_output=True, timeout=timeout,
                                     check=True, text=True)

            result.output = process.stdout if process.stdout is not None else ''
            result.error = process.stderr if process.stderr is not None else ''
            result.return_code = process.returncode

            # Check desired output on all channels
            for key, title, target, f in [
                ('output', 'Erwartete Ausgabe', result.output, re.search),
                ('output_match', 'Erwartete Ausgabe', result.output, re.match),
                ('error', 'Erwartete Fehler-Ausgabe', result.error, re.search),
                ('error_match', 'Erwartete Fehler-Ausgabe', result.error, re.match)
            ]:
                if self.options.get(key, None) is not None:
                    success = f(self.options[key], target) is not None
                    result.test_items.append((f'{title} \'{self.options[key]}\'', success))
                    result.successful &= success

            if self.options.get('return_code', None) is not None:
                codes = utils.ensure_list(self.options['return_code'])
                success = result.return_code in codes
                result.test_items.append(('Erwarteter Rückgabe-Code', success))
                result.successful &= success

        except subprocess.TimeoutExpired as e:
            result.output = e.stdout.decode('utf-8') if e.stdout is not None else ''
            result.error = e.stderr.decode('utf-8') if e.stderr is not None else ''
            result.successful = False

        except subprocess.CalledProcessError as e:
            result.output = e.stdout if e.stdout is not None else ''
            result.error = e.stderr if e.stderr is not None else ''
            result.successful = False


class DockerCommandTest(CommandTest):
    """
    Test by executing a command
    """
    TYPE = "docker"

    def __init__(self, options):
        """
        Init a command execution based test with options
        :param options: Test configuration options - supported parameters besides CommandTest-options are:
            image: str - Name of the docker image to run
            repo_volume_path: str - Path where to mount to repository volume to the container (Defaults to repo)
        """
        if 'image' not in options:
            raise Exception("Docker image must be supplied for the test")

        image = options['image']
        self.volume = self.options.get('repo_volume_path', '/repo')
        volume = f"{os.getcwd()}:{self.volume}"

        # Build basic docker command
        command = ['docker', 'run', '--rm', '--network=none', '-v', volume, image]

        # If a special command is given use this instead of the container command
        if options.get('command', None) is not None:
            command += options['command']

        # Supply interactive switch if stdin-data is required
        if self.options.get('input', None) is not None:
            command.insert(2, "-i")

        options['command'] = command
        super(DockerCommandTest, self).__init__(options)
