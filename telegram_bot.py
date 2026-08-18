"""
AMEVA-Crawler Telegram Bot Integration Module
Pure standard library implementation of Telegram Bot API.
"""
import urllib.request
import urllib.parse
import urllib.error
import ssl
import json
import datetime
import db

def get_bot_token():
    """Retrieve current bot token from DB settings or fallback to default."""
    return db.get_setting("telegram_bot_token", "").strip()

def get_target_chat_id():
    """Retrieve configured chat ID from DB settings."""
    return db.get_setting("telegram_chat_id", "").strip()

def is_telegram_enabled():
    """Check if telegram notifications are globally enabled."""
    val = db.get_setting("telegram_enabled", "true")
    return val.lower() in ("true", "1", "yes")

def send_message(text, chat_id=None, parse_mode="HTML"):
    """
    Send message to telegram user or channel.
    Automatically splits long messages (> 4000 chars).
    """
    token = get_bot_token()
    target_chat = chat_id or get_target_chat_id()
    
    if not token:
        db.log_system("ERROR", "Telegram token is empty. Cannot send message.")
        return {"success": False, "error": "Bot token not configured"}
        
    if not target_chat:
        db.log_system("ERROR", "Telegram chat_id is empty. Cannot send message.")
        return {"success": False, "error": "Chat ID not configured"}

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Split message if it exceeds Telegram limit (4096 chars)
    max_len = 3900
    chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)] if len(text) > max_len else [text]
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    last_res = None
    for chunk in chunks:
        payload = {
            "chat_id": target_chat,
            "text": chunk,
            "disable_web_page_preview": False
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
            
        data_bytes = json.dumps(payload).encode('utf-8')
        headers = {"Content-Type": "application/json"}
        
        try:
            req = urllib.request.Request(api_url, data=data_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15, context=ssl_context) as resp:
                resp_json = json.loads(resp.read().decode('utf-8'))
                last_res = {"success": True, "data": resp_json}
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8', errors='ignore')
            # If HTML parsing fails, fallback to plain text
            if parse_mode == "HTML" and "can't parse entities" in err_msg.lower():
                try:
                    payload.pop("parse_mode", None)
                    data_bytes = json.dumps(payload).encode('utf-8')
                    req = urllib.request.Request(api_url, data=data_bytes, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=15, context=ssl_context) as fallback_resp:
                        return {"success": True, "data": json.loads(fallback_resp.read().decode('utf-8'))}
                except Exception as fb_err:
                    err_msg = f"Fallback error: {fb_err}"
                    
            db.log_system("ERROR", f"Telegram API HTTP Error {e.code}: {err_msg}")
            return {"success": False, "error": f"HTTP {e.code}: {err_msg}"}
        except Exception as e:
            db.log_system("ERROR", f"Telegram send exception: {e}")
            return {"success": False, "error": str(e)}

    return last_res or {"success": False, "error": "Unknown error"}


def fetch_bot_updates():
    """
    Get recent updates from Telegram Bot to auto-detect chat_id.
    Returns: list of chat info dictionaries.
    """
    token = get_bot_token()
    if not token:
        return {"success": False, "error": "Bot token not configured"}

    api_url = f"https://api.telegram.org/bot{token}/getUpdates?limit=20"
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "AMEVA-Crawler/1.0"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
            if not data.get("ok"):
                return {"success": False, "error": data.get("description", "Unknown API error")}
                
            results = data.get("result", [])
            chats = []
            seen_ids = set()
            
            for item in reversed(results):
                msg = item.get("message") or item.get("edited_message") or item.get("channel_post") or {}
                chat = msg.get("chat", {})
                chat_id = chat.get("id")
                if chat_id and chat_id not in seen_ids:
                    seen_ids.add(chat_id)
                    from_user = msg.get("from", {})
                    chats.append({
                        "chat_id": str(chat_id),
                        "type": chat.get("type", "private"),
                        "title": chat.get("title", ""),
                        "username": chat.get("username") or from_user.get("username", ""),
                        "first_name": chat.get("first_name") or from_user.get("first_name", ""),
                        "last_name": chat.get("last_name") or from_user.get("last_name", ""),
                        "last_message": msg.get("text", "")
                    })
            return {"success": True, "chats": chats}
    except Exception as e:
        return {"success": False, "error": str(e)}


def notify_target_changed(target, diff_result, resp_info):
    """
    Format and send a structured Telegram alert when a target page has changed.
    """
    if not is_telegram_enabled():
        db.log_system("INFO", f"Telegram notification skipped for {target['name']} (Disabled in settings)")
        return

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_name = target.get("name", "웹사이트")
    target_url = target.get("url", "")
    method = target.get("method", "GET")
    resp_ms = resp_info.get("response_time_ms", 0)
    status_code = resp_info.get("status_code", 200)

    # Escape HTML special chars in text
    def escape_html(t):
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    msg_lines = [
        "🚨 <b>[AMEVA 크롤러] 사이트 변경 감지!</b>",
        "",
        f"🏷️ <b>대상명:</b> <code>{escape_html(target_name)}</code>",
        f"🌐 <b>URL:</b> <a href=\"{escape_html(target_url)}\">{escape_html(target_url)}</a> ({method})",
        f"⚡ <b>상태:</b> HTTP {status_code} ({resp_ms}ms)",
        ""
    ]

    new_links = diff_result.get("new_links", [])
    if new_links:
        msg_lines.append(f"🔥 <b>[신규 공고/링크 발견] ({len(new_links)}건)</b>")
        for link in new_links[:10]:
            title = escape_html(link.get("text", "새 링크"))
            href = escape_html(link.get("href", target_url))
            msg_lines.append(f"• <a href=\"{href}\">{title}</a>")
        if len(new_links) > 10:
            msg_lines.append(f"  <i>...외 {len(new_links) - 10}건 추가됨</i>")
        msg_lines.append("")

    added = diff_result.get("added_lines", [])
    if added:
        msg_lines.append(f"➕ <b>[추가된 본문 텍스트] ({len(added)}줄)</b>")
        for line in added[:8]:
            msg_lines.append(f"<code>+ {escape_html(line[:100])}</code>")
        if len(added) > 8:
            msg_lines.append(f"  <i>...외 {len(added) - 8}줄</i>")
        msg_lines.append("")

    removed = diff_result.get("removed_lines", [])
    if removed:
        msg_lines.append(f"➖ <b>[삭제된 본문 텍스트] ({len(removed)}줄)</b>")
        for line in removed[:5]:
            msg_lines.append(f"<code>- {escape_html(line[:100])}</code>")
        if len(removed) > 5:
            msg_lines.append(f"  <i>...외 {len(removed) - 5}줄</i>")
        msg_lines.append("")

    msg_lines.append(f"🕒 <i>감지 시각: {now_str}</i>")
    
    full_message = "\n".join(msg_lines)
    
    # Send
    res = send_message(full_message, parse_mode="HTML")
    if res.get("success"):
        db.log_telegram(target.get("id"), target_name, full_message, "SUCCESS")
        db.log_system("INFO", f"[{target_name}] 텔레그램 알림 발송 성공!")
    else:
        err = res.get("error", "Unknown error")
        db.log_telegram(target.get("id"), target_name, full_message, "FAILED", err)
        db.log_system("ERROR", f"[{target_name}] 텔레그램 알림 발송 실패: {err}")


def send_test_message(chat_id=None):
    """Send a test message to verify Telegram configuration."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_chat = chat_id or get_target_chat_id()
    msg = (
        "🤖 <b>[AMEVA-Crawler] 텔레그램 봇 연동 테스트 성공!</b>\n\n"
        f"✅ <b>수신자 Chat ID:</b> <code>{target_chat}</code>\n"
        "⚡ 웹사이트 변경 시 이 봇을 통해 실시간 diff 및 신규 링크가 전송됩니다.\n\n"
        f"🕒 <i>테스트 시각: {now_str}</i>"
    )
    res = send_message(msg, chat_id=target_chat, parse_mode="HTML")
    if res.get("success"):
        db.log_telegram(0, "System Test", msg, "SUCCESS")
        db.log_system("INFO", f"텔레그램 테스트 메시지 발송 성공 (Chat ID: {target_chat})")
    else:
        err = res.get("error", "Unknown error")
        db.log_telegram(0, "System Test", msg, "FAILED", err)
        db.log_system("ERROR", f"텔레그램 테스트 메시지 발송 실패: {err}")
    return res
