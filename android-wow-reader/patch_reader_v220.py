from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# Dedicated EPUB TOC state. The reading spine can contain front/back matter, but
# the TOC now shows only actual nav/NCX chapter entries and preserves fragments.
anchor = '    private final List<String> chapterTitles = new ArrayList<>();\n'
if anchor not in s:
    raise SystemExit('v2.2 reader: chapterTitles field anchor not found')
s = s.replace(anchor, anchor + '''    private final List<Integer> tocSpineIndices = new ArrayList<>();\n    private final List<String> tocTitles = new ArrayList<>();\n    private final List<String> tocFragments = new ArrayList<>();\n    private String pendingTocFragment = null;\n    private int emptyChapterSkipCount = 0;\n''', 1)

anchor = '''                    chapterTitles.clear();\n                    chapterTitles.addAll(info.chapterTitles);\n'''
if anchor not in s:
    raise SystemExit('v2.2 reader: BookInfo copy anchor not found')
s = s.replace(anchor, anchor + '''                    tocSpineIndices.clear();\n                    tocSpineIndices.addAll(info.tocSpineIndices);\n                    tocTitles.clear();\n                    tocTitles.addAll(info.tocTitles);\n                    tocFragments.clear();\n                    tocFragments.addAll(info.tocFragments);\n''', 1)

s = s.replace('}, 1250L);', '}, 3200L);', 1)

start = s.index('    private void showContents() {')
end = s.index('\n    private void applyReaderStyle', start)
contents = r'''    private void showContents() {
        if (isPdf || spine.isEmpty()) return;

        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        dialog.setCanceledOnTouchOutside(true);

        int panelBase = readerTheme == 2 ? Color.rgb(29, 30, 33)
                : readerTheme == 1 ? Color.rgb(249, 243, 225) : Color.WHITE;
        int text = readerTheme == 2 ? Color.rgb(238, 240, 244) : Color.rgb(32, 33, 36);
        int sub = readerTheme == 2 ? Color.rgb(190, 194, 201) : Color.rgb(95, 99, 104);
        int accent = readerTheme == 2 ? Color.rgb(138, 180, 248) : Color.rgb(103, 80, 164);

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(18), dp(16), dp(14), dp(10));
        card.setBackground(glassPanel(Color.argb(readerTheme == 2 ? 236 : 232,
                Color.red(panelBase), Color.green(panelBase), Color.blue(panelBase)), dp(22),
                Color.argb(readerTheme == 2 ? 70 : 95, 255, 255, 255)));

        TextView header = new TextView(this);
        header.setText("Table of contents");
        header.setTextSize(24);
        header.setTextColor(text);
        header.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(8), dp(2), dp(8), dp(10));
        card.addView(header, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setVerticalScrollBarEnabled(false);
        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(list, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        int entryCount = tocTitles.size();
        if (entryCount == 0) {
            TextView none = new TextView(this);
            none.setText("This EPUB does not contain a chapter table of contents.");
            none.setTextSize(16);
            none.setTextColor(sub);
            none.setPadding(dp(12), dp(18), dp(12), dp(18));
            list.addView(none, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        }

        for (int i = 0; i < entryCount; i++) {
            final int entry = i;
            final int spineIndex = tocSpineAt(i);
            final String fragment = tocFragmentAt(i);
            boolean selected = spineIndex == currentSpine;

            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(5), dp(6), dp(8), dp(6));
            row.setMinimumHeight(dp(58));
            if (selected) {
                row.setBackground(glassPanel(Color.argb(readerTheme == 2 ? 72 : 48,
                        Color.red(accent), Color.green(accent), Color.blue(accent)), dp(14), Color.TRANSPARENT));
            }

            TextView marker = new TextView(this);
            marker.setText(selected ? "●" : "○");
            marker.setTextSize(selected ? 19 : 22);
            marker.setTextColor(selected ? accent : sub);
            marker.setGravity(Gravity.CENTER);
            row.addView(marker, new LinearLayout.LayoutParams(dp(42), dp(46)));

            TextView label = new TextView(this);
            label.setText(tocTitleAt(entry));
            label.setTextSize(17);
            label.setTextColor(text);
            label.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
            label.setLineSpacing(0f, 1.12f);
            label.setPadding(dp(7), dp(4), dp(5), dp(4));
            row.addView(label, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            row.setOnClickListener(v -> {
                if (chapterLoading) return;
                if (spineIndex == currentSpine) {
                    pendingTocFragment = fragment;
                    jumpToPendingTocFragment(() -> {
                        saveEpubStateOnly();
                        updateBookmarkIcon();
                    });
                } else {
                    int direction = spineIndex > currentSpine ? 1 : -1;
                    prepareChapterTransition(direction);
                    pendingTocFragment = fragment;
                    currentSpine = spineIndex;
                    currentProgressPermille = direction < 0 ? 1000 : 0;
                    saveEpubStateOnly();
                    loadCurrentEpubChapter();
                }
                dialog.dismiss();
            });
            list.addView(row, new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        }

        card.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        TextView close = new TextView(this);
        close.setText("CLOSE");
        close.setTextSize(14);
        close.setTextColor(accent);
        close.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        close.setGravity(Gravity.CENTER);
        close.setPadding(dp(10), dp(8), dp(10), dp(6));
        close.setOnClickListener(v -> dialog.dismiss());
        LinearLayout.LayoutParams closeLp = new LinearLayout.LayoutParams(dp(92), dp(52));
        closeLp.gravity = Gravity.END;
        card.addView(close, closeLp);

        dialog.setContentView(card);
        dialog.show();

        Window window = dialog.getWindow();
        if (window != null) {
            window.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            window.setDimAmount(0.30f);
            int sw = getResources().getDisplayMetrics().widthPixels;
            int sh = getResources().getDisplayMetrics().heightPixels;
            window.setLayout(Math.min(sw - dp(26), dp(560)), Math.min(sh - dp(50), (int) (sh * 0.88f)));
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                window.addFlags(WindowManager.LayoutParams.FLAG_BLUR_BEHIND);
                window.setBackgroundBlurRadius(dp(28));
            }
        }
    }
'''
s = s[:start] + contents + s[end:]

start = s.index('    private void applyReaderStyle(boolean restoreProgress) {')
end = s.index('\n    private String jsQuote', start)
engine = r'''    private void applyReaderStyle(boolean restoreProgress) {
        if (webView == null) return;

        String bg = readerTheme == 2 ? "#121212" :
                readerTheme == 1 ? "#F4ECD8" : "#FFFFFF";
        String fg = readerTheme == 2 ? "#E8EAED" : "#202124";
        String headingFg = readerTheme == 2 ? "#F1F3F4" : fg;
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

        String darkCss = readerTheme == 2
                ? "body,body p,body div,body span,body section,body article,body li,body dd,body dt,body blockquote,body td,body th,body figcaption{color:" + fg + " !important;}" +
                  "h1,h2,h3,h4,h5,h6,strong,b{color:" + headingFg + " !important;}"
                : "";

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
                ".wow-mm-smart{text-justify:inter-character !important;word-spacing:0 !important;letter-spacing:normal !important;overflow-wrap:anywhere !important;word-break:normal !important;hyphens:none !important;}" +
                "h1,h2,h3,h4,h5,h6{break-after:avoid-column !important;page-break-after:avoid !important;}" +
                darkCss + familyCss;

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
                "}catch(e){}};" +
                "st.preparePagination=function(){try{" +
                "var all=flow.querySelectorAll('*'),first=null,last=null;" +
                "var forced=function(v){v=(v||'').toLowerCase();return v==='always'||v==='page'||v==='left'||v==='right'||v==='column';};" +
                "var mediaSel='img,svg,video,audio,object,embed,table,math,canvas,hr';" +
                "for(var i=0;i<all.length;i++){var n=all[i],cs=getComputedStyle(n);if(cs.display==='none'||cs.visibility==='hidden')continue;" +
                "var txt=(n.textContent||'').replace(/\\s+/g,'');var hasMedia=(n.matches&&n.matches(mediaSel))||(n.querySelector&&n.querySelector(mediaSel));" +
                "var meaningful=txt.length>0||!!hasMedia;" +
                "var bb=cs.breakBefore||cs.pageBreakBefore,ba=cs.breakAfter||cs.pageBreakAfter;" +
                "if(!meaningful){if(forced(bb)){n.style.setProperty('break-before','auto','important');n.style.setProperty('page-break-before','auto','important');}" +
                "if(forced(ba)){n.style.setProperty('break-after','auto','important');n.style.setProperty('page-break-after','auto','important');}" +
                "if(!n.children.length){n.style.setProperty('min-height','0','important');n.style.setProperty('padding-top','0','important');n.style.setProperty('padding-bottom','0','important');}}" +
                "else{if(!first)first=n;last=n;if(forced(bb)){n.style.setProperty('break-before','column','important');n.style.setProperty('page-break-before','always','important');}" +
                "if(forced(ba)){n.style.setProperty('break-after','column','important');n.style.setProperty('page-break-after','always','important');}}}" +
                "if(first){first.style.setProperty('break-before','auto','important');first.style.setProperty('page-break-before','auto','important');}" +
                "if(last){last.style.setProperty('break-after','auto','important');last.style.setProperty('page-break-after','auto','important');}" +
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
                    "st.physical=function(){if(st.pageMap&&st.pageMap.length)return st.pageMap[st.clamp(st.page||0,0,st.pageMap.length-1)];return st.page||0;};" +
                    "st.apply=function(anim){st.layout();var physical=st.physical(),x=st.marginPx-physical*st.step;flow.style.transition=anim?'transform 155ms cubic-bezier(.2,.75,.25,1)':'none';flow.style.transform='translate3d('+x+'px,0,0)';};" +
                    "st.progress=function(){return (st.count||1)<=1?0:Math.round(((st.page||0)/((st.count||1)-1))*1000);};" +
                    "st.report=function(){WoW.onPage((st.page||0)+1,st.count||1,st.progress());};" +
                    "st.collectPageMap=function(){var used={},walker=document.createTreeWalker(flow,NodeFilter.SHOW_TEXT,null,false),n,range=document.createRange(),seen=0;" +
                    "var mark=function(r){if(!r||r.width<0.35||r.height<0.35)return;var a=Math.max(0,Math.floor((r.left-st.marginPx+1)/st.step));var b=Math.max(a,Math.floor((r.right-st.marginPx-1)/st.step));for(var k=a;k<=b;k++)used[k]=1;};" +
                    "while((n=walker.nextNode())&&seen<24000){var t=(n.nodeValue||'').replace(/\\s+/g,'');if(!t)continue;seen++;try{range.selectNodeContents(n);var rr=range.getClientRects();for(var j=0;j<rr.length;j++)mark(rr[j]);}catch(e){}}" +
                    "var media=flow.querySelectorAll('img,svg,video,audio,object,embed,table,math,canvas,hr');for(var i=0;i<media.length;i++){var r=media[i].getBoundingClientRect();mark(r);}" +
                    "var keys=Object.keys(used).map(function(x){return parseInt(x,10);}).filter(function(x){return isFinite(x)&&x>=0;}).sort(function(a,b){return a-b;});return keys;};" +
                    "st.nearestLogical=function(physical){if(!st.pageMap||!st.pageMap.length)return 0;var best=0,dist=1e9;for(var i=0;i<st.pageMap.length;i++){var d=Math.abs(st.pageMap[i]-physical);if(d<dist){dist=d;best=i;}}return best;};" +
                    "st.goToFragment=function(id){try{if(!id)return false;var el=document.getElementById(id);if(!el&&document.getElementsByName){var named=document.getElementsByName(id);if(named&&named.length)el=named[0];}if(!el)return false;" +
                    "var currentPhysical=st.physical(),r=el.getBoundingClientRect(),docX=(r.left-st.marginPx)+(currentPhysical*st.step),physical=Math.max(0,Math.floor((docX+2)/st.step));st.page=st.nearestLogical(physical);st.apply(false);st.report();return true;}catch(e){return false;}};" +
                    "st.paperTurn=function(d,done){var mode=" + jsQuote(pageAnimation) + ";if(mode==='none'){st.apply(false);done();return;}st.apply(true);setTimeout(done,mode==='slide'?165:185);};" +
                    "st.measure=function(r){st.layout();st.page=0;st.pageMap=[0];flow.style.transition='none';flow.style.transform='translate3d('+st.marginPx+'px,0,0)';st.applyTypography();st.preparePagination();requestAnimationFrame(function(){requestAnimationFrame(function(){st.layout();var map=st.collectPageMap();if(!map.length){st.count=0;st.locked=false;WoW.onEmptyChapter();return;}st.pageMap=map;st.count=map.length;st.page=st.clamp(Math.round((st.count-1)*st.clamp(r,0,1)),0,st.count-1);st.apply(false);st.locked=false;st.report();WoW.onPageReady(st.page+1,st.count,st.progress());});});};" +
                    "st.turn=function(d){if(st.mode!=='page'||st.locked)return 'locked';if(d<0&&(st.page||0)<=0){st.locked=true;WoW.requestChapter(-1);return 'chapter';}if(d>0&&(st.page||0)>=(st.count||1)-1){st.locked=true;WoW.requestChapter(1);return 'chapter';}st.locked=true;st.page=st.clamp((st.page||0)+d,0,(st.count||1)-1);st.paperTurn(d,function(){st.report();st.locked=false;WoW.onPageTurnComplete(st.page+1,st.count,st.progress());});return 'page';};" +
                    "if(!st.resizeBound){st.resizeBound=true;window.addEventListener('resize',function(){if(st.mode!=='page')return;clearTimeout(st.resizeTimer);st.resizeTimer=setTimeout(function(){var r=st.progress()/1000;st.measure(r);},280);});}" +
                    "var images=Array.prototype.slice.call(flow.querySelectorAll('img'));var waits=images.map(function(im){if(im.complete)return Promise.resolve();return new Promise(function(done){var f=function(){done();};im.addEventListener('load',f,{once:true});im.addEventListener('error',f,{once:true});});});" +
                    "var ready=function(){var all=Promise.all(waits);var timeout=new Promise(function(done){setTimeout(done,900);});Promise.race([all,timeout]).then(function(){st.measure(" + ratio + ");});};" +
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
                    "st.goToFragment=function(id){try{if(!id)return false;var el=document.getElementById(id);if(!el&&document.getElementsByName){var named=document.getElementsByName(id);if(named&&named.length)el=named[0];}if(!el)return false;el.scrollIntoView({block:'start'});return true;}catch(e){return false;}};" +
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
'''
s = s[:start] + engine + s[end:]

marker = '    private String jsQuote(String'
idx = s.index(marker)
helpers = r'''    private int tocSpineAt(int entry) {
        if (entry >= 0 && entry < tocSpineIndices.size()) {
            return Math.max(0, Math.min(spine.size() - 1, tocSpineIndices.get(entry)));
        }
        return Math.max(0, Math.min(spine.size() - 1, entry));
    }

    private String tocTitleAt(int entry) {
        if (entry >= 0 && entry < tocTitles.size()) {
            String value = tocTitles.get(entry);
            if (value != null && !value.trim().isEmpty()) return value.trim();
        }
        return chapterDisplayTitle(tocSpineAt(entry));
    }

    private String tocFragmentAt(int entry) {
        if (entry >= 0 && entry < tocFragments.size()) {
            String value = tocFragments.get(entry);
            return value == null ? "" : value.trim();
        }
        return "";
    }

    private void jumpToPendingTocFragment(Runnable done) {
        String fragment = pendingTocFragment;
        pendingTocFragment = null;
        if (webView == null || fragment == null || fragment.isEmpty()) {
            if (done != null) done.run();
            return;
        }

        String script = "(window.__wowPageEngine&&window.__wowPageEngine.goToFragment)?window.__wowPageEngine.goToFragment(" +
                jsQuote(fragment) + "):false";
        try {
            webView.evaluateJavascript(script, result -> webView.postDelayed(() -> {
                if (done != null) done.run();
            }, 48L));
        } catch (Exception ignored) {
            if (done != null) done.run();
        }
    }

    private void completePageReady() {
        emptyChapterSkipCount = 0;
        jumpToPendingTocFragment(() -> {
            if (finishPendingChapterCurl()) return;
            pageTurnLocked = false;
            chapterLoading = false;
            finishChapterFade();
        });
    }

    private void skipEmptyEpubSpine() {
        if (spine.isEmpty()) return;
        emptyChapterSkipCount++;
        if (emptyChapterSkipCount > spine.size()) {
            chapterLoading = false;
            pageTurnLocked = false;
            pendingChapterCurlDirection = 0;
            if (pageCurlView != null) pageCurlView.release();
            finishChapterFade();
            return;
        }

        int direction = pendingChapterCurlDirection < 0 ? -1 : 1;
        int target = currentSpine + direction;
        if (target < 0 || target >= spine.size()) {
            direction = -direction;
            target = currentSpine + direction;
        }
        if (target < 0 || target >= spine.size()) {
            chapterLoading = false;
            pageTurnLocked = false;
            if (pageCurlView != null) pageCurlView.release();
            finishChapterFade();
            return;
        }

        currentSpine = target;
        currentProgressPermille = direction < 0 ? 1000 : 0;
        saveEpubStateOnly();
        loadCurrentEpubChapter();
    }

'''
s = s[:idx] + helpers + s[idx:]

start = s.index('    private class ReaderBridge {')
end = s.index('\n    @Override\n    public boolean onKeyDown', start)
bridge = r'''    private class ReaderBridge {
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
                completePageReady();
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
        public void onEmptyChapter() {
            runOnUiThread(() -> {
                if (!"page".equals(readingMode)) return;
                skipEmptyEpubSpine();
            });
        }

        @JavascriptInterface
        public void pageEngineFailed(String message) {
            runOnUiThread(() -> {
                if (!"page".equals(readingMode)) return;
                readingMode = "scroll";
                pageTurnLocked = false;
                chapterLoading = false;
                pendingChapterCurlDirection = 0;
                if (pageCurlView != null) pageCurlView.release();
                finishChapterFade();
                prefs.edit().putString("epub_reading_mode", "scroll").apply();
                applyReaderStyle(true);
                Toast.makeText(BookReaderActivity.this, "Page layout adjusted to Scroll for this book", Toast.LENGTH_SHORT).show();
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
s = s[:start] + bridge + s[end:]

assert 'tocSpineIndices' in s
assert 'tocFragments' in s
assert 'collectPageMap' in s
assert 'onEmptyChapter' in s
assert 'goToFragment' in s
assert 'break-before' in s
assert 'h1,h2,h3,h4,h5,h6' in s
assert '3200L' in s
assert 'private String jsQuote(String' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.2 exact pages + exact TOC + dark text patch applied')
