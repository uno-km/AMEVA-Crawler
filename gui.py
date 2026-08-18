"""
AMEVA-Crawler GUI Module
Pure Python standard library GUI built with tkinter and ttk with System Tray integration.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import threading
import webbrowser
import tempfile
import urllib.parse
import db
import crawler
import telegram_bot
from scheduler import scheduler_instance
from config import BASE_DIR

ICON_PATH = os.path.join(BASE_DIR, "assets", "icon.ico")

class AMEVACrawlerGUI:
    def __init__(self, root, tray=None):
        self.root = root
        self.tray = tray
        self.root.title("AMEVA-Crawler (Autonomous Web Monitor)")
        self.root.geometry("1120x720")
        self.root.minsize(920, 560)

        # Set Window Icon
        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except Exception:
                pass

        # Style configuration
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass

        self._create_widgets()
        self._load_targets()
        self._refresh_logs()
        self._update_status_bar()

        # Periodic refresh (every 2 seconds)
        self.root.after(2000, self._periodic_timer)

    def _create_widgets(self):
        # 1. Top Toolbar Frame
        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(toolbar, text="➕ 타겟 등록", command=self._open_add_target_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="✏️ 타겟 수정", command=self._open_edit_target_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ 타겟 삭제", command=self._delete_selected_target).pack(side=tk.LEFT, padx=3)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Button(toolbar, text="🎯 HTTP 테스터 (Postman)", command=self._open_api_tester_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="▶ 즉시 실행", command=self._run_selected_target).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="⏯️ 활성/정지 토글", command=self._toggle_selected_target).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📋 이력 & Diff 보기", command=self._open_history_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Button(toolbar, text="⚙️ 텔레그램 설정", command=self._open_telegram_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔽 트레이로 최소화", command=self.minimize_to_tray).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔄 새로고침", command=self._load_targets).pack(side=tk.RIGHT, padx=3)

        # 2. Main Paned Window (Split Target Table & Logs)
        paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # Upper: Target List Frame
        target_frame = ttk.LabelFrame(paned, text="모니터링 대상 사이트 목록", padding=6)
        paned.add(target_frame, weight=3)

        # Treeview for targets
        columns = ("id", "active", "name", "method", "url", "interval", "last_checked", "status", "changed")
        self.tree = ttk.Treeview(target_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="ID")
        self.tree.heading("active", text="상태")
        self.tree.heading("name", text="사이트 명칭")
        self.tree.heading("method", text="Method")
        self.tree.heading("url", text="URL")
        self.tree.heading("interval", text="주기")
        self.tree.heading("last_checked", text="마지막 체크")
        self.tree.heading("status", text="응답코드")
        self.tree.heading("changed", text="최근 변경 감지")

        self.tree.column("id", width=45, anchor=tk.CENTER)
        self.tree.column("active", width=65, anchor=tk.CENTER)
        self.tree.column("name", width=160)
        self.tree.column("method", width=60, anchor=tk.CENTER)
        self.tree.column("url", width=330)
        self.tree.column("interval", width=120)
        self.tree.column("last_checked", width=130, anchor=tk.CENTER)
        self.tree.column("status", width=70, anchor=tk.CENTER)
        self.tree.column("changed", width=130, anchor=tk.CENTER)

        tree_scroll_y = ttk.Scrollbar(target_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(target_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        target_frame.rowconfigure(0, weight=1)
        target_frame.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", lambda e: self._open_history_dialog())

        # Lower: System Logs Frame
        log_frame = ttk.LabelFrame(paned, text="실시간 시스템 & 크롤링 로그", padding=6)
        paned.add(log_frame, weight=2)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=("Consolas", 9), height=8, bg="#111726", fg="#e2e8f0")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 3. Status Bar
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=4)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text="준비 완료", font=("Segoe UI", 9))
        self.status_label.pack(side=tk.LEFT)

    def minimize_to_tray(self):
        """Hide window to system tray."""
        self.root.withdraw()
        if self.tray:
            self.tray.show_balloon("AMEVA-Crawler", "백그라운드에서 모니터링이 계속 실행 중입니다.\n트레이 아이콘을 더블클릭하면 다시 열립니다.")

    def show_window(self):
        """Restore window from system tray."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _periodic_timer(self):
        """Timer loop for updating UI."""
        self._load_targets(silent=True)
        self._refresh_logs()
        self._update_status_bar()
        self.root.after(2000, self._periodic_timer)

    def _load_targets(self, silent=False):
        """Refresh targets table."""
        selected = self.tree.selection()
        selected_id = self.tree.item(selected[0])["values"][0] if selected else None

        for item in self.tree.get_children():
            self.tree.delete(item)

        targets = db.get_all_targets()
        for t in targets:
            active_str = "🟢 활성" if t["is_active"] else "⚪ 정지"
            status_str = f"HTTP {t['last_status_code']}" if t["last_status_code"] else "-"
            
            interval_str = t["interval_value"]
            if t["interval_type"] == "interval":
                sec = int(t["interval_value"]) if t["interval_value"].isdigit() else 300
                interval_str = f"{sec}초 간격"
            elif t["interval_type"] == "daily":
                interval_str = f"매일 [{t['interval_value']}]"
            elif t["interval_type"] == "weekly":
                interval_str = f"매주 [{t['interval_value']}]"
            elif t["interval_type"] == "time_window":
                interval_str = f"시간대 [{t['interval_value']}]"

            last_chk = t["last_checked_at"][:19].replace("T", " ") if t["last_checked_at"] else "-"
            last_chg = t["last_change_detected_at"][:19].replace("T", " ") if t["last_change_detected_at"] else "-"

            item_id = self.tree.insert("", tk.END, values=(
                t["id"],
                active_str,
                t["name"],
                t["method"],
                t["url"],
                interval_str,
                last_chk,
                status_str,
                last_chg
            ))

            if selected_id and str(t["id"]) == str(selected_id):
                self.tree.selection_set(item_id)

    def _refresh_logs(self):
        """Fetch latest system logs and append to text."""
        logs = db.get_system_logs(limit=40)
        self.log_text.delete("1.0", tk.END)
        for log in reversed(logs):
            time_str = log["created_at"][:19].replace("T", " ")
            self.log_text.insert(tk.END, f"[{time_str}] [{log['level']}] {log['message']}\n")
        self.log_text.see(tk.END)

    def _update_status_bar(self):
        stats = db.get_dashboard_stats()
        tele_enabled = db.get_setting("telegram_enabled", "false") == "true"
        tele_status = "연동 ON" if tele_enabled else "연동 OFF"
        self.status_label.config(
            text=f"📊 총 타겟: {stats['total_targets']}개 | 활성: {stats['active_targets']}개 | "
                 f"24시간 변경: {stats['recent_changes_24h']}건 | 텔레그램 알림: {stats['telegram_sent_count']}회 ({tele_status})"
        )

    def _get_selected_target_id(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("선택 필요", "목록에서 타겟을 먼저 선택해주세요.")
            return None
        return self.tree.item(selected[0])["values"][0]

    def _run_selected_target(self):
        target_id = self._get_selected_target_id()
        if target_id:
            scheduler_instance.trigger_immediate(target_id)
            messagebox.showinfo("실행 요청", f"타겟 #{target_id} 즉시 크롤링을 요청했습니다.")

    def _toggle_selected_target(self):
        target_id = self._get_selected_target_id()
        if target_id:
            new_status = db.toggle_target_active(target_id)
            self._load_targets()

    def _delete_selected_target(self):
        target_id = self._get_selected_target_id()
        if target_id:
            if messagebox.askyesno("삭제 확인", f"정말로 타겟 #{target_id} 및 모든 이력을 삭제하시겠습니까?"):
                db.delete_target(target_id)
                self._load_targets()

    def _open_add_target_dialog(self, initial_data=None):
        TargetDialog(self.root, target=initial_data, on_saved=self._load_targets)

    def _open_api_tester_dialog(self, initial_data=None):
        APITesterDialog(self.root, initial_data=initial_data, on_create_target=self._open_add_target_dialog)

    def _open_edit_target_dialog(self):
        target_id = self._get_selected_target_id()
        if target_id:
            target = db.get_target_by_id(target_id)
            if target:
                TargetDialog(self.root, target=target, on_saved=self._load_targets)

    def _open_history_dialog(self):
        target_id = self._get_selected_target_id()
        if target_id:
            HistoryDialog(self.root, target_id=target_id)

    def _open_telegram_dialog(self):
        TelegramSettingsDialog(self.root, on_saved=self._update_status_bar)


# -----------------------------------------------------------------------------
# Target Add / Edit Dialog
# -----------------------------------------------------------------------------
class TargetDialog(tk.Toplevel):
    def __init__(self, parent, target=None, on_saved=None):
        super().__init__(parent)
        self.target = target
        self.on_saved = on_saved
        self.title("타겟 수정" if target else "신규 타겟 등록")
        self.geometry("620x560")
        self.minsize(550, 480)
        self.transient(parent)
        self.grab_set()

        if os.path.exists(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except Exception:
                pass

        self._create_widgets()
        if target:
            self._populate_fields()

    def _create_widgets(self):
        pad = {"padx": 10, "pady": 5}

        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Name & Method
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, **pad)

        ttk.Label(row1, text="타겟 명칭:").pack(side=tk.LEFT)
        self.entry_name = ttk.Entry(row1, width=32)
        self.entry_name.pack(side=tk.LEFT, padx=6)

        ttk.Label(row1, text="Method:").pack(side=tk.LEFT, padx=(10, 0))
        self.combo_method = ttk.Combobox(row1, values=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"], state="readonly", width=8)
        self.combo_method.set("GET")
        self.combo_method.pack(side=tk.LEFT, padx=6)
        self.combo_method.bind("<<ComboboxSelected>>", self._on_method_changed)

        # 2. URL
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, **pad)
        ttk.Label(row2, text="대상 URL:").pack(side=tk.LEFT)
        self.entry_url = ttk.Entry(row2)
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # 3. POST/PUT Body Frame (Conditional)
        self.post_frame = ttk.LabelFrame(main_frame, text="요청 본문 설정 (Body & Content-Type)", padding=6)
        
        row_ct = ttk.Frame(self.post_frame)
        row_ct.pack(fill=tk.X, pady=2)
        ttk.Label(row_ct, text="Content-Type:").pack(side=tk.LEFT)
        self.combo_content_type = ttk.Combobox(row_ct, values=["application/json", "application/x-www-form-urlencoded", "text/plain"], state="readonly", width=25)
        self.combo_content_type.set("application/json")
        self.combo_content_type.pack(side=tk.LEFT, padx=6)

        ttk.Label(self.post_frame, text="Request Body (JSON / Form Data):").pack(anchor=tk.W, pady=(4, 2))
        self.text_body = tk.Text(self.post_frame, height=3, font=("Consolas", 9))
        self.text_body.pack(fill=tk.X)

        # 4. Headers
        ttk.Label(main_frame, text="커스텀 HTTP 헤더 (JSON 선택사항):").pack(anchor=tk.W, padx=10, pady=(6, 2))
        self.text_headers = tk.Text(main_frame, height=2, font=("Consolas", 9))
        self.text_headers.pack(fill=tk.X, padx=10)

        # 5. Interval Frame
        int_frame = ttk.LabelFrame(main_frame, text="⏱️ 크롤링 주기 설정", padding=8)
        int_frame.pack(fill=tk.X, **pad)

        row_int = ttk.Frame(int_frame)
        row_int.pack(fill=tk.X)

        ttk.Label(row_int, text="주기 유형:").pack(side=tk.LEFT)
        self.combo_interval_type = ttk.Combobox(
            row_int, 
            values=["간격 반복 (초 단위)", "매일 특정 시각 (HH:MM)", "매주 특정 요일 (MON 09:00)", "특정 시간대 작동 (09:00-18:00/60)"],
            state="readonly",
            width=30
        )
        self.combo_interval_type.set("간격 반복 (초 단위)")
        self.combo_interval_type.pack(side=tk.LEFT, padx=6)
        self.combo_interval_type.bind("<<ComboboxSelected>>", self._on_interval_type_changed)

        row_val = ttk.Frame(int_frame)
        row_val.pack(fill=tk.X, pady=(6, 0))
        self.lbl_interval_val = ttk.Label(row_val, text="반복 간격 (초):")
        self.lbl_interval_val.pack(side=tk.LEFT)
        self.entry_interval_val = ttk.Entry(row_val, width=20)
        self.entry_interval_val.insert(0, "300")
        self.entry_interval_val.pack(side=tk.LEFT, padx=6)

        # 6. Filter & Detect Mode
        filter_frame = ttk.LabelFrame(main_frame, text="🔍 변경 감지 필터", padding=8)
        filter_frame.pack(fill=tk.X, **pad)

        row_fil = ttk.Frame(filter_frame)
        row_fil.pack(fill=tk.X)

        ttk.Label(row_fil, text="감지 모드:").pack(side=tk.LEFT)
        self.combo_detect_mode = ttk.Combobox(row_fil, values=["전체 (신규 링크 + 본문 변경)", "신규 링크/공고만", "본문 텍스트만"], state="readonly", width=22)
        self.combo_detect_mode.set("전체 (신규 링크 + 본문 변경)")
        self.combo_detect_mode.pack(side=tk.LEFT, padx=6)

        row_reg = ttk.Frame(filter_frame)
        row_reg.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(row_reg, text="정규식 필터:").pack(side=tk.LEFT)
        self.entry_rule = ttk.Entry(row_reg)
        self.entry_rule.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # 7. Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(btn_frame, text="저장", command=self._save_target).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="취소", command=self.destroy).pack(side=tk.RIGHT, padx=4)

    def _on_method_changed(self, event=None):
        if self.combo_method.get() in ("POST", "PUT", "PATCH", "DELETE"):
            self.post_frame.pack(fill=tk.X, padx=10, pady=5)
        else:
            self.post_frame.pack_forget()

    def _on_interval_type_changed(self, event=None):
        t = self.combo_interval_type.get()
        if "초 단위" in t:
            self.lbl_interval_val.config(text="반복 간격 (초):")
        elif "매일" in t:
            self.lbl_interval_val.config(text="매일 시각 (09:00 또는 09:00,18:00):")
            if not ":" in self.entry_interval_val.get():
                self.entry_interval_val.delete(0, tk.END)
                self.entry_interval_val.insert(0, "09:00")
        elif "매주" in t:
            self.lbl_interval_val.config(text="요일 및 시각 (MON,WED 09:00):")
            if not " " in self.entry_interval_val.get():
                self.entry_interval_val.delete(0, tk.END)
                self.entry_interval_val.insert(0, "MON,WED,FRI 09:00")
        elif "시간대" in t:
            self.lbl_interval_val.config(text="시간대 및 간격 (09:00-18:00/60):")
            if not "/" in self.entry_interval_val.get():
                self.entry_interval_val.delete(0, tk.END)
                self.entry_interval_val.insert(0, "09:00-18:00/60")

    def _populate_fields(self):
        t = self.target
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, t.get("name", ""))
        self.entry_url.delete(0, tk.END)
        self.entry_url.insert(0, t.get("url", ""))
        self.combo_method.set(t.get("method", "GET").upper())
        self._on_method_changed()

        if t.get("headers") and t.get("headers") != "{}":
            h = t.get("headers")
            if isinstance(h, dict):
                h = json.dumps(h, ensure_ascii=False, indent=2)
            self.text_headers.delete("1.0", tk.END)
            self.text_headers.insert("1.0", str(h))

        if t.get("method", "GET").upper() in ("POST", "PUT", "PATCH", "DELETE"):
            self.combo_content_type.set(t.get("content_type", "application/json"))
            self.text_body.delete("1.0", tk.END)
            self.text_body.insert("1.0", str(t.get("body", "")))

        itype = t.get("interval_type", "interval")
        if itype == "interval":
            self.combo_interval_type.set("간격 반복 (초 단위)")
        elif itype == "daily":
            self.combo_interval_type.set("매일 특정 시각 (HH:MM)")
        elif itype == "weekly":
            self.combo_interval_type.set("매주 특정 요일 (MON 09:00)")
        elif itype == "time_window":
            self.combo_interval_type.set("특정 시간대 작동 (09:00-18:00/60)")
        
        self.entry_interval_val.delete(0, tk.END)
        self.entry_interval_val.insert(0, t.get("interval_value", "300"))
        self._on_interval_type_changed()

        dmode = t.get("detect_mode", "all")
        if dmode == "links_only":
            self.combo_detect_mode.set("신규 링크/공고만")
        elif dmode == "text_only":
            self.combo_detect_mode.set("본문 텍스트만")
        else:
            self.combo_detect_mode.set("전체 (신규 링크 + 본문 변경)")

        self.entry_rule.delete(0, tk.END)
        self.entry_rule.insert(0, t.get("selector_rule", ""))

    def _save_target(self):
        name = self.entry_name.get().strip()
        url = self.entry_url.get().strip()
        if not name or not url:
            messagebox.showwarning("입력 오류", "타겟 명칭과 URL은 필수 입력 항목입니다.", parent=self)
            return

        method = self.combo_method.get()
        headers = self.text_headers.get("1.0", tk.END).strip() or "{}"
        body = self.text_body.get("1.0", tk.END).strip() if method in ("POST", "PUT", "PATCH", "DELETE") else ""
        content_type = self.combo_content_type.get() if method in ("POST", "PUT", "PATCH", "DELETE") else "application/json"

        itype_label = self.combo_interval_type.get()
        if "초 단위" in itype_label:
            interval_type = "interval"
        elif "매일" in itype_label:
            interval_type = "daily"
        elif "매주" in itype_label:
            interval_type = "weekly"
        else:
            interval_type = "time_window"

        interval_val = self.entry_interval_val.get().strip() or "300"

        dmode_label = self.combo_detect_mode.get()
        if "링크" in dmode_label:
            detect_mode = "links_only"
        elif "텍스트" in dmode_label:
            detect_mode = "text_only"
        else:
            detect_mode = "all"

        rule = self.entry_rule.get().strip()

        data = {
            "name": name,
            "url": url,
            "method": method,
            "headers": headers,
            "body": body,
            "content_type": content_type,
            "interval_type": interval_type,
            "interval_value": interval_val,
            "detect_mode": detect_mode,
            "selector_rule": rule,
            "is_active": True
        }

        if self.target:
            db.update_target(self.target["id"], data)
            messagebox.showinfo("수정 완료", f"타겟 '{name}'이 수정되었습니다.", parent=self)
        else:
            new_id = db.create_target(data)
            scheduler_instance.trigger_immediate(new_id)
            messagebox.showinfo("등록 완료", f"타겟 '{name}'이 등록되었으며 첫 크롤링을 시작합니다.", parent=self)

        if self.on_saved:
            self.on_saved()
        self.destroy()


# -----------------------------------------------------------------------------
# History & Diff Dialog
# -----------------------------------------------------------------------------
class HistoryDialog(tk.Toplevel):
    def __init__(self, parent, target_id):
        super().__init__(parent)
        self.target_id = target_id
        self.target = db.get_target_by_id(target_id)
        self.title(f"크롤링 이력 & Diff 분석 - {self.target['name'] if self.target else target_id}")
        self.geometry("900x600")
        self.transient(parent)

        if os.path.exists(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except Exception:
                pass

        self._create_widgets()
        self._load_history()

    def _create_widgets(self):
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left: History items
        left_frame = ttk.Frame(paned, padding=4)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="실행 이력 타임라인", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        
        self.tree_hist = ttk.Treeview(left_frame, columns=("time", "status", "changed"), show="headings", selectmode="browse")
        self.tree_hist.heading("time", text="실행 시각")
        self.tree_hist.heading("status", text="상태")
        self.tree_hist.heading("changed", text="변경여부")

        self.tree_hist.column("time", width=120)
        self.tree_hist.column("status", width=60, anchor=tk.CENTER)
        self.tree_hist.column("changed", width=70, anchor=tk.CENTER)

        hist_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree_hist.yview)
        self.tree_hist.configure(yscrollcommand=hist_scroll.set)

        self.tree_hist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hist_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_hist.bind("<<TreeviewSelect>>", self._on_hist_selected)

        # Right: Detail Diff & New Links
        right_frame = ttk.Frame(paned, padding=4)
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="🔥 새로 발견된 링크/공고:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.text_links = tk.Text(right_frame, height=5, font=("Consolas", 9), wrap=tk.WORD)
        self.text_links.pack(fill=tk.X, pady=(2, 6))

        ttk.Label(right_frame, text="📝 내용 변경 상세 요약 (Diff):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.text_diff = tk.Text(right_frame, font=("Consolas", 9), wrap=tk.WORD)
        self.text_diff.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

    def _load_history(self):
        self.history_records = db.get_target_history(self.target_id, limit=40)
        for h in self.history_records:
            t_str = h["created_at"][:19].replace("T", " ")
            st = f"HTTP {h['status_code']}" if h["status_code"] else "ERR"
            chg = "🔔 변경" if h["is_changed"] else "동일"
            self.tree_hist.insert("", tk.END, values=(t_str, st, chg), tags=(str(h["id"]),))

        children = self.tree_hist.get_children()
        if children:
            self.tree_hist.selection_set(children[0])

    def _on_hist_selected(self, event=None):
        selected = self.tree_hist.selection()
        if not selected:
            return
        idx = self.tree_hist.index(selected[0])
        h = self.history_records[idx]

        # New links
        self.text_links.delete("1.0", tk.END)
        try:
            links = json.loads(h.get("new_links") or "[]")
            if links:
                for l in links:
                    self.text_links.insert(tk.END, f"• {l.get('text')} -> {l.get('href')}\n")
            else:
                self.text_links.insert(tk.END, "신규 발견된 링크 없음\n")
        except Exception:
            self.text_links.insert(tk.END, "링크 파싱 오류\n")

        # Diff summary
        self.text_diff.delete("1.0", tk.END)
        diff_text = h.get("diff_summary", "내용 없음")
        if h.get("error_message"):
            diff_text = f"[오류 메시지]\n{h['error_message']}\n\n" + diff_text
        self.text_diff.insert(tk.END, diff_text)


# -----------------------------------------------------------------------------
# Telegram Settings Dialog
# -----------------------------------------------------------------------------
class TelegramSettingsDialog(tk.Toplevel):
    def __init__(self, parent, on_saved=None):
        super().__init__(parent)
        self.on_saved = on_saved
        self.title("⚙️ 텔레그램 봇 설정")
        self.geometry("560x420")
        self.transient(parent)
        self.grab_set()

        if os.path.exists(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except Exception:
                pass

        self._create_widgets()
        self._load_settings()

    def _create_widgets(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="Telegram Bot Token:").pack(anchor=tk.W)
        self.entry_token = ttk.Entry(main, width=55, font=("Consolas", 9))
        self.entry_token.pack(fill=tk.X, pady=(2, 8))

        ttk.Label(main, text="수신자 Chat ID:").pack(anchor=tk.W)
        row_chat = ttk.Frame(main)
        row_chat.pack(fill=tk.X, pady=(2, 8))
        self.entry_chat_id = ttk.Entry(row_chat, width=30, font=("Consolas", 9))
        self.entry_chat_id.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row_chat, text="🔍 대화방 자동 감지", command=self._detect_chat_id).pack(side=tk.RIGHT)

        self.var_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(main, text="텔레그램 알림 발송 활성화", variable=self.var_enabled).pack(anchor=tk.W, pady=4)

        ttk.Separator(main).pack(fill=tk.X, pady=8)

        # Test message button
        ttk.Button(main, text="📬 테스트 메시지 발송", command=self._send_test).pack(fill=tk.X, pady=4)

        # Bottom buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(12, 0))
        ttk.Button(btn_frame, text="저장", command=self._save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="닫기", command=self.destroy).pack(side=tk.RIGHT, padx=4)

    def _load_settings(self):
        token = db.get_setting("telegram_bot_token", "")
        chat_id = db.get_setting("telegram_chat_id", "")
        enabled = db.get_setting("telegram_enabled", "false") == "true"

        self.entry_token.insert(0, token)
        self.entry_chat_id.insert(0, chat_id)
        self.var_enabled.set(enabled)

    def _detect_chat_id(self):
        token = self.entry_token.get().strip()
        if not token:
            messagebox.showwarning("입력 필요", "먼저 Bot Token을 입력해주세요.", parent=self)
            return

        db.set_setting("telegram_bot_token", token)
        res = telegram_bot.fetch_bot_updates()
        if res.get("success"):
            chats = res.get("chats", [])
            if chats:
                first_chat = chats[0]
                self.entry_chat_id.delete(0, tk.END)
                self.entry_chat_id.insert(0, first_chat["chat_id"])
                user_info = first_chat.get("username") or first_chat.get("first_name") or ""
                messagebox.showinfo("감지 성공", f"대화방을 감지했습니다!\nChat ID: {first_chat['chat_id']} ({user_info})", parent=self)
            else:
                messagebox.showinfo("검색 결과", "최근 봇에게 전송된 대화가 없습니다. 텔레그램에서 봇에게 /start 또는 아무 메시지를 보낸 후 다시 클릭하세요.", parent=self)
        else:
            messagebox.showerror("감지 실패", f"오류: {res.get('error')}", parent=self)

    def _send_test(self):
        token = self.entry_token.get().strip()
        chat_id = self.entry_chat_id.get().strip()
        if not token or not chat_id:
            messagebox.showwarning("입력 필요", "Bot Token과 Chat ID를 모두 입력해주세요.", parent=self)
            return

        db.set_setting("telegram_bot_token", token)
        db.set_setting("telegram_chat_id", chat_id)
        
        res = telegram_bot.send_test_message(chat_id=chat_id)
        if res.get("success"):
            messagebox.showinfo("전송 성공", f"Chat ID [{chat_id}]로 테스트 메시지를 성공적으로 발송했습니다!", parent=self)
        else:
            messagebox.showerror("전송 실패", f"발송 실패:\n{res.get('error')}", parent=self)

    def _save(self):
        token = self.entry_token.get().strip()
        chat_id = self.entry_chat_id.get().strip()
        enabled = "true" if self.var_enabled.get() else "false"

        db.set_setting("telegram_bot_token", token)
        db.set_setting("telegram_chat_id", chat_id)
        db.set_setting("telegram_enabled", enabled)

        messagebox.showinfo("저장 완료", "텔레그램 설정이 안전하게 저장되었습니다.", parent=self)
        if self.on_saved:
            self.on_saved()
        self.destroy()


# -----------------------------------------------------------------------------
# Postman-style HTTP / API Tester Dialog (찔러보기 & 실시간 렌더링)
# -----------------------------------------------------------------------------
class APITesterDialog(tk.Toplevel):
    def __init__(self, parent, initial_data=None, on_create_target=None):
        super().__init__(parent)
        self.initial_data = initial_data or {}
        self.on_create_target = on_create_target
        self.title("AMEVA HTTP/API Tester (Postman 모드 / 찔러보기)")
        self.geometry("1000x720")
        self.minsize(840, 580)
        self.transient(parent)

        if os.path.exists(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except Exception:
                pass

        self._is_loading = False
        self._current_response = None
        self._temp_html_path = None

        self._create_widgets()
        self._load_initial_data()

    def _create_widgets(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # 1. Top URL / Request Bar
        req_bar = ttk.LabelFrame(main, text="🚀 HTTP 요청 전송 (Request Builder)", padding=8)
        req_bar.pack(fill=tk.X, pady=(0, 6))

        row_req = ttk.Frame(req_bar)
        row_req.pack(fill=tk.X)

        self.combo_method = ttk.Combobox(
            row_req, 
            values=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"], 
            state="readonly", 
            width=9, 
            font=("Segoe UI", 10, "bold")
        )
        self.combo_method.set("GET")
        self.combo_method.pack(side=tk.LEFT, padx=(0, 6))
        self.combo_method.bind("<<ComboboxSelected>>", self._on_method_change)

        self.entry_url = ttk.Entry(row_req, font=("Consolas", 10))
        self.entry_url.insert(0, "https://")
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_url.bind("<Return>", lambda e: self._send_request())

        self.btn_send = ttk.Button(row_req, text="⚡ 찔러보기 (Send)", command=self._send_request)
        self.btn_send.pack(side=tk.LEFT, padx=4)

        self.btn_schedule = ttk.Button(row_req, text="📌 모니터링 타겟으로 등록", command=self._create_schedule_target)
        self.btn_schedule.pack(side=tk.LEFT, padx=4)

        # 2. Main Paned Split (Upper: Request Config, Lower: Response Viewer)
        paned = ttk.PanedWindow(main, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # --- Request Notebook ---
        req_frame = ttk.Frame(paned)
        paned.add(req_frame, weight=2)

        self.req_notebook = ttk.Notebook(req_frame)
        self.req_notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Params
        tab_params = ttk.Frame(self.req_notebook, padding=6)
        self.req_notebook.add(tab_params, text="QueryParams (파라미터)")
        self._build_params_tab(tab_params)

        # Tab 2: Headers
        tab_headers = ttk.Frame(self.req_notebook, padding=6)
        self.req_notebook.add(tab_headers, text="Headers (헤더/쿠키)")
        self._build_headers_tab(tab_headers)

        # Tab 3: Body
        tab_body = ttk.Frame(self.req_notebook, padding=6)
        self.req_notebook.add(tab_body, text="Body (요청 본문)")
        self._build_body_tab(tab_body)

        # Tab 4: Auth
        tab_auth = ttk.Frame(self.req_notebook, padding=6)
        self.req_notebook.add(tab_auth, text="Auth (인증)")
        self._build_auth_tab(tab_auth)

        # --- Response Frame ---
        resp_frame = ttk.Frame(paned)
        paned.add(resp_frame, weight=3)

        # Status Bar Header
        resp_header = ttk.Frame(resp_frame, padding=(4, 4))
        resp_header.pack(fill=tk.X)

        ttk.Label(resp_header, text="응답 결과 (Response):", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(resp_header, text="대기 중...", font=("Segoe UI", 9, "bold"), foreground="#6b7280")
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        self.lbl_time = ttk.Label(resp_header, text="", font=("Segoe UI", 9))
        self.lbl_time.pack(side=tk.LEFT, padx=6)

        self.lbl_size = ttk.Label(resp_header, text="", font=("Segoe UI", 9))
        self.lbl_size.pack(side=tk.LEFT, padx=6)

        self.btn_copy_resp = ttk.Button(resp_header, text="📋 응답 복사", command=self._copy_response_body)
        self.btn_copy_resp.pack(side=tk.RIGHT, padx=4)

        # Response Notebook
        self.resp_notebook = ttk.Notebook(resp_frame)
        self.resp_notebook.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        # Resp Tab 1: Pretty
        tab_pretty = ttk.Frame(self.resp_notebook, padding=4)
        self.resp_notebook.add(tab_pretty, text="✨ Pretty (포맷팅)")
        self.text_pretty = tk.Text(tab_pretty, font=("Consolas", 9), wrap=tk.NONE)
        scroll_py = ttk.Scrollbar(tab_pretty, orient=tk.VERTICAL, command=self.text_pretty.yview)
        scroll_px = ttk.Scrollbar(tab_pretty, orient=tk.HORIZONTAL, command=self.text_pretty.xview)
        self.text_pretty.configure(yscrollcommand=scroll_py.set, xscrollcommand=scroll_px.set)
        scroll_py.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_px.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_pretty.pack(fill=tk.BOTH, expand=True)

        # Resp Tab 2: Raw
        tab_raw = ttk.Frame(self.resp_notebook, padding=4)
        self.resp_notebook.add(tab_raw, text="📄 Raw (원문)")
        self.text_raw = tk.Text(tab_raw, font=("Consolas", 9), wrap=tk.NONE)
        scroll_ry = ttk.Scrollbar(tab_raw, orient=tk.VERTICAL, command=self.text_raw.yview)
        scroll_rx = ttk.Scrollbar(tab_raw, orient=tk.HORIZONTAL, command=self.text_raw.xview)
        self.text_raw.configure(yscrollcommand=scroll_ry.set, xscrollcommand=scroll_rx.set)
        scroll_ry.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_rx.pack(side=tk.BOTTOM, fill=tk.X)
        self.text_raw.pack(fill=tk.BOTH, expand=True)

        # Resp Tab 3: HTML View / Preview
        tab_html = ttk.Frame(self.resp_notebook, padding=4)
        self.resp_notebook.add(tab_html, text="🌐 HTML 뷰 / 프리뷰")
        
        bar_html = ttk.Frame(tab_html)
        bar_html.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(bar_html, text="🖥️ 기본 웹 브라우저로 실시간 렌더링 열기", command=self._open_in_system_browser).pack(side=tk.LEFT, padx=2)
        ttk.Label(bar_html, text="(HTML 응답을 실제 브라우저 엔진으로 즉시 렌더링하여 확인합니다)", font=("Segoe UI", 8), foreground="#6b7280").pack(side=tk.LEFT, padx=6)

        self.text_html_preview = tk.Text(tab_html, font=("Segoe UI", 9), wrap=tk.WORD)
        scroll_hy = ttk.Scrollbar(tab_html, orient=tk.VERTICAL, command=self.text_html_preview.yview)
        self.text_html_preview.configure(yscrollcommand=scroll_hy.set)
        scroll_hy.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_html_preview.pack(fill=tk.BOTH, expand=True)

        # Resp Tab 4: Headers
        tab_rheaders = ttk.Frame(self.resp_notebook, padding=4)
        self.resp_notebook.add(tab_rheaders, text="📑 Headers (응답 헤더)")
        self.tree_rheaders = ttk.Treeview(tab_rheaders, columns=("header", "value"), show="headings")
        self.tree_rheaders.heading("header", text="헤더 이름 (Header)")
        self.tree_rheaders.heading("value", text="헤더 값 (Value)")
        self.tree_rheaders.column("header", width=220)
        self.tree_rheaders.column("value", width=600)
        scroll_rhy = ttk.Scrollbar(tab_rheaders, orient=tk.VERTICAL, command=self.tree_rheaders.yview)
        self.tree_rheaders.configure(yscrollcommand=scroll_rhy.set)
        scroll_rhy.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_rheaders.pack(fill=tk.BOTH, expand=True)

        # Resp Tab 5: Links
        tab_links = ttk.Frame(self.resp_notebook, padding=4)
        self.resp_notebook.add(tab_links, text="🔗 추출된 링크 (Links)")
        
        bar_links = ttk.Frame(tab_links)
        bar_links.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(bar_links, text="🔗 선택 링크 브라우저로 열기", command=self._open_selected_link).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar_links, text="📋 선택 링크 URL 복사", command=self._copy_selected_link).pack(side=tk.LEFT, padx=2)
        
        self.tree_links = ttk.Treeview(tab_links, columns=("text", "href"), show="headings")
        self.tree_links.heading("text", text="링크 명칭 (Text / Title)")
        self.tree_links.heading("href", text="대상 URL (HREF)")
        self.tree_links.column("text", width=300)
        self.tree_links.column("href", width=550)
        scroll_ly = ttk.Scrollbar(tab_links, orient=tk.VERTICAL, command=self.tree_links.yview)
        self.tree_links.configure(yscrollcommand=scroll_ly.set)
        scroll_ly.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_links.pack(fill=tk.BOTH, expand=True)

    # ----------------- Request Builders -----------------

    def _build_params_tab(self, parent):
        ttk.Label(parent, text="URL 쿼리 파라미터 (JSON 또는 key=value 라인별 입력):", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 2))
        self.text_params = tk.Text(parent, height=5, font=("Consolas", 9))
        self.text_params.pack(fill=tk.BOTH, expand=True)
        
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(bar, text="URL에서 파라미터 가져오기", command=self._sync_params_from_url).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="URL로 파라미터 적용", command=self._sync_params_to_url).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="지우기", command=lambda: self.text_params.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=2)

    def _build_headers_tab(self, parent):
        top_bar = ttk.Frame(parent)
        top_bar.pack(fill=tk.X, pady=(0, 4))
        
        ttk.Label(top_bar, text="HTTP 요청 헤더 (JSON 형식):", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        ttk.Label(top_bar, text="프리셋 추가:").pack(side=tk.LEFT, padx=(16, 4))
        self.combo_header_preset = ttk.Combobox(
            top_bar, 
            values=[
                "JSON (application/json)",
                "Form (x-www-form-urlencoded)",
                "X-Requested-With (XMLHttpRequest)",
                "Referer (현재 도메인)",
                "User-Agent (Chrome 데스크톱)",
                "Cookie (session_id=...)"
            ],
            state="readonly",
            width=28
        )
        self.combo_header_preset.pack(side=tk.LEFT, padx=2)
        ttk.Button(top_bar, text="➕ 추가", command=self._apply_header_preset).pack(side=tk.LEFT, padx=2)

        self.text_req_headers = tk.Text(parent, height=5, font=("Consolas", 9))
        self.text_req_headers.pack(fill=tk.BOTH, expand=True)
        self.text_req_headers.insert("1.0", "{}")

    def _build_body_tab(self, parent):
        top_bar = ttk.Frame(parent)
        top_bar.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(top_bar, text="Content-Type:").pack(side=tk.LEFT, padx=(0, 4))
        self.var_content_type = tk.StringVar(value="application/json")
        for ct, label in [
            ("none", "None"),
            ("application/json", "JSON"),
            ("application/x-www-form-urlencoded", "x-www-form-urlencoded"),
            ("text/plain", "Raw/Text")
        ]:
            ttk.Radiobutton(top_bar, text=label, value=ct, variable=self.var_content_type, command=self._on_content_type_change).pack(side=tk.LEFT, padx=4)

        ttk.Button(top_bar, text="✨ JSON 포맷팅", command=self._beautify_json_body).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top_bar, text="지우기", command=lambda: self.text_req_body.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=2)

        self.text_req_body = tk.Text(parent, height=5, font=("Consolas", 9))
        self.text_req_body.pack(fill=tk.BOTH, expand=True)

    def _build_auth_tab(self, parent):
        top_bar = ttk.Frame(parent)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(top_bar, text="인증 방식 (Type):").pack(side=tk.LEFT, padx=(0, 6))
        self.combo_auth_type = ttk.Combobox(top_bar, values=["No Auth", "Bearer Token", "Basic Auth", "API Key (Header)"], state="readonly", width=18)
        self.combo_auth_type.set("No Auth")
        self.combo_auth_type.pack(side=tk.LEFT, padx=4)
        self.combo_auth_type.bind("<<ComboboxSelected>>", self._on_auth_type_change)

        self.auth_fields_frame = ttk.Frame(parent)
        self.auth_fields_frame.pack(fill=tk.X, pady=4)
        self._render_auth_fields()

    def _render_auth_fields(self):
        for child in self.auth_fields_frame.winfo_children():
            child.destroy()

        atype = self.combo_auth_type.get()
        if atype == "Bearer Token":
            row = ttk.Frame(self.auth_fields_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text="Token:").pack(side=tk.LEFT, padx=4)
            self.entry_auth_token = ttk.Entry(row, width=60, font=("Consolas", 9))
            self.entry_auth_token.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        elif atype == "Basic Auth":
            row1 = ttk.Frame(self.auth_fields_frame)
            row1.pack(fill=tk.X, pady=2)
            ttk.Label(row1, text="Username:").pack(side=tk.LEFT, padx=4)
            self.entry_auth_user = ttk.Entry(row1, width=30)
            self.entry_auth_user.pack(side=tk.LEFT, padx=4)
            
            ttk.Label(row1, text="Password:").pack(side=tk.LEFT, padx=4)
            self.entry_auth_pass = ttk.Entry(row1, width=30, show="*")
            self.entry_auth_pass.pack(side=tk.LEFT, padx=4)
        elif atype == "API Key (Header)":
            row = ttk.Frame(self.auth_fields_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text="Key Name:").pack(side=tk.LEFT, padx=4)
            self.entry_auth_key = ttk.Entry(row, width=25)
            self.entry_auth_key.insert(0, "X-API-KEY")
            self.entry_auth_key.pack(side=tk.LEFT, padx=4)
            
            ttk.Label(row, text="Value:").pack(side=tk.LEFT, padx=4)
            self.entry_auth_val = ttk.Entry(row, width=40, font=("Consolas", 9))
            self.entry_auth_val.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        else:
            ttk.Label(self.auth_fields_frame, text="인증 헤더가 추가되지 않습니다.", foreground="#6b7280").pack(anchor=tk.W, padx=4)

    def _on_auth_type_change(self, event=None):
        self._render_auth_fields()

    def _on_method_change(self, event=None):
        m = self.combo_method.get()
        if m in ("POST", "PUT", "PATCH"):
            if self.var_content_type.get() == "none":
                self.var_content_type.set("application/json")
        elif m in ("GET", "HEAD"):
            pass

    def _on_content_type_change(self):
        ct = self.var_content_type.get()
        if ct == "none":
            self.text_req_body.config(state=tk.DISABLED)
        else:
            self.text_req_body.config(state=tk.NORMAL)

    def _apply_header_preset(self):
        preset = self.combo_header_preset.get()
        cur_text = self.text_req_headers.get("1.0", tk.END).strip() or "{}"
        try:
            h_dict = json.loads(cur_text)
            if not isinstance(h_dict, dict):
                h_dict = {}
        except Exception:
            h_dict = {}

        if "JSON" in preset:
            h_dict["Content-Type"] = "application/json"
        elif "Form" in preset:
            h_dict["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        elif "X-Requested-With" in preset:
            h_dict["X-Requested-With"] = "XMLHttpRequest"
        elif "Referer" in preset:
            url = self.entry_url.get().strip()
            parsed = urllib.parse.urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else url
            h_dict["Referer"] = base
        elif "User-Agent" in preset:
            h_dict["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        elif "Cookie" in preset:
            if "Cookie" not in h_dict:
                h_dict["Cookie"] = "session_id=example_token"

        self.text_req_headers.delete("1.0", tk.END)
        self.text_req_headers.insert("1.0", json.dumps(h_dict, ensure_ascii=False, indent=2))

    def _beautify_json_body(self):
        raw = self.text_req_body.get("1.0", tk.END).strip()
        if not raw:
            return
        try:
            parsed = json.loads(raw)
            self.text_req_body.delete("1.0", tk.END)
            self.text_req_body.insert("1.0", json.dumps(parsed, ensure_ascii=False, indent=2))
        except Exception as e:
            messagebox.showwarning("JSON 파싱 오류", f"유효한 JSON 형식이 아닙니다:\n{e}", parent=self)

    def _sync_params_from_url(self):
        url = self.entry_url.get().strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.query:
            params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            flat = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
            self.text_params.delete("1.0", tk.END)
            self.text_params.insert("1.0", json.dumps(flat, ensure_ascii=False, indent=2))
        else:
            messagebox.showinfo("알림", "URL에 쿼리 파라미터가 없습니다.", parent=self)

    def _sync_params_to_url(self):
        raw = self.text_params.get("1.0", tk.END).strip()
        if not raw:
            return
        params_dict = {}
        if raw.startswith("{"):
            try:
                params_dict = json.loads(raw)
            except Exception:
                pass
        else:
            for line in raw.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    params_dict[k.strip()] = v.strip()

        if params_dict:
            url = self.entry_url.get().strip()
            parsed = urllib.parse.urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.netloc else url
            qstr = urllib.parse.urlencode(params_dict)
            self.entry_url.delete(0, tk.END)
            self.entry_url.insert(0, f"{base}?{qstr}")

    def _load_initial_data(self):
        d = self.initial_data
        if not d:
            return
        if d.get("method"):
            self.combo_method.set(d["method"].upper())
        if d.get("url"):
            self.entry_url.delete(0, tk.END)
            self.entry_url.insert(0, d["url"])
        if d.get("headers"):
            h = d["headers"]
            if isinstance(h, dict):
                h = json.dumps(h, ensure_ascii=False, indent=2)
            self.text_req_headers.delete("1.0", tk.END)
            self.text_req_headers.insert("1.0", str(h))
        if d.get("body"):
            self.text_req_body.delete("1.0", tk.END)
            self.text_req_body.insert("1.0", str(d["body"]))
        if d.get("content_type"):
            self.var_content_type.set(d["content_type"])
        self._on_method_change()

    # ----------------- Execution & Response -----------------

    def _send_request(self):
        if self._is_loading:
            return

        url = self.entry_url.get().strip()
        if not url or url == "https://" or url == "http://":
            messagebox.showwarning("입력 필요", "요청을 전송할 URL을 입력해주세요.", parent=self)
            return

        method = self.combo_method.get().upper()
        
        # Headers
        headers_str = self.text_req_headers.get("1.0", tk.END).strip()
        headers_dict = {}
        if headers_str:
            try:
                headers_dict = json.loads(headers_str)
            except Exception:
                for line in headers_str.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        headers_dict[k.strip()] = v.strip()

        # Body
        ct = self.var_content_type.get()
        body_content = ""
        if ct != "none":
            body_content = self.text_req_body.get("1.0", tk.END).strip()

        # Auth
        atype = self.combo_auth_type.get()
        auth_data = {}
        if atype == "Bearer Token" and hasattr(self, "entry_auth_token"):
            auth_data["token"] = self.entry_auth_token.get().strip()
        elif atype == "Basic Auth" and hasattr(self, "entry_auth_user"):
            auth_data["username"] = self.entry_auth_user.get().strip()
            auth_data["password"] = self.entry_auth_pass.get().strip()
        elif atype == "API Key (Header)" and hasattr(self, "entry_auth_key"):
            auth_data["key"] = self.entry_auth_key.get().strip()
            auth_data["value"] = self.entry_auth_val.get().strip()

        auth_key_map = {
            "No Auth": "none",
            "Bearer Token": "bearer",
            "Basic Auth": "basic",
            "API Key (Header)": "apikey"
        }

        self._is_loading = True
        self.btn_send.config(state=tk.DISABLED, text="⏳ 전송 중...")
        self.lbl_status.config(text="서버로 요청 전송 중...", foreground="#2563eb")

        threading.Thread(
            target=self._worker_send,
            args=(method, url, headers_dict, body_content, ct if ct != "none" else "", auth_key_map.get(atype, "none"), auth_data),
            daemon=True
        ).start()

    def _worker_send(self, method, url, headers_dict, body_content, content_type, auth_type, auth_data):
        res = crawler.test_http_request(
            method=method,
            url=url,
            headers=headers_dict,
            body=body_content,
            content_type=content_type,
            auth_type=auth_type,
            auth_data=auth_data,
            timeout=25
        )
        self.after(0, self._render_response, res)

    def _render_response(self, res):
        self._is_loading = False
        self.btn_send.config(state=tk.NORMAL, text="⚡ 찔러보기 (Send)")
        self._current_response = res

        status_code = res.get("status_code", 0)
        status_reason = res.get("status_reason", "")
        time_ms = res.get("response_time_ms", 0)
        size_bytes = res.get("content_bytes_len", 0)
        size_str = f"{size_bytes} B" if size_bytes < 1024 else f"{size_bytes/1024:.1f} KB"

        # 1. Update Status Badge
        if 200 <= status_code < 300:
            color = "#16a34a" # Green
        elif 300 <= status_code < 400:
            color = "#2563eb" # Blue
        elif 400 <= status_code < 500:
            color = "#d97706" # Orange
        else:
            color = "#dc2626" # Red

        status_text = f"Status: {status_code} {status_reason}" if status_code > 0 else f"Error: {res.get('error', 'Failed')}"
        self.lbl_status.config(text=status_text, foreground=color)
        self.lbl_time.config(text=f"⏱️ {time_ms} ms")
        self.lbl_size.config(text=f"📦 {size_str}")

        raw_str = res.get("content_str", "")

        # 2. Pretty Tab
        self.text_pretty.delete("1.0", tk.END)
        if raw_str.strip().startswith(('{', '[')):
            try:
                parsed_json = json.loads(raw_str)
                self.text_pretty.insert("1.0", json.dumps(parsed_json, ensure_ascii=False, indent=2))
            except Exception:
                self.text_pretty.insert("1.0", res.get("extracted_text") or raw_str)
        else:
            self.text_pretty.insert("1.0", res.get("extracted_text") or raw_str)

        # 3. Raw Tab
        self.text_raw.delete("1.0", tk.END)
        self.text_raw.insert("1.0", raw_str)

        # 4. HTML Preview Tab
        self.text_html_preview.delete("1.0", tk.END)
        preview_header = f"=== [HTML 응답 분석 프리뷰] ===\nURL: {res.get('url')}\n크기: {size_str} | 상태: {status_code}\n\n"
        self.text_html_preview.insert("1.0", preview_header + (res.get("extracted_text") or raw_str))

        # Save to temp html file for browser opening
        try:
            temp_dir = tempfile.gettempdir()
            self._temp_html_path = os.path.join(temp_dir, "ameva_preview.html")
            with open(self._temp_html_path, "w", encoding="utf-8", errors="replace") as f:
                if "<html" not in raw_str.lower():
                    f.write(f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>AMEVA Preview</title><style>body{{font-family:sans-serif;padding:20px;background:#f8fafc;}}pre{{background:#fff;padding:15px;border-radius:8px;border:1px solid #e2e8f0;}}</style></head><body><h2>AMEVA-Crawler Response Preview</h2><pre>{raw_str}</pre></body></html>")
                else:
                    f.write(raw_str)
        except Exception:
            self._temp_html_path = None

        # 5. Response Headers Tab
        for item in self.tree_rheaders.get_children():
            self.tree_rheaders.delete(item)
        for h, v in res.get("response_headers", {}).items():
            self.tree_rheaders.insert("", tk.END, values=(h, v))

        # 6. Links Tab
        for item in self.tree_links.get_children():
            self.tree_links.delete(item)
        for l in res.get("extracted_links", []):
            self.tree_links.insert("", tk.END, values=(l.get("text", "-"), l.get("href", "-")))

    def _open_in_system_browser(self):
        if self._temp_html_path and os.path.exists(self._temp_html_path):
            webbrowser.open(f"file:///{os.path.abspath(self._temp_html_path).replace('\\', '/')}")
        else:
            url = self.entry_url.get().strip()
            if url.startswith("http"):
                webbrowser.open(url)
            else:
                messagebox.showinfo("알림", "렌더링할 HTML 응답이 없습니다.", parent=self)

    def _open_selected_link(self):
        sel = self.tree_links.selection()
        if not sel:
            messagebox.showinfo("선택 필요", "열고자 하는 링크를 목록에서 선택해주세요.", parent=self)
            return
        vals = self.tree_links.item(sel[0], "values")
        if vals and len(vals) >= 2 and vals[1] != "-":
            webbrowser.open(vals[1])

    def _copy_selected_link(self):
        sel = self.tree_links.selection()
        if not sel:
            return
        vals = self.tree_links.item(sel[0], "values")
        if vals and len(vals) >= 2:
            self.clipboard_clear()
            self.clipboard_append(vals[1])
            messagebox.showinfo("복사 완료", f"링크 URL이 클립보드에 복사되었습니다:\n{vals[1]}", parent=self)

    def _copy_response_body(self):
        if not self._current_response:
            return
        raw = self._current_response.get("content_str", "")
        if raw:
            self.clipboard_clear()
            self.clipboard_append(raw)
            messagebox.showinfo("복사 완료", "응답 내용이 클립보드에 복사되었습니다.", parent=self)

    def _create_schedule_target(self):
        url = self.entry_url.get().strip()
        if not url or url == "https://" or url == "http://":
            messagebox.showwarning("입력 필요", "등록할 대상 URL을 입력해주세요.", parent=self)
            return

        method = self.combo_method.get().upper()
        
        # Headers
        h_str = self.text_req_headers.get("1.0", tk.END).strip()
        
        # Body
        ct = self.var_content_type.get()
        body_val = self.text_req_body.get("1.0", tk.END).strip() if ct != "none" else ""

        # Default Name extraction
        parsed = urllib.parse.urlparse(url)
        target_name = parsed.netloc or "새로운 타겟"

        target_data = {
            "name": target_name,
            "url": url,
            "method": method,
            "headers": h_str,
            "body": body_val,
            "content_type": ct if ct != "none" else "application/json",
            "interval_type": "daily" if "json" in url else "interval",
            "interval_value": "09:00" if "json" in url else "300",
            "detect_mode": "all"
        }

        if self.on_create_target:
            self.on_create_target(target_data)
        self.destroy()
