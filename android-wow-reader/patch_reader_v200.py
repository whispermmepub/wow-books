from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# Page-turn animation preference. Paper is the product default.
anchor = '    private boolean autoSpacingAdjustment = true;\n'
if anchor not in s:
    raise SystemExit('v2.0 reader: auto spacing field anchor not found')
s = s.replace(anchor, anchor + '    private String pageAnimation = "paper";\n', 1)

anchor = '''        autoSpacingAdjustment = prefs.getBoolean("epub_auto_spacing", true);\n'''
if anchor not in s:
    raise SystemExit('v2.0 reader: preference load anchor not found')
s = s.replace(anchor, anchor + '''        pageAnimation = prefs.getString("epub_page_animation", "paper");\n        if (!"paper".equals(pageAnimation) && !"slide".equals(pageAnimation) && !"none".equals(pageAnimation))\n            pageAnimation = "paper";\n        if (!prefs.getBoolean("reader_v20_defaults_applied", false)) {\n            pageAnimation = "paper";\n            prefs.edit().putString("epub_page_animation", "paper").putBoolean("reader_v20_defaults_applied", true).apply();\n        }\n''', 1)

# Add the lightweight paper-turn effect to the exact-pixel v1.9 engine.
apply_anchor = '''                    "st.apply=function(anim){st.layout();var x=st.marginPx-(st.page||0)*st.step;flow.style.transition=anim?'transform 155ms cubic-bezier(.2,.75,.25,1)':'none';flow.style.transform='translate3d('+x+'px,0,0)';};" +\n'''
if apply_anchor not in s:
    raise SystemExit('v2.0 reader: page apply anchor not found')
paper_js = '''                    "st.paperTurn=function(d,done){var mode=" + jsQuote(pageAnimation) + ";if(mode==='none'){st.apply(false);done();return;}if(mode==='slide'){st.apply(true);setTimeout(done,165);return;}try{var sh=document.getElementById('wow-paper-sheet');if(!sh){sh=document.createElement('div');sh.id='wow-paper-sheet';st.viewport.appendChild(sh);}st.layout();sh.style.cssText='position:absolute;pointer-events:none;z-index:50;top:0;height:100%;left:'+st.marginPx+'px;width:'+st.pageWidth+'px;background:" + bg + ";opacity:0;transform-style:preserve-3d;backface-visibility:hidden;';sh.style.transformOrigin=d>0?'100% 50%':'0 50%';sh.style.boxShadow=d>0?'-18px 0 28px rgba(0,0,0,.16)':'18px 0 28px rgba(0,0,0,.16)';sh.style.transition='none';sh.style.transform='perspective(1200px) rotateY(0deg)';sh.style.opacity='.32';requestAnimationFrame(function(){sh.style.transition='transform 105ms cubic-bezier(.45,.05,.55,.95),opacity 105ms linear';sh.style.transform='perspective(1200px) rotateY('+(d>0?-78:78)+'deg)';sh.style.opacity='.08';setTimeout(function(){st.apply(false);sh.style.transition='none';sh.style.transform='perspective(1200px) rotateY('+(d>0?78:-78)+'deg)';sh.style.opacity='.10';requestAnimationFrame(function(){sh.style.transition='transform 115ms cubic-bezier(.2,.8,.25,1),opacity 115ms linear';sh.style.transform='perspective(1200px) rotateY(0deg)';sh.style.opacity='0';setTimeout(function(){sh.style.transform='none';done();},120);});},108);});}catch(e){st.apply(true);setTimeout(done,170);}};" +\n'''
s = s.replace(apply_anchor, apply_anchor + paper_js, 1)

turn_anchor = '''                    "st.turn=function(d){if(st.mode!=='page'||st.locked)return 'locked';if(d<0&&(st.page||0)<=0){st.locked=true;WoW.requestChapter(-1);return 'chapter';}if(d>0&&(st.page||0)>=(st.count||1)-1){st.locked=true;WoW.requestChapter(1);return 'chapter';}st.locked=true;st.page=st.clamp((st.page||0)+d,0,(st.count||1)-1);st.apply(true);st.report();setTimeout(function(){st.locked=false;WoW.onPageTurnComplete(st.page+1,st.count,st.progress());},170);return 'page';};" +\n'''
turn_new = '''                    "st.turn=function(d){if(st.mode!=='page'||st.locked)return 'locked';if(d<0&&(st.page||0)<=0){st.locked=true;WoW.requestChapter(-1);return 'chapter';}if(d>0&&(st.page||0)>=(st.count||1)-1){st.locked=true;WoW.requestChapter(1);return 'chapter';}st.locked=true;st.page=st.clamp((st.page||0)+d,0,(st.count||1)-1);st.paperTurn(d,function(){st.report();st.locked=false;WoW.onPageTurnComplete(st.page+1,st.count,st.progress());});return 'page';};" +\n'''
if turn_anchor not in s:
    raise SystemExit('v2.0 reader: turn function anchor not found')
s = s.replace(turn_anchor, turn_new, 1)

# Reader settings: expose Paper / Slide / None, defaulting to Paper.
start = s.index('    private void showReaderSettings() {')
end = s.index('\n    private void showPdfSettings()', start)
settings = r'''    private void showReaderSettings() {
        if (isPdf) {
            showPdfSettings();
            return;
        }

        String[] options = new String[]{
                "Reading mode · " + readingModeDisplayName(),
                "Page animation · " + pageAnimationDisplayName(),
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
                        case 1: showPageAnimationDialog(); break;
                        case 2: showAlignmentDialog(); break;
                        case 3:
                            autoSpacingAdjustment = !autoSpacingAdjustment;
                            saveReaderPreferences();
                            applyReaderStyle(true);
                            showReaderSettings();
                            break;
                        case 4: showFontSizeDialog(); break;
                        case 5: showFontDialog(); break;
                        case 6: showLineSpacingDialog(); break;
                        case 7: showMarginDialog(); break;
                        case 8: showThemeDialog(); break;
                        case 9: showBrightnessDialog(); break;
                        case 10:
                            keepScreenOn = !keepScreenOn;
                            saveReaderPreferences();
                            applyWindowPreferences();
                            showReaderSettings();
                            break;
                        case 11:
                            lockOrientation = !lockOrientation;
                            saveReaderPreferences();
                            applyWindowPreferences();
                            showReaderSettings();
                            break;
                        case 12:
                            volumeChapterKeys = !volumeChapterKeys;
                            saveReaderPreferences();
                            showReaderSettings();
                            break;
                        case 13: resetReaderPreferences(); break;
                    }
                })
                .setNegativeButton("Close", null)
                .show();
    }

    private void showPageAnimationDialog() {
        String[] labels = {"Paper · default", "Smooth slide", "None"};
        String[] values = {"paper", "slide", "none"};
        int selected = "slide".equals(pageAnimation) ? 1 : ("none".equals(pageAnimation) ? 2 : 0);
        new AlertDialog.Builder(this)
                .setTitle("Page animation")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    pageAnimation = values[which];
                    saveReaderPreferences();
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }
'''
s = s[:start] + settings + s[end:]

# Reset retains the v1.9 typography defaults and Paper animation.
reset_anchor = '''        autoSpacingAdjustment = true;\n        readerTheme = 0;\n'''
if reset_anchor not in s:
    raise SystemExit('v2.0 reader: reset anchor not found')
s = s.replace(reset_anchor, '''        autoSpacingAdjustment = true;\n        pageAnimation = "paper";\n        readerTheme = 0;\n''', 1)

# Persist page animation and mark all reader changes for Drive state sync.
save_anchor = '''                .putBoolean("epub_auto_spacing", autoSpacingAdjustment)\n                .putInt("reader_theme", readerTheme)\n'''
if save_anchor not in s:
    raise SystemExit('v2.0 reader: save preference anchor not found')
s = s.replace(save_anchor, '''                .putBoolean("epub_auto_spacing", autoSpacingAdjustment)\n                .putString("epub_page_animation", pageAnimation)\n                .putInt("reader_theme", readerTheme)\n''', 1)

save_apply_anchor = '''                .putString("epub_reading_mode", readingMode)\n                .apply();\n'''
if save_apply_anchor not in s:
    raise SystemExit('v2.0 reader: save apply anchor not found')
s = s.replace(save_apply_anchor, '''                .putString("epub_reading_mode", readingMode)\n                .putLong("sync_updated_ms", System.currentTimeMillis())\n                .apply();\n''', 1)

# Reading progress and bookmarks also participate in cross-device state sync.
state_anchor = '''                .putInt("epub_scroll_" + bookFile.getName(), currentProgressPermille)\n                .apply();\n'''
if state_anchor not in s:
    raise SystemExit('v2.0 reader: epub state anchor not found')
s = s.replace(state_anchor, '''                .putInt("epub_scroll_" + bookFile.getName(), currentProgressPermille)\n                .putLong("sync_updated_ms", System.currentTimeMillis())\n                .apply();\n''', 1)

bookmark_anchor = '''        prefs.edit().putString(key, value).apply();\n'''
if bookmark_anchor not in s:
    raise SystemExit('v2.0 reader: bookmark anchor not found')
s = s.replace(bookmark_anchor, '''        prefs.edit().putString(key, value).putLong("sync_updated_ms", System.currentTimeMillis()).apply();\n''', 1)

# Display helper.
marker = '    private String alignmentDisplayName() {\n'
if marker not in s:
    raise SystemExit('v2.0 reader: alignment helper anchor not found')
s = s.replace(marker, '''    private String pageAnimationDisplayName() {\n        if ("slide".equals(pageAnimation)) return "Slide";\n        if ("none".equals(pageAnimation)) return "None";\n        return "Paper";\n    }\n\n''' + marker, 1)

assert 'pageAnimation = "paper"' in s
assert 'Paper · default' in s
assert 'st.paperTurn' in s
assert 'perspective(1200px)' in s
assert '.putString("epub_page_animation", pageAnimation)' in s
assert '.putLong("sync_updated_ms", System.currentTimeMillis())' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.0 paper animation + Drive state timestamps patch applied')
