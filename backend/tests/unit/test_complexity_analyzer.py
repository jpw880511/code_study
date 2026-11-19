import pytest
from sqlalchemy import CheckConstraint, Table
from src.models import UploadedCode
from src.services.code_analysis import complexity_analyzer
from src.services.code_analysis.complexity_analyzer import (
    ADVANCED,
    BEGINNER,
    INTERMEDIATE,
    LEVELS,
    ComplexityReport,
    FileMetrics,
    assess,
    classify_level,
    measure_source,
)

# ----------------------------------------------------------- the three levels


def test_the_levels_are_the_ones_the_database_accepts() -> None:
    table = UploadedCode.__table__
    assert isinstance(table, Table)
    checks = {c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
    assert LEVELS == (BEGINNER, INTERMEDIATE, ADVANCED)
    for level in LEVELS:
        assert f"'{level}'" in checks["uploaded_code_complexity_level_check"]


@pytest.mark.parametrize(
    ("lines", "functions", "depth", "level"),
    [
        (0, 0, 0, BEGINNER),
        (100, 5, 4, BEGINNER),  # every metric exactly at the beginner ceiling
        (101, 0, 0, INTERMEDIATE),
        (0, 6, 0, INTERMEDIATE),
        (0, 0, 5, INTERMEDIATE),
        (300, 15, 6, INTERMEDIATE),  # every metric exactly at the advanced threshold
        (301, 0, 0, ADVANCED),
        (0, 16, 0, ADVANCED),
        (0, 0, 7, ADVANCED),
        (500, 40, 9, ADVANCED),
    ],
)
def test_the_level_is_set_by_the_most_demanding_metric(
    lines: int, functions: int, depth: int, level: str
) -> None:
    assert classify_level(lines, functions, depth) == level


# --------------------------------------------------------------------- Python

PYTHON = """import os

class A:
    def method(self, x):
        for i in range(x):
            if i % 2:
                print("def not_a_function(): {")  # def fake():
        return lambda y: y

def top():
    return 1
"""


def test_python_counts_lines_functions_and_indentation_depth() -> None:
    assert measure_source(PYTHON, "python") == FileMetrics(
        language="python", lines=9, functions=2, max_depth=4
    )


def test_python_ignores_deep_indentation_inside_a_docstring() -> None:
    source = (
        "def f():\n"
        '    """\n'
        "            deeply indented text\n"
        "                even deeper\n"
        '    """\n'
        "    return 1\n"
    )
    assert measure_source(source, "python").max_depth == 1


def test_python_counts_async_functions() -> None:
    assert (
        measure_source("async def a():\n    pass\n\ndef b():\n    pass\n", "python").functions == 2
    )


def test_python_with_a_syntax_error_keeps_what_was_measured_before_it() -> None:
    metrics = measure_source("def f():\n    if x:\n        return (\n", "python")
    assert metrics.functions == 1
    assert metrics.max_depth == 2


def test_python_with_inconsistent_indentation_does_not_raise() -> None:
    metrics = measure_source("if x:\n        a = 1\n    b = 2\n", "python")
    assert metrics.max_depth == 1


def test_a_flat_python_script_has_no_depth() -> None:
    assert measure_source("a = 1\nb = 2\n", "python") == FileMetrics("python", 2, 0, 0)


# --------------------------------------------------------- brace languages

JAVASCRIPT = """function a(x) { return x; }
const b = (x) => x + 1;
const c = function (x) { return x; };
class K { method(x) { if (x) { return "function fake() {"; } } }
// function commented() {}
arr.map((v) => v * 2);
"""


def test_javascript_counts_function_keywords_and_arrows_but_not_text() -> None:
    # Class methods are not found (Pygments does not tag them), so this is a lower bound.
    assert measure_source(JAVASCRIPT, "javascript") == FileMetrics("javascript", 6, 4, 3)


def test_typescript_is_measured_like_javascript() -> None:
    source = (
        "function a(x: number): number { return x; }\n"
        "const b = (x: number): number => x + 1;\n"
        "interface I { m(): void; }\n"
        "class K { method(x: number) { return x; } }\n"
    )
    assert measure_source(source, "typescript") == FileMetrics("typescript", 4, 2, 2)


JAVA = """public class Main {
    private int x;
    public static void main(String[] args) {
        for (int i = 0; i < 3; i++) {
            if (i > 1) { System.out.println("{ not a block"); }
        }
    }
    int helper(int a, int b) { return a + b; }
}
"""


def test_java_counts_methods_and_block_depth() -> None:
    assert measure_source(JAVA, "java") == FileMetrics("java", 9, 2, 4)


def test_c_counts_function_definitions() -> None:
    source = (
        "#include <stdio.h>\n"
        "static int add(int a, int b) { return a + b; }\n"
        "int main(void) {\n"
        '    if (1) { printf("{ text }"); }\n'
        "    return 0;\n"
        "}\n"
    )
    assert measure_source(source, "c") == FileMetrics("c", 6, 2, 2)


def test_cpp_counts_function_definitions() -> None:
    source = "int main() {\n    if (1) {\n        return 0;\n    }\n}\nvoid f() {}\n"
    assert measure_source(source, "cpp") == FileMetrics("cpp", 6, 2, 2)


def test_css_has_block_depth_but_no_functions() -> None:
    source = ".a { color: red; }\n@media (x) { .b { margin: 0; } }\n"
    assert measure_source(source, "css") == FileMetrics("css", 2, 0, 2)


def test_a_stray_closing_brace_does_not_make_the_depth_negative() -> None:
    assert measure_source("}\n}\nint main() { }\n", "c").max_depth == 1


# ------------------------------------------------------- everything else


def test_markup_and_unmeasured_languages_only_get_a_line_count() -> None:
    html = "<html>\n  <body>\n    <p>hi</p>\n  </body>\n</html>\n"
    assert measure_source(html, "html") == FileMetrics("html", 5, 0, 0)
    assert measure_source("puts 'hi'\n\nputs 'bye'\n", "ruby") == FileMetrics("ruby", 2, 0, 0)


def test_empty_and_blank_content_has_no_lines() -> None:
    assert measure_source("", "python") == FileMetrics("python", 0, 0, 0)
    assert measure_source("\n   \n\t\r\n", "java") == FileMetrics("java", 0, 0, 0)


def test_windows_line_endings_are_counted_like_unix_ones() -> None:
    assert measure_source("a = 1\r\n\r\nb = 2\r\n", "python").lines == 2


def test_only_the_start_of_a_huge_file_is_analysed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(complexity_analyzer, "MAX_ANALYZED_CHARS", 40)
    source = "function a() {}\n// " + "x" * 60 + "\nfunction b() {}\n"
    metrics = measure_source(source, "javascript")
    assert metrics.lines == 3  # lines are counted over the whole file
    assert metrics.functions == 1  # the second function lies beyond the cap


# --------------------------------------------------------------- assessment


def test_an_upload_without_files_is_beginner_with_zero_everything() -> None:
    assert assess([]) == ComplexityReport(BEGINNER, 0, 0, 0, 0)


def test_files_add_up_and_the_deepest_one_counts() -> None:
    files = [FileMetrics("python", 60, 3, 2), FileMetrics("javascript", 50, 4, 5)]
    assert assess(files) == ComplexityReport(
        level=INTERMEDIATE, total_lines=110, code_lines=110, function_count=7, max_depth=5
    )


def test_documentation_counts_as_lines_but_not_as_complexity() -> None:
    files = [FileMetrics("python", 40, 2, 2), FileMetrics("markdown", 900, 0, 0)]
    report = assess(files)
    assert report.total_lines == 940
    assert report.code_lines == 40
    assert report.level == BEGINNER


def test_text_and_unknown_files_are_not_code_either() -> None:
    report = assess([FileMetrics("text", 500, 0, 0), FileMetrics("unknown", 500, 0, 0)])
    assert (report.total_lines, report.code_lines, report.level) == (1000, 0, BEGINNER)


def test_many_small_files_can_add_up_to_advanced() -> None:
    files = [FileMetrics("python", 40, 1, 1) for _ in range(8)]
    report = assess(files)
    assert (report.code_lines, report.function_count) == (320, 8)
    assert report.level == ADVANCED


def test_a_deeply_nested_file_makes_the_whole_upload_advanced() -> None:
    files = [FileMetrics("python", 10, 1, 1), FileMetrics("python", 10, 1, 7)]
    assert assess(files).level == ADVANCED


def test_assess_accepts_any_iterable() -> None:
    assert assess(FileMetrics("python", 1, 0, 0) for _ in range(3)).code_lines == 3
