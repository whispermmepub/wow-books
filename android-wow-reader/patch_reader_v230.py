from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# Imports for selection actions, notes, clipboard and translation.
s = s.replace('import android.content.SharedPreferences;\n',
'''import android.content.ClipData;\nimport android.content.ClipboardManager;\nimport android.content.Intent;\nimport android.content.SharedPreferences;\n''', 1)
s = s.replace('import android.view.GestureDetector;\n',
'''import android.view.ActionMode;\nimport android.view.GestureDetector;\nimport android.view.Menu;\nimport android.view.MenuItem;\n''', 1)
s = s.replace('import java.util.zip.ZipEntry;\n',
'''import org.json.JSONObject;\nimport org.json.JSONTokener;\n\nimport java.util.zip.ZipEntry;\n''', 1)

# Annotation toolbar state.
anchor = '    private TextView appearanceButton;\n'
if anchor not in s:
    raise SystemExit('v2.3 reader: appearanceButton anchor not found')
s = s.replace(anchor, anchor + '''    private TextView annotationButton;\n    private String pendingAnnotationId = null;\n    private static final int SEL_HIGHLIGHT = 9301;\n    private static final int SEL_NOTE = 9302;\n    private static final int SEL_TRANSLATE = 9303;\n    private static final int SEL_COPY = 9304;\n''', 1)

# Notes & highlights button beside the existing bookmark control.
anchor = '''        topBar.addView(bookmarkButton, new LinearLayout.LayoutParams(dp(46), dp(50)));\n\n        appearanceButton = iconButton("Aa", 15);\n'''
if anchor not in s:
    raise SystemExit('v2.3 reader: bookmark toolbar anchor not found')
s = s.replace(anchor, '''        topBar.addView(bookmarkButton, new LinearLayout.LayoutParams(dp(44), dp(50)));\n\n        annotationButton = iconButton("✎", 18);\n        annotationButton.setContentDescription("Notes and highlights");\n        annotationButton.setOnClickListener(v -> showAnnotations());\n        topBar.addView(annotationButton, new LinearLayout.LayoutParams(dp(42), dp(50)));\n\n        appearanceButton = iconButton("Aa", 15);\n''', 1)

# PDFs do not yet expose text annotations through PdfRenderer.
anchor = '''        if (isPdf) {\n            contentsButton.setVisibility(View.GONE);\n            search.setVisibility(View.GONE);\n        }\n'''
if anchor not in s:
    raise SystemExit('v2.3 reader: PDF toolbar anchor not found')
s = s.replace(anchor, '''        if (isPdf) {\n            contentsButton.setVisibility(View.GONE);\n            search.setVisibility(View.GONE);\n            if (annotationButton != null) annotationButton.setVisibility(View.GONE);\n        }\n''', 1)

# Add a custom WebView selection toolbar. The selected text is captured before
# ActionMode closes so Android cannot clear the selection too early.
anchor = '        webView.addJavascriptInterface(new ReaderBridge(), "WoW");\n\n'
if anchor not in s:
    raise SystemExit('v2.3 reader: JS bridge anchor not found')
s = s.replace(anchor, anchor + '''        webView.setCustomSelectionActionModeCallback(createSelectionActionModeCallback());\n\n''', 1)

# Re-apply persistent annotations after typography/page layout is injected.
anchor = '''                applyReaderStyle(true);\n                if ("scroll".equals(readingMode)) {\n'''
if anchor not in s:
    raise SystemExit('v2.3 reader: onPageFinished anchor not found')
s = s.replace(anchor, '''                applyReaderStyle(true);\n                webView.postDelayed(() -> applySavedAnnotations(), 420L);\n                webView.postDelayed(() -> applySavedAnnotations(), 1350L);\n                if ("scroll".equals(readingMode)) {\n''', 1)

# Insert annotation/translation implementation before PDF view setup.
marker = '    private void setupPdfView(FrameLayout content) {'
pos = s.index(marker)
helpers = r'''    private static final class SelectionData {
        String text;
        int start;
        int end;
    }

    private ActionMode.Callback createSelectionActionModeCallback() {
        return new ActionMode.Callback() {
            @Override public boolean onCreateActionMode(ActionMode mode, Menu menu) {
                menu.clear();
                menu.add(0, SEL_HIGHLIGHT, 0, "Highlight").setShowAsAction(MenuItem.SHOW_AS_ACTION_IF_ROOM);
                menu.add(0, SEL_NOTE, 1, "Add note").setShowAsAction(MenuItem.SHOW_AS_ACTION_IF_ROOM);
                menu.add(0, SEL_TRANSLATE, 2, "Translate").setShowAsAction(MenuItem.SHOW_AS_ACTION_IF_ROOM);
                menu.add(0, SEL_COPY, 3, "Copy").setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
                return true;
            }

            @Override public boolean onPrepareActionMode(ActionMode mode, Menu menu) { return false; }

            @Override public boolean onActionItemClicked(ActionMode mode, MenuItem item) {
                int id = item.getItemId();
                if (id != SEL_HIGHLIGHT && id != SEL_NOTE && id != SEL_TRANSLATE && id != SEL_COPY)
                    return false;
                captureCurrentSelection(id, mode);
                return true;
            }

            @Override public void onDestroyActionMode(ActionMode mode) {}
        };
    }

    private void captureCurrentSelection(int action, ActionMode mode) {
        if (webView == null || isPdf) {
            if (mode != null) mode.finish();
            return;
        }
        String js = "(function(){try{" +
                "var sel=window.getSelection&&window.getSelection();if(!sel||sel.rangeCount===0||sel.isCollapsed)return null;" +
                "var range=sel.getRangeAt(0),root=document.getElementById('wow-page-flow')||document.body;" +
                "if(!root||!root.contains(range.commonAncestorContainer))return null;" +
                "var pre=document.createRange();pre.selectNodeContents(root);pre.setEnd(range.startContainer,range.startOffset);" +
                "var start=pre.toString().length;var text=range.toString();" +
                "return JSON.stringify({text:text,start:start,end:start+text.length});" +
                "}catch(e){return null;}})()";
        try {
            webView.evaluateJavascript(js, result -> {
                SelectionData data = parseSelectionResult(result);
                if (mode != null) mode.finish();
                clearWebSelection();
                if (data == null || data.text == null || data.text.trim().isEmpty() || data.end <= data.start) {
                    Toast.makeText(this, "Select some text first", Toast.LENGTH_SHORT).show();
                    return;
                }
                data.text = data.text.trim();
                if (action == SEL_HIGHLIGHT) showHighlightColorDialog(data);
                else if (action == SEL_NOTE) showNoteEditor(data);
                else if (action == SEL_TRANSLATE) showTranslateDialog(data.text);
                else if (action == SEL_COPY) copySelectedText(data.text);
            });
        } catch (Exception e) {
            if (mode != null) mode.finish();
        }
    }

    private SelectionData parseSelectionResult(String result) {
        if (result == null || "null".equals(result)) return null;
        try {
            Object decoded = new JSONTokener(result).nextValue();
            String raw = decoded instanceof String ? (String) decoded : String.valueOf(decoded);
            JSONObject o = new JSONObject(raw);
            SelectionData d = new SelectionData();
            d.text = o.optString("text", "");
            d.start = Math.max(0, o.optInt("start", 0));
            d.end = Math.max(d.start, o.optInt("end", d.start));
            return d;
        } catch (Exception ignored) {
            return null;
        }
    }

    private void clearWebSelection() {
        if (webView == null) return;
        try {
            webView.evaluateJavascript("(function(){try{var s=window.getSelection();if(s)s.removeAllRanges();}catch(e){}})()", null);
        } catch (Exception ignored) {}
    }

    private void showHighlightColorDialog(SelectionData data) {
        String[] labels = {"Yellow", "Green", "Blue", "Pink"};
        String[] colors = {
                "rgba(255,235,59,.48)",
                "rgba(129,199,132,.45)",
                "rgba(100,181,246,.42)",
                "rgba(244,143,177,.42)"
        };
        new AlertDialog.Builder(this)
                .setTitle("Highlight")
                .setItems(labels, (dialog, which) -> saveAnnotation(data, colors[which], ""))
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void showNoteEditor(SelectionData data) {
        EditText input = new EditText(this);
        input.setHint("Write a note…");
        input.setMinLines(3);
        input.setMaxLines(7);
        input.setPadding(dp(16), dp(10), dp(16), dp(10));
        new AlertDialog.Builder(this)
                .setTitle("Add note")
                .setMessage(shortQuote(data.text, 180))
                .setView(input)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", (dialog, which) ->
                        saveAnnotation(data, "rgba(255,235,59,.42)", input.getText().toString()))
                .show();
    }

    private void saveAnnotation(SelectionData data, String color, String note) {
        ReaderAnnotationStore.add(prefs, bookFile.getName(), currentSpine,
                data.start, data.end, data.text, color, note);
        applySavedAnnotations();
        updateAnnotationButton();
        Toast.makeText(this, note == null || note.trim().isEmpty() ? "Highlighted" : "Note saved",
                Toast.LENGTH_SHORT).show();
    }

    private void applySavedAnnotations() {
        if (webView == null || isPdf || spine.isEmpty()) return;
        String json = ReaderAnnotationStore.chapterJson(prefs, bookFile.getName(), currentSpine);
        String pending = pendingAnnotationId;
        pendingAnnotationId = null;
        String js = "(function(){try{" +
                "var root=document.getElementById('wow-page-flow')||document.body;if(!root)return;" +
                "var old=root.querySelectorAll('span.wow-annotation');for(var oi=old.length-1;oi>=0;oi--){var q=old[oi];if(q.parentNode)q.parentNode.replaceChild(document.createTextNode(q.textContent||''),q);}" +
                "root.normalize();var anns=JSON.parse(" + jsQuote(json) + ");" +
                "function nodes(){var out=[],w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:function(n){var p=n.parentElement;if(!p)return NodeFilter.FILTER_REJECT;var tag=p.tagName;" +
                "if(tag==='SCRIPT'||tag==='STYLE'||tag==='NOSCRIPT'||p.closest('span.wow-annotation'))return NodeFilter.FILTER_REJECT;return n.nodeValue&&n.nodeValue.length?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT;}});var n;while(n=w.nextNode())out.push(n);return out;}" +
                "function apply(a){var ns=nodes(),pos=0,parts=[];for(var i=0;i<ns.length;i++){var n=ns[i],len=n.nodeValue.length,lo=Math.max(a.start-pos,0),hi=Math.min(a.end-pos,len);if(hi>lo)parts.push({n:n,lo:lo,hi:hi});pos+=len;if(pos>=a.end)break;}" +
                "for(var j=parts.length-1;j>=0;j--){try{var p=parts[j],r=document.createRange();r.setStart(p.n,p.lo);r.setEnd(p.n,p.hi);var sp=document.createElement('span');sp.className='wow-annotation';sp.setAttribute('data-wow-ann-id',a.id);sp.style.background=a.color||'rgba(255,235,59,.48)';sp.style.borderRadius='3px';sp.style.boxDecorationBreak='clone';sp.style.webkitBoxDecorationBreak='clone';if(a.note)sp.style.borderBottom='2px solid rgba(251,188,4,.9)';r.surroundContents(sp);}catch(e){}}}" +
                "for(var ai=0;ai<anns.length;ai++)apply(anns[ai]);" +
                (pending == null ? "" : "setTimeout(function(){var el=root.querySelector('[data-wow-ann-id=\"'+" + jsQuote(pending) + "+'\"]');if(!el)return;var st=window.__wowPageEngine||{};if(st.mode==='page'&&st.step){var fr=(st.flow||root).getBoundingClientRect(),er=el.getBoundingClientRect();var pg=Math.max(0,Math.min((st.count||1)-1,Math.floor(Math.max(0,er.left-fr.left)/st.step)));st.page=pg;if(st.apply)st.apply(false);if(st.report)st.report();}else{el.scrollIntoView({block:'center',behavior:'smooth'});}},80);") +
                "}catch(e){}})();";
        try { webView.evaluateJavascript(js, null); } catch (Exception ignored) {}
        updateAnnotationButton();
    }

    private void updateAnnotationButton() {
        if (annotationButton == null || isPdf) return;
        int count = ReaderAnnotationStore.count(prefs, bookFile.getName());
        annotationButton.setContentDescription(count == 0 ? "Notes and highlights" : "Notes and highlights · " + count);
        annotationButton.setAlpha(count == 0 ? 0.82f : 1f);
    }

    private void showAnnotations() {
        if (isPdf) return;
        List<ReaderAnnotationStore.Annotation> items = ReaderAnnotationStore.load(prefs, bookFile.getName());
        if (items.isEmpty()) {
            new AlertDialog.Builder(this)
                    .setTitle("Notes & highlights")
                    .setMessage("Select text while reading, then choose Highlight or Add note.")
                    .setPositiveButton("OK", null)
                    .show();
            return;
        }
        String[] labels = new String[items.size()];
        for (int i = 0; i < items.size(); i++) {
            ReaderAnnotationStore.Annotation a = items.get(i);
            String chapter = a.chapter >= 0 && a.chapter < spine.size() ? chapterDisplayTitle(a.chapter) : "Chapter " + (a.chapter + 1);
            String kind = a.note == null || a.note.isEmpty() ? "Highlight" : "Note";
            labels[i] = kind + " · " + chapter + "\n" + shortQuote(a.quote, 100) +
                    (a.note == null || a.note.isEmpty() ? "" : "\n✎ " + shortQuote(a.note, 80));
        }
        new AlertDialog.Builder(this)
                .setTitle("Notes & highlights · " + items.size())
                .setItems(labels, (dialog, which) -> showAnnotationDetail(items.get(which)))
                .setNegativeButton("Close", null)
                .show();
    }

    private void showAnnotationDetail(ReaderAnnotationStore.Annotation a) {
        String chapter = a.chapter >= 0 && a.chapter < spine.size() ? chapterDisplayTitle(a.chapter) : "Chapter " + (a.chapter + 1);
        String message = chapter + "\n\n“" + a.quote + "”" +
                (a.note == null || a.note.isEmpty() ? "" : "\n\nNote\n" + a.note);
        new AlertDialog.Builder(this)
                .setTitle(a.note == null || a.note.isEmpty() ? "Highlight" : "Note")
                .setMessage(message)
                .setPositiveButton("Go to text", (dialog, which) -> goToAnnotation(a))
                .setNeutralButton("Delete", (dialog, which) -> {
                    ReaderAnnotationStore.remove(prefs, bookFile.getName(), a.id);
                    applySavedAnnotations();
                    updateAnnotationButton();
                    Toast.makeText(this, "Removed", Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("Close", null)
                .show();
    }

    private void goToAnnotation(ReaderAnnotationStore.Annotation a) {
        if (a == null || a.chapter < 0 || a.chapter >= spine.size()) return;
        pendingAnnotationId = a.id;
        if (a.chapter == currentSpine) {
            applySavedAnnotations();
            return;
        }
        int direction = a.chapter > currentSpine ? 1 : -1;
        prepareChapterTransition(direction);
        currentSpine = a.chapter;
        currentProgressPermille = 0;
        saveEpubStateOnly();
        loadCurrentEpubChapter();
    }

    private String shortQuote(String text, int max) {
        if (text == null) return "";
        String clean = text.replaceAll("\\s+", " ").trim();
        if (clean.length() <= max) return clean;
        return clean.substring(0, Math.max(1, max - 1)) + "…";
    }

    private void copySelectedText(String text) {
        try {
            ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("WoW Reader", text));
            Toast.makeText(this, "Copied", Toast.LENGTH_SHORT).show();
        } catch (Exception ignored) {}
    }

    private void showTranslateDialog(String text) {
        boolean hasMyanmar = text != null && text.matches("(?s).*[\\u1000-\\u109F\\uA9E0-\\uA9FF\\uAA60-\\uAA7F].*");
        String[] labels = hasMyanmar ? new String[]{"English", "မြန်မာ"} : new String[]{"မြန်မာ", "English"};
        String[] codes = hasMyanmar ? new String[]{"en", "my"} : new String[]{"my", "en"};
        new AlertDialog.Builder(this)
                .setTitle("Translate to")
                .setItems(labels, (dialog, which) -> openTranslation(text, codes[which]))
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void openTranslation(String text, String targetLanguage) {
        try {
            String url = "https://translate.google.com/?sl=auto&tl=" + targetLanguage +
                    "&text=" + Uri.encode(text == null ? "" : text) + "&op=translate";
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            Toast.makeText(this, "Unable to open translation", Toast.LENGTH_SHORT).show();
        }
    }

'''
s = s[:pos] + helpers + s[pos:]

# Initialize annotation count once the reader UI is ready.
anchor = '''        setContentView(root);\n        updateChromeTheme();\n        hideControls();\n'''
if anchor not in s:
    raise SystemExit('v2.3 reader: setContentView anchor not found')
s = s.replace(anchor, '''        setContentView(root);\n        updateChromeTheme();\n        updateAnnotationButton();\n        hideControls();\n''', 1)

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.3 highlights, notes and translate patch applied')
