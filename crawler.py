"""
AMEVA-Crawler Engine
Zero-dependency HTTP client, HTML parser, link extractor, and diff analyzer using standard library.
"""
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time
import json
import hashlib
import re
import difflib
from html.parser import HTMLParser
from config import DEFAULT_USER_AGENT, DEFAULT_TIMEOUT_SEC, DEFAULT_MAX_DIFF_LINES, DEFAULT_MAX_NEW_LINKS
import db

class SmartHTMLParser(HTMLParser):
    """
    Extracts readable text and normalized links from HTML while stripping
    scripts, styles, and boilerplate tags.
    """
    def __init__(self, base_url=""):
        super().__init__()
        self.base_url = base_url
        self.ignore_tags = {'script', 'style', 'noscript', 'svg', 'canvas', 'template'}
        self.block_tags = {'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr', 'article', 'section'}
        self.tag_stack = []
        
        self.text_chunks = []
        self.links = []
        
        self._current_a_href = None
        self._current_a_text = []

    def handle_starttag(self, tag, attrs):
        self.tag_stack.append(tag)
        attrs_dict = dict(attrs)
        
        if tag == 'a':
            raw_href = attrs_dict.get('href', '').strip()
            if raw_href and not raw_href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                # Normalize relative URL to absolute URL
                try:
                    full_url = urllib.parse.urljoin(self.base_url, raw_href)
                    self._current_a_href = full_url
                    self._current_a_text = []
                except Exception:
                    self._current_a_href = None
            else:
                self._current_a_href = None

    def handle_endtag(self, tag):
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()
            
        if tag == 'a' and self._current_a_href:
            link_text = " ".join("".join(self._current_a_text).split()).strip()
            if not link_text:
                link_text = self._current_a_href
            self.links.append({
                "text": link_text,
                "href": self._current_a_href
            })
            self._current_a_href = None
            self._current_a_text = []
            
        if tag in self.block_tags:
            self.text_chunks.append("\n")

    def handle_data(self, data):
        # Ignore text inside ignored tags
        if any(ignored in self.tag_stack for ignored in self.ignore_tags):
            return
            
        text = data.strip()
        if text:
            self.text_chunks.append(data)
            if self._current_a_href is not None:
                self._current_a_text.append(data)

    def get_clean_text(self):
        """Return formatted plain text."""
        raw_text = "".join(self.text_chunks)
        # Collapse excessive blank lines
        lines = [line.strip() for line in raw_text.splitlines()]
        cleaned_lines = [l for l in lines if l]
        return "\n".join(cleaned_lines)

    def get_links(self):
        """Return unique links preserving order."""
        seen_hrefs = set()
        unique_links = []
        for item in self.links:
            if item["href"] not in seen_hrefs:
                seen_hrefs.add(item["href"])
                unique_links.append(item)
        return unique_links


def compute_content_hash(text):
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()


def fetch_url(target):
    """
    Perform HTTP GET or POST request using urllib.
    Returns: dict with status_code, content, response_time_ms, error
    """
    url = target.get("url", "").strip()
    method = target.get("method", "GET").upper()
    headers_raw = target.get("headers", "{}")
    body_data = target.get("body", "")
    content_type = target.get("content_type", "application/json")
    
    # Custom headers
    headers = {
        "User-Agent": db.get_setting("global_user_agent") or DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    if isinstance(headers_raw, str) and headers_raw.strip():
        try:
            custom_headers = json.loads(headers_raw)
            if isinstance(custom_headers, dict):
                headers.update(custom_headers)
        except Exception as e:
            db.log_system("WARN", f"Failed to parse custom headers for {target.get('name')}: {e}")

    # Prepare POST data if needed
    data_bytes = None
    if method == "POST":
        headers["Content-Type"] = content_type
        if body_data:
            if isinstance(body_data, str):
                data_bytes = body_data.encode('utf-8')
            elif isinstance(body_data, dict):
                if "json" in content_type:
                    data_bytes = json.dumps(body_data).encode('utf-8')
                else:
                    data_bytes = urllib.parse.urlencode(body_data).encode('utf-8')

    # SSL Context - Allow flexible SSL connections
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    start_time = time.time()
    try:
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        timeout = float(db.get_setting("crawler_timeout", str(DEFAULT_TIMEOUT_SEC)))
        
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as response:
            status_code = response.status
            content_bytes = response.read()
            
            # Detect charset
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                content_str = content_bytes.decode(charset)
            except (UnicodeDecodeError, LookupError):
                try:
                    content_str = content_bytes.decode("utf-8", errors="replace")
                except Exception:
                    content_str = content_bytes.decode("cp949", errors="replace")
                    
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "success": True,
                "status_code": status_code,
                "content": content_str,
                "response_time_ms": elapsed_ms,
                "error": None
            }
            
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        err_content = ""
        try:
            err_content = e.read().decode('utf-8', errors='ignore')
        except Exception:
            pass
        return {
            "success": False,
            "status_code": e.code,
            "content": err_content,
            "response_time_ms": elapsed_ms,
            "error": f"HTTP Error {e.code}: {e.reason}"
        }
    except urllib.error.URLError as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "status_code": 0,
            "content": "",
            "response_time_ms": elapsed_ms,
            "error": f"URL Connection Error: {e.reason}"
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "status_code": 0,
            "content": "",
            "response_time_ms": elapsed_ms,
            "error": f"Unexpected Exception: {str(e)}"
        }


def analyze_diff(old_text, new_text, old_links, new_links):
    """
    Compare previous crawl state with current crawl state.
    Returns: dict with is_changed, diff_summary, new_links, removed_links, added_lines, removed_lines
    """
    old_lines = old_text.splitlines() if old_text else []
    new_lines = new_text.splitlines() if new_text else []
    
    # 1. Compare Links
    old_href_map = {item.get("href"): item.get("text", "") for item in (old_links or []) if item.get("href")}
    new_href_map = {item.get("href"): item.get("text", "") for item in (new_links or []) if item.get("href")}
    
    brand_new_links = []
    for href, text in new_href_map.items():
        if href not in old_href_map:
            brand_new_links.append({"text": text, "href": href})
            
    removed_links = []
    for href, text in old_href_map.items():
        if href not in new_href_map:
            removed_links.append({"text": text, "href": href})

    # 2. Text Diff
    added_lines = []
    removed_lines = []
    
    diff_gen = difflib.unified_diff(old_lines, new_lines, lineterm='', n=0)
    for line in diff_gen:
        if line.startswith('+') and not line.startswith('+++'):
            clean_l = line[1:].strip()
            if clean_l and clean_l not in added_lines:
                added_lines.append(clean_l)
        elif line.startswith('-') and not line.startswith('---'):
            clean_l = line[1:].strip()
            if clean_l and clean_l not in removed_lines:
                removed_lines.append(clean_l)

    is_changed = bool(brand_new_links or removed_links or added_lines or removed_lines)
    
    # Build human-readable summary
    summary_parts = []
    if brand_new_links:
        summary_parts.append(f"🔗 신규 링크 {len(brand_new_links)}건 발견")
        for item in brand_new_links[:DEFAULT_MAX_NEW_LINKS]:
            summary_parts.append(f"  + [{item['text']}]({item['href']})")
        if len(brand_new_links) > DEFAULT_MAX_NEW_LINKS:
            summary_parts.append(f"  ... 외 {len(brand_new_links) - DEFAULT_MAX_NEW_LINKS}건")

    if added_lines:
        summary_parts.append(f"➕ 추가된 내용 ({len(added_lines)}줄)")
        for l in added_lines[:DEFAULT_MAX_DIFF_LINES]:
            summary_parts.append(f"  + {l}")
        if len(added_lines) > DEFAULT_MAX_DIFF_LINES:
            summary_parts.append(f"  ... 외 {len(added_lines) - DEFAULT_MAX_DIFF_LINES}줄")

    if removed_lines:
        summary_parts.append(f"➖ 삭제된 내용 ({len(removed_lines)}줄)")
        for l in removed_lines[:15]:
            summary_parts.append(f"  - {l}")
        if len(removed_lines) > 15:
            summary_parts.append(f"  ... 외 {len(removed_lines) - 15}줄")

    diff_summary = "\n".join(summary_parts) if summary_parts else "내용 변경 없음"

    return {
        "is_changed": is_changed,
        "diff_summary": diff_summary,
        "new_links": brand_new_links,
        "removed_links": removed_links,
        "added_lines": added_lines,
        "removed_lines": removed_lines
    }


def parse_content_and_links(raw_content, base_url=""):
    """
    Intelligently parse raw HTTP response content (JSON or HTML).
    Returns: (extracted_text, extracted_links)
    """
    raw_str = (raw_content or "").strip()
    
    # 1. Try JSON parsing
    if raw_str.startswith(('{', '[')):
        try:
            data = json.loads(raw_str)
            text_lines = []
            links = []
            
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                if 'list' in data and isinstance(data['list'], list):
                    items = data['list']
                elif 'data' in data and isinstance(data['data'], list):
                    items = data['data']
                elif 'items' in data and isinstance(data['items'], list):
                    items = data['items']
                elif 'results' in data and isinstance(data['results'], list):
                    items = data['results']
                    
            if items:
                for it in items:
                    if isinstance(it, dict):
                        title = it.get('jobnoticeName') or it.get('title') or it.get('name') or it.get('subject') or ''
                        sn = it.get('jobnoticeSn') or it.get('id') or it.get('sn')
                        href = it.get('url') or it.get('href') or it.get('link')
                        if not href and sn and 'recruiter.co.kr' in base_url:
                            href = urllib.parse.urljoin(base_url, f'/app/jobnotice/view?jobnoticeSn={sn}')
                        elif href:
                            href = urllib.parse.urljoin(base_url, str(href))
                            
                        line_parts = []
                        if title:
                            line_parts.append(str(title))
                        for k in ['recruitClassName', 'recruitTypeName', 'receiptState', 'category', 'status', 'dept', 'location']:
                            if it.get(k):
                                line_parts.append(f'[{it.get(k)}]')
                        if line_parts:
                            text_lines.append(' '.join(line_parts))
                        if title and href:
                            links.append({'text': str(title), 'href': str(href)})
                            
            if not text_lines:
                text_lines.append(json.dumps(data, ensure_ascii=False, indent=2))
                
            return '\n'.join(text_lines), links
        except Exception:
            pass

    # 2. HTML parsing via SmartHTMLParser
    parser = SmartHTMLParser(base_url=base_url)
    try:
        parser.feed(raw_content)
        extracted_text = parser.get_clean_text()
        extracted_links = parser.get_links()
    except Exception as e:
        extracted_text = re.sub(r'<[^>]+>', ' ', raw_content)
        extracted_lines = [l.strip() for l in extracted_text.splitlines() if l.strip()]
        extracted_text = '\n'.join(extracted_lines)
        extracted_links = []
        
    return extracted_text, extracted_links


def execute_crawl(target_id):
    """
    Execute crawling on a specific target ID, process changes, and trigger notification if changed.
    """
    target = db.get_target_by_id(target_id)
    if not target:
        db.log_system("ERROR", f"Target ID {target_id} not found.")
        return None

    db.log_system("INFO", f"[{target['name']}] 크롤링 시작: {target['url']}")
    
    # 1. Fetch content
    resp = fetch_url(target)
    
    # Handle fetch failure
    if not resp["success"]:
        db.log_system("ERROR", f"[{target['name']}] 크롤링 실패: {resp['error']}")
        db.update_target_crawl_status(target_id, resp["status_code"], "", False, has_error=True)
        db.add_crawl_history({
            "target_id": target_id,
            "status_code": resp["status_code"],
            "response_time_ms": resp["response_time_ms"],
            "is_changed": False,
            "error_message": resp["error"]
        })
        return {
            "success": False,
            "target": target,
            "error": resp["error"]
        }

    raw_html = resp["content"]
    
    # 2. Intelligently parse content (JSON API or HTML) & extract text & links
    extracted_text, extracted_links = parse_content_and_links(raw_html, base_url=target["url"])

    # Filter rule if specified (Regex or Keyword)
    rule = target.get("selector_rule", "").strip()
    if rule:
        try:
            pattern = re.compile(rule, re.IGNORECASE | re.MULTILINE)
            matches = pattern.findall(extracted_text)
            if matches:
                extracted_text = "\n".join([str(m) for m in matches])
        except Exception as e:
            db.log_system("WARN", f"Selector rule regex failed on {target['name']}: {e}")

    content_hash = compute_content_hash(extracted_text)
    
    # 3. Compare with previous successful crawl
    prev_crawl = db.get_latest_successful_crawl(target_id)
    
    is_first_crawl = prev_crawl is None
    is_changed = False
    diff_result = {
        "is_changed": False,
        "diff_summary": "최초 등록 크롤링 (기준 데이터 생성 완료)",
        "new_links": extracted_links,
        "removed_links": [],
        "added_lines": [],
        "removed_lines": []
    }
    
    if not is_first_crawl:
        prev_hash = prev_crawl.get("content_hash", "")
        # Fast hash comparison
        if prev_hash != content_hash:
            prev_links = []
            try:
                prev_links = json.loads(prev_crawl.get("extracted_links") or "[]")
            except Exception:
                pass
            diff_result = analyze_diff(
                prev_crawl.get("extracted_text", ""),
                extracted_text,
                prev_links,
                extracted_links
            )
            is_changed = diff_result["is_changed"]
        else:
            is_changed = False
            diff_result["diff_summary"] = "이전과 동일함 (변화 없음)"
    else:
        # First time
        is_changed = False
        db.log_system("INFO", f"[{target['name']}] 최초 크롤링 완료 (링크 {len(extracted_links)}개 수집)")

    # 4. Save history & Update target state
    db.add_crawl_history({
        "target_id": target_id,
        "status_code": resp["status_code"],
        "response_time_ms": resp["response_time_ms"],
        "is_changed": is_changed,
        "content_hash": content_hash,
        "extracted_text": extracted_text,
        "extracted_links": json.dumps(extracted_links, ensure_ascii=False),
        "diff_summary": diff_result["diff_summary"],
        "new_links": json.dumps(diff_result["new_links"], ensure_ascii=False),
        "removed_links": json.dumps(diff_result["removed_links"], ensure_ascii=False),
        "error_message": ""
    })
    
    db.update_target_crawl_status(target_id, resp["status_code"], content_hash, is_changed, has_error=False)
    
    # 5. Send Telegram Notification & Tray Balloon if changed
    if is_changed:
        db.log_system("INFO", f"🔔 [{target['name']}] 사이트 변경 감지! 텔레그램 알림 발송 준비")
        import telegram_bot
        telegram_bot.notify_target_changed(target, diff_result, resp)
        
        # System Tray Balloon Notification
        try:
            from tray import global_tray_instance
            if global_tray_instance:
                new_links_count = len(diff_result.get("new_links", []))
                balloon_msg = f"[{target['name']}] 사이트 내용이 변경되었습니다!"
                if new_links_count > 0:
                    balloon_msg += f"\n신규 링크 {new_links_count}건 발견"
                global_tray_instance.show_balloon("AMEVA-Crawler 변경 감지", balloon_msg)
        except Exception:
            pass

    return {
        "success": True,
        "target": target,
        "status_code": resp["status_code"],
        "is_changed": is_changed,
        "diff": diff_result,
        "links_count": len(extracted_links)
    }
