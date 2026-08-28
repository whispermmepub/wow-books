from pathlib import Path
import re

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# --- Fields: add stable page-mode state -------------------------------------
old = '''    private boolean volumeChapterKeys = false;\n    private boolean chapterLoading = false;\n    private long lastChapterNavMs = 0L;\n'''
new = '''    private boolean volumeChapterKeys = false;\n    private String readingMode = "scroll";\n    private int currentPageInChapter = 1;\n    private int pageCountInChapter = 1;\n    private boolean pageTurnLocked = false;\n    private boolean tapHitTestPending = false;\n    private long lastPageTurnMs = 0L;\n    private boolean chapterLoading = false;\n    private long lastChapterNavMs = 0L;\n'''
if old not in s:
    raise SystemExit('v1.7: field anchor not found')
s = s.replace(old, new, 1)

# --- Restore reading mode preference instead of forcing scroll --------------
old = '''        // v1.6 is intentionally scroll-only. Older unstable page-mode preference is ignored.\n        prefs.edit().putString("epub_reading_mode", "scroll").apply();\n'''
new = '''        readingMode = prefs.getString("epub_reading_mode", "scroll");\n        if (!"page".equals(readingMode) && !"scroll".equals(readingMode)) readingMode = "scroll";\n'''
if old not in s:
    raise SystemExit('v1.7: scroll-only preference anchor not found')
s = s.replace(old, new, 1)

# --- Native tap + safe horizontal fling detection ---------------------------
old = '''        readerTapDetector = new GestureDetector(this, new GestureDetector.SimpleOnGestureListener() {\n            @Override public boolean onDown(MotionEvent e) { return true; }\n\n            @Override public boolean onSingleTapConfirmed(MotionEvent e) {\n                handleReaderTap(e.getX(), e.getY());\n                return true;\n            }\n        });\n'''
new = '''        readerTapDetector = new GestureDetector(this, new GestureDetector.SimpleOnGestureListener() {\n            @Override public boolean onDown(MotionEvent e) { return true; }\n\n            @Override public boolean onSingleTapConfirmed(MotionEvent e) {\n                handleReaderTap(e.getX(), e.getY());\n                return true;\n            }\n\n            @Override public boolean onFling(MotionEvent e1, MotionEvent e2, float velocityX, float velocityY) {\n                if (!"page".equals(readingMode) || e1 == null || e2 == null || chapterLoading || pageTurnLocked)\n                    return false;\n                float dx = e2.getX() - e1.getX();\n                float dy = e2.getY() - e1.getY();\n                int edgeSafe = dp(30);\n                if (e1.getX() < edgeSafe || e1.getX() > webView.getWidth() - edgeSafe) return false;\n                if (Math.abs(dx) < dp(64) || Math.abs(dx) < Math.abs(dy) * 1.35f || Math.abs(velocityX) < 500f)\n                    return false;\n                turnPage(dx < 0 ? 1 : -1);\n                return true;\n            }\n        });\n'''
if old not in s:
    raise SystemExit('v1.7: gesture anchor not found')
s = s.replace(old, new, 1)

# --- Wait for page engine readiness in page mode -----------------------------
old = '''            public void onPageFinished(WebView view, String url) {\n                super.onPageFinished(view, url);\n                applyReaderStyle(true);\n                chapterLoading = false;\n            }\n'''
new = '''            public void onPageFinished(WebView view, String url) {\n                super.onPageFinished(view, url);\n                applyReaderStyle(true);\n                if ("scroll".equals(readingMode)) chapterLoading = false;\n                else webView.postDelayed(() -> { if (chapterLoading) chapterLoading = false; }, 900L);\n            }\n'''
if old not in s:
    raise SystemExit('v1.7: onPageFinished anchor not found')
s = s.replace(old, new, 1)

# --- Tap routing: one async hit test at a time -------------------------------
start = s.index('    private void handleReaderTap(float x, float y) {')
end = s.index('\n    private void setupPdfView', start)
new_method = r'''    private void handleReaderTap(float x, float y) {
        if (webView == null || chapterLoading || tapHitTestPending) return;

        final float ratio = x / Math.max(1f, webView.getWidth());
        final int px = Math.round(x);
        final int py = Math.round(y);
        tapHitTestPending = true;

        String hitTest = "(function(){try{" +
                "if(window.getSelection&&String(window.getSelection()).length>0)return 'selection';" +
                "var n=document.elementFromPoint(" + px + "," + py + ");" +
                "while(n){if(n.tagName&&n.tagName.toLowerCase()==='a')return 'link';n=n.parentElement;}" +
                "return 'plain';}catch(e){return 'plain';}})()";

        try {
            webView.evaluateJavascript(hitTest, result -> {
                tapHitTestPending = false;
                if (result != null && (result.contains("link") || result.contains("selection"))) return;

                if ("page".equals(readingMode)) {
                    if (ratio < 0.30f) turnPage(-1);
                    else if (ratio > 0.70f) turnPage(1);
                    else toggleControls();
                } else {
                    if (ratio < 0.24f) navigateChapter(-1, true);
                    else if (ratio > 0.76f) navigateChapter(1, false);
                    else toggleControls();
                }
            });
        } catch (Exception ignored) {
            tapHitTestPending = false;
            toggleControls();
        }
    }
'''
s = s[:start] + new_method + s[end:]

# --- Chapter loading state ---------------------------------------------------
old = '''        chapterLoading = true;\n        try {\n            webView.loadUrl(Uri.fromFile(spine.get(currentSpine)).toString());\n'''
new = '''        chapterLoading = true;\n        pageTurnLocked = "page".equals(readingMode);\n        currentPageInChapter = 1;\n        pageCountInChapter = 1;\n        try {\n            webView.loadUrl(Uri.fromFile(spine.get(currentSpine)).toString());\n'''
if old not in s:
    raise SystemExit('v1.7: load chapter anchor not found')
s = s.replace(old, new, 1)

# --- Replace style engine with scroll + exact viewport pagination ------------
start = s.index('    private void applyReaderStyle(boolean restoreProgress) {')
end = s.index('\n    private String jsQuote', start)
new_style = r'''    private void applyReaderStyle(boolean restoreProgress) {
        if (webView == null) return;

        String bg = readerTheme == 2 ? "#121212" :
                readerTheme == 1 ? "#F4ECD8" : "#FFFFFF";
        String fg = readerTheme == 2 ? "#E8EAED" : "#202124";
        String link = readerTheme == 2 ? "#AECBFA" : "#1967D2";

        String familyCss = "";
        if ("pyidaungsu".equals(fontChoice))
            familyCss = "body,body *{font-family:'WoWPyidaungsu',sans-serif !important;}";
        else if ("yoeshin".equals(fontChoice))
            familyCss = "body,body *{font-family:'WoWYoeShin',sans-serif !important;}";
        else if ("burma2".equals(fontChoice))
            familyCss = "body,body *{font-family:'WoWBurma2',sans-serif !important;}";

        int restore = restoreProgress ? currentProgressPermille : -1;
        double ratio = restore >= 0 ? restore / 1000.0 : 0.0;
        double line = lineSpacing / 100.0;

        String commonCss =
                "@font-face{font-family:'WoWPyidaungsu';src:url('file:///android_asset/fonts/pyidaungsu.woff2') format('woff2');}" +
                "@font-face{font-family:'WoWYoeShin';src:url('file:///android_asset/fonts/yoeshin.woff2') format('woff2');}" +
                "@font-face{font-family:'WoWBurma2';src:url('file:///android_asset/fonts/burma2.woff2') format('woff2');}" +
                "html,body{background:" + bg + " !important;color:" + fg + " !important;}" +
                "p{line-height:" + line + " !important;}" +
                "a{color:" + link + " !important;}" +
                "pre{white-space:pre-wrap !important;overflow-wrap:anywhere !important;}" +
                "table{max-width:82vw !important;}" + familyCss;

        String css;
        String js;

        if ("page".equals(readingMode)) {
            // 86vw column + 14vw gap = exactly one physical viewport per page.
            // The whole column strip is shifted 7vw right, keeping every page centered.
            css = commonCss +
                    "html{height:100% !important;width:100% !important;margin:0 !important;padding:0 !important;overflow:hidden !important;overscroll-behavior:none !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:" + line + " !important;" +
                    "height:100vh !important;min-height:100vh !important;width:auto !important;max-width:none !important;" +
                    "margin:0 !important;padding:4vh 0 5vh 0 !important;box-sizing:border-box !important;overflow:visible !important;" +
                    "column-width:86vw !important;column-gap:14vw !important;column-fill:auto !important;" +
                    "will-change:transform !important;backface-visibility:hidden !important;transform-origin:0 0 !important;}" +
                    "img,svg,video{max-width:82vw !important;max-height:78vh !important;height:auto !important;}";

            js = "(function(){" +
                    "var style=document.getElementById('wow-reader-style');if(!style){style=document.createElement('style');style.id='wow-reader-style';document.head.appendChild(style);}style.innerHTML=" + jsQuote(css) + ";" +
                    "var st=window.__wowPageEngine||{};window.__wowPageEngine=st;st.mode='page';st.locked=true;" +
                    "st.clamp=function(v,a,b){return Math.max(a,Math.min(b,v));};" +
                    "st.apply=function(anim){var w=Math.max(1,window.innerWidth),m=w*0.07;document.body.style.transition=anim?'transform 180ms cubic-bezier(.22,.72,.24,1)':'none';document.body.style.transform='translate3d('+(m-(st.page||0)*w)+'px,0,0)';};" +
                    "st.progress=function(){return (st.count||1)<=1?0:Math.round(((st.page||0)/((st.count||1)-1))*1000);};" +
                    "st.report=function(){WoW.onPage((st.page||0)+1,st.count||1,st.progress());};" +
                    "st.measure=function(r){document.documentElement.scrollLeft=0;document.body.scrollLeft=0;document.body.style.transition='none';document.body.style.transform='translate3d(0,0,0)';requestAnimationFrame(function(){requestAnimationFrame(function(){var w=Math.max(1,window.innerWidth);var sw=Math.max(document.body.scrollWidth,document.documentElement.scrollWidth,w*0.86);st.count=Math.max(1,Math.ceil((sw+1)/w));st.page=st.clamp(Math.round((st.count-1)*st.clamp(r,0,1)),0,st.count-1);st.apply(false);st.locked=false;st.report();WoW.onPageReady(st.page+1,st.count,st.progress());});});};" +
                    "st.turn=function(d){if(st.mode!=='page'||st.locked)return 'locked';if(d<0&&(st.page||0)<=0){st.locked=true;WoW.requestChapter(-1);return 'chapter';}if(d>0&&(st.page||0)>=(st.count||1)-1){st.locked=true;WoW.requestChapter(1);return 'chapter';}st.locked=true;st.page=st.clamp((st.page||0)+d,0,(st.count||1)-1);st.apply(true);st.report();setTimeout(function(){st.locked=false;WoW.onPageTurnComplete(st.page+1,st.count,st.progress());},195);return 'page';};" +
                    "if(!st.resizeBound){st.resizeBound=true;window.addEventListener('resize',function(){if(st.mode!=='page')return;clearTimeout(st.resizeTimer);st.resizeTimer=setTimeout(function(){var r=st.progress()/1000;st.measure(r);},220);});}" +
                    "var images=Array.prototype.slice.call(document.images||[]);var waits=images.map(function(im){if(im.complete)return Promise.resolve();return new Promise(function(done){var f=function(){done();};im.addEventListener('load',f,{once:true});im.addEventListener('error',f,{once:true});});});" +
                    "var ready=function(){var all=Promise.all(waits);var timeout=new Promise(function(done){setTimeout(done,650);});Promise.race([all,timeout]).then(function(){st.measure(" + ratio + ");});};" +
                    "if(document.fonts&&document.fonts.ready)document.fonts.ready.then(ready);else ready();" +
                    "})();";
        } else {
            css = commonCss +
                    "html{overflow-x:hidden !important;overscroll-behavior:none !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:" + line + " !important;" +
                    "padding:5vh " + marginPercent + "vw 12vh " + marginPercent + "vw !important;" +
                    "height:auto !important;max-width:900px !important;margin:auto !important;box-sizing:border-box !important;" +
                    "column-width:auto !important;column-gap:normal !important;transform:none !important;transition:none !important;}" +
                    "body *{max-width:100%;}" +
                    "img,svg,video{max-width:100% !important;height:auto !important;}";

            js = "(function(){" +
                    "var style=document.getElementById('wow-reader-style');if(!style){style=document.createElement('style');style.id='wow-reader-style';document.head.appendChild(style);}style.innerHTML=" + jsQuote(css) + ";" +
                    "if(window.__wowPageEngine){window.__wowPageEngine.mode='scroll';window.__wowPageEngine.locked=false;}" +
                    "if(!window.__wowScrollBound){window.__wowScrollBound=true;var t=0;window.addEventListener('scroll',function(){if(window.__wowPageEngine&&window.__wowPageEngine.mode==='page')return;clearTimeout(t);t=setTimeout(function(){var h=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);WoW.onScroll(Math.round((window.scrollY/h)*1000));},90);},{passive:true});}" +
                    (restore >= 0 ? "setTimeout(function(){var h=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);window.scrollTo(0,h*" + ratio + ");},90);" : "") +
                    "})();";
        }

        try {
            webView.evaluateJavascript(js, null);
        } catch (Exception ignored) {
            if ("page".equals(readingMode)) {
                readingMode = "scroll";
                pageTurnLocked = false;
                chapterLoading = false;
                prefs.edit().putString("epub_reading_mode", "scroll").apply();
                Toast.makeText(this, "Page mode unavailable — switched to Scroll", Toast.LENGTH_SHORT).show();
            }
        }

        updateChromeTheme();
    }

    private void turnPage(int delta) {
        if (webView == null || chapterLoading || !"page".equals(readingMode)) return;
        long now = System.currentTimeMillis();
        if (pageTurnLocked || now - lastPageTurnMs < 260L) return;

        lastPageTurnMs = now;
        pageTurnLocked = true;
        try {
            webView.evaluateJavascript(
                    "(window.__wowPageEngine&&window.__wowPageEngine.turn)?window.__wowPageEngine.turn(" + delta + "): 'unavailable'",
                    result -> {
                        if (result != null && result.contains("unavailable")) {
                            pageTurnLocked = false;
                            readingMode = "scroll";
                            prefs.edit().putString("epub_reading_mode", "scroll").apply();
                            applyReaderStyle(true);
                            Toast.makeText(this, "Page mode unavailable — switched to Scroll", Toast.LENGTH_SHORT).show();
                        }
                    });
        } catch (Exception e) {
            pageTurnLocked = false;
        }

        // Safety valve only; normal unlock comes from onPageTurnComplete/onPageReady.
        webView.postDelayed(() -> {
            if (pageTurnLocked && !chapterLoading) {
                pageTurnLocked = false;
                try { webView.evaluateJavascript("if(window.__wowPageEngine)window.__wowPageEngine.locked=false", null); }
                catch (Exception ignored) {}
            }
        }, 520L);
    }
'''
s = s[:start] + new_style + s[end:]

# --- Reader settings: re-add mode selector ----------------------------------
start = s.index('    private void showReaderSettings() {')
end = s.index('\n    private void showPdfSettings()', start)
new_settings = r'''    private void showReaderSettings() {
        if (isPdf) {
            showPdfSettings();
            return;
        }

        String[] options = new String[]{
                "Reading mode · " + readingModeDisplayName(),
                "Font size · " + fontPercent + "%",
                "Font · " + fontDisplayName(),
                "Line spacing · " + lineSpacingDisplay(),
                "Margins · " + marginPercent + "%",
                "Theme · " + themeDisplayName(),
                "Brightness · " + brightnessDisplayName(),
                "Keep screen on · " + onOff(keepScreenOn),
                "Lock orientation · " + onOff(lockOrientation),
                "Volume keys navigate · " + onOff(volumeChapterKeys),
                "Reset reader settings"
        };

        new AlertDialog.Builder(this)
                .setTitle("Reader settings")
                .setItems(options, (d, which) -> {
                    switch (which) {
                        case 0: showReadingModeDialog(); break;
                        case 1: showFontSizeDialog(); break;
                        case 2: showFontDialog(); break;
                        case 3: showLineSpacingDialog(); break;
                        case 4: showMarginDialog(); break;
                        case 5: showThemeDialog(); break;
                        case 6: showBrightnessDialog(); break;
                        case 7:
                            keepScreenOn = !keepScreenOn;
                            saveReaderPreferences();
                            applyWindowPreferences();
                            showReaderSettings();
                            break;
                        case 8:
                            lockOrientation = !lockOrientation;
                            saveReaderPreferences();
                            applyWindowPreferences();
                            showReaderSettings();
                            break;
                        case 9:
                            volumeChapterKeys = !volumeChapterKeys;
                            saveReaderPreferences();
                            showReaderSettings();
                            break;
                        case 10:
                            resetReaderPreferences();
                            break;
                    }
                })
                .setNegativeButton("Close", null)
                .show();
    }

    private void showReadingModeDialog() {
        String[] labels = {"Vertical scroll", "Page by page"};
        int selected = "page".equals(readingMode) ? 1 : 0;
        new AlertDialog.Builder(this)
                .setTitle("Reading mode")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    String mode = which == 1 ? "page" : "scroll";
                    if (!mode.equals(readingMode)) {
                        readingMode = mode;
                        pageTurnLocked = false;
                        saveReaderPreferences();
                        applyReaderStyle(true);
                    }
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }
'''
s = s[:start] + new_settings + s[end:]

# --- Reset + persistence -----------------------------------------------------
s = s.replace('''        volumeChapterKeys = false;\n        saveReaderPreferences();\n''', '''        volumeChapterKeys = false;\n        readingMode = "scroll";\n        pageTurnLocked = false;\n        saveReaderPreferences();\n''', 1)
s = s.replace('''.putBoolean("reader_volume_chapter", volumeChapterKeys)\n                .putString("epub_reading_mode", "scroll")\n''', '''.putBoolean("reader_volume_chapter", volumeChapterKeys)\n                .putString("epub_reading_mode", readingMode)\n''', 1)

# Add display helper before fontDisplayName.
marker = '    private String fontDisplayName() {\n'
if marker not in s:
    raise SystemExit('v1.7: fontDisplayName anchor not found')
s = s.replace(marker, '''    private String readingModeDisplayName() {\n        return "page".equals(readingMode) ? "Pages" : "Scroll";\n    }\n\n''' + marker, 1)

# --- Previous/next and progress ---------------------------------------------
old = '''        } else {\n            navigateChapter(-1, true);\n        }\n    }\n\n    private void next() {\n'''
new = '''        } else {\n            if ("page".equals(readingMode)) turnPage(-1);\n            else navigateChapter(-1, true);\n        }\n    }\n\n    private void next() {\n'''
if old not in s:
    raise SystemExit('v1.7: previous anchor not found')
s = s.replace(old, new, 1)
old = '''        } else {\n            navigateChapter(1, false);\n        }\n    }\n\n    private void updateEpubProgress(int p) {\n'''
new = '''        } else {\n            if ("page".equals(readingMode)) turnPage(1);\n            else navigateChapter(1, false);\n        }\n    }\n\n    private void updateEpubProgress(int p) {\n'''
if old not in s:
    raise SystemExit('v1.7: next anchor not found')
s = s.replace(old, new, 1)

old = '''        String chapter = currentSpine < chapterTitles.size()\n                ? chapterTitles.get(currentSpine)\n                : "Chapter " + (currentSpine + 1);\n\n        positionView.setText(chapter + " · " + percent + "%");\n        prefs.edit().putInt("percent_" + bookFile.getName(), percent).apply();\n    }\n'''
new = '''        String chapter = currentSpine < chapterTitles.size()\n                ? chapterTitles.get(currentSpine)\n                : "Chapter " + (currentSpine + 1);\n\n        if ("page".equals(readingMode))\n            positionView.setText("Page " + currentPageInChapter + " / " + pageCountInChapter + " · " + percent + "%");\n        else\n            positionView.setText(chapter + " · " + percent + "%");\n        prefs.edit().putInt("percent_" + bookFile.getName(), percent).apply();\n    }\n\n    private void updateEpubPageProgress(int page, int count, int p) {\n        currentPageInChapter = Math.max(1, page);\n        pageCountInChapter = Math.max(1, count);\n        updateEpubProgress(p);\n        saveEpubStateOnly();\n    }\n'''
if old not in s:
    raise SystemExit('v1.7: progress anchor not found')
s = s.replace(old, new, 1)

# --- JS bridge ---------------------------------------------------------------
start = s.index('    private class ReaderBridge {')
end = s.index('\n    @Override\n    public boolean onKeyDown', start)
new_bridge = r'''    private class ReaderBridge {
        @JavascriptInterface
        public void onScroll(int p) {
            runOnUiThread(() -> {
                if (!"scroll".equals(readingMode)) return;
                updateEpubProgress(p);
                saveEpubStateOnly();
            });
        }

        @JavascriptInterface
        public void onPage(int page, int count, int p) {
            runOnUiThread(() -> {
                if (!"page".equals(readingMode)) return;
                updateEpubPageProgress(page, count, p);
            });
        }

        @JavascriptInterface
        public void onPageReady(int page, int count, int p) {
            runOnUiThread(() -> {
                if (!"page".equals(readingMode)) return;
                updateEpubPageProgress(page, count, p);
                pageTurnLocked = false;
                chapterLoading = false;
            });
        }

        @JavascriptInterface
        public void onPageTurnComplete(int page, int count, int p) {
            runOnUiThread(() -> {
                if (!"page".equals(readingMode)) return;
                updateEpubPageProgress(page, count, p);
                pageTurnLocked = false;
            });
        }

        @JavascriptInterface
        public void requestChapter(int delta) {
            runOnUiThread(() -> {
                if (!"page".equals(readingMode) || delta == 0) return;
                int target = currentSpine + (delta < 0 ? -1 : 1);
                if (target < 0 || target >= spine.size()) {
                    pageTurnLocked = false;
                    try { webView.evaluateJavascript("if(window.__wowPageEngine)window.__wowPageEngine.locked=false", null); }
                    catch (Exception ignored) {}
                    return;
                }
                navigateChapter(delta < 0 ? -1 : 1, delta < 0);
            });
        }
    }
'''
s = s[:start] + new_bridge + s[end:]

# --- Volume keys: pages in page mode, chapters in scroll ---------------------
old = '''            if (keyCode == KeyEvent.KEYCODE_VOLUME_DOWN) {\n                navigateChapter(1, false);\n                return true;\n            }\n            if (keyCode == KeyEvent.KEYCODE_VOLUME_UP) {\n                navigateChapter(-1, true);\n                return true;\n            }\n'''
new = '''            if (keyCode == KeyEvent.KEYCODE_VOLUME_DOWN) {\n                if ("page".equals(readingMode)) turnPage(1); else navigateChapter(1, false);\n                return true;\n            }\n            if (keyCode == KeyEvent.KEYCODE_VOLUME_UP) {\n                if ("page".equals(readingMode)) turnPage(-1); else navigateChapter(-1, true);\n                return true;\n            }\n'''
if old not in s:
    raise SystemExit('v1.7: volume-key anchor not found')
s = s.replace(old, new, 1)

# Static safety assertions: production page engine must be viewport-index based.
assert 'column-width:86vw' in s
assert 'column-gap:14vw' in s
assert 'st.page=st.clamp((st.page||0)+d' in s
assert 'pageTurnLocked' in s
assert 'Page by page' in s
assert '.putString("epub_reading_mode", readingMode)' in s
assert 'window.scrollTo({left:' not in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v1.7.0 smooth page engine patch applied')
