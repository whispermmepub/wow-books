package com.whisper.wowreader;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.content.pm.ActivityInfo;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.view.GestureDetector;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class BookReaderActivity extends Activity {
    private File bookFile;
    private SharedPreferences prefs;
    private boolean isPdf;

    private FrameLayout root;
    private LinearLayout topBar;
    private LinearLayout bottomBar;
    private TextView titleView;
    private TextView positionView;
    private TextView bookmarkButton;
    private TextView contentsButton;
    private TextView appearanceButton;
    private boolean controlsVisible = false;

    private WebView webView;
    private GestureDetector readerTapDetector;
    private final List<File> spine = new ArrayList<>();
    private final List<String> chapterTitles = new ArrayList<>();
    private int currentSpine = 0;
    private int currentProgressPermille = 0;
    private int readerTheme = 0;
    private int fontPercent = 115;
    private String fontChoice = "publisher";
    private int lineSpacing = 170;
    private int marginPercent = 7;
    private int brightnessPercent = -1;
    private boolean keepScreenOn = false;
    private boolean lockOrientation = false;
    private boolean volumeChapterKeys = false;
    private boolean chapterLoading = false;
    private long lastChapterNavMs = 0L;

    private ParcelFileDescriptor pdfDescriptor;
    private PdfRenderer pdfRenderer;
    private PdfRenderer.Page pdfPage;
    private ImageView pdfImage;
    private int currentPdfPage = 0;
    private float pdfScale = 1f;
    private ScaleGestureDetector pdfScaleDetector;
    private GestureDetector pdfGestureDetector;
    private float lastTouchX;
    private float lastTouchY;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        enterImmersive();

        String path = getIntent().getStringExtra("path");
        if (path == null) {
            finish();
            return;
        }

        bookFile = new File(path);
        prefs = getSharedPreferences("wow_reader", MODE_PRIVATE);
        isPdf = bookFile.getName().toLowerCase(Locale.ROOT).endsWith(".pdf");

        readerTheme = prefs.getInt("reader_theme", 0);
        fontPercent = prefs.getInt("epub_font", 115);
        fontChoice = prefs.getString("epub_font_choice", "publisher");
        lineSpacing = prefs.getInt("epub_line_spacing", 170);
        marginPercent = prefs.getInt("epub_margin", 7);
        brightnessPercent = prefs.getInt("reader_brightness", -1);
        keepScreenOn = prefs.getBoolean("reader_keep_screen_on", false);
        lockOrientation = prefs.getBoolean("reader_lock_orientation", false);
        volumeChapterKeys = prefs.getBoolean("reader_volume_chapter", false);

        // v1.6 is intentionally scroll-only. Older unstable page-mode preference is ignored.
        prefs.edit().putString("epub_reading_mode", "scroll").apply();

        applyWindowPreferences();
        buildReaderUi();
        if (isPdf) openPdf(); else openEpub();
    }

    private void buildReaderUi() {
        root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        FrameLayout content = new FrameLayout(this);
        root.addView(content, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        if (isPdf) setupPdfView(content); else setupWebView(content);

        topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setPadding(dp(4), dp(5), dp(4), dp(5));
        topBar.setElevation(dp(5));

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
        titleView.setTextColor(Color.rgb(32, 33, 36));
        titleView.setGravity(Gravity.CENTER_VERTICAL);
        titleView.setSingleLine(true);
        titleView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(0, dp(50), 1);
        titleLp.leftMargin = dp(4);
        topBar.addView(titleView, titleLp);

        contentsButton = iconButton("☰", 19);
        contentsButton.setContentDescription("Table of contents");
        contentsButton.setOnClickListener(v -> showContents());
        topBar.addView(contentsButton, new LinearLayout.LayoutParams(dp(46), dp(50)));

        TextView search = iconButton("⌕", 22);
        search.setContentDescription("Search in book");
        search.setOnClickListener(v -> searchInBook());
        topBar.addView(search, new LinearLayout.LayoutParams(dp(46), dp(50)));

        bookmarkButton = iconButton("☆", 23);
        bookmarkButton.setContentDescription("Bookmark");
        bookmarkButton.setOnClickListener(v -> toggleBookmark());
        topBar.addView(bookmarkButton, new LinearLayout.LayoutParams(dp(46), dp(50)));

        appearanceButton = iconButton("Aa", 15);
        appearanceButton.setContentDescription("Reader settings");
        appearanceButton.setOnClickListener(v -> showReaderSettings());
        topBar.addView(appearanceButton, new LinearLayout.LayoutParams(dp(48), dp(50)));

        FrameLayout.LayoutParams topLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(60), Gravity.TOP);
        root.addView(topBar, topLp);

        bottomBar = new LinearLayout(this);
        bottomBar.setOrientation(LinearLayout.HORIZONTAL);
        bottomBar.setGravity(Gravity.CENTER_VERTICAL);
        bottomBar.setPadding(dp(8), dp(4), dp(8), dp(4));
        bottomBar.setElevation(dp(5));

        TextView prev = textButton("‹");
        prev.setTextSize(28);
        prev.setContentDescription(isPdf ? "Previous page" : "Previous chapter");
        prev.setOnClickListener(v -> previous());
        bottomBar.addView(prev, new LinearLayout.LayoutParams(dp(56), dp(50)));

        positionView = new TextView(this);
        positionView.setText("—");
        positionView.setTextSize(13);
        positionView.setTextColor(Color.rgb(95, 99, 104));
        positionView.setGravity(Gravity.CENTER);
        positionView.setSingleLine(true);
        positionView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        bottomBar.addView(positionView, new LinearLayout.LayoutParams(0, dp(50), 1));

        TextView next = textButton("›");
        next.setTextSize(28);
        next.setContentDescription(isPdf ? "Next page" : "Next chapter");
        next.setOnClickListener(v -> next());
        bottomBar.addView(next, new LinearLayout.LayoutParams(dp(56), dp(50)));

        FrameLayout.LayoutParams bottomLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(58), Gravity.BOTTOM);
        root.addView(bottomBar, bottomLp);

        if (isPdf) {
            contentsButton.setVisibility(View.GONE);
            search.setVisibility(View.GONE);
        }

        setContentView(root);
        updateChromeTheme();
        hideControls();
        enterImmersive();
    }

    private TextView iconButton(String text, int size) {
        TextView v = new TextView(this);
        v.setText(text);
        v.setTextSize(size);
        v.setTextColor(Color.rgb(60, 64, 67));
        v.setGravity(Gravity.CENTER);
        v.setClickable(true);
        v.setBackgroundColor(Color.TRANSPARENT);
        return v;
    }

    private TextView textButton(String text) {
        return iconButton(text, 18);
    }

    private void setupWebView(FrameLayout content) {
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
                chapterLoading = false;
            }
        });

        content.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private void handleReaderTap(float x, float y) {
        if (webView == null || chapterLoading) return;

        final float ratio = x / Math.max(1f, webView.getWidth());
        final int px = Math.round(x);
        final int py = Math.round(y);

        String hitTest = "(function(){try{" +
                "if(window.getSelection&&String(window.getSelection()).length>0)return 'selection';" +
                "var n=document.elementFromPoint(" + px + "," + py + ");" +
                "while(n){if(n.tagName&&n.tagName.toLowerCase()==='a')return 'link';n=n.parentElement;}" +
                "return 'plain';}catch(e){return 'plain';}})()";

        try {
            webView.evaluateJavascript(hitTest, result -> {
                if (result != null && (result.contains("link") || result.contains("selection"))) return;

                if (ratio < 0.24f) {
                    navigateChapter(-1, true);
                } else if (ratio > 0.76f) {
                    navigateChapter(1, false);
                } else {
                    toggleControls();
                }
            });
        } catch (Exception ignored) {
            toggleControls();
        }
    }

    private void setupPdfView(FrameLayout content) {
        pdfImage = new ImageView(this);
        pdfImage.setScaleType(ImageView.ScaleType.FIT_CENTER);
        pdfImage.setBackgroundColor(Color.rgb(48, 49, 52));
        content.addView(pdfImage, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        pdfScaleDetector = new ScaleGestureDetector(this,
                new ScaleGestureDetector.SimpleOnScaleGestureListener() {
                    @Override public boolean onScale(ScaleGestureDetector detector) {
                        pdfScale *= detector.getScaleFactor();
                        pdfScale = Math.max(1f, Math.min(pdfScale, 4f));
                        pdfImage.setScaleX(pdfScale);
                        pdfImage.setScaleY(pdfScale);
                        return true;
                    }
                });

        pdfGestureDetector = new GestureDetector(this,
                new GestureDetector.SimpleOnGestureListener() {
                    @Override public boolean onDown(MotionEvent e) { return true; }

                    @Override public boolean onDoubleTap(MotionEvent e) {
                        if (pdfScale > 1.05f) {
                            resetPdfZoom();
                        } else {
                            pdfScale = 2f;
                            pdfImage.setPivotX(e.getX());
                            pdfImage.setPivotY(e.getY());
                            pdfImage.setScaleX(pdfScale);
                            pdfImage.setScaleY(pdfScale);
                        }
                        return true;
                    }

                    @Override public boolean onSingleTapConfirmed(MotionEvent e) {
                        float r = e.getX() / Math.max(1f, pdfImage.getWidth());
                        if (pdfScale <= 1.05f && r < 0.24f) previous();
                        else if (pdfScale <= 1.05f && r > 0.76f) next();
                        else toggleControls();
                        return true;
                    }
                });

        pdfImage.setOnTouchListener((v, event) -> {
            pdfScaleDetector.onTouchEvent(event);
            pdfGestureDetector.onTouchEvent(event);

            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                lastTouchX = event.getX();
                lastTouchY = event.getY();
            } else if (event.getActionMasked() == MotionEvent.ACTION_MOVE &&
                    pdfScale > 1.01f && !pdfScaleDetector.isInProgress()) {
                float dx = event.getX() - lastTouchX;
                float dy = event.getY() - lastTouchY;
                pdfImage.setTranslationX(pdfImage.getTranslationX() + dx);
                pdfImage.setTranslationY(pdfImage.getTranslationY() + dy);
                lastTouchX = event.getX();
                lastTouchY = event.getY();
            }
            return true;
        });
    }

    private void openEpub() {
        chapterLoading = true;
        new Thread(() -> {
            try {
                String id = Integer.toHexString((bookFile.getAbsolutePath() + ":" +
                        bookFile.lastModified() + ":" + bookFile.length()).hashCode());
                File extractDir = new File(getFilesDir(), "epub_cache/" + id);

                if (!new File(extractDir, ".ready").exists()) {
                    deleteRecursive(extractDir);
                    if (!extractDir.mkdirs() && !extractDir.exists())
                        throw new Exception("Cannot prepare EPUB folder");
                    unzipEpub(bookFile, extractDir);
                    new File(extractDir, ".ready").createNewFile();
                }

                EpubUtil.BookInfo info = EpubUtil.parseExtracted(extractDir);

                runOnUiThread(() -> {
                    spine.clear();
                    spine.addAll(info.spine);
                    chapterTitles.clear();
                    chapterTitles.addAll(info.chapterTitles);

                    if (info.title != null && !info.title.isEmpty()) titleView.setText(info.title);

                    if (spine.isEmpty()) {
                        chapterLoading = false;
                        Toast.makeText(this, "This EPUB has no readable chapters", Toast.LENGTH_LONG).show();
                        return;
                    }

                    currentSpine = Math.max(0, Math.min(
                            prefs.getInt("epub_chapter_" + bookFile.getName(), 0),
                            spine.size() - 1));
                    currentProgressPermille =
                            prefs.getInt("epub_scroll_" + bookFile.getName(), 0);
                    loadCurrentEpubChapter();
                });

            } catch (Exception e) {
                runOnUiThread(() -> {
                    chapterLoading = false;
                    Toast.makeText(this, "EPUB error: " + e.getMessage(), Toast.LENGTH_LONG).show();
                    positionView.setText("Unable to open EPUB");
                });
            }
        }).start();
    }

    private void loadCurrentEpubChapter() {
        if (spine.isEmpty() || webView == null) return;

        chapterLoading = true;
        try {
            webView.loadUrl(Uri.fromFile(spine.get(currentSpine)).toString());
            updateEpubProgress(currentProgressPermille);
            updateBookmarkIcon();
        } catch (Exception e) {
            chapterLoading = false;
            Toast.makeText(this, "Cannot open chapter", Toast.LENGTH_SHORT).show();
        }
    }

    private void navigateChapter(int delta, boolean restoreEnd) {
        if (isPdf || spine.isEmpty() || chapterLoading) return;

        long now = System.currentTimeMillis();
        if (now - lastChapterNavMs < 650L) return;

        int target = currentSpine + delta;
        if (target < 0 || target >= spine.size()) return;

        lastChapterNavMs = now;
        currentSpine = target;
        currentProgressPermille = restoreEnd ? 1000 : 0;
        saveEpubStateOnly();
        loadCurrentEpubChapter();
    }

    private void showContents() {
        if (isPdf || spine.isEmpty()) return;

        String[] items = new String[spine.size()];
        for (int i = 0; i < items.length; i++) {
            String name = i < chapterTitles.size() ? chapterTitles.get(i) : "Chapter " + (i + 1);
            items[i] = (i == currentSpine ? "●  " : "     ") + name;
        }

        new AlertDialog.Builder(this)
                .setTitle("Table of contents")
                .setSingleChoiceItems(items, currentSpine, (dialog, which) -> {
                    if (!chapterLoading && which != currentSpine) {
                        currentSpine = which;
                        currentProgressPermille = 0;
                        saveEpubStateOnly();
                        loadCurrentEpubChapter();
                    }
                    dialog.dismiss();
                })
                .setNegativeButton("Close", null)
                .show();
    }

    private void applyReaderStyle(boolean restoreProgress) {
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
        double line = lineSpacing / 100.0;

        String css =
                "@font-face{font-family:'WoWPyidaungsu';src:url('file:///android_asset/fonts/pyidaungsu.woff2') format('woff2');}" +
                "@font-face{font-family:'WoWYoeShin';src:url('file:///android_asset/fonts/yoeshin.woff2') format('woff2');}" +
                "@font-face{font-family:'WoWBurma2';src:url('file:///android_asset/fonts/burma2.woff2') format('woff2');}" +
                "html{overflow-x:hidden !important;background:" + bg + " !important;color:" + fg + " !important;}" +
                "body{font-size:" + fontPercent + "% !important;line-height:" + line + " !important;" +
                "padding:5vh " + marginPercent + "vw 12vh " + marginPercent + "vw !important;" +
                "max-width:900px !important;margin:auto !important;box-sizing:border-box !important;" +
                "background:" + bg + " !important;color:" + fg + " !important;}" +
                "body *{max-width:100%;}" +
                "p{line-height:" + line + " !important;}" +
                "img,svg{max-width:100% !important;height:auto !important;}" +
                "a{color:" + link + " !important;}" +
                familyCss;

        double ratio = restore >= 0 ? restore / 1000.0 : 0.0;

        String js = "(function(){" +
                "var s=document.getElementById('wow-reader-style');" +
                "if(!s){s=document.createElement('style');s.id='wow-reader-style';document.head.appendChild(s);}" +
                "s.innerHTML=" + jsQuote(css) + ";" +
                "if(!window.__wowScrollBound){window.__wowScrollBound=true;var t=0;" +
                "window.addEventListener('scroll',function(){clearTimeout(t);t=setTimeout(function(){" +
                "var h=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);" +
                "WoW.onScroll(Math.round((window.scrollY/h)*1000));},90);},{passive:true});}" +
                (restore >= 0 ?
                        "setTimeout(function(){var h=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);" +
                        "window.scrollTo(0,h*" + ratio + ");},90);" : "") +
                "})();";

        try {
            webView.evaluateJavascript(js, null);
        } catch (Exception ignored) {
        }

        updateChromeTheme();
    }

    private String jsQuote(String s) {
        return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ") + "'";
    }

    private void showReaderSettings() {
        if (isPdf) {
            showPdfSettings();
            return;
        }

        String[] options = new String[]{
                "Font size · " + fontPercent + "%",
                "Font · " + fontDisplayName(),
                "Line spacing · " + lineSpacingDisplay(),
                "Margins · " + marginPercent + "%",
                "Theme · " + themeDisplayName(),
                "Brightness · " + brightnessDisplayName(),
                "Keep screen on · " + onOff(keepScreenOn),
                "Lock orientation · " + onOff(lockOrientation),
                "Volume keys change chapter · " + onOff(volumeChapterKeys),
                "Reset reader settings"
        };

        new AlertDialog.Builder(this)
                .setTitle("Reader settings")
                .setItems(options, (d, which) -> {
                    switch (which) {
                        case 0: showFontSizeDialog(); break;
                        case 1: showFontDialog(); break;
                        case 2: showLineSpacingDialog(); break;
                        case 3: showMarginDialog(); break;
                        case 4: showThemeDialog(); break;
                        case 5: showBrightnessDialog(); break;
                        case 6:
                            keepScreenOn = !keepScreenOn;
                            saveReaderPreferences();
                            applyWindowPreferences();
                            showReaderSettings();
                            break;
                        case 7:
                            lockOrientation = !lockOrientation;
                            saveReaderPreferences();
                            applyWindowPreferences();
                            showReaderSettings();
                            break;
                        case 8:
                            volumeChapterKeys = !volumeChapterKeys;
                            saveReaderPreferences();
                            showReaderSettings();
                            break;
                        case 9:
                            resetReaderPreferences();
                            break;
                    }
                })
                .setNegativeButton("Close", null)
                .show();
    }

    private void showPdfSettings() {
        String[] options = new String[]{
                "Brightness · " + brightnessDisplayName(),
                "Keep screen on · " + onOff(keepScreenOn),
                "Lock orientation · " + onOff(lockOrientation)
        };

        new AlertDialog.Builder(this)
                .setTitle("Reader settings")
                .setItems(options, (d, which) -> {
                    if (which == 0) showBrightnessDialog();
                    else if (which == 1) {
                        keepScreenOn = !keepScreenOn;
                        saveReaderPreferences();
                        applyWindowPreferences();
                        showPdfSettings();
                    } else if (which == 2) {
                        lockOrientation = !lockOrientation;
                        saveReaderPreferences();
                        applyWindowPreferences();
                        showPdfSettings();
                    }
                })
                .setNegativeButton("Close", null)
                .show();
    }

    private void showFontSizeDialog() {
        final int[] values = {80, 90, 100, 110, 115, 125, 140, 160, 180, 200};
        String[] labels = new String[values.length];
        int selected = 0;
        for (int i = 0; i < values.length; i++) {
            labels[i] = values[i] + "%";
            if (values[i] == fontPercent) selected = i;
        }

        new AlertDialog.Builder(this)
                .setTitle("Font size")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    fontPercent = values[which];
                    saveReaderPreferences();
                    applyReaderStyle(true);
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void showFontDialog() {
        String[] fonts = {
                "Publisher font (EPUB original)",
                "Pyidaungsu",
                "A10 YoeShin",
                "Burma2"
        };
        String[] ids = {"publisher", "pyidaungsu", "yoeshin", "burma2"};

        int selected = 0;
        for (int i = 0; i < ids.length; i++)
            if (ids[i].equals(fontChoice)) selected = i;

        new AlertDialog.Builder(this)
                .setTitle("Font")
                .setSingleChoiceItems(fonts, selected, (dialog, which) -> {
                    fontChoice = ids[which];
                    saveReaderPreferences();
                    applyReaderStyle(true);
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void showLineSpacingDialog() {
        final int[] values = {135, 150, 165, 170, 185, 200};
        String[] labels = {"Compact · 1.35", "1.50", "1.65", "Comfortable · 1.70", "1.85", "Relaxed · 2.00"};

        int selected = 3;
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

    private void showMarginDialog() {
        final int[] values = {4, 6, 7, 9, 12};
        String[] labels = {"Narrow", "Medium", "Comfortable", "Wide", "Extra wide"};

        int selected = 2;
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

    private void showThemeDialog() {
        String[] labels = {"Light", "Sepia", "Dark"};

        new AlertDialog.Builder(this)
                .setTitle("Theme")
                .setSingleChoiceItems(labels, readerTheme, (dialog, which) -> {
                    readerTheme = which;
                    saveReaderPreferences();
                    applyReaderStyle(true);
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void showBrightnessDialog() {
        final int[] values = {-1, 40, 60, 80, 100};
        String[] labels = {"System", "40%", "60%", "80%", "100%"};

        int selected = 0;
        for (int i = 0; i < values.length; i++)
            if (values[i] == brightnessPercent) selected = i;

        new AlertDialog.Builder(this)
                .setTitle("Brightness")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    brightnessPercent = values[which];
                    saveReaderPreferences();
                    applyWindowPreferences();
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void resetReaderPreferences() {
        fontPercent = 115;
        fontChoice = "publisher";
        lineSpacing = 170;
        marginPercent = 7;
        readerTheme = 0;
        brightnessPercent = -1;
        keepScreenOn = false;
        lockOrientation = false;
        volumeChapterKeys = false;
        saveReaderPreferences();
        applyWindowPreferences();
        if (!isPdf) applyReaderStyle(true);
        Toast.makeText(this, "Reader settings reset", Toast.LENGTH_SHORT).show();
    }

    private void saveReaderPreferences() {
        prefs.edit()
                .putInt("epub_font", fontPercent)
                .putString("epub_font_choice", fontChoice)
                .putInt("epub_line_spacing", lineSpacing)
                .putInt("epub_margin", marginPercent)
                .putInt("reader_theme", readerTheme)
                .putInt("reader_brightness", brightnessPercent)
                .putBoolean("reader_keep_screen_on", keepScreenOn)
                .putBoolean("reader_lock_orientation", lockOrientation)
                .putBoolean("reader_volume_chapter", volumeChapterKeys)
                .putString("epub_reading_mode", "scroll")
                .apply();
    }

    private String fontDisplayName() {
        if ("pyidaungsu".equals(fontChoice)) return "Pyidaungsu";
        if ("yoeshin".equals(fontChoice)) return "A10 YoeShin";
        if ("burma2".equals(fontChoice)) return "Burma2";
        return "Publisher";
    }

    private String lineSpacingDisplay() {
        return String.format(Locale.US, "%.2f", lineSpacing / 100.0);
    }

    private String themeDisplayName() {
        if (readerTheme == 1) return "Sepia";
        if (readerTheme == 2) return "Dark";
        return "Light";
    }

    private String brightnessDisplayName() {
        return brightnessPercent < 0 ? "System" : brightnessPercent + "%";
    }

    private String onOff(boolean value) {
        return value ? "On" : "Off";
    }

    private void applyWindowPreferences() {
        if (keepScreenOn) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }

        WindowManager.LayoutParams lp = getWindow().getAttributes();
        lp.screenBrightness = brightnessPercent < 0 ? -1f : Math.max(0.05f, brightnessPercent / 100f);
        getWindow().setAttributes(lp);

        try {
            setRequestedOrientation(lockOrientation
                    ? ActivityInfo.SCREEN_ORIENTATION_LOCKED
                    : ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
        } catch (Exception ignored) {
        }

        enterImmersive();
    }

    private void previous() {
        if (isPdf) {
            if (currentPdfPage > 0) {
                currentPdfPage--;
                renderPdfPage();
            }
        } else {
            navigateChapter(-1, true);
        }
    }

    private void next() {
        if (isPdf) {
            if (pdfRenderer != null && currentPdfPage < pdfRenderer.getPageCount() - 1) {
                currentPdfPage++;
                renderPdfPage();
            }
        } else {
            navigateChapter(1, false);
        }
    }

    private void updateEpubProgress(int p) {
        currentProgressPermille = Math.max(0, Math.min(1000, p));
        if (spine.isEmpty()) return;

        double overall = (currentSpine + currentProgressPermille / 1000.0) / spine.size();
        int percent = Math.max(0, Math.min(100, (int) Math.round(overall * 100.0)));

        String chapter = currentSpine < chapterTitles.size()
                ? chapterTitles.get(currentSpine)
                : "Chapter " + (currentSpine + 1);

        positionView.setText(chapter + " · " + percent + "%");
        prefs.edit().putInt("percent_" + bookFile.getName(), percent).apply();
    }

    private void saveEpubStateOnly() {
        prefs.edit()
                .putInt("epub_chapter_" + bookFile.getName(), currentSpine)
                .putInt("epub_scroll_" + bookFile.getName(), currentProgressPermille)
                .apply();
    }

    private void saveEpubState() {
        saveEpubStateOnly();
        updateEpubProgress(currentProgressPermille);
    }

    private void searchInBook() {
        if (isPdf || webView == null) return;

        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("Word or phrase");
        input.setPadding(dp(20), dp(8), dp(20), dp(8));

        new AlertDialog.Builder(this)
                .setTitle("Find in chapter")
                .setView(input)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Find", (d, w) -> {
                    String q = input.getText().toString().trim();
                    if (!q.isEmpty()) {
                        webView.findAllAsync(q);
                        webView.showFindDialog(q, false);
                    }
                })
                .show();
    }

    private void toggleBookmark() {
        String key = "marks_" + bookFile.getName();
        int pos = isPdf ? currentPdfPage : currentSpine;
        String token = "," + pos + ",";
        String value = prefs.getString(key, ",");

        boolean marked = value.contains(token);
        value = marked ? value.replace(token, ",") : value + pos + ",";
        prefs.edit().putString(key, value).apply();

        updateBookmarkIcon();
        Toast.makeText(this,
                marked ? "Bookmark removed" : "Bookmarked",
                Toast.LENGTH_SHORT).show();
    }

    private void updateBookmarkIcon() {
        if (bookmarkButton == null) return;

        String value = prefs.getString("marks_" + bookFile.getName(), ",");
        int pos = isPdf ? currentPdfPage : currentSpine;
        bookmarkButton.setText(value.contains("," + pos + ",") ? "★" : "☆");
    }

    private void hideControls() {
        controlsVisible = false;
        if (topBar != null) topBar.setVisibility(View.GONE);
        if (bottomBar != null) bottomBar.setVisibility(View.GONE);
    }

    private void showControls() {
        controlsVisible = true;
        if (topBar != null) topBar.setVisibility(View.VISIBLE);
        if (bottomBar != null) bottomBar.setVisibility(View.VISIBLE);
        enterImmersive();
    }

    private void toggleControls() {
        if (controlsVisible) hideControls();
        else showControls();
        enterImmersive();
    }

    private void enterImmersive() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY |
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE |
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                View.SYSTEM_UI_FLAG_FULLSCREEN);
    }

    private void updateChromeTheme() {
        int bg;
        int fg;

        if (isPdf) {
            bg = Color.WHITE;
            fg = Color.rgb(32, 33, 36);
        } else {
            bg = readerTheme == 2
                    ? Color.rgb(18, 18, 18)
                    : readerTheme == 1
                    ? Color.rgb(244, 236, 216)
                    : Color.WHITE;
            fg = readerTheme == 2
                    ? Color.rgb(232, 234, 237)
                    : Color.rgb(32, 33, 36);
        }

        topBar.setBackgroundColor(bg);
        bottomBar.setBackgroundColor(bg);
        titleView.setTextColor(fg);
        positionView.setTextColor(fg);
        if (root != null) root.setBackgroundColor(bg);
    }

    private void openPdf() {
        try {
            pdfDescriptor = ParcelFileDescriptor.open(bookFile, ParcelFileDescriptor.MODE_READ_ONLY);
            pdfRenderer = new PdfRenderer(pdfDescriptor);

            if (pdfRenderer.getPageCount() == 0)
                throw new Exception("PDF has no pages");

            currentPdfPage = Math.max(0, Math.min(
                    prefs.getInt("pdf_page_" + bookFile.getName(), 0),
                    pdfRenderer.getPageCount() - 1));

            renderPdfPage();

        } catch (Exception e) {
            Toast.makeText(this, "PDF error: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void renderPdfPage() {
        if (pdfRenderer == null) return;

        try {
            if (pdfPage != null) pdfPage.close();
            pdfPage = pdfRenderer.openPage(currentPdfPage);

            int screenWidth = getResources().getDisplayMetrics().widthPixels;
            int targetWidth = Math.min(Math.max(screenWidth, 720), 1600);
            float scale = targetWidth / (float) pdfPage.getWidth();
            int targetHeight = Math.max(1, Math.round(pdfPage.getHeight() * scale));

            Bitmap bitmap = Bitmap.createBitmap(
                    targetWidth,
                    targetHeight,
                    Bitmap.Config.ARGB_8888);

            bitmap.eraseColor(Color.WHITE);

            Matrix matrix = new Matrix();
            matrix.postScale(scale, scale);

            pdfPage.render(
                    bitmap,
                    null,
                    matrix,
                    PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);

            pdfImage.setImageBitmap(bitmap);
            resetPdfZoom();

            int percent = (int) Math.round(
                    ((currentPdfPage + 1.0) / pdfRenderer.getPageCount()) * 100.0);

            positionView.setText(
                    "Page " + (currentPdfPage + 1) +
                    " / " + pdfRenderer.getPageCount() +
                    " · " + percent + "%");

            prefs.edit()
                    .putInt("pdf_page_" + bookFile.getName(), currentPdfPage)
                    .putInt("percent_" + bookFile.getName(), percent)
                    .apply();

            updateBookmarkIcon();

        } catch (Exception e) {
            Toast.makeText(this,
                    "Unable to render PDF page",
                    Toast.LENGTH_SHORT).show();
        }
    }

    private void resetPdfZoom() {
        pdfScale = 1f;
        if (pdfImage != null) {
            pdfImage.setScaleX(1f);
            pdfImage.setScaleY(1f);
            pdfImage.setTranslationX(0f);
            pdfImage.setTranslationY(0f);
            pdfImage.setPivotX(pdfImage.getWidth() / 2f);
            pdfImage.setPivotY(pdfImage.getHeight() / 2f);
        }
    }

    private void unzipEpub(File epub, File dest) throws Exception {
        String destPath = dest.getCanonicalPath() + File.separator;

        try (ZipInputStream zis = new ZipInputStream(new FileInputStream(epub))) {
            ZipEntry entry;
            byte[] buffer = new byte[64 * 1024];

            while ((entry = zis.getNextEntry()) != null) {
                File out = new File(dest, entry.getName());
                String outPath = out.getCanonicalPath();

                if (!outPath.startsWith(destPath))
                    throw new SecurityException("Unsafe EPUB path");

                if (entry.isDirectory()) {
                    out.mkdirs();
                } else {
                    File parent = out.getParentFile();
                    if (parent != null) parent.mkdirs();

                    try (FileOutputStream fos = new FileOutputStream(out)) {
                        int n;
                        while ((n = zis.read(buffer)) > 0)
                            fos.write(buffer, 0, n);
                    }
                }

                zis.closeEntry();
            }
        }
    }

    private void deleteRecursive(File f) {
        if (f == null || !f.exists()) return;

        if (f.isDirectory()) {
            File[] children = f.listFiles();
            if (children != null)
                for (File c : children)
                    deleteRecursive(c);
        }

        f.delete();
    }

    private class ReaderBridge {
        @JavascriptInterface
        public void onScroll(int p) {
            runOnUiThread(() -> {
                updateEpubProgress(p);
                saveEpubStateOnly();
            });
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (!isPdf && volumeChapterKeys) {
            if (keyCode == KeyEvent.KEYCODE_VOLUME_DOWN) {
                navigateChapter(1, false);
                return true;
            }
            if (keyCode == KeyEvent.KEYCODE_VOLUME_UP) {
                navigateChapter(-1, true);
                return true;
            }
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public void onBackPressed() {
        // Back gestures never leave a book accidentally. Use the visible ‹ button to exit.
        if (!controlsVisible) showControls();
        else hideControls();
        enterImmersive();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) enterImmersive();
    }

    @Override
    protected void onResume() {
        super.onResume();
        enterImmersive();
        applyWindowPreferences();
    }

    @Override
    protected void onPause() {
        if (!isPdf) saveEpubState();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            try { webView.removeJavascriptInterface("WoW"); } catch (Exception ignored) {}
            try { webView.stopLoading(); } catch (Exception ignored) {}
            try { webView.destroy(); } catch (Exception ignored) {}
        }

        try { if (pdfPage != null) pdfPage.close(); } catch (Exception ignored) {}
        try { if (pdfRenderer != null) pdfRenderer.close(); } catch (Exception ignored) {}
        try { if (pdfDescriptor != null) pdfDescriptor.close(); } catch (Exception ignored) {}

        super.onDestroy();
    }

    private String stripExtension(String name) {
        int dot = name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
