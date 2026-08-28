from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/EpubUtil.java')
s = path.read_text(encoding='utf-8')

# ---------------------------------------------------------------------------
# v2.2: keep the reading spine separate from the user-visible table of contents.
# The previous reader displayed every spine XHTML as a chapter, which exposed
# cover/about/publisher helper pages and guessed paragraph titles as chapters.
# ---------------------------------------------------------------------------
old = '''    static final class BookInfo {\n        String title;\n        String author;\n        final List<File> spine = new ArrayList<>();\n        final List<String> chapterTitles = new ArrayList<>();\n    }\n'''
new = '''    static final class BookInfo {\n        String title;\n        String author;\n        final List<File> spine = new ArrayList<>();\n        final List<String> chapterTitles = new ArrayList<>();\n        final List<Integer> tocSpineIndices = new ArrayList<>();\n        final List<String> tocTitles = new ArrayList<>();\n        final List<String> tocFragments = new ArrayList<>();\n    }\n'''
if old not in s:
    raise SystemExit('v2.2 epub: BookInfo anchor not found')
s = s.replace(old, new, 1)

# Honor the EPUB linear reading-order flag and drop truly empty XHTML resources.
old = '''        NodeList refs = elements(opfDoc, "itemref");\n        for (int i = 0; i < refs.getLength(); i++) {\n            Element ref = (Element) refs.item(i);\n            ManifestItem item = items.get(ref.getAttribute("idref"));\n            if (item == null || item.href == null || item.href.isEmpty()) continue;\n            File chapter = resolveFile(opfDir, item.href);\n            if (!chapter.isFile()) continue;\n            int index = info.spine.size();\n            info.spine.add(chapter);\n            info.chapterTitles.add(guessChapterTitle(chapter, index + 1));\n            spineIndex.put(canonical(chapter), index);\n        }\n'''
new = '''        NodeList refs = elements(opfDoc, "itemref");\n        for (int i = 0; i < refs.getLength(); i++) {\n            Element ref = (Element) refs.item(i);\n            if ("no".equalsIgnoreCase(ref.getAttribute("linear"))) continue;\n            ManifestItem item = items.get(ref.getAttribute("idref"));\n            if (item == null || item.href == null || item.href.isEmpty()) continue;\n            if (hasWord(item.properties, "nav")) continue;\n            File chapter = resolveFile(opfDir, item.href);\n            if (!chapter.isFile() || !hasReadableContent(chapter)) continue;\n            int index = info.spine.size();\n            info.spine.add(chapter);\n            info.chapterTitles.add(guessChapterTitle(chapter, index + 1));\n            spineIndex.put(canonical(chapter), index);\n        }\n'''
if old not in s:
    raise SystemExit('v2.2 epub: spine loop anchor not found')
s = s.replace(old, new, 1)

# Build a dedicated TOC from the EPUB's actual nav/NCX entries. Only when the
# package has no usable TOC do we fall back to strict visible headings.
old = '''        boolean tocFound = false;\n        if (navItem != null) tocFound = applyNavTitles(resolveFile(opfDir, navItem.href), spineIndex, info.chapterTitles);\n        if (!tocFound && ncxItem != null) applyNcxTitles(resolveFile(opfDir, ncxItem.href), spineIndex, info.chapterTitles);\n        return info;\n'''
new = '''        boolean tocFound = false;\n        if (navItem != null) tocFound = applyNavTitles(resolveFile(opfDir, navItem.href), spineIndex, info.chapterTitles);\n        if (!tocFound && ncxItem != null) applyNcxTitles(resolveFile(opfDir, ncxItem.href), spineIndex, info.chapterTitles);\n\n        boolean exactToc = false;\n        if (navItem != null) exactToc = collectNavEntries(resolveFile(opfDir, navItem.href), spineIndex, info);\n        if (!exactToc && ncxItem != null) exactToc = collectNcxEntries(resolveFile(opfDir, ncxItem.href), spineIndex, info);\n        if (!exactToc) collectStrictHeadingFallback(info);\n\n        return info;\n'''
if old not in s:
    raise SystemExit('v2.2 epub: TOC finish anchor not found')
s = s.replace(old, new, 1)

# Insert exact TOC and blank-resource helpers before resolveFile.
marker = '    private static File resolveFile(File base, String href) {'
if marker not in s:
    raise SystemExit('v2.2 epub: helper insertion anchor not found')
helpers = r'''    private static boolean collectNavEntries(File navFile, Map<String, Integer> spineIndex, BookInfo info) {
        if (navFile == null || !navFile.isFile()) return false;
        boolean added = false;
        try {
            Document doc = parseXml(navFile);
            Element targetNav = null;
            NodeList navs = elements(doc, "nav");
            for (int i = 0; i < navs.getLength(); i++) {
                Element nav = (Element) navs.item(i);
                String type = nav.getAttribute("epub:type");
                if (type.isEmpty()) type = nav.getAttributeNS("http://www.idpf.org/2007/ops", "type");
                if (type.toLowerCase(Locale.ROOT).contains("toc")) { targetNav = nav; break; }
            }
            if (targetNav == null) return false;

            NodeList anchors = targetNav.getElementsByTagNameNS("*", "a");
            if (anchors.getLength() == 0) anchors = targetNav.getElementsByTagName("a");
            for (int i = 0; i < anchors.getLength(); i++) {
                Element a = (Element) anchors.item(i);
                String href = a.getAttribute("href");
                String label = clean(a.getTextContent());
                if (href.isEmpty() || !isMeaningfulChapterTitle(label) || isAuxiliaryTocLabel(label)) continue;
                Integer idx = spineIndex.get(canonical(resolveFile(navFile.getParentFile(), href)));
                if (idx == null || idx < 0 || idx >= info.spine.size()) continue;
                String fragment = fragmentFromHref(href);
                if (addTocEntry(info, idx, label, fragment)) added = true;
            }
        } catch (Exception ignored) {}
        return added;
    }

    private static boolean collectNcxEntries(File ncxFile, Map<String, Integer> spineIndex, BookInfo info) {
        if (ncxFile == null || !ncxFile.isFile()) return false;
        boolean added = false;
        try {
            Document doc = parseXml(ncxFile);
            NodeList points = elements(doc, "navPoint");
            for (int i = 0; i < points.getLength(); i++) {
                Element point = (Element) points.item(i);
                NodeList contents = point.getElementsByTagNameNS("*", "content");
                if (contents.getLength() == 0) contents = point.getElementsByTagName("content");
                NodeList texts = point.getElementsByTagNameNS("*", "text");
                if (texts.getLength() == 0) texts = point.getElementsByTagName("text");
                if (contents.getLength() == 0 || texts.getLength() == 0) continue;
                String href = ((Element) contents.item(0)).getAttribute("src");
                String label = clean(texts.item(0).getTextContent());
                if (!isMeaningfulChapterTitle(label) || isAuxiliaryTocLabel(label)) continue;
                Integer idx = spineIndex.get(canonical(resolveFile(ncxFile.getParentFile(), href)));
                if (idx == null || idx < 0 || idx >= info.spine.size()) continue;
                if (addTocEntry(info, idx, label, fragmentFromHref(href))) added = true;
            }
        } catch (Exception ignored) {}
        return added;
    }

    private static boolean addTocEntry(BookInfo info, int spineIndex, String title, String fragment) {
        String cleanTitle = clean(title);
        if (!isMeaningfulChapterTitle(cleanTitle) || isAuxiliaryTocLabel(cleanTitle)) return false;
        String cleanFragment = fragment == null ? "" : fragment.trim();
        for (int i = 0; i < info.tocTitles.size(); i++) {
            if (info.tocSpineIndices.get(i) == spineIndex &&
                    info.tocTitles.get(i).equals(cleanTitle) &&
                    info.tocFragments.get(i).equals(cleanFragment)) return false;
        }
        info.tocSpineIndices.add(spineIndex);
        info.tocTitles.add(cleanTitle);
        info.tocFragments.add(cleanFragment);
        return true;
    }

    private static void collectStrictHeadingFallback(BookInfo info) {
        for (int i = 0; i < info.spine.size(); i++) {
            String title = strictChapterHeading(info.spine.get(i));
            if (title != null && !isAuxiliaryTocLabel(title)) addTocEntry(info, i, title, "");
        }
        if (info.tocTitles.isEmpty() && !info.spine.isEmpty()) {
            addTocEntry(info, 0, "Start", "");
        }
    }

    private static String strictChapterHeading(File chapter) {
        try {
            Document doc = parseXml(chapter);
            for (String tag : new String[]{"h1", "h2", "h3", "h4"}) {
                NodeList nodes = elements(doc, tag);
                for (int i = 0; i < nodes.getLength(); i++) {
                    String value = clean(nodes.item(i).getTextContent());
                    if (isMeaningfulChapterTitle(value) && value.length() <= 180) return value;
                }
            }
            NodeList all = doc.getElementsByTagName("*");
            for (int i = 0; i < all.getLength(); i++) {
                if (!(all.item(i) instanceof Element)) continue;
                Element e = (Element) all.item(i);
                String hint = (e.getAttribute("class") + " " + e.getAttribute("id")).toLowerCase(Locale.ROOT);
                if (!(hint.contains("chapter") || hint.contains("heading") || hint.contains("chapter-title"))) continue;
                String value = clean(e.getTextContent());
                if (isMeaningfulChapterTitle(value) && value.length() <= 180) return value;
            }
        } catch (Exception ignored) {}
        return null;
    }

    private static boolean hasReadableContent(File chapter) {
        try {
            Document doc = parseXml(chapter);
            Element body = firstElement(doc, "body");
            if (body != null) {
                String text = clean(body.getTextContent());
                if (text != null && !text.replaceAll("[\\p{Punct}\\s]+", "").isEmpty()) return true;
            }
            for (String tag : new String[]{"img", "image", "svg", "math", "table", "video", "audio", "object", "embed", "canvas"}) {
                if (elements(doc, tag).getLength() > 0) return true;
            }
            return false;
        } catch (Exception ignored) {
            // Broken-but-renderable HTML should be kept rather than silently lost.
            return true;
        }
    }

    private static boolean isAuxiliaryTocLabel(String value) {
        if (value == null) return true;
        String low = clean(value).toLowerCase(Locale.ROOT)
                .replaceAll("[._-]+", " ").replaceAll("\\s+", " ").trim();
        return low.equals("cover") || low.equals("cover page") || low.equals("title page") ||
                low.equals("copyright") || low.equals("copyright page") || low.equals("imprint") ||
                low.equals("about us") || low.equals("publisher") || low.equals("publishers") ||
                low.equals("contents") || low.equals("table of contents") || low.equals("toc");
    }

    private static String fragmentFromHref(String href) {
        if (href == null) return "";
        int hash = href.indexOf('#');
        if (hash < 0 || hash + 1 >= href.length()) return "";
        String fragment = href.substring(hash + 1);
        try { fragment = URLDecoder.decode(fragment, StandardCharsets.UTF_8.name()); } catch (Exception ignored) {}
        return fragment.trim();
    }

'''
s = s.replace(marker, helpers + marker, 1)

assert 'tocSpineIndices' in s
assert '"no".equalsIgnoreCase(ref.getAttribute("linear"))' in s
assert 'hasReadableContent(chapter)' in s
assert 'collectNavEntries' in s
assert 'collectNcxEntries' in s
assert 'isAuxiliaryTocLabel' in s
assert 'fragmentFromHref' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.2 exact TOC + readable spine filtering patch applied')
