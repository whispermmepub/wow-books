from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# WebView does not expose TextView's custom selection callback API. Keep the
# same actions, but surface them through a lightweight WoW floating bar driven
# by the DOM selectionchange event.
s = s.replace('        webView.setCustomSelectionActionModeCallback(createSelectionActionModeCallback());\n\n', '', 1)

anchor = '    private String pendingAnnotationId = null;\n'
if anchor not in s:
    raise SystemExit('v2.3 selection: pending annotation field not found')
s = s.replace(anchor, anchor + '''    private LinearLayout selectionBar;\n    private SelectionData currentSelection;\n''', 1)

# Add the floating action bar above the reader bottom controls.
anchor = '''        FrameLayout.LayoutParams bottomLp = new FrameLayout.LayoutParams(\n                ViewGroup.LayoutParams.MATCH_PARENT, dp(58), Gravity.BOTTOM);\n        root.addView(bottomBar, bottomLp);\n\n'''
if anchor not in s:
    raise SystemExit('v2.3 selection: bottom bar anchor not found')
bar = r'''        selectionBar = new LinearLayout(this);
        selectionBar.setOrientation(LinearLayout.HORIZONTAL);
        selectionBar.setGravity(Gravity.CENTER);
        selectionBar.setPadding(dp(5), dp(4), dp(5), dp(4));
        int selectionBg = readerTheme == 2 ? Color.argb(242, 39, 40, 43) : Color.argb(244, 255, 255, 255);
        int selectionStroke = readerTheme == 2 ? Color.argb(90, 255, 255, 255) : Color.argb(65, 70, 70, 70);
        selectionBar.setBackground(glassPanel(selectionBg, dp(18), selectionStroke));
        selectionBar.setElevation(dp(10));
        selectionBar.addView(selectionActionButton("Highlight", SEL_HIGHLIGHT));
        selectionBar.addView(selectionActionButton("Note", SEL_NOTE));
        selectionBar.addView(selectionActionButton("Translate", SEL_TRANSLATE));
        selectionBar.addView(selectionActionButton("Copy", SEL_COPY));
        selectionBar.setVisibility(View.GONE);
        FrameLayout.LayoutParams selectionLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, dp(48), Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        selectionLp.bottomMargin = dp(68);
        root.addView(selectionBar, selectionLp);

'''
s = s.replace(anchor, anchor + bar, 1)

# Install the DOM selection watcher on every chapter load.
anchor = '''                webView.postDelayed(() -> applySavedAnnotations(), 420L);\n                webView.postDelayed(() -> applySavedAnnotations(), 1350L);\n'''
if anchor not in s:
    raise SystemExit('v2.3 selection: annotation post-delay anchor not found')
s = s.replace(anchor, anchor + '''                webView.postDelayed(() -> installSelectionWatcher(), 500L);\n''', 1)

# Add selection bar helpers before the PDF setup.
marker = '    private void setupPdfView(FrameLayout content) {'
pos = s.index(marker)
helpers = r'''    private TextView selectionActionButton(String label, int action) {
        TextView button = new TextView(this);
        button.setText(label);
        button.setTextSize(12);
        button.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        button.setTextColor(readerTheme == 2 ? Color.rgb(238, 240, 244) : Color.rgb(45, 48, 52));
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(9), 0, dp(9), 0);
        button.setOnClickListener(v -> performSelectionAction(action));
        return button;
    }

    private void installSelectionWatcher() {
        if (webView == null || isPdf) return;
        String js = "(function(){try{" +
                "if(window.__wowSelectionWatcher)return;window.__wowSelectionWatcher=true;var timer=0;" +
                "document.addEventListener('selectionchange',function(){clearTimeout(timer);timer=setTimeout(function(){try{" +
                "var sel=window.getSelection&&window.getSelection();if(!sel||sel.rangeCount===0||sel.isCollapsed){WoW.onSelection('',0,0);return;}" +
                "var range=sel.getRangeAt(0),root=document.getElementById('wow-page-flow')||document.body;if(!root||!root.contains(range.commonAncestorContainer)){WoW.onSelection('',0,0);return;}" +
                "var pre=document.createRange();pre.selectNodeContents(root);pre.setEnd(range.startContainer,range.startOffset);var start=pre.toString().length,text=range.toString();" +
                "if(!text||!text.trim()){WoW.onSelection('',0,0);return;}WoW.onSelection(text,start,start+text.length);" +
                "}catch(e){WoW.onSelection('',0,0);}},110);});" +
                "}catch(e){}})();";
        try { webView.evaluateJavascript(js, null); } catch (Exception ignored) {}
    }

    private void onWebSelection(String text, int start, int end) {
        if (text == null || text.trim().isEmpty() || end <= start) {
            currentSelection = null;
            hideSelectionBar();
            return;
        }
        SelectionData data = new SelectionData();
        data.text = text.trim();
        data.start = Math.max(0, start);
        data.end = Math.max(data.start, end);
        currentSelection = data;
        showSelectionBar();
    }

    private void showSelectionBar() {
        if (selectionBar == null || isPdf) return;
        selectionBar.setVisibility(View.VISIBLE);
        selectionBar.bringToFront();
    }

    private void hideSelectionBar() {
        if (selectionBar != null) selectionBar.setVisibility(View.GONE);
    }

    private void performSelectionAction(int action) {
        SelectionData data = currentSelection;
        if (data == null || data.text == null || data.text.trim().isEmpty()) {
            hideSelectionBar();
            return;
        }
        currentSelection = null;
        hideSelectionBar();
        clearWebSelection();
        if (action == SEL_HIGHLIGHT) showHighlightColorDialog(data);
        else if (action == SEL_NOTE) showNoteEditor(data);
        else if (action == SEL_TRANSLATE) showTranslateDialog(data.text);
        else if (action == SEL_COPY) copySelectedText(data.text);
    }

'''
s = s[:pos] + helpers + s[pos:]

# Extend the existing JS bridge. v1.7/v2.x add other bridge methods later, so
# inserting immediately after the class declaration is stable across builds.
anchor = '    private class ReaderBridge {\n'
if anchor not in s:
    raise SystemExit('v2.3 selection: ReaderBridge anchor not found')
s = s.replace(anchor, anchor + '''        @JavascriptInterface\n        public void onSelection(String text, int start, int end) {\n            runOnUiThread(() -> onWebSelection(text, start, end));\n        }\n\n''', 1)

# Do not leave a contextual bar visible while changing chapters.
anchor = '''    private void loadCurrentEpubChapter() {\n        if (spine.isEmpty() || webView == null) return;\n\n        chapterLoading = true;\n'''
if anchor in s:
    s = s.replace(anchor, '''    private void loadCurrentEpubChapter() {\n        if (spine.isEmpty() || webView == null) return;\n\n        currentSelection = null;\n        hideSelectionBar();\n        chapterLoading = true;\n''', 1)

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.3 WebView selection action bar patch applied')
