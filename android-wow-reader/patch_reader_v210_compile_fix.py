from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

signature = '    private String jsQuote(String s) {'
if signature not in s:
    marker = '    private void showReaderSettings() {\n'
    if marker not in s:
        raise SystemExit('v2.1 compile fix: settings marker not found')
    helper = r'''    private String jsQuote(String value) {
        if (value == null) return "''";
        return "'" + value
                .replace("\\", "\\\\")
                .replace("'", "\\'")
                .replace("\r", " ")
                .replace("\n", " ") + "'";
    }

'''
    s = s.replace(marker, helper + marker, 1)

assert 'private String jsQuote(String' in s
assert 'jsQuote(textAlignment)' in s
assert 'jsQuote(css)' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.1 JS quoting helper restored')
