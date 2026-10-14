"""Turn a JUnit XML report into a short Markdown summary: python summary.py report.xml"""
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
s = root if root.tag == "testsuite" else root.find("testsuite")
t, f, e, sk = (int(s.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
print("## DAQ testbench\n")
print("| total | passed | failed | errors | skipped |\n|---|---|---|---|---|")
print(f"| {t} | {t - f - e - sk} | {f} | {e} | {sk} |\n")
for tc in s.iter("testcase"):
    fail = tc.find("failure")
    if fail is not None:
        print(f"- FAIL `{tc.get('name')}`: {(fail.get('message') or '').splitlines()[0]}")
