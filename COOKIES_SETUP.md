# YouTube Cookies Setup Guide

## Method 1: Export from Browser (Recommended)

### Chrome/Edge:
1. Install extension: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Go to youtube.com and make sure you're logged in
3. Click the extension icon
4. Click "Export" → saves `cookies.txt` to Downloads
5. Upload to server

### Firefox:
1. Install addon: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
2. Go to youtube.com (logged in)
3. Click addon icon → "Current Site"
4. Save the file
5. Upload to server

## Method 2: Manual Export (Advanced)

1. Open DevTools (F12) on youtube.com
2. Go to Application → Cookies → https://youtube.com
3. Copy all cookies
4. Format as Netscape cookies.txt

## Upload to Server

Once you have `cookies.txt`:

```bash
# From your local machine:
scp cookies.txt root@104.248.158.217:/root/projects/file-converter/youtube_cookies.txt
```

Or use any file transfer method (SFTP, panel file manager, etc.)

## Security Note

⚠️ **Cookies contain your login session** - treat like a password:
- Don't share the file
- Cookies expire after ~6 months (you'll need to re-export)
- If you change your YouTube password, re-export cookies
