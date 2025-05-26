import os
import shutil

def create_test_submissions():
    """Creates realistic test data for plagiarism detection"""
    
    test_dir = "test_submissions"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    # Test Case 1: 100% Identical (Clear Plagiarism)
    identical_code = """#include <stdio.h>
#include <stdlib.h>

int main() {
    int n, sum = 0;
    printf("Enter number: ");
    scanf("%d", &n);
    
    for(int i = 1; i <= n; i++) {
        sum += i;
    }
    
    printf("Sum: %d\\n", sum);
    return 0;
}"""
    
    identical_makefile = """CC=gcc
CFLAGS=-Wall -Wextra -std=c99
TARGET=main
SOURCE=main.c

$(TARGET): $(SOURCE)
\t$(CC) $(CFLAGS) -o $(TARGET) $(SOURCE)

clean:
\trm -f $(TARGET)"""

    # Create identical submissions
    for student in ["student_identical_1", "student_identical_2"]:
        os.makedirs(f"{test_dir}/{student}", exist_ok=True)
        with open(f"{test_dir}/{student}/main.c", "w") as f:
            f.write(identical_code)
        with open(f"{test_dir}/{student}/Makefile", "w") as f:
            f.write(identical_makefile)
    
    # Test Case 2: ~70% Similar (Suspicious)
    similar_code_1 = """#include <stdio.h>
#include <stdlib.h>

int main() {
    int number, total = 0;
    printf("Enter number: ");
    scanf("%d", &number);
    
    for(int i = 1; i <= number; i++) {
        total += i;
    }
    
    printf("Sum: %d\\n", total);
    return 0;
}"""
    
    similar_code_2 = """#include <stdio.h>
#include <stdlib.h>

int main() {
    int num, result = 0;
    printf("Please enter a number: ");
    scanf("%d", &num);
    
    // Calculate sum from 1 to num
    for(int j = 1; j <= num; j++) {
        result = result + j;
    }
    
    printf("The sum is: %d\\n", result);
    return 0;
}"""
    
    # Create similar submissions
    for i, code in enumerate([similar_code_1, similar_code_2], 1):
        student = f"student_similar_{i}"
        os.makedirs(f"{test_dir}/{student}", exist_ok=True)
        with open(f"{test_dir}/{student}/main.c", "w") as f:
            f.write(code)
        with open(f"{test_dir}/{student}/Makefile", "w") as f:
            f.write(identical_makefile)  # Same makefiles
    
    # Test Case 3: Completely Different (No Plagiarism)
    different_codes = [
        """#include <stdio.h>
int main() {
    char str[100];
    printf("Enter string: ");
    fgets(str, sizeof(str), stdin);
    printf("You entered: %s", str);
    return 0;
}""",
        """#include <stdio.h>
#include <math.h>
int main() {
    double radius, area;
    printf("Enter radius: ");
    scanf("%lf", &radius);
    area = 3.14159 * radius * radius;
    printf("Area: %.2f\\n", area);
    return 0;
}""",
        """#include <stdio.h>
int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int sum = 0;
    for(int i = 0; i < 5; i++) {
        sum += arr[i];
    }
    printf("Array sum: %d\\n", sum);
    return 0;
}"""
    ]
    
    # Create different submissions
    for i, code in enumerate(different_codes, 1):
        student = f"student_unique_{i}"
        os.makedirs(f"{test_dir}/{student}", exist_ok=True)
        with open(f"{test_dir}/{student}/main.c", "w") as f:
            f.write(code)
        with open(f"{test_dir}/{student}/Makefile", "w") as f:
            f.write(identical_makefile)  # Same makefiles to test extension filtering

    # Test Case 4: Completely Different (0% Similarity)
    zero_similarity_codes = [
        """#include <stdio.h>
        int main() {
            printf(\"This is a completely unique file.\n\");
            return 0;
        }""",
        """#include <stdio.h>
        int main() {
            printf(\"Another unique file with no shared content.\n\");
            return 0;
        }"""
    ]

    # Create submissions with 0% similarity
    for i, code in enumerate(zero_similarity_codes, 1):
        student = f"student_zero_similarity_{i}"
        os.makedirs(f"{test_dir}/{student}", exist_ok=True)
        with open(f"{test_dir}/{student}/main.c", "w") as f:
            f.write(code)

    print(f"Test data created in {test_dir}/")
    print("Expected results:")
    print("- student_identical_1 & student_identical_2: ~100% similarity")
    print("- student_similar_1 & student_similar_2: ~70% similarity") 
    print("- All Makefiles: 100% similarity (should be grouped separately)")
    print("- Unique students: <30% similarity with others")
    print("- Zero similarity test cases added: student_zero_similarity_1 & student_zero_similarity_2")

if __name__ == "__main__":
    create_test_submissions()