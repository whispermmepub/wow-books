from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# v1.8: Page-by-page is the default for fresh installs. Existing user choice remains.
old = '''        readingMode = prefs.getString("epub_reading_mode", "scroll");\n        if (!"page".equals(readingMode) && !"scroll".equals(readingMode)) readingMode = "scroll";\n'''
new = '''        readingMode = prefs.getString("epub_reading_mode", "page");\n        if (!"page".equals(readingMode) && !"scroll".equals(readingMode)) readingMode = "page";\n'''
if old not in s:
    raise SystemExit('v1.8: reading mode default anchor not found')
s = s.replace(old, new, 1)

# Reset should return to the product default as well.
old = '''        volumeChapterKeys = false;\n        readingMode = "scroll";\n        pageTurnLocked = false;\n        saveReaderPreferences();\n'''
new = '''        volumeChapterKeys = false;\n        readingMode = "page";\n        pageTurnLocked = false;\n        saveReaderPreferences();\n'''
if old not in s:
    raise SystemExit('v1.8: reset reading mode anchor not found')
s = s.replace(old, new, 1)

# Add smart Myanmar typography rules to the common reader CSS. We only normalize
# blocks that the JS detector marks as problematic, preserving centered headings,
# poetry, publisher fonts and other intentional EPUB styling.
old = '''                "pre{white-space:pre-wrap !important;overflow-wrap:anywhere !important;}" +\n                "table{max-width:82vw !important;}" + familyCss;\n'''
new = '''                "pre{white-space:pre-wrap !important;overflow-wrap:anywhere !important;}" +\n                "table{max-width:82vw !important;}" +\n                ".wow-mm-normalize{text-align:start !important;text-align-last:auto !important;text-justify:auto !important;word-spacing:normal !important;letter-spacing:normal !important;white-space:normal !important;}" +\n                ".wow-mm-normalize *{word-spacing:normal !important;letter-spacing:normal !important;}" + familyCss;\n'''
if old not in s:
    raise SystemExit('v1.8: common CSS anchor not found')
s = s.replace(old, new, 1)

# Replace only the page branch inside applyReaderStyle. The new engine paginates a
# dedicated flow wrapper instead of translating <body>. This isolates publisher
# body widths/margins, clips exactly one viewport, and keeps each turn one page.
method_start = s.index('    private void applyReaderStyle(boolean restoreProgress) {')
method_end = s.index('\n    private String jsQuote', method_start)
method = s[method_start:method_end]
page_start = method.index('        if ("page".equals(readingMode)) {')
page_else = method.index('        } else {', page_start)

new_page = r'''        if ("page".equals(readingMode)) {
            int pageMargin = Math.max(4, Math.min(12, marginPercent));
            int pageWidth = 100 - pageMargin * 2;
            int pageGap = pageMargin * 2;

            css = commonCss +
                    "html,body{height:100% !important;width:100% !important;margin:0 !important;padding:0 !important;overflow:hidden !important;overscroll-behavior:none !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:" + line + " !important;height:100vh !important;min-height:100vh !important;max-width:none !important;box-sizing:border-box !important;}" +
                    "#wow-page-flow{position:absolute !important;left:0 !important;top:0 !important;height:100vh !important;width:auto !important;max-width:none !important;" +
                    "margin:0 !important;padding:4.2vh 0 5.2vh 0 !important;box-sizing:border-box !important;overflow:visible !important;" +
                    "column-width:" + pageWidth + "vw !important;column-gap:" + pageGap + "vw !important;column-fill:auto !important;" +
                    "will-change:transform !important;backface-visibility:hidden !important;transform-origin:0 0 !important;contain:layout style !important;}" +
                    "#wow-page-flow>*,#wow-page-flow p,#wow-page-flow div,#wow-page-flow li,#wow-page-flow blockquote{box-sizing:border-box !important;max-width:" + pageWidth + "vw;}" +
                    "#wow-page-flow img,#wow-page-flow svg,#wow-page-flow video{max-width:" + Math.max(60, pageWidth - 4) + "vw !important;max-height:78vh !important;height:auto !important;}";

            js = "(function(){try{" +
                    "var style=document.getElementById('wow-reader-style');if(!style){style=document.createElement('style');style.id='wow-reader-style';document.head.appendChild(style);}style.innerHTML=" + jsQuote(css) + ";" +
                    "var flow=document.getElementById('wow-page-flow');if(!flow){flow=document.createElement('div');flow.id='wow-page-flow';while(document.body.firstChild)flow.appendChild(document.body.firstChild);document.body.appendChild(flow);}" +
                    "var st=window.__wowPageEngine||{};window.__wowPageEngine=st;st.mode='page';st.locked=true;st.flow=flow;st.margin=" + (pageMargin / 100.0) + ";st.gap=" + (pageGap / 100.0) + ";" +
                    "st.clamp=function(v,a,b){return Math.max(a,Math.min(b,v));};" +
                    "st.normalizeMyanmar=function(){try{var rx=/[\\u1000-\\u109F\\uA9E0-\\uA9FF\\uAA60-\\uAA7F]/;var nodes=flow.querySelectorAll('p,div,li,blockquote,dd,dt');for(var i=0;i<nodes.length;i++){var n=nodes[i],txt=(n.textContent||'').trim();if(txt.length<8||!rx.test(txt))continue;var cs=getComputedStyle(n);var ws=parseFloat(cs.wordSpacing)||0,ls=parseFloat(cs.letterSpacing)||0;var bad=cs.textAlign==='justify'||Math.abs(ws)>2||Math.abs(ls)>1;if(bad)n.classList.add('wow-mm-normalize');else n.classList.remove('wow-mm-normalize');}}catch(e){}};" +
                    "st.apply=function(anim){var w=Math.max(1,window.innerWidth),m=w*st.margin;flow.style.transition=anim?'transform 170ms cubic-bezier(.22,.72,.24,1)':'none';flow.style.transform='translate3d('+(m-(st.page||0)*w)+'px,0,0)';};" +
                    "st.progress=function(){return (st.count||1)<=1?0:Math.round(((st.page||0)/((st.count||1)-1))*1000);};" +
                    "st.report=function(){WoW.onPage((st.page||0)+1,st.count||1,st.progress());};" +
                    "st.measure=function(r){flow.style.transition='none';flow.style.transform='translate3d(0,0,0)';st.normalizeMyanmar();requestAnimationFrame(function(){requestAnimationFrame(function(){var w=Math.max(1,window.innerWidth),gap=w*st.gap;var sw=Math.max(flow.scrollWidth,w*(1-st.gap));st.count=Math.max(1,Math.ceil((sw+gap-1)/w));st.page=st.clamp(Math.round((st.count-1)*st.clamp(r,0,1)),0,st.count-1);st.apply(false);st.locked=false;st.report();WoW.onPageReady(st.page+1,st.count,st.progress());});});};" +
                    "st.turn=function(d){if(st.mode!=='page'||st.locked)return 'locked';if(d<0&&(st.page||0)<=0){st.locked=true;WoW.requestChapter(-1);return 'chapter';}if(d>0&&(st.page||0)>=(st.count||1)-1){st.locked=true;WoW.requestChapter(1);return 'chapter';}st.locked=true;st.page=st.clamp((st.page||0)+d,0,(st.count||1)-1);st.apply(true);st.report();setTimeout(function(){st.locked=false;WoW.onPageTurnComplete(st.page+1,st.count,st.progress());},185);return 'page';};" +
                    "if(!st.resizeBound){st.resizeBound=true;window.addEventListener('resize',function(){if(st.mode!=='page')return;clearTimeout(st.resizeTimer);st.resizeTimer=setTimeout(function(){var r=st.progress()/1000;st.measure(r);},260);});}" +
                    "var images=Array.prototype.slice.call(flow.querySelectorAll('img'));var waits=images.map(function(im){if(im.complete)return Promise.resolve();return new Promise(function(done){var f=function(){done();};im.addEventListener('load',f,{once:true});im.addEventListener('error',f,{once:true});});});" +
                    "var ready=function(){var all=Promise.all(waits);var timeout=new Promise(function(done){setTimeout(done,700);});Promise.race([all,timeout]).then(function(){st.measure(" + ratio + ");});};" +
                    "if(document.fonts&&document.fonts.ready)document.fonts.ready.then(ready);else ready();" +
                    "}catch(e){WoW.pageEngineFailed(String(e));}})();";
'''
method = method[:page_start] + new_page + method[page_else:]
s = s[:method_start] + method + s[method_end:]

# When switching to Scroll, unwrap the dedicated page-flow container first so the
# EPUB returns to its natural document flow. Also normalize pathological Myanmar
# justification in scroll mode without touching centered headings.
old = '''            js = "(function(){" +\n                    "var style=document.getElementById('wow-reader-style');if(!style){style=document.createElement('style');style.id='wow-reader-style';document.head.appendChild(style);}style.innerHTML=" + jsQuote(css) + ";" +\n                    "if(window.__wowPageEngine){window.__wowPageEngine.mode='scroll';window.__wowPageEngine.locked=false;}" +\n'''
new = '''            js = "(function(){" +\n                    "var flow=document.getElementById('wow-page-flow');if(flow){while(flow.firstChild)document.body.insertBefore(flow.firstChild,flow);flow.remove();}" +\n                    "var style=document.getElementById('wow-reader-style');if(!style){style=document.createElement('style');style.id='wow-reader-style';document.head.appendChild(style);}style.innerHTML=" + jsQuote(css) + ";" +\n                    "try{var rx=/[\\u1000-\\u109F\\uA9E0-\\uA9FF\\uAA60-\\uAA7F]/;var nodes=document.querySelectorAll('p,div,li,blockquote,dd,dt');for(var i=0;i<nodes.length;i++){var n=nodes[i],txt=(n.textContent||'').trim();if(txt.length<8||!rx.test(txt))continue;var cs=getComputedStyle(n);var ws=parseFloat(cs.wordSpacing)||0,ls=parseFloat(cs.letterSpacing)||0;if(cs.textAlign==='justify'||Math.abs(ws)>2||Math.abs(ls)>1)n.classList.add('wow-mm-normalize');}}catch(e){}" +\n                    "if(window.__wowPageEngine){window.__wowPageEngine.mode='scroll';window.__wowPageEngine.locked=false;}" +\n'''
if old not in s:
    raise SystemExit('v1.8: scroll JS anchor not found')
s = s.replace(old, new, 1)

# Add a defensive JS bridge callback. Any unexpected page-engine exception falls
# back to Scroll instead of crashing or exiting the reader.
bridge_marker = '''        @JavascriptInterface\n        public void requestChapter(int delta) {\n'''
if bridge_marker not in s:
    raise SystemExit('v1.8: ReaderBridge requestChapter anchor not found')
bridge_method = '''        @JavascriptInterface\n        public void pageEngineFailed(String message) {\n            runOnUiThread(() -> {\n                if (!"page".equals(readingMode)) return;\n                readingMode = "scroll";\n                pageTurnLocked = false;\n                chapterLoading = false;\n                prefs.edit().putString("epub_reading_mode", "scroll").apply();\n                applyReaderStyle(true);\n                Toast.makeText(BookReaderActivity.this, "Page layout adjusted to Scroll for this book", Toast.LENGTH_SHORT).show();\n            });\n        }\n\n'''
s = s.replace(bridge_marker, bridge_method + bridge_marker, 1)

# Static assertions for the v1.8 production contract.
assert 'prefs.getString("epub_reading_mode", "page")' in s
assert 'readingMode = "page";' in s
assert 'wow-page-flow' in s
assert 'normalizeMyanmar' in s
assert 'wow-mm-normalize' in s
assert 'pageEngineFailed' in s
assert 'pageWidth = 100 - pageMargin * 2' in s
assert "st.page=st.clamp((st.page||0)+d" in s
assert 'window.scrollTo({left:' not in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v1.8.0 smart Burmese pagination patch applied')
