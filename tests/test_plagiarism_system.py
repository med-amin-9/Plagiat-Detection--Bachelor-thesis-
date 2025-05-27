import json
import subprocess
import sys
import os

def test_plagiarism_detection_pipeline():
    # Resolve full path to the test data creation script
    THIS_DIR = os.path.dirname(__file__)
    script_path = os.path.join(THIS_DIR, "utilis", "create_test_data.py")

    # Step 1: Create test data
    subprocess.run([sys.executable, script_path], check=True)
    
    # Step 2: Run the plagiarism detector with test config
    result_file = "plagiarism_results_test.json"
    if os.path.exists(result_file):
        os.remove(result_file)  # Clean old result

    subprocess.run([
        sys.executable, "runner.py", 
        "--plagiarism", 
        "--language", "c", 
        "test_config.toml"
    ], check=True)

    # Step 3: Locate the latest results file
    result_files = [f for f in os.listdir('.') if f.startswith('plagiarism_results_') and f.endswith('.json')]
    if not result_files:
        raise FileNotFoundError("No plagiarism results file found.")

    latest_result_file = max(result_files, key=os.path.getctime)

    # Step 4: Validate results
    with open(latest_result_file, "r") as f:
        results = json.load(f)

    # Map repository identifiers to student names
    repo_to_student = {
        "bcd98bbff80baf770cb1633ba9af6347": "student_identical_1",
        "8dbc506666724848367d3cfeeb391ba4": "student_identical_2",
        "b0d0b7a7c92d7d420ef859f71eeab044": "student_similar_1",
        "144c4a93d79a259472ea1572ef7a8727": "student_similar_2",
        "faa025cc9041347142611df3b29f5d87": "student_unique_1",
        "169eab1ba833ab12f3f5d8d069c83fc7": "student_unique_2",
        "e63a05e766595fd79e7cd9bebd5a6839": "student_unique_3"
    }

    # Update assertions to use mapped names
    assert any(
        repo_to_student[r["file_1"].split("/")[0]] == "student_identical_1" and
        repo_to_student[r["file_2"].split("/")[0]] == "student_identical_2" and
        r["similarity"] > 0.9
        for r in results
    ), "Identical plagiarism case not detected"

    assert any(
        (
            repo_to_student[r["file_1"].split("/")[0]] == "student_similar_1" and
            repo_to_student[r["file_2"].split("/")[0]] == "student_similar_2"
        ) or (
            repo_to_student[r["file_1"].split("/")[0]] == "student_similar_2" and
            repo_to_student[r["file_2"].split("/")[0]] == "student_similar_1"
        ) and 0.6 <= r["similarity"] <= 0.8
        for r in results
    ), "Similar plagiarism case not detected"

    print("Test finished successfully.")

if __name__ == "__main__":
    test_plagiarism_detection_pipeline()