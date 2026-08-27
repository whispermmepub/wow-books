from pathlib import Path
import re

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# Handler for automatic fullscreen controls.
s = s.replace('import android.os.Bundle;\n', 'import android.os.Bundle;\nimport android.os.Handler;\nimport android.os.Looper;\n')
s = s.replace('    private long backArmedUntil = 0L;\n', '''    private long backArmedUntil = 0L;\n    private final Handler uiHandler = new Handler(Looper.getMainLooper());\n    private final Runnable autoHideRunnable = this::hideControls;\n''')

new_build = r'''    private void buildReaderUi() {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        // Reader content always keeps the same full-screen viewport. Toolbars are overlays,
        // so showing/hiding them never changes EPUB pagination.
        FrameLayout content = new FrameLayout(this);
        root.addView(content, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        if (isPdf) setupPdfView(content); else setupWebView(content);

        topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setPadding(dp(4), dp(5), dp(4), dp(5));
        topBar.setElevation(dp(4));

        TextView back = iconButton("‹", 30);
        back.setContentDescription("Back to Library");
        back.setOnClickListener(v -> {
            if (!isPdf) saveEpubState();
            finish();
        });
        topBar.addView(back, new LinearLayout.LayoutParams(dp(48), dp(50)));

        titleView = new TextView(this);
        titleView.setText(stripExtension(bookFile.getName()));
        titleView.setTextSize(16);
        titleView.setTextColor(Color.rgb(32,33,36));
        titleView.setGravity(Gravity.CENTER_VERTICAL);
        titleView.setSingleLine(true);
        titleView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(0, dp(50), 1);
        titleLp.leftMargin = dp(4);
        topBar.addView(titleView, titleLp);

        contentsButton = iconButton("☰", 19);
        contentsButton.setContentDescription("Table of contents");
        contentsButton.setOnClickListener(v -> { cancelAutoHide(); showContents(); });
        topBar.addView(contentsButton, new LinearLayout.LayoutParams(dp(46), dp(50)));

        TextView search = iconButton("⌕", 22);
        search.setContentDescription("Search chapter");
        search.setOnClickListener(v -> { cancelAutoHide(); searchInBook(); });
        topBar.addView(search, new LinearLayout.LayoutParams(dp(46), dp(50)));

        bookmarkButton = iconButton("☆", 23);
        bookmarkButton.setContentDescription("Bookmark");
        bookmarkButton.setOnClickListener(v -> { toggleBookmark(); showControlsTemporarily(); });
        topBar.addView(bookmarkButton, new LinearLayout.LayoutParams(dp(46), dp(50)));

        TextView appearance = iconButton("Aa", 15);
        appearance.setContentDescription("Reading appearance");
        appearance.setOnClickListener(v -> { cancelAutoHide(); showAppearanceDialog(); });
        topBar.addView(appearance, new LinearLayout.LayoutParams(dp(48), dp(50)));

        FrameLayout.LayoutParams topLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(60), Gravity.TOP);
        root.addView(topBar, topLp);

        bottomBar = new LinearLayout(this);
        bottomBar.setOrientation(LinearLayout.HORIZONTAL);
        bottomBar.setGravity(Gravity.CENTER_VERTICAL);
        bottomBar.setPadding(dp(8), dp(4), dp(8), dp(4));
        bottomBar.setElevation(dp(4));

        TextView prev = textButton("‹");
        prev.setTextSize(28);
        prev.setOnClickListener(v -> { previous(); showControlsTemporarily(); });
        bottomBar.addView(prev, new LinearLayout.LayoutParams(dp(56), dp(50)));

        positionView = new TextView(this);
        positionView.setText("—");
        positionView.setTextSize(13);
        positionView.setTextColor(Color.rgb(95,99,104));
        positionView.setGravity(Gravity.CENTER);
        positionView.setSingleLine(true);
        positionView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        bottomBar.addView(positionView, new LinearLayout.LayoutParams(0, dp(50), 1));

        TextView next = textButton("›");
        next.setTextSize(28);
        next.setOnClickListener(v -> { next(); showControlsTemporarily(); });
        bottomBar.addView(next, new LinearLayout.LayoutParams(dp(56), dp(50)));

        FrameLayout.LayoutParams bottomLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(58), Gravity.BOTTOM);
        root.addView(bottomBar, bottomLp);

        if (isPdf) {
            contentsButton.setVisibility(View.GONE);
            search.setVisibility(View.GONE);
            appearance.setVisibility(View.GONE);
        }

        setContentView(root);
        updateChromeTheme();
        enterImmersive();
        scheduleAutoHide(900);
    }
'''
s, n = re.subn(r'    private void buildReaderUi\(\) \{.*?\n    \}\n\n    private TextView iconButton', new_build + '\n    private TextView iconButton', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('Could not replace buildReaderUi')

new_style = r'''    private void applyReaderStyle(boolean restoreScroll) {
        if (webView == null) return;
        String bg = readerTheme == 2 ? "#121212" : readerTheme == 1 ? "#F4ECD8" : "#FFFFFF";
        String fg = readerTheme == 2 ? "#E8EAED" : "#202124";
        String link = readerTheme == 2 ? "#AECBFA" : "#1967D2";
        String familyCss = "";
        if ("pyidaungsu".equals(fontChoice)) familyCss = "body,body *{font-family:'WoWPyidaungsu',sans-serif !important;}";
        else if ("yoeshin".equals(fontChoice)) familyCss = "body,body *{font-family:'WoWYoeShin',sans-serif !important;}";
        else if ("burma2".equals(fontChoice)) familyCss = "body,body *{font-family:'WoWBurma2',sans-serif !important;}";
        int restore = restoreScroll ? currentScrollPermille : -1;
        boolean paged = "page".equals(readingMode);

        String baseCss =
                "@font-face{font-family:'WoWPyidaungsu';src:url('file:///android_asset/fonts/pyidaungsu.woff2') format('woff2');}" +
                "@font-face{font-family:'WoWYoeShin';src:url('file:///android_asset/fonts/yoeshin.woff2') format('woff2');}" +
                "@font-face{font-family:'WoWBurma2';src:url('file:///android_asset/fonts/burma2.woff2') format('woff2');}" +
                "html,body{background:" + bg + " !important;color:" + fg + " !important;}" +
                "p{line-height:1.72 !important;} img,svg{max-width:100% !important;height:auto !important;} a{color:" + link + " !important;}" + familyCss;

        String modeCss;
        if (paged) {
            // 86vw column + 14vw gap = exactly one screen step. The page index is kept
            // explicitly in JavaScript instead of being guessed from scrollX.
            modeCss =
                    "html{height:100% !important;width:100% !important;margin:0 !important;padding:0 !important;overflow:hidden !important;overscroll-behavior:none !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:1.72 !important;height:100vh !important;width:auto !important;max-width:none !important;" +
                    "margin:0 !important;padding:4vh 7vw 5vh 7vw !important;box-sizing:border-box !important;overflow:visible !important;direction:ltr !important;" +
                    "column-width:86vw !important;column-gap:14vw !important;column-fill:auto !important;will-change:transform !important;transform:translate3d(0,0,0);}" +
                    "img,svg{max-height:82vh !important;}";
        } else {
            modeCss =
                    "html{overflow-x:hidden !important;overscroll-behavior:none !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:1.72 !important;padding:5vh 7vw 12vh 7vw !important;" +
                    "max-width:900px !important;margin:auto !important;box-sizing:border-box !important;transform:none !important;}";
        }
        String css = baseCss + modeCss;
        String mode = paged ? "page" : "scroll";
        double restoreRatio = restore >= 0 ? restore / 1000.0 : 0.0;

        String js = "(function(){" +
                "window.__wowMode='" + mode + "';" +
                "var st=window.__wowPageState||{page:0,count:1,locked:false};window.__wowPageState=st;" +
                "var style=document.getElementById('wow-reader-style');if(!style){style=document.createElement('style');style.id='wow-reader-style';document.head.appendChild(style);}style.innerHTML=" + jsQuote(css) + ";" +
                "window.__wowApply=function(anim){if(window.__wowMode!=='page')return;var w=Math.max(1,window.innerWidth);var b=document.body;b.style.transition=anim?'transform 180ms cubic-bezier(.2,.7,.2,1)':'none';b.style.transform='translate3d('+(-st.page*w)+'px,0,0)';};" +
                "window.__wowReport=function(){if(window.__wowMode!=='page')return;var perm=st.count<=1?0:Math.round((st.page/(st.count-1))*1000);WoW.onPage(st.page+1,st.count,perm);};" +
                "window.__wowMeasure=function(ratio){if(window.__wowMode!=='page')return;document.documentElement.scrollLeft=0;document.body.scrollLeft=0;document.body.style.transform='translate3d(0,0,0)';var w=Math.max(1,window.innerWidth);var sw=Math.max(document.body.scrollWidth,document.documentElement.scrollWidth,w);st.count=Math.max(1,Math.ceil((sw-1)/w));if(ratio>=0)st.page=Math.round((st.count-1)*Math.max(0,Math.min(1,ratio)));else st.page=Math.max(0,Math.min(st.count-1,st.page));window.__wowApply(false);window.__wowReport();};" +
                "window.__wowTurn=function(delta){if(window.__wowMode!=='page'||st.locked)return;if(delta<0&&st.page<=0){WoW.prevChapter();return;}if(delta>0&&st.page>=st.count-1){WoW.nextChapter();return;}st.page=Math.max(0,Math.min(st.count-1,st.page+delta));st.locked=true;window.__wowApply(true);window.__wowReport();setTimeout(function(){st.locked=false;},190);};" +
                "if(!window.__wowBound){window.__wowBound=true;var timer=0,sx=0,sy=0,start=0,suppress=0,resizeTimer=0;" +
                "window.addEventListener('scroll',function(){if(window.__wowMode!=='scroll')return;clearTimeout(timer);timer=setTimeout(function(){var h=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);WoW.onScroll(Math.round((window.scrollY/h)*1000));},90);},{passive:true});" +
                "document.addEventListener('touchstart',function(e){if(!e.touches||e.touches.length!==1)return;sx=e.touches[0].clientX;sy=e.touches[0].clientY;start=Date.now();},{passive:true});" +
                "document.addEventListener('touchend',function(e){if(window.__wowMode!=='page'||!e.changedTouches||!e.changedTouches.length)return;var ex=e.changedTouches[0].clientX,ey=e.changedTouches[0].clientY,dx=ex-sx,dy=ey-sy;if(sx<28||sx>window.innerWidth-28)return;if(Math.abs(dx)>52&&Math.abs(dx)>Math.abs(dy)*1.25&&Date.now()-start<850){suppress=Date.now()+350;window.__wowTurn(dx>0?-1:1);}},{passive:true});" +
                "document.addEventListener('click',function(e){if(Date.now()<suppress)return;var node=e.target;while(node&&node!==document){if(node.tagName&&node.tagName.toLowerCase()==='a')return;node=node.parentNode;}if(window.__wowMode==='page'){var x=e.clientX/window.innerWidth;if(x<0.30)window.__wowTurn(-1);else if(x>0.70)window.__wowTurn(1);else WoW.toggle();}else WoW.toggle();});" +
                "window.addEventListener('resize',function(){if(window.__wowMode!=='page')return;clearTimeout(resizeTimer);resizeTimer=setTimeout(function(){var r=st.count<=1?0:st.page/(st.count-1);window.__wowMeasure(r);},160);});" +
                "}" +
                "if(window.__wowMode==='page'){var startMeasure=function(){window.__wowMeasure(" + restoreRatio + ");};if(document.fonts&&document.fonts.ready)document.fonts.ready.then(function(){setTimeout(startMeasure,30);});else setTimeout(startMeasure,180);}" +
                "else{" + (restore >= 0 ? "setTimeout(function(){var h=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);window.scrollTo(0,h*" + restoreRatio + ");},80);" : "") + "}" +
                "})();";
        webView.evaluateJavascript(js, null);
        updateChromeTheme();
        scheduleAutoHide(1100);
    }
'''
s, n = re.subn(r'    private void applyReaderStyle\(boolean restoreScroll\) \{.*?\n    \}\n\n    private String jsQuote', new_style + '\n    private String jsQuote', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('Could not replace applyReaderStyle')

# Overlay controls can be GONE without resizing the WebView because they are not in a LinearLayout anymore.
old_toggle = '    private void toggleControls(){boolean show=topBar.getVisibility()!=View.VISIBLE;topBar.setVisibility(show?View.VISIBLE:View.INVISIBLE);bottomBar.setVisibility(show?View.VISIBLE:View.INVISIBLE);}\n'
new_controls = r'''    private void cancelAutoHide(){uiHandler.removeCallbacks(autoHideRunnable);}
    private void scheduleAutoHide(long delayMs){cancelAutoHide();uiHandler.postDelayed(autoHideRunnable,delayMs);}
    private void hideControls(){if(topBar!=null)topBar.setVisibility(View.GONE);if(bottomBar!=null)bottomBar.setVisibility(View.GONE);enterImmersive();}
    private void showControlsTemporarily(){if(topBar!=null)topBar.setVisibility(View.VISIBLE);if(bottomBar!=null)bottomBar.setVisibility(View.VISIBLE);enterImmersive();scheduleAutoHide(2800);}
    private void toggleControls(){if(topBar!=null&&topBar.getVisibility()==View.VISIBLE)hideControls();else showControlsTemporarily();}
    private void enterImmersive(){getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY |
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE |
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_FULLSCREEN);}
'''
if old_toggle not in s:
    raise SystemExit('Could not find toggleControls')
s = s.replace(old_toggle, new_controls)

# System back/edge gesture must never throw the user out of the reader. Only the visible ‹ button exits.
new_back = r'''    @Override public void onWindowFocusChanged(boolean hasFocus){
        super.onWindowFocusChanged(hasFocus);
        if(hasFocus){enterImmersive();scheduleAutoHide(900);}
    }

    @Override protected void onResume(){
        super.onResume();
        enterImmersive();
        scheduleAutoHide(900);
    }

    @Override public void onBackPressed(){
        enterImmersive();
        showControlsTemporarily();
        long now=System.currentTimeMillis();
        if(now>backArmedUntil){
            backArmedUntil=now+1600L;
            Toast.makeText(this,"Use ‹ to return to Library",Toast.LENGTH_SHORT).show();
        }
    }
'''
s, n = re.subn(r'    @Override public void onBackPressed\(\)\{.*?\n    \}\n\n    @Override protected void onPause', new_back + '\n    @Override protected void onPause', s, count=1, flags=re.S)
if n != 1:
    raise SystemExit('Could not replace onBackPressed')

# Clean up Handler callbacks on destroy.
s = s.replace('    @Override protected void onDestroy(){super.onDestroy();', '    @Override protected void onDestroy(){cancelAutoHide();super.onDestroy();')

path.write_text(s, encoding='utf-8')
print('WoW Reader v1.3.0 reader patch applied')
