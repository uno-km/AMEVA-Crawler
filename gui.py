"""
AMEVA-Crawler GUI Module
Pure Python standard library GUI built with tkinter and ttk with System Tray integration.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
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

    def _open_add_target_dialog(self):
        TargetDialog(self.root, on_saved=self._load_targets)

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
        self.combo_method = ttk.Combobox(row1, values=["GET", "POST"], state="readonly", width=8)
        self.combo_method.set("GET")
        self.combo_method.pack(side=tk.LEFT, padx=6)
        self.combo_method.bind("<<ComboboxSelected>>", self._on_method_changed)

        # 2. URL
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, **pad)
        ttk.Label(row2, text="대상 URL:").pack(side=tk.LEFT)
        self.entry_url = ttk.Entry(row2)
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # 3. POST Body Frame (Conditional)
        self.post_frame = ttk.LabelFrame(main_frame, text="POST 요청 설정 (Body & Content-Type)", padding=6)
        
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
        if self.combo_method.get() == "POST":
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
        self.entry_name.insert(0, t.get("name", ""))
        self.entry_url.insert(0, t.get("url", ""))
        self.combo_method.set(t.get("method", "GET"))
        self._on_method_changed()

        if t.get("headers") and t.get("headers") != "{}":
            self.text_headers.insert("1.0", t.get("headers"))

        if t.get("method") == "POST":
            self.combo_content_type.set(t.get("content_type", "application/json"))
            self.text_body.insert("1.0", t.get("body", ""))

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

        self.entry_rule.insert(0, t.get("selector_rule", ""))

    def _save_target(self):
        name = self.entry_name.get().strip()
        url = self.entry_url.get().strip()
        if not name or not url:
            messagebox.showwarning("입력 오류", "타겟 명칭과 URL은 필수 입력 항목입니다.", parent=self)
            return

        method = self.combo_method.get()
        headers = self.text_headers.get("1.0", tk.END).strip() or "{}"
        body = self.text_body.get("1.0", tk.END).strip() if method == "POST" else ""
        content_type = self.combo_content_type.get() if method == "POST" else "application/json"

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
