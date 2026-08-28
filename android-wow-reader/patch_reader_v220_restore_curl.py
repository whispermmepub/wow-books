from pathlib import Path

reader = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
source_patch = Path('android-wow-reader/patch_reader_v210.py')
s = reader.read_text(encoding='utf-8')

if '    private void startNativePageCurl(' not in s:
    patch_text = source_patch.read_text(encoding='utf-8')
    start_marker = "turn = r'''"
    start = patch_text.index(start_marker) + len(start_marker)
    end = patch_text.index("\n'''\ns = s[:start] + turn + s[end:]", start)
    native_block = patch_text[start:end]

    marker = '    private String jsQuote(String'
    pos = s.index(marker)
    s = s[:pos] + native_block + '\n\n' + s[pos:]

assert 'private void turnPage(int delta)' in s
assert 'private void startNativePageCurl' in s
assert 'private void finishPendingChapterCurl' in s
assert 'private Bitmap captureWebViewBitmap' in s

reader.write_text(s, encoding='utf-8')
print('WoW Reader v2.2 native curl methods restored')
