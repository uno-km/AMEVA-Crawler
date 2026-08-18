"""
AMEVA-Crawler Test Suite
Unit tests for database, parser, diff analyzer, and scheduler.
"""
import unittest
import os
import json
import datetime
from crawler import SmartHTMLParser, analyze_diff, compute_content_hash
import db
from scheduler import CrawlerScheduler

class TestAMEVACrawler(unittest.TestCase):

    def setUp(self):
        # Initialize DB
        db.init_db()

    def test_database_crud(self):
        """Test target CRUD and history operations."""
        # 1. Create Target
        target_id = db.create_target({
            "name": "테스트 공고 사이트",
            "url": "https://example.com/test-notices",
            "method": "GET",
            "interval_type": "interval",
            "interval_value": "60"
        })
        self.assertIsNotNone(target_id)

        # 2. Read Target
        target = db.get_target_by_id(target_id)
        self.assertEqual(target["name"], "테스트 공고 사이트")
        self.assertEqual(target["method"], "GET")

        # 3. Update Target
        db.update_target(target_id, {
            "name": "테스트 공고 사이트 (수정됨)",
            "url": "https://example.com/test-notices-v2",
            "method": "POST",
            "headers": '{"X-Custom": "Test"}',
            "body": '{"page": 1}',
            "interval_type": "interval",
            "interval_value": "120"
        })
        updated = db.get_target_by_id(target_id)
        self.assertEqual(updated["name"], "테스트 공고 사이트 (수정됨)")
        self.assertEqual(updated["method"], "POST")

        # 4. Add History
        h_id = db.add_crawl_history({
            "target_id": target_id,
            "status_code": 200,
            "response_time_ms": 150,
            "is_changed": 1,
            "content_hash": "abc123hash",
            "extracted_text": "신규 공고가 등록되었습니다.",
            "diff_summary": "신규 공고 등록됨",
            "new_links": json.dumps([{"text": "2026 하반기 신입 채용", "href": "https://example.com/job/1"}])
        })
        self.assertIsNotNone(h_id)

        # 5. Get History
        histories = db.get_target_history(target_id)
        self.assertGreaterEqual(len(histories), 1)
        self.assertEqual(histories[0]["status_code"], 200)

        # 6. Delete Target
        db.delete_target(target_id)
        deleted = db.get_target_by_id(target_id)
        self.assertIsNone(deleted)

    def test_html_parser_and_link_extraction(self):
        """Test HTML clean text and link extraction."""
        html_sample = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>채용 공고 게시판</title>
            <style>body { color: red; }</style>
            <script>console.log("ignore me");</script>
        </head>
        <body>
            <header>헤더 영역</header>
            <h1>진행 중인 채용 공고</h1>
            <p>2026년도 하반기 신규 인재를 모집합니다.</p>
            <ul>
                <li><a href="/jobs/101">AI 엔지니어 채용</a></li>
                <li><a href="https://example.com/jobs/102">백엔드 개발자 채용</a></li>
                <li><a href="javascript:void(0)">무효 링크</a></li>
            </ul>
        </body>
        </html>
        """
        parser = SmartHTMLParser(base_url="https://example.com/notices")
        parser.feed(html_sample)
        
        clean_text = parser.get_clean_text()
        links = parser.get_links()

        # Check script and style stripped
        self.assertNotIn("console.log", clean_text)
        self.assertNotIn("color: red", clean_text)
        self.assertIn("진행 중인 채용 공고", clean_text)
        self.assertIn("2026년도 하반기 신규 인재를 모집합니다.", clean_text)

        # Check links
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["text"], "AI 엔지니어 채용")
        self.assertEqual(links[0]["href"], "https://example.com/jobs/101")
        self.assertEqual(links[1]["text"], "백엔드 개발자 채용")
        self.assertEqual(links[1]["href"], "https://example.com/jobs/102")

    def test_diff_analysis_engine(self):
        """Test text diff and brand new link identification."""
        old_text = "공지사항 1: 서비스 점검 안내"
        new_text = "공지사항 1: 서비스 점검 안내\n공지사항 2: 2026년 신규 서비스 오픈 안내"
        
        old_links = [{"text": "공지 1", "href": "https://example.com/notice/1"}]
        new_links = [
            {"text": "공지 1", "href": "https://example.com/notice/1"},
            {"text": "공지 2 (신규)", "href": "https://example.com/notice/2"}
        ]

        diff_res = analyze_diff(old_text, new_text, old_links, new_links)
        
        self.assertTrue(diff_res["is_changed"])
        self.assertEqual(len(diff_res["new_links"]), 1)
        self.assertEqual(diff_res["new_links"][0]["href"], "https://example.com/notice/2")
        self.assertEqual(len(diff_res["added_lines"]), 1)
        self.assertIn("2026년 신규 서비스 오픈 안내", diff_res["added_lines"][0])

    def test_scheduler_timing_rules(self):
        """Test scheduler interval and schedule evaluations."""
        scheduler = CrawlerScheduler()
        now = datetime.datetime(2026, 8, 18, 14, 30, 0)

        # Target never checked
        target_new = {"id": 999, "last_checked_at": None, "interval_type": "interval", "interval_value": "300"}
        self.assertTrue(scheduler._should_run_target(target_new, now))

        # Target interval 300s, checked 100s ago -> False
        target_recent = {
            "id": 999,
            "last_checked_at": (now - datetime.timedelta(seconds=100)).isoformat(),
            "interval_type": "interval",
            "interval_value": "300"
        }
        self.assertFalse(scheduler._should_run_target(target_recent, now))

        # Target interval 300s, checked 400s ago -> True
        target_due = {
            "id": 999,
            "last_checked_at": (now - datetime.timedelta(seconds=400)).isoformat(),
            "interval_type": "interval",
            "interval_value": "300"
        }
        self.assertTrue(scheduler._should_run_target(target_due, now))

    def test_parse_content_and_links_json(self):
        """Test intelligent JSON response parsing."""
        from crawler import parse_content_and_links
        json_sample = json.dumps({
            "list": [
                {
                    "jobnoticeName": "AI/Cloud Engineer",
                    "jobnoticeSn": 1001,
                    "recruitClassName": "Tech",
                    "receiptState": "접수중"
                }
            ]
        })
        text, links = parse_content_and_links(json_sample, base_url="https://ktds.recruiter.co.kr/app/jobnotice/list.json")
        self.assertIn("AI/Cloud Engineer", text)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["text"], "AI/Cloud Engineer")
        self.assertIn("jobnoticeSn=1001", links[0]["href"])

    def test_http_tester_engine(self):
        """Test HTTP request tester with mock and live options."""
        from crawler import test_http_request
        # Test with mock/known URL
        res = test_http_request("GET", "https://httpbin.org/get", params={"test": "123"}, timeout=5)
        # Verify structure
        self.assertIn("status_code", res)
        self.assertIn("response_time_ms", res)
        self.assertIn("response_headers", res)
        self.assertIn("extracted_text", res)
        self.assertIn("extracted_links", res)

if __name__ == "__main__":
    unittest.main()
