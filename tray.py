"""
AMEVA-Crawler System Tray Module
Pure Python standard library Windows System Tray integration using ctypes (Win32 API).
Zero external dependencies.
"""
import ctypes
from ctypes import wintypes
import threading
import os
import time

# Global Tray Instance for balloon notifications
global_tray_instance = None
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_COMMAND = 0x0111
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_DESTROY = 0x0002

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010

NIIF_NONE = 0x00000000
NIIF_INFO = 0x00000001
NIIF_WARNING = 0x00000002
NIIF_ERROR = 0x00000003

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002

# Menu IDs
IDM_SHOW = 1001
IDM_RUN_ALL = 1002
IDM_EXIT = 1003

# Win32 Structures
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8)
    ]

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]

# C functions
user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR)
    ]

# Explicit 64-bit / 32-bit Win32 prototypes
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT

user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.LoadImageW.restype = wintypes.HANDLE

user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadIconW.restype = wintypes.HICON

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = wintypes.HMENU

user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.AppendMenuW.restype = wintypes.BOOL

user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.TrackPopupMenu.restype = wintypes.BOOL

user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.DestroyMenu.restype = wintypes.BOOL

class WindowsTrayIcon:
    def __init__(self, icon_path, tooltip="AMEVA-Crawler", on_show=None, on_run_all=None, on_exit=None):
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.on_show = on_show
        self.on_run_all = on_run_all
        self.on_exit = on_exit

        self.hwnd = None
        self.hicon = None
        self._thread = None
        self._running = False
        self._nid = None
        self.wnd_proc = WNDPROC(self._wnd_proc_callback)

    def start(self):
        """Start tray message loop in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_tray_thread, daemon=True, name="TrayThread")
        self._thread.start()

    def stop(self):
        """Remove tray icon and destroy hidden window."""
        self._running = False
        if self.hwnd and self._nid:
            try:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            except Exception:
                pass
            try:
                user32.PostMessageW(self.hwnd, WM_DESTROY, 0, 0)
            except Exception:
                pass

    def show_balloon(self, title, message, is_warning=False):
        """Display Windows system tray balloon notification."""
        if not self.hwnd or not self._nid:
            return

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = str(title)[:63]
        nid.szInfo = str(message)[:255]
        nid.dwInfoFlags = NIIF_WARNING if is_warning else NIIF_INFO
        nid.uTimeoutOrVersion = 10000

        try:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        except Exception:
            pass

    def _run_tray_thread(self):
        hinstance = kernel32.GetModuleHandleW(None)
        class_name = "AMEVATrayWindowClass"

        wndclass = WNDCLASSW()
        wndclass.hInstance = hinstance
        wndclass.lpszClassName = class_name
        wndclass.lpfnWndProc = self.wnd_proc
        wndclass.style = 0
        wndclass.cbClsExtra = 0
        wndclass.cbWndExtra = 0
        wndclass.hIcon = 0
        wndclass.hCursor = 0
        wndclass.hbrBackground = 0
        wndclass.lpszMenuName = None

        user32.RegisterClassW(ctypes.byref(wndclass))

        self.hwnd = user32.CreateWindowExW(
            0, class_name, "AMEVATrayWindow",
            0, 0, 0, 0, 0,
            0, 0, hinstance, 0
        )

        # Load Icon
        if os.path.exists(self.icon_path):
            self.hicon = user32.LoadImageW(
                None, self.icon_path, IMAGE_ICON,
                0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
        else:
            self.hicon = user32.LoadIconW(0, 32512) # IDI_APPLICATION fallback

        # Register System Tray Icon
        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = self.hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP
        self._nid.uCallbackMessage = WM_TRAYICON
        self._nid.hIcon = self.hicon
        self._nid.szTip = self.tooltip[:127]

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))

        # Windows Message Loop
        msg = wintypes.MSG()
        while self._running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _show_menu(self):
        """Show context popup menu on right-click."""
        hmenu = user32.CreatePopupMenu()
        user32.AppendMenuW(hmenu, MF_STRING, IDM_SHOW, "🖥️ AMEVA-Crawler 열기")
        user32.AppendMenuW(hmenu, MF_STRING, IDM_RUN_ALL, "⚡ 지금 전체 크롤링")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, "")
        user32.AppendMenuW(hmenu, MF_STRING, IDM_EXIT, "❌ 프로그램 완전 종료")

        pos = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pos))
        user32.SetForegroundWindow(self.hwnd)
        user32.TrackPopupMenu(hmenu, TPM_RIGHTBUTTON, pos.x, pos.y, 0, self.hwnd, None)
        user32.DestroyMenu(hmenu)

    def _wnd_proc_callback(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAYICON:
                if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    if self.on_show:
                        self.on_show()
                elif lparam == WM_RBUTTONUP:
                    self._show_menu()
                return 0

            elif msg == WM_COMMAND:
                cmd = wparam & 0xFFFF
                if cmd == IDM_SHOW and self.on_show:
                    self.on_show()
                elif cmd == IDM_RUN_ALL and self.on_run_all:
                    self.on_run_all()
                elif cmd == IDM_EXIT and self.on_exit:
                    self.on_exit()
                return 0

            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0

            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except Exception:
            return 0
