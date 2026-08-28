from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# Imports used by the glass TOC and seamless WebView snapshots.
s = s.replace('import android.app.AlertDialog;\n', 'import android.app.AlertDialog;\nimport android.app.Dialog;\n', 1)
s = s.replace('import android.graphics.Bitmap;\n', 'import android.graphics.Bitmap;\nimport android.graphics.Canvas;\n', 1)
s = s.replace('import android.graphics.Matrix;\n', 'import android.graphics.Matrix;\nimport android.graphics.drawable.ColorDrawable;\nimport android.graphics.drawable.GradientDrawable;\n', 1)
s = s.replace('import android.os.Bundle;\n', 'import android.os.Build;\nimport android.os.Bundle;\n', 1)
s = s.replace('import android.view.ViewGroup;\n', 'import android.view.ViewGroup;\nimport android.view.Window;\n', 1)
s = s.replace('import android.widget.LinearLayout;\n', 'import android.widget.LinearLayout;\nimport android.widget.ScrollView;\n', 1)

# Native page-curl and chapter transition state.
anchor = '    private WebView webView;\n'
if anchor not in s:
    raise SystemExit('v2.1 reader: webView field anchor not found')
s = s.replace(anchor, anchor + '''    private PageCurlView pageCurlView;\n    private ImageView chapterTransitionOverlay;\n    private Bitmap chapterTransitionBitmap;\n    private int pendingChapterCurlDirection = 0;\n    private boolean pendingChapterFade = false;\n''', 1)

# Rebuild the EPUB WebView setup so a native curl layer and a frozen chapter
# snapshot always sit over the document while the next content is preparing.
start = s.index('    private void setupWebView(FrameLayout content) {')
end = s.index('\n    private void handleReaderTap', start)
setup = r'''    private void setupWebView(FrameLayout content) {
        webView = new WebView(this);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setDefaultTextEncodingName("UTF-8");
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setSupportZoom(false);

        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        webView.setHorizontalScrollBarEnabled(false);
        webView.setVerticalScrollBarEnabled(false);
        webView.addJavascriptInterface(new ReaderBridge(), "WoW");

        readerTapDetector = new GestureDetector(this, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent e) { return true; }

            @Override public boolean onSingleTapConfirmed(MotionEvent e) {
                handleReaderTap(e.getX(), e.getY());
                return true;
            }

            @Override public boolean onFling(MotionEvent e1, MotionEvent e2, float velocityX, float velocityY) {
                if (!"page".equals(readingMode) || e1 == null || e2 == null || chapterLoading || pageTurnLocked)
                    return false;
                float dx = e2.getX() - e1.getX();
                float dy = e2.getY() - e1.getY();
                int edgeSafe = dp(30);
                if (e1.getX() < edgeSafe || e1.getX() > webView.getWidth() - edgeSafe) return false;
                if (Math.abs(dx) < dp(64) || Math.abs(dx) < Math.abs(dy) * 1.35f || Math.abs(velocityX) < 500f)
                    return false;
                turnPage(dx < 0 ? 1 : -1);
                return true;
            }
        });

        webView.setOnTouchListener((v, event) -> {
            readerTapDetector.onTouchEvent(event);
            return false;
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                applyReaderStyle(true);
                if ("scroll".equals(readingMode)) {
                    webView.postDelayed(() -> {
                        chapterLoading = false;
                        pageTurnLocked = false;
                        finishChapterFade();
                    }, 90L);
                } else {
                    // Page mode waits for onPageReady so pagination and fonts are
                    // final before the old chapter is removed from the screen.
                    webView.postDelayed(() -> {
                        if (!chapterLoading) return;
                        chapterLoading = false;
                        pageTurnLocked = false;
                        pendingChapterCurlDirection = 0;
                        if (pageCurlView != null) pageCurlView.release();
                        finishChapterFade();
                    }, 1250L);
                }
            }
        });

        content.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        chapterTransitionOverlay = new ImageView(this);
        chapterTransitionOverlay.setScaleType(ImageView.ScaleType.FIT_XY);
        chapterTransitionOverlay.setVisibility(View.GONE);
        chapterTransitionOverlay.setClickable(false);
        content.addView(chapterTransitionOverlay, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        pageCurlView = new PageCurlView(this);
        content.addView(pageCurlView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
    }
'''
s = s[:start] + setup + s[end:]

# Never let broken metadata replace a useful filename with Untitled/Unknown.
old = '''                    if (info.title != null && !info.title.isEmpty()) titleView.setText(info.title);\n'''
new = '''                    if (info.title != null && !info.title.isEmpty() && !isGenericDisplayTitle(info.title))\n                        titleView.setText(info.title);\n                    else\n                        titleView.setText(stripExtension(bookFile.getName()));\n'''
if old not in s:
    raise SystemExit('v2.1 reader: book title anchor not found')
s = s.replace(old, new, 1)

# Chapter navigation holds the old page in place before changing the spine.
start = s.index('    private void navigateChapter(int delta, boolean restoreEnd) {')
end = s.index('\n    private void showContents()', start)
navigate = r'''    private void navigateChapter(int delta, boolean restoreEnd) {
        if (isPdf || spine.isEmpty() || chapterLoading) return;

        long now = System.currentTimeMillis();
        if (now - lastChapterNavMs < 420L) return;

        int target = currentSpine + delta;
        if (target < 0 || target >= spine.size()) {
            pageTurnLocked = false;
            return;
        }

        prepareChapterTransition(delta);
        lastChapterNavMs = now;
        currentSpine = target;
        currentProgressPermille = restoreEnd ? 1000 : 0;
        saveEpubStateOnly();
        loadCurrentEpubChapter();
    }
'''
s = s[:start] + navigate + s[end:]

# Replace Android's uneven radio-list dialog with a fixed-column glass sheet.
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

        for (int i = 0; i < spine.size(); i++) {
            final int index = i;
            boolean selected = i == currentSpine;

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
            label.setText(chapterDisplayTitle(i));
            label.setTextSize(17);
            label.setTextColor(text);
            label.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
            label.setLineSpacing(0f, 1.12f);
            label.setPadding(dp(7), dp(4), dp(5), dp(4));
            row.addView(label, new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            row.setOnClickListener(v -> {
                if (!chapterLoading && index != currentSpine) {
                    int direction = index > currentSpine ? 1 : -1;
                    prepareChapterTransition(direction);
                    currentSpine = index;
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

    private String chapterDisplayTitle(int index) {
        String value = index >= 0 && index < chapterTitles.size() ? chapterTitles.get(index) : null;
        if (isGenericDisplayTitle(value)) return "Chapter " + (index + 1);
        return value.trim();
    }

    private boolean isGenericDisplayTitle(String value) {
        if (value == null) return true;
        String low = value.trim().toLowerCase(Locale.ROOT).replace('_', ' ').replace('-', ' ').replaceAll("\\s+", " ");
        if (low.isEmpty() || low.equals("unknown") || low.equals("untitled") || low.equals("undefined") ||
                low.equals("null") || low.equals("none") || low.equals("n/a") || low.equals("no title")) return true;
        return low.matches("^(chapter|section|part|page|text|content|item|file)\\s*$");
    }

    private GradientDrawable glassPanel(int fill, int radius, int stroke) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(radius);
        if (Color.alpha(stroke) > 0) d.setStroke(Math.max(1, dp(1)), stroke);
        return d;
    }
'''
s = s[:start] + contents + s[end:]

# Native mesh curl for ordinary page turns. The WebView is silently moved to
# the target page underneath a bitmap of the current page, then PageCurlView
# bends that bitmap away to reveal the target. Chapter boundaries keep using
# the JS requestChapter path, where the same curl is continued after loading.
start = s.index('    private void turnPage(int delta) {')
end = s.index('\n    private void showReaderSettings()', start)
turn = r'''    private void turnPage(int delta) {
        if (webView == null || chapterLoading || !"page".equals(readingMode) || delta == 0) return;
        long now = System.currentTimeMillis();
        if (pageTurnLocked || now - lastPageTurnMs < 300L) return;

        lastPageTurnMs = now;
        int targetPage = currentPageInChapter + (delta < 0 ? -1 : 1);
        boolean insideChapter = targetPage >= 1 && targetPage <= pageCountInChapter;

        if ("paper".equals(pageAnimation) && insideChapter && pageCurlView != null) {
            startNativePageCurl(delta < 0 ? -1 : 1, targetPage - 1);
        } else {
            performJsPageTurn(delta < 0 ? -1 : 1);
        }
    }

    private void startNativePageCurl(int direction, int targetZeroBased) {
        Bitmap current = captureWebViewBitmap();
        if (current == null || pageCurlView == null) {
            performJsPageTurn(direction);
            return;
        }

        pageTurnLocked = true;
        pageCurlView.hold(current);
        String jump = "(function(){var st=window.__wowPageEngine;if(!st||st.mode!=='page')return 'unavailable';" +
                "st.locked=true;st.page=st.clamp(" + targetZeroBased + ",0,(st.count||1)-1);st.apply(false);return 'ok';})()";
        try {
            webView.evaluateJavascript(jump, result -> {
                if (result == null || result.contains("unavailable")) {
                    if (pageCurlView != null) pageCurlView.release();
                    pageTurnLocked = false;
                    performJsPageTurn(direction);
                    return;
                }
                webView.postDelayed(() -> {
                    Bitmap target = captureWebViewBitmap();
                    if (target == null || pageCurlView == null) {
                        if (pageCurlView != null) pageCurlView.release();
                        finishNativePageCurl();
                        return;
                    }
                    pageCurlView.startCurl(target, direction, this::finishNativePageCurl);
                }, 48L);
            });
        } catch (Exception e) {
            if (pageCurlView != null) pageCurlView.release();
            pageTurnLocked = false;
            performJsPageTurn(direction);
        }
    }

    private void finishNativePageCurl() {
        try {
            webView.evaluateJavascript(
                    "(function(){var st=window.__wowPageEngine;if(!st)return;st.locked=false;st.report();WoW.onPageTurnComplete((st.page||0)+1,st.count||1,st.progress());})()",
                    null);
        } catch (Exception ignored) {}
        pageTurnLocked = false;
    }

    private void performJsPageTurn(int delta) {
        if (webView == null) return;
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
            if (pageTurnLocked && !chapterLoading && (pageCurlView == null || !pageCurlView.isBusy())) {
                pageTurnLocked = false;
                try { webView.evaluateJavascript("if(window.__wowPageEngine)window.__wowPageEngine.locked=false", null); }
                catch (Exception ignored) {}
            }
        }, 750L);
    }

    private Bitmap captureWebViewBitmap() {
        if (webView == null || webView.getWidth() <= 0 || webView.getHeight() <= 0) return null;
        try {
            Bitmap bitmap = Bitmap.createBitmap(webView.getWidth(), webView.getHeight(), Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(bitmap);
            webView.draw(canvas);
            return bitmap;
        } catch (OutOfMemoryError | RuntimeException e) {
            return null;
        }
    }

    private void prepareChapterTransition(int direction) {
        if (webView == null || webView.getUrl() == null) return;
        Bitmap shot = captureWebViewBitmap();
        if (shot == null) return;

        if ("page".equals(readingMode) && "paper".equals(pageAnimation) && pageCurlView != null) {
            finishChapterFadeImmediate();
            pendingChapterCurlDirection = direction < 0 ? -1 : 1;
            pageCurlView.hold(shot);
            return;
        }

        pendingChapterCurlDirection = 0;
        if (chapterTransitionBitmap != null && !chapterTransitionBitmap.isRecycled()) chapterTransitionBitmap.recycle();
        chapterTransitionBitmap = shot;
        chapterTransitionOverlay.setImageBitmap(shot);
        chapterTransitionOverlay.setAlpha(1f);
        chapterTransitionOverlay.setVisibility(View.VISIBLE);
        chapterTransitionOverlay.bringToFront();
        pendingChapterFade = true;
    }

    private boolean finishPendingChapterCurl() {
        if (pendingChapterCurlDirection == 0 || pageCurlView == null) return false;
        int direction = pendingChapterCurlDirection;
        pendingChapterCurlDirection = 0;
        Bitmap target = captureWebViewBitmap();
        if (target == null) {
            pageCurlView.release();
            return false;
        }
        pageCurlView.startCurl(target, direction, () -> {
            chapterLoading = false;
            pageTurnLocked = false;
        });
        return true;
    }

    private void finishChapterFade() {
        if (!pendingChapterFade || chapterTransitionOverlay == null) return;
        pendingChapterFade = false;
        chapterTransitionOverlay.animate().cancel();
        chapterTransitionOverlay.animate().alpha(0f).setDuration(190L).withEndAction(this::finishChapterFadeImmediate).start();
    }

    private void finishChapterFadeImmediate() {
        pendingChapterFade = false;
        if (chapterTransitionOverlay != null) {
            chapterTransitionOverlay.animate().cancel();
            chapterTransitionOverlay.setVisibility(View.GONE);
            chapterTransitionOverlay.setImageDrawable(null);
            chapterTransitionOverlay.setAlpha(1f);
        }
        if (chapterTransitionBitmap != null && !chapterTransitionBitmap.isRecycled()) chapterTransitionBitmap.recycle();
        chapterTransitionBitmap = null;
    }
'''
s = s[:start] + turn + s[end:]

# ReaderBridge now keeps the frozen old chapter on-screen until the newly
# paginated target chapter is actually ready, then curls between them.
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
                if (finishPendingChapterCurl()) return;
                pageTurnLocked = false;
                chapterLoading = false;
                finishChapterFade();
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

# Reader chrome gets a translucent glass surface. On old Android this is a
# graceful frosted-color fallback; the TOC uses real background blur on API 31+.
start = s.index('    private void updateChromeTheme() {')
end = s.index('\n    private void openPdf()', start)
chrome = r'''    private void updateChromeTheme() {
        int solid;
        int fg;
        int glass;
        int stroke;

        if (isPdf) {
            solid = Color.WHITE;
            fg = Color.rgb(32, 33, 36);
            glass = Color.argb(232, 255, 255, 255);
            stroke = Color.argb(78, 255, 255, 255);
        } else if (readerTheme == 2) {
            solid = Color.rgb(18, 18, 18);
            fg = Color.rgb(232, 234, 237);
            glass = Color.argb(224, 24, 25, 28);
            stroke = Color.argb(48, 255, 255, 255);
        } else if (readerTheme == 1) {
            solid = Color.rgb(244, 236, 216);
            fg = Color.rgb(32, 33, 36);
            glass = Color.argb(230, 248, 241, 222);
            stroke = Color.argb(82, 255, 255, 255);
        } else {
            solid = Color.WHITE;
            fg = Color.rgb(32, 33, 36);
            glass = Color.argb(228, 255, 255, 255);
            stroke = Color.argb(88, 255, 255, 255);
        }

        if (topBar != null) topBar.setBackground(glassPanel(glass, 0, stroke));
        if (bottomBar != null) bottomBar.setBackground(glassPanel(glass, 0, stroke));
        if (titleView != null) titleView.setTextColor(fg);
        if (positionView != null) positionView.setTextColor(fg);
        if (root != null) root.setBackgroundColor(solid);
        if (webView != null) webView.setBackgroundColor(solid);
    }
'''
s = s[:start] + chrome + s[end:]

# Release transition bitmaps with the reader.
destroy_anchor = '''    @Override\n    protected void onDestroy() {\n        if (webView != null) {\n'''
if destroy_anchor not in s:
    raise SystemExit('v2.1 reader: onDestroy anchor not found')
s = s.replace(destroy_anchor, '''    @Override\n    protected void onDestroy() {\n        pendingChapterCurlDirection = 0;\n        if (pageCurlView != null) pageCurlView.release();\n        finishChapterFadeImmediate();\n        if (webView != null) {\n''', 1)

assert 'PageCurlView pageCurlView' in s
assert 'startNativePageCurl' in s
assert 'finishPendingChapterCurl' in s
assert 'window.setBackgroundBlurRadius' in s
assert 'chapterDisplayTitle' in s
assert 'isGenericDisplayTitle' in s
assert 'Untitled' not in s or 'Untitled/Unknown' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.1 native curl + seamless chapters + glass TOC patch applied')
