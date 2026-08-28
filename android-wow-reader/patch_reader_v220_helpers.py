from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

marker = '    private String jsQuote(String'
if marker not in s:
    raise SystemExit('v2.2 helpers: jsQuote marker not found')

helpers = r'''    private String chapterDisplayTitle(int index) {
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
    s = s.replace(marker, helpers + marker, 1)

assert 'private String chapterDisplayTitle(int index)' in s
assert 'private boolean isGenericDisplayTitle(String value)' in s
assert 'private GradientDrawable glassPanel(int fill, int radius, int stroke)' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.2 reader display helpers restored')
