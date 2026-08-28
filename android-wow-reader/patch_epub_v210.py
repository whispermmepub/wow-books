from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/EpubUtil.java')
s = path.read_text(encoding='utf-8')

# Generic package metadata such as Unknown/Untitled must never replace the
# filename that the library already has available as a better fallback.
old = '''            result.title = clean(firstText(opfDoc, "title"));\n            result.author = clean(firstText(opfDoc, "creator"));\n'''
new = '''            result.title = clean(firstText(opfDoc, "title"));\n            if (isGenericTitle(result.title)) result.title = null;\n            result.author = clean(firstText(opfDoc, "creator"));\n'''
if old not in s:
    raise SystemExit('v2.1 epub: summary metadata anchor not found')
s = s.replace(old, new, 1)

old = '''        info.title = clean(firstText(opfDoc, "title"));\n        info.author = clean(firstText(opfDoc, "creator"));\n'''
new = '''        info.title = clean(firstText(opfDoc, "title"));\n        if (isGenericTitle(info.title)) info.title = null;\n        info.author = clean(firstText(opfDoc, "creator"));\n'''
if old not in s:
    raise SystemExit('v2.1 epub: book metadata anchor not found')
s = s.replace(old, new, 1)

# Broken nav documents often contain literal Unknown/Untitled labels. Keep the
# chapter title guessed from the chapter body instead of overwriting it.
old = '''                if (idx != null && idx >= 0 && idx < titles.size()) { titles.set(idx, label); applied = true; }\n'''
new = '''                if (idx != null && idx >= 0 && idx < titles.size() && !isGenericTitle(label)) { titles.set(idx, label); applied = true; }\n'''
if old not in s:
    raise SystemExit('v2.1 epub: nav title anchor not found')
s = s.replace(old, new, 1)

old = '''                if (idx != null && label != null && !label.isEmpty()) { titles.set(idx, label); applied = true; }\n'''
new = '''                if (idx != null && label != null && !label.isEmpty() && !isGenericTitle(label)) { titles.set(idx, label); applied = true; }\n'''
if old not in s:
    raise SystemExit('v2.1 epub: ncx title anchor not found')
s = s.replace(old, new, 1)

start = s.index('    private static String guessChapterTitle(File chapter, int number) {')
end = s.index('\n    private static File resolveFile', start)
replacement = r'''    private static String guessChapterTitle(File chapter, int number) {
        try {
            Document doc = parseXml(chapter);

            String title = clean(firstText(doc, "title"));
            if (isMeaningfulChapterTitle(title)) return title;

            for (String tag : new String[]{"h1", "h2", "h3", "h4"}) {
                NodeList nodes = elements(doc, tag);
                for (int i = 0; i < nodes.getLength(); i++) {
                    String h = clean(nodes.item(i).getTextContent());
                    if (isMeaningfulChapterTitle(h) && h.length() <= 160) return h;
                }
            }

            // Some EPUBs put a chapter heading in an ordinary element whose
            // class/id contains title/chapter/heading rather than using h1-h4.
            NodeList all = doc.getElementsByTagName("*");
            for (int i = 0; i < all.getLength(); i++) {
                if (!(all.item(i) instanceof Element)) continue;
                Element e = (Element) all.item(i);
                String hint = (e.getAttribute("class") + " " + e.getAttribute("id")).toLowerCase(Locale.ROOT);
                if (!(hint.contains("title") || hint.contains("chapter") || hint.contains("heading"))) continue;
                String value = clean(e.getTextContent());
                if (isMeaningfulChapterTitle(value) && value.length() <= 160) return value;
            }

            // Last body-text fallback: only use short text, never a full
            // paragraph. This removes generic labels while keeping the TOC readable.
            NodeList paragraphs = elements(doc, "p");
            for (int i = 0; i < paragraphs.getLength(); i++) {
                String p = clean(paragraphs.item(i).getTextContent());
                if (isMeaningfulChapterTitle(p) && p.length() >= 2 && p.length() <= 84) return p;
            }
        } catch (Exception ignored) {}

        String fileTitle = titleFromFilename(chapter == null ? null : chapter.getName());
        if (fileTitle != null) return fileTitle;
        return "Chapter " + number;
    }

    private static boolean isMeaningfulChapterTitle(String value) {
        if (value == null) return false;
        String v = clean(value);
        if (v == null || v.length() < 1 || isGenericTitle(v)) return false;
        String compact = v.replaceAll("[\\p{Punct}\\s]+", "");
        return !compact.isEmpty();
    }

    private static boolean isGenericTitle(String value) {
        if (value == null) return true;
        String v = clean(value);
        if (v == null || v.isEmpty()) return true;
        String low = v.toLowerCase(Locale.ROOT).replaceAll("[._-]+", " ").replaceAll("\\s+", " ").trim();
        if (low.equals("unknown") || low.equals("untitled") || low.equals("undefined") ||
                low.equals("null") || low.equals("none") || low.equals("n a") ||
                low.equals("no title") || low.equals("no name") || low.equals("title")) return true;
        return low.matches("^(chapter|section|part|page|text|content|item|file)\\s*\\d*$");
    }

    private static String titleFromFilename(String name) {
        if (name == null || name.isEmpty()) return null;
        int dot = name.lastIndexOf('.');
        String base = dot > 0 ? name.substring(0, dot) : name;
        String cleaned = clean(base.replace('_', ' ').replace('-', ' '));
        if (!isMeaningfulChapterTitle(cleaned)) return null;
        String low = cleaned.toLowerCase(Locale.ROOT);
        if (low.matches("^(chapter|section|part|page|text|content|item|file)\\s*\\d+$")) return null;
        if (cleaned.matches("^\\d+$")) return null;
        return cleaned;
    }
'''
s = s[:start] + replacement + s[end:]

assert 'isGenericTitle(result.title)' in s
assert 'isGenericTitle(info.title)' in s
assert 'titleFromFilename' in s
assert 'isMeaningfulChapterTitle' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.1 EPUB title cleanup patch applied')
