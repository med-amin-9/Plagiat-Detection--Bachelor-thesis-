import toml
import sys
import os

from toml import TomlDecodeError

from tester import ExerciseTester


def get_configuration_paths() -> list[str]:
    """
    Returns a list of configuration paths to look for configuration files
    :return: List of paths to check
    """
    configuration_paths = []
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        configuration_paths.append(sys.argv[1])

    configuration_paths.append(os.path.join(os.getcwd(), "exercise-tester.toml"))

    if os.environ.get("HOME", None) is not None:
        configuration_paths.append(os.path.join(os.environ["HOME"], ".exercise-tester.rc"))

    configuration_paths.append("/etc/default/exercise-tester.conf")
    return configuration_paths


if __name__ == "__main__":
    configs = []
    for configuration_path in get_configuration_paths():
        if os.path.isfile(configuration_path):
            try:
                config = toml.load(configuration_path)
                configs.append(config)
            except TomlDecodeError:
                print("File %s is not a valid toml" % configuration_path)

    tester = ExerciseTester(configs)
    tester.run()
