"""
Script chạy pytest và tự động xuất báo cáo kết quả kiểm thử ra file Excel/CSV.
Mở trực tiếp bằng Microsoft Excel (hỗ trợ hiển thị tiếng Việt UTF-8 chuẩn).
"""

import csv
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def run_tests_and_export():
    backend_dir = Path(__file__).resolve().parent
    xml_path = backend_dir / "test_results.xml"
    csv_path = backend_dir / "test_results.csv"

    print("🚀 Đang thực thi các testcase với pytest...")
    # Chạy pytest và xuất ra file XML trung gian
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "unit_tests/test_social_moderation_unit.py",
        f"--junitxml={xml_path}",
        "-q",
    ]

    result = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True)

    if not xml_path.exists():
        print("❌ Lỗi: Không thể sinh báo cáo XML từ pytest!")
        print(result.stderr or result.stdout)
        return

    print("📊 Đang phân tích kết quả và xuất ra file Excel (CSV)...")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    rows = []
    stt = 1

    for testsuite in root.iter("testsuite"):
        for testcase in testsuite.iter("testcase"):
            name = testcase.get("name", "")
            classname = testcase.get("classname", "")
            duration = testcase.get("time", "0")

            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")

            if failure is not None:
                status = "FAILED"
                detail = failure.text.strip().split("\n")[-1] if failure.text else "Failed"
            elif error is not None:
                status = "ERROR"
                detail = error.text.strip().split("\n")[-1] if error.text else "Error"
            elif skipped is not None:
                status = "SKIPPED"
                detail = skipped.get("message", "Skipped")
            else:
                status = "PASSED"
                detail = "Thành công"

            rows.append({
                "STT": stt,
                "Tập kiểm thử (File / Module)": classname,
                "Tên Test Case": name,
                "Kết quả": status,
                "Thời gian chạy (giây)": duration,
                "Chi tiết / Ghi chú": detail,
            })
            stt += 1

    # Ghi ra file CSV với mã hóa utf-8-sig để Excel mở chuẩn font tiếng Việt
    fieldnames = ["STT", "Tập kiểm thử (File / Module)", "Tên Test Case", "Kết quả", "Thời gian chạy (giây)", "Chi tiết / Ghi chú"]
    with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Dọn dẹp file XML tạm
    if xml_path.exists():
        xml_path.unlink()

    total = len(rows)
    passed = sum(1 for r in rows if r["Kết quả"] == "PASSED")
    failed = sum(1 for r in rows if r["Kết quả"] == "FAILED")

    print(f"✅ Hoàn thành! Đã xuất {total} testcase ra file: {csv_path.name}")
    print(f"   - Passed: {passed}/{total}")
    print(f"   - Failed: {failed}/{total}")
    print(f"👉 Bạn có thể nhấp đúp để mở file '{csv_path}' trực tiếp trong Microsoft Excel!")


if __name__ == "__main__":
    run_tests_and_export()
