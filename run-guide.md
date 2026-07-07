## Tóm tắt nhanh (copy-paste all-in-one)

```powershell
cd D:\UCTalent\openwork\linkedin_outreach\linkedin_outreach

# Cài đặt
pip install -r requirements.txt

# Mở Chrome (đóng hết Chrome trước!)
.\start_chrome.bat

# Kiểm tra
python chrome_utils.py diagnose

# Chạy
python guide.py
```

---

## Troubleshooting

| Vấn đề | Fix |
|--------|-----|
| `start_chrome.bat` không chạy | Dùng `.\start_chrome.bat` (có `.\`) |
| Chrome debug không active | Task Manager → kill hết chrome.exe → chạy lại `.\start_chrome.bat` |
| `pip` không tìm thấy | Dùng `python -m pip install -r requirements.txt` |
| Lỗi emoji / Unicode | PowerShell tự xử lý, nếu lỗi thì chạy: `$OutputEncoding = [console]::OutputEncoding = [Text.UTF8Encoding]::UTF8` |
