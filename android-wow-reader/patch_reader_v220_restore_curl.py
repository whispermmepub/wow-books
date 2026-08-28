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

# v2.2 replaces the v2.1 TOC range, so also restore the small display/glass
# helpers that were originally defined in that range.
marker = '    private String jsQuote(String'
helper_block = r'''    private String chapterDisplayTitle(int index) {
        String value = index >= 0 && index < chapterTitles.size() ? chapterTitles.get(index) : null;
        if (isGenericDisplayTitle(value)) return "Chapter " + (index + 1);
        return value.trim();
    }

    private boolean isGenericDisplayTitle(String value) {
        if (value == null) return true;
        String low = value.trim().toLowerCase(Locale.ROOT).replace('_', ' ').replace('-', ' ').replaceAll("\\s+", " ");
        if (low.isEmpty() || low.equals("unknown") || low.equals("untitled") || low.equals("undefined") ||
                low.equals("null") || low.equals("none") || low.equals("n/a") || low.equals("no title")) return true;
        return low.matches("^(chapter|section|part|page|text|content|item|file)\\s*$");
    }

    private GradientDrawable glassPanel(int fill, int radius, int stroke) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(radius);
        if (Color.alpha(stroke) > 0) d.setStroke(Math.max(1, dp(1)), stroke);
        return d;
    }

'''
if '    private String chapterDisplayTitle(int index)' not in s:
    pos = s.index(marker)
    s = s[:pos] + helper_block + s[pos:]

assert 'private void turnPage(int delta)' in s
assert 'private void startNativePageCurl' in s
assert 'private boolean finishPendingChapterCurl' in s
assert 'private Bitmap captureWebViewBitmap' in s
assert 'private String chapterDisplayTitle(int index)' in s
assert 'private boolean isGenericDisplayTitle(String value)' in s
assert 'private GradientDrawable glassPanel(int fill, int radius, int stroke)' in s

reader.write_text(s, encoding='utf-8')
print('WoW Reader v2.2 native curl + glass helpers restored')
