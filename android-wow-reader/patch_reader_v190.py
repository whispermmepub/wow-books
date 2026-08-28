from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# ---------------------------------------------------------------------------
# v1.9 state: user text alignment + Smart Myanmar spacing.
# ---------------------------------------------------------------------------
anchor = '    private String readingMode = "scroll";\n'
if anchor not in s:
    raise SystemExit('v1.9: readingMode field anchor not found')
s = s.replace(anchor, anchor +
'''    private String textAlignment = "justify";\n    private boolean autoSpacingAdjustment = true;\n''', 1)

# v1.9 product defaults. This one-time migration makes the requested defaults
# effective for existing v1.8 installs as well as fresh installs.
anchor = '''        readingMode = prefs.getString("epub_reading_mode", "page");\n        if (!"page".equals(readingMode) && !"scroll".equals(readingMode)) readingMode = "page";\n'''
if anchor not in s:
    raise SystemExit('v1.9: default reading mode anchor not found')
replacement = anchor + '''        textAlignment = prefs.getString("epub_text_alignment", "justify");\n        if (!"justify".equals(textAlignment) && !"left".equals(textAlignment) && !"right".equals(textAlignment))\n            textAlignment = "justify";\n        autoSpacingAdjustment = prefs.getBoolean("epub_auto_spacing", true);\n\n        if (!prefs.getBoolean("reader_v19_defaults_applied", false)) {\n            fontPercent = 100;\n            lineSpacing = 160;\n            marginPercent = 5;\n            textAlignment = "justify";\n            autoSpacingAdjustment = true;\n            prefs.edit()\n                    .putInt("epub_font", 100)\n                    .putInt("epub_line_spacing", 160)\n                    .putInt("epub_margin", 5)\n                    .putString("epub_text_alignment", "justify")\n                    .putBoolean("epub_auto_spacing", true)\n                    .putBoolean("reader_v19_defaults_applied", true)\n                    .apply();\n        }\n'''
s = s.replace(anchor, replacement, 1)

# ---------------------------------------------------------------------------
# Replace the complete EPUB rendering engine. The page flow has an exact pixel
# width of one page, while the gap is chosen so pageWidth + gap == viewport.
# A dedicated viewport clips adjacent columns, preventing page bleed.
# ---------------------------------------------------------------------------
start = s.index('    private void applyReaderStyle(boolean restoreProgress) {')
end = s.index('\n    private String jsQuote', start)
new_engine = r'''    private void applyReaderStyle(boolean restoreProgress) {
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
        int safeMargin = Math.max(3, Math.min(14, marginPercent));

        String commonCss =
                "@font-face{font-family:'WoWPyidaungsu';src:url('file:///android_asset/fonts/pyidaungsu.woff2') format('woff2');}" +
                "@font-face{font-family:'WoWYoeShin';src:url('file:///android_asset/fonts/yoeshin.woff2') format('woff2');}" +
                "@font-face{font-family:'WoWBurma2';src:url('file:///android_asset/fonts/burma2.woff2') format('woff2');}" +
                "html,body{background:" + bg + " !important;color:" + fg + " !important;}" +
                "a{color:" + link + " !important;}" +
                "pre{white-space:pre-wrap !important;overflow-wrap:anywhere !important;}" +
                ".wow-reader-block{letter-spacing:normal !important;}" +
                ".wow-align-justify{text-align:justify !important;text-align-last:start !important;}" +
                ".wow-align-left{text-align:left !important;text-align-last:auto !important;}" +
                ".wow-align-right{text-align:right !important;text-align-last:auto !important;}" +
                ".wow-mm-smart{text-justify:inter-character !important;word-spacing:0 !important;letter-spacing:normal !important;overflow-wrap:anywhere !important;word-break:normal !important;hyphens:none !important;}" + familyCss;

        String typographyJs =
                "st.applyTypography=function(){try{" +
                "var align=" + jsQuote(textAlignment) + ",smart=" + (autoSpacingAdjustment ? "true" : "false") + ";" +
                "var rx=/[\\u1000-\\u109F\\uA9E0-\\uA9FF\\uAA60-\\uAA7F]/g;" +
                "var blocks=flow.querySelectorAll('p,li,blockquote,dd,dt,div');" +
                "for(var i=0;i<blocks.length;i++){var n=blocks[i],txt=(n.textContent||'').trim();if(txt.length<8)continue;" +
                "if(n.tagName==='DIV'&&n.querySelector('p,div,li,blockquote,dd,dt'))continue;" +
                "var cs=getComputedStyle(n);if(cs.display==='none')continue;" +
                "var centered=(cs.textAlign==='center');if(centered&&txt.length<180)continue;" +
                "n.classList.add('wow-reader-block');n.classList.remove('wow-align-justify','wow-align-left','wow-align-right','wow-mm-smart');" +
                "n.classList.add(align==='right'?'wow-align-right':(align==='left'?'wow-align-left':'wow-align-justify'));" +
                "var mm=(txt.match(rx)||[]).length;var visible=txt.replace(/\\s/g,'').length;" +
                "if(align==='justify'&&smart&&visible>0&&mm/visible>0.18)n.classList.add('wow-mm-smart');" +
                "}" +
                "}catch(e){}};";

        String css;
        String js;

        if ("page".equals(readingMode)) {
            css = commonCss +
                    "html,body{height:100% !important;width:100% !important;margin:0 !important;padding:0 !important;overflow:hidden !important;overscroll-behavior:none !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:" + line + " !important;max-width:none !important;}" +
                    "#wow-page-viewport{position:absolute !important;left:0 !important;top:0 !important;width:100vw !important;height:100vh !important;overflow:hidden !important;clip-path:inset(0) !important;contain:layout paint size !important;}" +
                    "#wow-page-flow{position:absolute !important;left:0 !important;top:0 !important;height:100vh !important;max-width:none !important;" +
                    "margin:0 !important;padding:4.2vh 0 5.2vh 0 !important;box-sizing:border-box !important;overflow:visible !important;" +
                    "column-fill:auto !important;will-change:transform !important;backface-visibility:hidden !important;transform-origin:0 0 !important;}" +
                    "#wow-page-flow p,#wow-page-flow li,#wow-page-flow blockquote,#wow-page-flow dd,#wow-page-flow dt{box-sizing:border-box !important;max-width:100% !important;}" +
                    "#wow-page-flow img,#wow-page-flow svg,#wow-page-flow video,#wow-page-flow table{max-width:100% !important;height:auto !important;}";

            js = "(function(){try{" +
                    "var style=document.getElementById('wow-reader-style');if(!style){style=document.createElement('style');style.id='wow-reader-style';document.head.appendChild(style);}style.innerHTML=" + jsQuote(css) + ";" +
                    "var viewport=document.getElementById('wow-page-viewport'),flow=document.getElementById('wow-page-flow');" +
                    "if(!viewport){viewport=document.createElement('div');viewport.id='wow-page-viewport';" +
                    "if(!flow){flow=document.createElement('div');flow.id='wow-page-flow';while(document.body.firstChild)flow.appendChild(document.body.firstChild);}" +
                    "viewport.appendChild(flow);document.body.appendChild(viewport);}else if(!flow){flow=document.createElement('div');flow.id='wow-page-flow';viewport.appendChild(flow);}" +
                    "var st=window.__wowPageEngine||{};window.__wowPageEngine=st;st.mode='page';st.locked=true;st.flow=flow;st.viewport=viewport;st.marginRatio=" + (safeMargin / 100.0) + ";" +
                    "st.clamp=function(v,a,b){return Math.max(a,Math.min(b,v));};" + typographyJs +
                    "st.layout=function(){var w=Math.max(1,viewport.clientWidth||window.innerWidth),m=Math.max(0,Math.round(w*st.marginRatio)),pw=Math.max(1,w-2*m),gap=Math.max(0,w-pw);st.step=w;st.marginPx=m;st.pageWidth=pw;st.gapPx=gap;flow.style.width=pw+'px';flow.style.minWidth=pw+'px';flow.style.columnWidth=pw+'px';flow.style.columnGap=gap+'px';};" +
                    "st.apply=function(anim){st.layout();var x=st.marginPx-(st.page||0)*st.step;flow.style.transition=anim?'transform 155ms cubic-bezier(.2,.75,.25,1)':'none';flow.style.transform='translate3d('+x+'px,0,0)';};" +
                    "st.progress=function(){return (st.count||1)<=1?0:Math.round(((st.page||0)/((st.count||1)-1))*1000);};" +
                    "st.report=function(){WoW.onPage((st.page||0)+1,st.count||1,st.progress());};" +
                    "st.measure=function(r){st.layout();flow.style.transition='none';flow.style.transform='translate3d('+st.marginPx+'px,0,0)';st.applyTypography();requestAnimationFrame(function(){requestAnimationFrame(function(){st.layout();var sw=Math.max(flow.scrollWidth,st.pageWidth);st.count=Math.max(1,Math.round((sw+st.gapPx)/st.step));st.page=st.clamp(Math.round((st.count-1)*st.clamp(r,0,1)),0,st.count-1);st.apply(false);st.locked=false;st.report();WoW.onPageReady(st.page+1,st.count,st.progress());});});};" +
                    "st.turn=function(d){if(st.mode!=='page'||st.locked)return 'locked';if(d<0&&(st.page||0)<=0){st.locked=true;WoW.requestChapter(-1);return 'chapter';}if(d>0&&(st.page||0)>=(st.count||1)-1){st.locked=true;WoW.requestChapter(1);return 'chapter';}st.locked=true;st.page=st.clamp((st.page||0)+d,0,(st.count||1)-1);st.apply(true);st.report();setTimeout(function(){st.locked=false;WoW.onPageTurnComplete(st.page+1,st.count,st.progress());},170);return 'page';};" +
                    "if(!st.resizeBound){st.resizeBound=true;window.addEventListener('resize',function(){if(st.mode!=='page')return;clearTimeout(st.resizeTimer);st.resizeTimer=setTimeout(function(){var r=st.progress()/1000;st.measure(r);},280);});}" +
                    "var images=Array.prototype.slice.call(flow.querySelectorAll('img'));var waits=images.map(function(im){if(im.complete)return Promise.resolve();return new Promise(function(done){var f=function(){done();};im.addEventListener('load',f,{once:true});im.addEventListener('error',f,{once:true});});});" +
                    "var ready=function(){var all=Promise.all(waits);var timeout=new Promise(function(done){setTimeout(done,750);});Promise.race([all,timeout]).then(function(){st.measure(" + ratio + ");});};" +
                    "if(document.fonts&&document.fonts.ready)document.fonts.ready.then(ready);else ready();" +
                    "}catch(e){WoW.pageEngineFailed(String(e));}})();";
        } else {
            css = commonCss +
                    "html{overflow-x:hidden !important;overscroll-behavior:none !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:" + line + " !important;" +
                    "padding:5vh " + safeMargin + "vw 12vh " + safeMargin + "vw !important;" +
                    "height:auto !important;max-width:900px !important;margin:auto !important;box-sizing:border-box !important;" +
                    "column-width:auto !important;column-gap:normal !important;transform:none !important;transition:none !important;}" +
                    "body *{max-width:100%;}" +
                    "img,svg,video{max-width:100% !important;height:auto !important;}";

            js = "(function(){try{" +
                    "var viewport=document.getElementById('wow-page-viewport'),flow=document.getElementById('wow-page-flow');" +
                    "if(flow){var before=viewport||flow;while(flow.firstChild)document.body.insertBefore(flow.firstChild,before);if(viewport)viewport.remove();else flow.remove();}" +
                    "var style=document.getElementById('wow-reader-style');if(!style){style=document.createElement('style');style.id='wow-reader-style';document.head.appendChild(style);}style.innerHTML=" + jsQuote(css) + ";" +
                    "var flow=document.body;var st=window.__wowPageEngine||{};window.__wowPageEngine=st;st.mode='scroll';st.locked=false;" + typographyJs +
                    "st.applyTypography();" +
                    "if(!window.__wowScrollBound){window.__wowScrollBound=true;var t=0;window.addEventListener('scroll',function(){if(window.__wowPageEngine&&window.__wowPageEngine.mode==='page')return;clearTimeout(t);t=setTimeout(function(){var h=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);WoW.onScroll(Math.round((window.scrollY/h)*1000));},90);},{passive:true});}" +
                    (restore >= 0 ? "setTimeout(function(){var h=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);window.scrollTo(0,h*" + ratio + ");},90);" : "") +
                    "}catch(e){}})();";
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
        if (pageTurnLocked || now - lastPageTurnMs < 240L) return;

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

        webView.postDelayed(() -> {
            if (pageTurnLocked && !chapterLoading) {
                pageTurnLocked = false;
                try { webView.evaluateJavascript("if(window.__wowPageEngine)window.__wowPageEngine.locked=false", null); }
                catch (Exception ignored) {}
            }
        }, 500L);
    }
'''
s = s[:start] + new_engine + s[end:]

# ---------------------------------------------------------------------------
# Reader settings: reading mode, alignment and auto-spacing are first-class.
# ---------------------------------------------------------------------------
start = s.index('    private void showReaderSettings() {')
end = s.index('\n    private void showPdfSettings()', start)
new_settings = r'''    private void showReaderSettings() {
        if (isPdf) {
            showPdfSettings();
            return;
        }

        String[] options = new String[]{
                "Reading mode · " + readingModeDisplayName(),
                "Text alignment · " + alignmentDisplayName(),
                "Auto spacing adjustment · " + onOff(autoSpacingAdjustment),
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
                        case 1: showAlignmentDialog(); break;
                        case 2:
                            autoSpacingAdjustment = !autoSpacingAdjustment;
                            saveReaderPreferences();
                            applyReaderStyle(true);
                            showReaderSettings();
                            break;
                        case 3: showFontSizeDialog(); break;
                        case 4: showFontDialog(); break;
                        case 5: showLineSpacingDialog(); break;
                        case 6: showMarginDialog(); break;
                        case 7: showThemeDialog(); break;
                        case 8: showBrightnessDialog(); break;
                        case 9:
                            keepScreenOn = !keepScreenOn;
                            saveReaderPreferences();
                            applyWindowPreferences();
                            showReaderSettings();
                            break;
                        case 10:
                            lockOrientation = !lockOrientation;
                            saveReaderPreferences();
                            applyWindowPreferences();
                            showReaderSettings();
                            break;
                        case 11:
                            volumeChapterKeys = !volumeChapterKeys;
                            saveReaderPreferences();
                            showReaderSettings();
                            break;
                        case 12: resetReaderPreferences(); break;
                    }
                })
                .setNegativeButton("Close", null)
                .show();
    }

    private void showReadingModeDialog() {
        String[] labels = {"Page by page", "Vertical scroll"};
        int selected = "page".equals(readingMode) ? 0 : 1;
        new AlertDialog.Builder(this)
                .setTitle("Reading mode")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    String mode = which == 0 ? "page" : "scroll";
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

    private void showAlignmentDialog() {
        String[] labels = {"Justify", "Left", "Right"};
        String[] values = {"justify", "left", "right"};
        int selected = "left".equals(textAlignment) ? 1 : ("right".equals(textAlignment) ? 2 : 0);
        new AlertDialog.Builder(this)
                .setTitle("Text alignment")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    textAlignment = values[which];
                    saveReaderPreferences();
                    applyReaderStyle(true);
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }
'''
s = s[:start] + new_settings + s[end:]

# Line spacing selector includes the requested 1.60 default exactly.
start = s.index('    private void showLineSpacingDialog() {')
end = s.index('\n    private void showMarginDialog()', start)
s = s[:start] + r'''    private void showLineSpacingDialog() {
        final int[] values = {135, 150, 160, 175, 190, 205};
        String[] labels = {"Compact · 1.35", "1.50", "Default · 1.60", "1.75", "1.90", "Relaxed · 2.05"};

        int selected = 2;
        for (int i = 0; i < values.length; i++)
            if (values[i] == lineSpacing) selected = i;

        new AlertDialog.Builder(this)
                .setTitle("Line spacing")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    lineSpacing = values[which];
                    saveReaderPreferences();
                    applyReaderStyle(true);
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }
''' + s[end:]

# Narrow margin is exactly 5% and is the default selection.
start = s.index('    private void showMarginDialog() {')
end = s.index('\n    private void showThemeDialog()', start)
s = s[:start] + r'''    private void showMarginDialog() {
        final int[] values = {3, 5, 7, 9, 12};
        String[] labels = {"Extra narrow", "Narrow · default", "Medium", "Wide", "Extra wide"};

        int selected = 1;
        for (int i = 0; i < values.length; i++)
            if (values[i] == marginPercent) selected = i;

        new AlertDialog.Builder(this)
                .setTitle("Page margins")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    marginPercent = values[which];
                    saveReaderPreferences();
                    applyReaderStyle(true);
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }
''' + s[end:]

# Reset returns to the v1.9 requested defaults.
start = s.index('    private void resetReaderPreferences() {')
end = s.index('\n    private void saveReaderPreferences()', start)
s = s[:start] + r'''    private void resetReaderPreferences() {
        fontPercent = 100;
        fontChoice = "publisher";
        lineSpacing = 160;
        marginPercent = 5;
        textAlignment = "justify";
        autoSpacingAdjustment = true;
        readerTheme = 0;
        brightnessPercent = -1;
        keepScreenOn = false;
        lockOrientation = false;
        volumeChapterKeys = false;
        readingMode = "page";
        pageTurnLocked = false;
        saveReaderPreferences();
        applyWindowPreferences();
        if (!isPdf) applyReaderStyle(true);
        Toast.makeText(this, "Reader settings reset", Toast.LENGTH_SHORT).show();
    }
''' + s[end:]

# Persist new preferences alongside the existing ones.
start = s.index('    private void saveReaderPreferences() {')
end = s.index('\n    private String readingModeDisplayName()', start)
new_save = r'''    private void saveReaderPreferences() {
        prefs.edit()
                .putInt("epub_font", fontPercent)
                .putString("epub_font_choice", fontChoice)
                .putInt("epub_line_spacing", lineSpacing)
                .putInt("epub_margin", marginPercent)
                .putString("epub_text_alignment", textAlignment)
                .putBoolean("epub_auto_spacing", autoSpacingAdjustment)
                .putInt("reader_theme", readerTheme)
                .putInt("reader_brightness", brightnessPercent)
                .putBoolean("reader_keep_screen_on", keepScreenOn)
                .putBoolean("reader_lock_orientation", lockOrientation)
                .putBoolean("reader_volume_chapter", volumeChapterKeys)
                .putString("epub_reading_mode", readingMode)
                .apply();
    }
'''
s = s[:start] + new_save + s[end:]

# Alignment display helper.
marker = '    private String fontDisplayName() {\n'
if marker not in s:
    raise SystemExit('v1.9: font display helper anchor not found')
s = s.replace(marker, '''    private String alignmentDisplayName() {\n        if ("left".equals(textAlignment)) return "Left";\n        if ("right".equals(textAlignment)) return "Right";\n        return "Justify";\n    }\n\n''' + marker, 1)

# Static production-contract checks.
assert 'wow-page-viewport' in s
assert "flow.style.width=pw+'px'" in s
assert "flow.style.columnWidth=pw+'px'" in s
assert "flow.style.columnGap=gap+'px'" in s
assert 'Math.round((sw+st.gapPx)/st.step)' in s
assert 'textAlignment = "justify"' in s
assert 'autoSpacingAdjustment = true' in s
assert 'wow-mm-smart' in s
assert 'text-justify:inter-character' in s
assert 'fontPercent = 100' in s
assert 'lineSpacing = 160' in s
assert 'marginPercent = 5' in s
assert '"Justify", "Left", "Right"' in s
assert 'prefs.getString("epub_reading_mode", "page")' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v1.9.0 isolated pages + smart justify patch applied')
