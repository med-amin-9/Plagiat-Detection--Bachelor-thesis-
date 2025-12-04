import datetime
import glob
import hashlib
import itertools
import os
import random
import re
import signal
import string
import subprocess
import tempfile
from collections.abc import Mapping
import time

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
        # optional list injected by plagiarism detector (or others)
        self._filtered_files = None
        self.fingerprints = {}  # Stores fingerprints for plagiarism detection

    # ---------------------------------------------------------------------
    # endpoint helpers
    # ---------------------------------------------------------------------
    @property
    def current_grade(self):
        return self._endpoint.get_current_grade(self)

    def download(self):
        self._endpoint.download(self)

    def has_update(self) -> bool:
        return self._endpoint.has_update(self)

    # ---------------------------------------------------------------------
    # locking helpers
    # ---------------------------------------------------------------------
    def is_locked(self, consider_own_pid_locked=True) -> bool:
        """
        Check if this repository is locked.
        """
        if not os.path.isfile(self.lock_path):
            return False

        pid = os.getpid()
        locked_pid = open(self.lock_path, "r").read()
        return locked_pid.isdigit() and (consider_own_pid_locked or pid != int(locked_pid))

    def lock(self):
        if self.is_locked(False):
            raise Exception("Repository is already locked")
        with open(self.lock_path, "w") as fd:
            fd.write(str(os.getpid()))

    def unlock(self, force=False):
        if self.is_locked(False) and not force:
            raise Exception(
                "Repository is already locked by another process – you’re not allowed to remove this lock"
            )
        if os.path.isfile(self.lock_path):
            os.remove(self.lock_path)

    # ---------------------------------------------------------------------
    # grading helpers
    # ---------------------------------------------------------------------
    def unzip(self, remove_archive: bool):
        return self._endpoint.unzip(self, remove_archive)

    def submit_grade(self, grade: int, message: str):
        timestamp = datetime.datetime.now().timestamp()
        self._endpoint.submit_grade(self, grade, message)
        self.metadata[Repository.MODIFIED_AT_METADATA_KEY] = timestamp
        self._save_metadata()

    # ---------------------------------------------------------------------
    # simple accessors
    # ---------------------------------------------------------------------
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
        return f"repo_{self.identifier}"

    @property
    def path(self):
        return f"{self.working_directory}/repo_{self.identifier}"

    # ---------------------------------------------------------------------
    # **modified** files property  (getter + NEW setter)
    # ---------------------------------------------------------------------
    @property
    def files(self):
        """
        Return all files in the repo unless an external tool
        has already supplied a filtered list.
        """
        if self._filtered_files is not None:
            return self._filtered_files

        result = []
        p = self.path
        for root, dirs, files in os.walk(p):
            for f in files:
                absolute_path = os.path.join(root, f)
                result.append(os.path.relpath(absolute_path, p))
        return result
    
    # -----------------------------------------------------------------
    # optional helper the plagiarism detector expects
    # -----------------------------------------------------------------
    def read_file(self, relative_path, mode="r"):
        """
        Return the contents of a file inside this repository.
        """
        abs_path = os.path.join(self.path, relative_path)
        with open(abs_path, mode) as f:
            return f.read()

    @files.setter
    def files(self, value):
        """
        Allow external tools (plagiarism detector, unit-test filter, …)
        to override the automatic file list.
        """
        self._filtered_files = value

    # ---------------------------------------------------------------------
    # metadata & misc
    # ---------------------------------------------------------------------
    @property
    def metadata_path(self):
        return f"{self.working_directory}/repo_{self.identifier}_meta.toml"

    @property
    def lock_path(self):
        return f"{self.working_directory}/repo_{self.identifier}.lock"

    @property
    def metadata(self):
        if self._metadata is None:
            if os.path.isfile(self.metadata_path):
                with open(self.metadata_path, "r") as fd:
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
        with open(self.metadata_path, "w") as fd:
            toml.dump(self._metadata, fd)

    # ---------------------------------------------------------------------
    def __repr__(self):
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

        display_index = 1
        for index, test in enumerate(self.tests):
            if test.test.visible:
                result += f'## Test {display_index}\n\n{test.message}'
                display_index += 1

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
        self.additional_records = []
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
        result = f'- Test: *{self.test.name}*\n'

        if self.test.description is not None:
            result += f'- Beschreibung: {self.test.description}\n'

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
        result += f'- Erfolgreich: **{"Ja" if self.successful else "Nein"}**\n'

        # Append runtime if available
        if self.runtime is not None:
            result += f'- Laufzeit: {self.runtime}\n'

        # Append grade if available
        if self.test.points:
            result += f'- Punkte: **{self.test.points if self.successful else 0}**\n'

        # Append return code if available
        if self.return_code is not None:
            result += f'- Return-Code / Fehlercode: `{self.return_code}`\n'

        # Append additional records data
        if self.additional_records:
            for additional_record in self.additional_records:
                result += f'- {additional_record[0]}: `{additional_record[1]}`\n'

        # Append output
        if self.test_items:
            result += f'##### Testschritte\n'
            for text, success in self.test_items:
                if success is True or success is False:
                    result += f'- {text}: {"OK" if success else "fehlgeschlagen"}\n'
                else:
                    result += f'- {text}: {success}\n'

            result += '\n'

        if self.output:
            result += f'##### Ausgabe\n\n```{self.output.strip()}\n```\n\n'

        if self.error:
            result += f'##### Fehlerausgabe\n\n```{self.error.strip()}\n```\n\n'

        if not self.successful:
            if self.state == TestStepResult.STATE_PREPARED:
                result += (f'##### Hinweise zur Behebung des Fehlers\n\nDer Test wurde nicht ausgeführt, da '
                           f'vorherige Tests fehlgeschlagen sind. Beheben Sie die vorherigen Probleme und '
                           f'versuchen Sie es dann erneut.\n\n')
            elif self.test.failure_hint:
                result += f'##### Hinweise zur Behebung des Fehlers\n\n{self.test.failure_hint}\n\n'

        return result


class TestStorage(dict):
    """
    Class to exchange data between tests
    """
    pass


class BasicTest(object):
    """
    Basic test class all tests are derived from
    """

    def __init__(self, options, storage: TestStorage):
        """
        Init the base test with options
        :param options: Test configuration options - supported parameters are:
             type: str - Base test type identifier
             name: str - Human readable name of the test
             terminate_on_fail: True|False - End execution if the test fails
             points: int - Number of points to assign if the test is successful
        :param storage: Test interchange storage
        """
        self.options = options
        for key in ['type', 'name']:
            if key not in self.options:
                raise KeyError(f'Missing test option: {key}')

        self.storage = storage

    @staticmethod
    def from_configuration(config, storage: TestStorage):
        """
        Build a test model from the given configuration
        :param config: Configuration to process
        :param storage: Test interchange storage
        :return: appropriate test case model
        """
        t = config.get('type')
        if t == FileTest.TYPE:
            return FileTest(config, storage)
        elif t == CommandTest.TYPE:
            return CommandTest(config, storage)
        elif t == DockerCommandTest.TYPE:
            return DockerCommandTest(config, storage)
        elif t == FileLocateTest.TYPE:
            return FileLocateTest(config, storage)
        else:
            raise Exception(f'Unknown test type "{t}"')

    @property
    def type(self):
        return self.options['type']

    @property
    def name(self):
        return self.options['name']

    @property
    def description(self):
        return self.options.get('description', None)

    @property
    def visible(self):
        return self.options.get('visible', True)

    @property
    def terminate_on_fail(self):
        return self.options.get('terminate_on_fail', False)

    @property
    def points(self):
        p = self.options.get('points', 0)
        return p if p != 'auto' else 0

    @property
    def has_auto_points(self):
        return self.options.get('points') == 'auto'

    @property
    def failure_hint(self):
        return self.options.get('failure_hint', None)

    def update_points(self, p):
        self.options['points'] = p

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


class FileLocateTest(BasicTest):
    """
    Test to find a certain file
    """
    TYPE = "locate"

    def __init__(self, options, storage: TestStorage):
        """
        Init a file based test with options
        :param options: Test configuration options - supported parameters besides BasicTest-options are:
            glob: str - glob to match for files
            recursive: bool (Default False) - search the glob recursively
            max_num_matches: int - (Default 1) maximum number of matches
            min_num_matches: int - (Default 1) minimum number of matches
            directory: str - directory to apply glob in
        :param storage: Test interchange storage
        """
        super(FileLocateTest, self).__init__(options, storage)

        self.glob = self.options.get("glob")
        if not self.glob:
            raise Exception("glob parameter is required")

        self.recursive = self.options.get("recursive", False)
        self.max_num_matches = self.options.get("max_num_matches", 1)
        self.min_num_matches = self.options.get("min_num_matches", 1)
        self.directory = self.options.get("directory")

    def run(self, result: TestStepResult):
        """
        Execute the test
        :param result: Container to write the result of the test to
        """
        cwd = os.getcwd()
        if self.directory is not None:
            try:
                os.chdir(self.directory)
            except OSError:
                result.test_items.append((f"Angefordertes Verzeichnis {self.directory} wurde nicht gefunden", False))
                result.successful = False
                return

        items = glob.glob(self.glob, recursive=self.recursive)
        if len(items) < self.min_num_matches:
            result.test_items.append(
                (f"Für {self.glob} wurden nur {len(items)} von {self.min_num_matches} Dateien gefunden", False))
            result.successful = False
        elif len(items) > self.max_num_matches:
            result.test_items.append(
                (f"Für {self.glob} wurden {len(items)} von maximal {self.min_num_matches} Dateien gefunden", False))
            result.successful = False
        else:
            result.test_items.append(
                (f"Für {self.glob} wurde {', '.join(items)} gefunden", True))
            result.successful = True

        os.chdir(cwd)

        if self.options.get('storage'):
            self.storage[self.options['storage']] = items if result.successful else []

        if self.options.get('storage_error'):
            self.storage[self.options['storage_error']] = items if not result.successful else []


class FileTest(BasicTest):
    """
    Test to check the status of a file
    """
    TYPE = "file"
    MODE_EXIST = "exist"  # Check for item existence
    MODE_NOT_EXIST = "not_exist"  # Check that the given items does not exist
    MODE_CONTAINS = "contains"  # Check if the given items contains the given content
    MODE_HASH = "hash"  # Check if the given items match the given hashes

    def __init__(self, options, storage: TestStorage):
        """
        Init a file based test with options
        :param options: Test configuration options - supported parameters besides BasicTest-options are:
            mode: str (Default MODE_EXIST) - Mode of operation
            items: str|list[str] - List of items to test with the given mode
            allow_other: bool (Default True) - Indicator if other items are allowed to be present
            contents: str|list[str]|dict[str, str] - File contents to match the content of files against (MODE_CONTAINS)
            hashes: str|list[str]|dict[str, str] - Hashes to test the files against (MODE_HASH)
        :param storage: Test interchange storage
        """
        super(FileTest, self).__init__(options, storage)
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
        success_items = []
        failure_items = []
        for item in self.items:
            success = os.path.exists(item) == desired_state
            message = f'{item} soll {"vorhanden" if desired_state else "nicht vorhanden"} sein'
            result.test_items.append((message, success))
            result.successful &= success
            if success:
                success_items.append(item)
            else:
                failure_items.append(item)

        self._update_storage(success_items, failure_items)

    def _run_contains_check(self, result):
        """
        Check if the files of this check have the desired content
        :param result: test result container
        :return: None
        """
        result.successful = True
        success_items = []
        failure_items = []
        for index, item in enumerate(self.items):
            message = f'Inhalt von {item} prüfen'
            desired_content = self.contents[item] if isinstance(self.contents, Mapping) else self.contents[index]
            try:
                with open(item, 'r') as fd:
                    content = fd.read()
                    success = re.search(desired_content, content, re.MULTILINE) is not None

                result.test_items.append((message, success))
                result.successful &= success
                if success:
                    success_items.append(item)
                else:
                    failure_items.append(item)

            except FileNotFoundError:
                result.test_items.append((message, 'DATEI nicht gefunden'))
                result.successful = False
                failure_items.append(item)
            except IsADirectoryError:
                result.test_items.append((message, 'Objekt ist ein VERZEICHNIS'))
                result.successful = False
                failure_items.append(item)
            except PermissionError:
                result.test_items.append((message, 'KEINE ZUGRIFFSBERECHTIGUNG'))
                result.successful = False
                failure_items.append(item)

        self._update_storage(success_items, failure_items)

    def _run_hash_check(self, result):
        """
        Check if the files of this check have the desired has value
        :param result: test result container
        :return: None
        """
        result.successful = True
        success_items = []
        failure_items = []
        for index, item in enumerate(self.items):
            sha1 = hashlib.sha1()
            desired_hash = self.hashes[item] if isinstance(self.hashes, Mapping) else self.hashes[index]
            desired_hash = utils.ensure_list(desired_hash)
            message = f'Hash-Test von {item} auf {desired_hash}'
            if os.path.exists(item) and os.path.isfile(item):
                with open(item, 'rb') as f:
                    while True:
                        data = f.read(65536)
                        if not data:
                            break

                        sha1.update(data)

                h = sha1.hexdigest()
                success = h in desired_hash
                result.test_items.append((message, success))
                result.successful &= success
                if success:
                    success_items.append(item)
                else:
                    failure_items.append(item)
            else:
                result.test_items.append((message, 'Objekt NICHT GEFUNDEN'))
                result.successful = False
                failure_items.append(item)

        self._update_storage(success_items, failure_items)

    def _update_storage(self, success_items, failure_items):
        """
        Update the storage to publish matched items
        :param success_items: Successfully detected items
        :param failure_items: Failed to locate items
        :return:
        """
        if self.options.get('storage'):
            self.storage[self.options['storage']] = success_items

        if self.options.get('storage_error'):
            self.storage[self.options['storage_error']] = failure_items

class CommandTest(BasicTest):
    """
    Test by executing a command
    """
    TYPE = "command"

    COMMAND_OPTION_PREFIX_GLOB = "__glob:"
    COMMAND_OPTION_PREFIX_STORAGE = "__storage:"
    COMMAND_OPTION_PREFIX_PATTERN = "__pattern:"

    DEFAULT_TIMEOUT = 60

    UNICODE_CHARS_REMOVE_STRING = ''.join(map(chr, itertools.chain(range(0x00, 0x09), range(0x0b, 0x20), range(0x7f, 0xa0))))
    UNICODE_CHARS_REMOVE_EXPRESSION = re.compile('[%s]' % re.escape(UNICODE_CHARS_REMOVE_STRING))

    def __init__(self, options, storage: TestStorage):
        """
        Init a command execution based test with options
        :param options: Test configuration options - supported parameters besides BasicTest-options are:
            return_code: int|list[int] - Return code or list of return codes to accept as success (optional)
            command: str|list[str] - Command to be executed with parameters
            timeout: int - Command timeout before to kill the application because of a hang
            input: str - Input to provide to the command
            output: str - Regular expression of required output (optional) - this is tested with re.search
            output_match: str - Regular expression of required output (optional) - this is tested with re.match
            output_max_length: int - Maximum number of characters for the output (Default 256 kB)
            error: str - Regular expression of required error output (optional) - this is tested with re.search
            error_match: str - Regular expression of required error output (optional) - this is tested with re.match
            error_max_length: int - Maximum number of characters for the output (Default 256 kB)
        :param storage: Test interchange storage
        """
        super(CommandTest, self).__init__(options, storage)

        if 'command' not in options:
            raise Exception("Command must be supplied for the test")

        self.timeout = self.options.get('timeout', -1)
        self.command = utils.ensure_list(options['command'])
        self.output_max_length = self.options.get('output_max_length', 256 * 1024)
        self.clear_output = self.options.get('clear_output', False)
        self.error_max_length = self.options.get('error_max_length', 256 * 1024)
        self.clear_error = self.options.get('clear_error', False)

    @property
    def command_invocation(self) -> str:
        """
        Return the printable command
        :return: command print string
        """
        return " ".join(self._apply_replacements(self.command))

    def _apply_replacements(self, command: list[str]) -> list[str]:
        """
        Apply any placeholders replacements in the command string
        :param command: Command to process
        :return: Updated command record
        """
        result = []

        for item in command:
            if item.startswith(self.COMMAND_OPTION_PREFIX_GLOB):
                item = item[len(self.COMMAND_OPTION_PREFIX_GLOB):]
                matches = glob.glob(item)
                result += matches
            elif item.startswith(self.COMMAND_OPTION_PREFIX_STORAGE):
                key = item[len(self.COMMAND_OPTION_PREFIX_STORAGE):]
                if key.startswith(self.COMMAND_OPTION_PREFIX_PATTERN):
                    key = key[len(self.COMMAND_OPTION_PREFIX_PATTERN):]
                    pattern, key = key.split(":", 1)
                else:
                    pattern = None

                matches = utils.ensure_list(self.storage.get(key, []))
                if pattern:
                    matches = list(map(lambda x: pattern.format(item=x), matches))

                result += matches
            else:
                result.append(item)

        return result

    def prepare_command(self, command: list[str]) -> list[str]:
        """
        Pre-process command and options and allow derived classes to manipulate the command string
        :param command: Configuration supplied command string
        :return: Fixed command string
        """
        return self._apply_replacements(command)

    @staticmethod
    def set_working_directory(directory: str):
        """
        Set the working directory of the command
        :param directory: Desired working directory
        """
        os.chdir(directory)

    @staticmethod
    def filter_non_printable(s):
        """
        Filter unicode output from unprintable strings
        :param s: Input string or bytes
        :return: Result string
        """
        if not s:
            return ''
        elif type(s) == bytes:
            s = s.decode("utf-8", errors="ignore")

        return CommandTest.UNICODE_CHARS_REMOVE_EXPRESSION.sub('', s)

    def run(self, result: TestStepResult):
        """
        Execute the test
        :param result: Container to write the result of the test to
        :return: test result
        """

        result.successful = True
        pid = 0
        try:
            command = self.prepare_command(self.command)
            if self.options.get('show_command', True):
                result.additional_records.append(('Kommandozeile', self.command_invocation))

            if self.options.get('working_directory'):
                self.set_working_directory(self.options['working_directory'])

            timeout = self.DEFAULT_TIMEOUT if self.timeout is None or self.timeout < 0 else self.timeout
            input_data = self.options.get('input', None)
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       stdin=subprocess.PIPE)

            pid = process.pid
            if input_data is not None:
                if isinstance(input_data, str):
                    process.stdin.write(input_data.encode('utf-8'))
                else:
                    for input_config in input_data:
                        process.stdin.write(input_config.get('data').encode('utf-8'))
                        process.stdin.flush()
                        time.sleep(input_config.get('sleep', 0))

            output, error = process.communicate(timeout=timeout)
            result.output = CommandTest.filter_non_printable(output)
            result.error = CommandTest.filter_non_printable(error)
            result.return_code = process.returncode

            # Check desired output on all channels
            for key, title_public, title_hidden, target, f in [
                ('output', 'Ausgabe enthält String', 'Ausgabe ist korrekt', result.output, re.search),
                ('output_match', 'Ausgabe passt auf', 'Ausgabe ist korrekt', result.output, re.match),
                ('error', 'Fehler-Ausgabe enthält String', 'Fehler-Ausgabe ist korrekt', result.error, re.search),
                ('error_match', 'Fehler-Ausgabe passt auf', 'Fehler-Ausgabe ist korrekt', result.error, re.match)
            ]:
                if self.options.get(key, None) is not None:
                    success = f(self.options[key], target, re.MULTILINE) is not None
                    if self.options.get('show_expected_output', False):
                        result.test_items.append((f'{title_public} `{self.options[key]}`', success))
                    else:
                        result.test_items.append((title_hidden, success))

                    result.successful &= success

            if self.options.get('return_code', None) is not None:
                codes = utils.ensure_list(self.options['return_code'])
                success = result.return_code in codes
                result.test_items.append((f'Rückgabe-Code ist `{" oder ".join(map(str, codes))}`', success))
                result.successful &= success

        except subprocess.TimeoutExpired as e:
            result.output = CommandTest.filter_non_printable(e.stdout)
            result.error = CommandTest.filter_non_printable(e.stderr)
            result.error += "\nAbbruch nach Überschreitung des Zeitlimits"
            result.successful = False
            self.kill(pid)

        except subprocess.CalledProcessError as e:
            result.output = CommandTest.filter_non_printable(e.stdout)
            result.error = CommandTest.filter_non_printable(e.stderr)
            result.error += "\nAbbruch nach Fehler beim Aufruf des Befehls"
            result.successful = False
            self.kill(pid)

        finally:
            if len(result.output) > self.output_max_length:
                result.output = result.output[:self.output_max_length] + "<TRUNCATED>"

            if len(result.error) > self.error_max_length:
                result.error = result.error[:self.error_max_length] + "<TRUNCATED>"

            if self.clear_output:
                result.output = "<AUSGABE WIRD NICHT ANGEZEIGT>"

            if self.clear_error:
                result.error = "<FEHLER-AUSGABE WIRD NICHT ANGEZEIGT>"

    def kill(self, pid):
        """
        Kill and cleanup the process after failure
        :param pid: process id to kill
        """
        pass


class DockerCommandTest(CommandTest):
    """
    Test by executing a command
    """
    TYPE = "docker"

    def __init__(self, options, storage: TestStorage):
        """
        Init a command execution based test with options
        :param options: Test configuration options - supported parameters besides CommandTest-options are:
            image: str - Name of the docker image to run
            repo_volume_path: str - Path where to mount to repository volume to the container (Defaults to repo)
        :param storage: Test interchange storage
        """
        if 'image' not in options:
            raise Exception("Docker image must be supplied for the test")

        self.volume = options.get('repo_volume_path', '/repo')

        # Determine random name
        self.container_name = "".join([random.choice(string.hexdigits) for _ in range(32)])
        if 'command' not in options:
            options['command'] = []

        super(DockerCommandTest, self).__init__(options, storage)

    def prepare_command(self, command: list[str]) -> list[str]:
        """
        Pre-process command and options and allow derived classes to manipulate the command string
        :param command: Configuration supplied command string
        :return: Fixed command string
        """
        # Build basic docker command
        volume = f".:{self.volume}"
        command = ['docker', 'run', '-i', '--name', self.container_name, '--rm', '--network=none', '-v', volume ]

        if self.options.get('working_directory'):
            command += [ '-w', self.options['working_directory'] ]

        # Append image to start
        command.append(self.options['image'])

        # If a special command is given use this instead of the container command
        if len(self.options.get('command', [])) > 0:
            command += super(DockerCommandTest, self).prepare_command(self.options['command'])

        return command

    @staticmethod
    def set_working_directory(directory: str):
        """
        Set the working directory of the command
        :param directory: Desired working directory
        """
        # Working directory is set through command line options
        pass

    def kill(self, pid):
        os.kill(pid, signal.SIGKILL)
        subprocess.run(['docker', 'pause', self.container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'kill', '-s', '9', self.container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)