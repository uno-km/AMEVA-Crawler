"""
AMEVA-Crawler Scheduler Module
Background scheduler supporting intervals, daily times, weekly times, and time-windows.
"""
import threading
import time
import datetime
import queue
import db
import crawler

class CrawlerScheduler:
    def __init__(self):
        self._running = False
        self._thread = None
        self._manual_queue = queue.Queue()
        self._running_targets = set()
        self._running_lock = threading.Lock()

    def start(self):
        """Start scheduler background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="AMEVA-Scheduler", daemon=True)
        self._thread.start()
        db.log_system("INFO", "크롤러 백그라운드 스케줄러가 시작되었습니다.")

    def stop(self):
        """Stop scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        db.log_system("INFO", "크롤러 스케줄러가 정지되었습니다.")

    def trigger_immediate(self, target_id):
        """Queue a target for immediate execution."""
        self._manual_queue.put(target_id)
        db.log_system("INFO", f"타겟 ID {target_id} 즉시 실행 큐에 추가됨")

    def _run_loop(self):
        """Main loop checking schedule every second."""
        while self._running:
            try:
                # 1. Process manual queue first
                while not self._manual_queue.empty():
                    target_id = self._manual_queue.get_nowait()
                    self._dispatch_crawl(target_id, is_manual=True)

                # 2. Check scheduled active targets
                active_targets = db.get_active_targets()
                now = datetime.datetime.now()
                
                for target in active_targets:
                    if self._should_run_target(target, now):
                        self._dispatch_crawl(target["id"], is_manual=False)

            except Exception as e:
                db.log_system("ERROR", f"스케줄러 루프 오류: {e}")

            time.sleep(1.0)

    def _should_run_target(self, target, now):
        """Determine if target is due for crawl according to its interval type and value."""
        target_id = target["id"]
        
        with self._running_lock:
            if target_id in self._running_targets:
                return False

        last_checked_str = target.get("last_checked_at")
        if not last_checked_str:
            return True  # Never run before -> Run immediately

        try:
            last_checked = datetime.datetime.fromisoformat(last_checked_str)
        except Exception:
            return True

        interval_type = target.get("interval_type", "interval").lower()
        val_str = str(target.get("interval_value", "300")).strip()

        # 1. Interval (Seconds)
        if interval_type == "interval":
            try:
                seconds = max(5, int(val_str))
            except ValueError:
                seconds = 300
            return (now - last_checked).total_seconds() >= seconds

        # 2. Daily (e.g. "09:00" or "09:00, 18:00")
        elif interval_type == "daily":
            times = [t.strip() for t in val_str.split(",") if t.strip()]
            for t_spec in times:
                try:
                    target_hour, target_min = map(int, t_spec.split(":"))
                    # If current time is past target time today
                    scheduled_today = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
                    if now >= scheduled_today:
                        # Check if last run was before this scheduled time today
                        if last_checked < scheduled_today:
                            return True
                except Exception:
                    continue
            return False

        # 3. Weekly (e.g. "MON,WED,FRI 09:00" or "MON 14:00")
        elif interval_type == "weekly":
            try:
                parts = val_str.split()
                if len(parts) >= 2:
                    days_part = parts[0].upper()
                    time_part = parts[1]
                    target_days = [d.strip() for d in days_part.split(",")]
                    
                    day_abbrs = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
                    current_day = day_abbrs[now.weekday()]
                    
                    if current_day in target_days:
                        target_hour, target_min = map(int, time_part.split(":"))
                        scheduled_today = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
                        if now >= scheduled_today and last_checked < scheduled_today:
                            return True
            except Exception:
                pass
            return False

        # 4. Time Window (e.g. "09:00-18:00/60" -> between 09:00 and 18:00, every 60 seconds)
        elif interval_type == "time_window":
            try:
                # Format: "START-END/INTERVAL"
                time_range, step_sec_str = val_str.split("/")
                start_str, end_str = time_range.split("-")
                
                s_h, s_m = map(int, start_str.strip().split(":"))
                e_h, e_m = map(int, end_str.strip().split(":"))
                step_sec = max(5, int(step_sec_str.strip()))
                
                win_start = now.replace(hour=s_h, minute=s_m, second=0, microsecond=0)
                win_end = now.replace(hour=e_h, minute=e_m, second=0, microsecond=0)
                
                # Check if current time is inside the window
                if win_start <= now <= win_end:
                    return (now - last_checked).total_seconds() >= step_sec
            except Exception:
                pass
            return False

        return False

    def _dispatch_crawl(self, target_id, is_manual=False):
        """Run crawl in a separate worker thread."""
        with self._running_lock:
            if target_id in self._running_targets:
                return
            self._running_targets.add(target_id)

        def worker():
            try:
                crawler.execute_crawl(target_id)
            except Exception as e:
                db.log_system("ERROR", f"Worker execution error for target {target_id}: {e}")
            finally:
                with self._running_lock:
                    self._running_targets.discard(target_id)

        threading.Thread(target=worker, daemon=True).start()

# Global scheduler singleton
scheduler_instance = CrawlerScheduler()
