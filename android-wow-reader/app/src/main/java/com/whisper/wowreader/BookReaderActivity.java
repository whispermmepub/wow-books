package com.whisper.wowreader;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.view.GestureDetector;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import javax.xml.parsers.DocumentBuilderFactory;

public class BookReaderActivity extends Activity {
    private File bookFile;
    private SharedPreferences prefs;
    private boolean isPdf;

    private LinearLayout topBar;
    private LinearLayout bottomBar;
    private TextView titleView;
    private TextView positionView;
    private Button bookmarkButton;

    // EPUB
    private WebView webView;
    private final List<File> spine = new ArrayList<>();
    private int currentSpine = 0;
    private int currentScrollPermille = 0;
    private int readerTheme = 0; // 0 light, 1 sepia, 2 dark
    private int fontPercent = 115;

    // PDF
    private ParcelFileDescriptor pdfDescriptor;
    private PdfRenderer pdfRenderer;
    private PdfRenderer.Page pdfPage;
    private ImageView pdfImage;
    private int currentPdfPage = 0;
    private float pdfScale = 1f;
    private ScaleGestureDetector scaleDetector;
    private GestureDetector gestureDetector;
    private float lastTouchX;
    private float lastTouchY;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
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

        buildReaderUi();
        if (isPdf) openPdf(); else openEpub();
    }

    private void buildReaderUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setPadding(dp(6), dp(6), dp(6), dp(6));
        topBar.setBackgroundColor(Color.WHITE);

        Button back = button("‹");
        back.setTextSize(28);
        back.setOnClickListener(v -> finish());
        topBar.addView(back, new LinearLayout.LayoutParams(dp(48), dp(48)));

        titleView = new TextView(this);
        titleView.setText(stripExtension(bookFile.getName()));
        titleView.setTextSize(16);
        titleView.setTextColor(Color.rgb(45, 40, 52));
        titleView.setGravity(Gravity.CENTER_VERTICAL);
        titleView.setSingleLine(true);
        titleView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(0, dp(48), 1);
        titleLp.leftMargin = dp(4);
        topBar.addView(titleView, titleLp);

        Button search = button("⌕");
        search.setTextSize(22);
        search.setOnClickListener(v -> searchInBook());
        topBar.addView(search, new LinearLayout.LayoutParams(dp(48), dp(48)));
        if (isPdf) search.setVisibility(View.GONE);

        bookmarkButton = button("☆");
        bookmarkButton.setTextSize(22);
        bookmarkButton.setOnClickListener(v -> toggleBookmark());
        topBar.addView(bookmarkButton, new LinearLayout.LayoutParams(dp(48), dp(48)));

        Button appearance = button("Aa");
        appearance.setTextSize(14);
        appearance.setOnClickListener(v -> showAppearanceDialog());
        topBar.addView(appearance, new LinearLayout.LayoutParams(dp(52), dp(48)));
        if (isPdf) appearance.setVisibility(View.GONE);

        root.addView(topBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(60)));

        FrameLayout content = new FrameLayout(this);
        content.setId(View.generateViewId());
        root.addView(content, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        bottomBar = new LinearLayout(this);
        bottomBar.setOrientation(LinearLayout.HORIZONTAL);
        bottomBar.setGravity(Gravity.CENTER_VERTICAL);
        bottomBar.setPadding(dp(10), dp(5), dp(10), dp(5));
        bottomBar.setBackgroundColor(Color.WHITE);

        Button prev = button("‹ Prev");
        prev.setOnClickListener(v -> previous());
        bottomBar.addView(prev, new LinearLayout.LayoutParams(dp(92), dp(48)));

        positionView = new TextView(this);
        positionView.setText("—");
        positionView.setTextSize(13);
        positionView.setTextColor(Color.rgb(95, 88, 102));
        positionView.setGravity(Gravity.CENTER);
        bottomBar.addView(positionView, new LinearLayout.LayoutParams(0, dp(48), 1));

        Button next = button("Next ›");
        next.setOnClickListener(v -> next());
        bottomBar.addView(next, new LinearLayout.LayoutParams(dp(92), dp(48)));

        root.addView(bottomBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(60)));
        setContentView(root);

        if (isPdf) setupPdfView(content); else setupWebView(content);
        updateChromeTheme();
    }

    private Button button(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextColor(Color.rgb(80, 66, 112));
        b.setBackgroundColor(Color.TRANSPARENT);
        b.setPadding(0, 0, 0, 0);
        return b;
    }

    private void setupWebView(FrameLayout content) {
        webView = new WebView(this);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setDefaultTextEncodingName("UTF-8");
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        webView.setHorizontalScrollBarEnabled(false);
        webView.setVerticalScrollBarEnabled(false);
        webView.addJavascriptInterface(new ReaderBridge(), "WoW");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                applyReaderStyle(true);
            }
        });
        content.addView(webView, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private void setupPdfView(FrameLayout content) {
        pdfImage = new ImageView(this);
        pdfImage.setScaleType(ImageView.ScaleType.FIT_CENTER);
        pdfImage.setBackgroundColor(Color.rgb(54, 54, 58));
        content.addView(pdfImage, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        scaleDetector = new ScaleGestureDetector(this, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override
            public boolean onScale(ScaleGestureDetector detector) {
                pdfScale *= detector.getScaleFactor();
                pdfScale = Math.max(1f, Math.min(pdfScale, 4f));
                pdfImage.setScaleX(pdfScale);
                pdfImage.setScaleY(pdfScale);
                return true;
            }
        });
        gestureDetector = new GestureDetector(this, new GestureDetector.SimpleOnGestureListener() {
            @Override
            public boolean onDoubleTap(MotionEvent e) {
                if (pdfScale > 1.05f) resetPdfZoom();
                else {
                    pdfScale = 2f;
                    pdfImage.setPivotX(e.getX());
                    pdfImage.setPivotY(e.getY());
                    pdfImage.setScaleX(pdfScale);
                    pdfImage.setScaleY(pdfScale);
                }
                return true;
            }

            @Override
            public boolean onSingleTapConfirmed(MotionEvent e) {
                toggleControls();
                return true;
            }
        });
        pdfImage.setOnTouchListener((v, event) -> {
            scaleDetector.onTouchEvent(event);
            gestureDetector.onTouchEvent(event);
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                lastTouchX = event.getX();
                lastTouchY = event.getY();
            } else if (event.getActionMasked() == MotionEvent.ACTION_MOVE && pdfScale > 1.01f && !scaleDetector.isInProgress()) {
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
        new Thread(() -> {
            try {
                String id = Integer.toHexString(bookFile.getAbsolutePath().hashCode());
                File extractDir = new File(getFilesDir(), "epub_cache/" + id);
                if (!new File(extractDir, ".ready").exists()) {
                    deleteRecursive(extractDir);
                    if (!extractDir.mkdirs() && !extractDir.exists()) throw new Exception("Cannot prepare EPUB folder");
                    unzipEpub(bookFile, extractDir);
                    new File(extractDir, ".ready").createNewFile();
                }
                EpubInfo info = parseEpub(extractDir);
                runOnUiThread(() -> {
                    spine.clear();
                    spine.addAll(info.spine);
                    if (info.title != null && !info.title.trim().isEmpty()) titleView.setText(info.title);
                    if (spine.isEmpty()) {
                        Toast.makeText(this, "This EPUB has no readable spine", Toast.LENGTH_LONG).show();
                        return;
                    }
                    currentSpine = Math.max(0, Math.min(prefs.getInt("epub_chapter_" + bookFile.getName(), 0), spine.size() - 1));
                    currentScrollPermille = prefs.getInt("epub_scroll_" + bookFile.getName(), 0);
                    loadCurrentEpubChapter();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    Toast.makeText(this, "EPUB error: " + e.getMessage(), Toast.LENGTH_LONG).show();
                    positionView.setText("Unable to open EPUB");
                });
            }
        }).start();
    }

    private void loadCurrentEpubChapter() {
        if (spine.isEmpty()) return;
        File chapter = spine.get(currentSpine);
        webView.loadUrl(Uri.fromFile(chapter).toString());
        updateEpubProgress(currentScrollPermille);
        updateBookmarkIcon();
    }

    private void applyReaderStyle(boolean restoreScroll) {
        if (webView == null) return;
        String bg = readerTheme == 2 ? "#121212" : readerTheme == 1 ? "#F4ECD8" : "#FFFFFF";
        String fg = readerTheme == 2 ? "#E7E3EA" : "#26232A";
        String link = readerTheme == 2 ? "#B9A7E3" : "#5F4B8B";
        int scroll = restoreScroll ? currentScrollPermille : -1;
        String js = "(function(){" +
                "var s=document.getElementById('wow-reader-style');if(!s){s=document.createElement('style');s.id='wow-reader-style';document.head.appendChild(s);}" +
                "s.innerHTML='html,body{background:" + bg + " !important;color:" + fg + " !important;} body{font-size:" + fontPercent + "% !important;line-height:1.75 !important;padding:4vh 7vw 12vh 7vw !important;max-width:900px !important;margin:auto !important;box-sizing:border-box !important;} p{line-height:1.75 !important;} img,svg{max-width:100% !important;height:auto !important;} a{color:" + link + " !important;}';" +
                "if(!window.__wowBound){window.__wowBound=true;var t=0;window.addEventListener('scroll',function(){clearTimeout(t);t=setTimeout(function(){var h=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);WoW.onScroll(Math.round((window.scrollY/h)*1000));},120);});document.addEventListener('click',function(e){var x=e.clientX/window.innerWidth;if(x<0.22){WoW.prev();}else if(x>0.78){WoW.next();}else{WoW.toggle();}});}" +
                (scroll >= 0 ? "setTimeout(function(){var h=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);window.scrollTo(0,h*" + (scroll / 1000.0) + ");},250);" : "") +
                "})();";
        webView.evaluateJavascript(js, null);
        updateChromeTheme();
    }

    private void previous() {
        if (isPdf) {
            if (currentPdfPage > 0) {
                currentPdfPage--;
                renderPdfPage();
            }
        } else if (currentSpine > 0) {
            currentSpine--;
            currentScrollPermille = 0;
            saveEpubState();
            loadCurrentEpubChapter();
        }
    }

    private void next() {
        if (isPdf) {
            if (pdfRenderer != null && currentPdfPage < pdfRenderer.getPageCount() - 1) {
                currentPdfPage++;
                renderPdfPage();
            }
        } else if (currentSpine < spine.size() - 1) {
            currentSpine++;
            currentScrollPermille = 0;
            saveEpubState();
            loadCurrentEpubChapter();
        }
    }

    private void updateEpubProgress(int scrollPermille) {
        currentScrollPermille = Math.max(0, Math.min(1000, scrollPermille));
        if (spine.isEmpty()) return;
        double overall = (currentSpine + currentScrollPermille / 1000.0) / spine.size();
        int percent = (int) Math.round(overall * 100.0);
        positionView.setText("Chapter " + (currentSpine + 1) + " / " + spine.size() + "   •   " + percent + "%");
        prefs.edit().putInt("percent_" + bookFile.getName(), percent).apply();
    }

    private void saveEpubState() {
        prefs.edit()
                .putInt("epub_chapter_" + bookFile.getName(), currentSpine)
                .putInt("epub_scroll_" + bookFile.getName(), currentScrollPermille)
                .apply();
        updateEpubProgress(currentScrollPermille);
    }

    private void openPdf() {
        try {
            pdfDescriptor = ParcelFileDescriptor.open(bookFile, ParcelFileDescriptor.MODE_READ_ONLY);
            pdfRenderer = new PdfRenderer(pdfDescriptor);
            if (pdfRenderer.getPageCount() == 0) throw new Exception("PDF has no pages");
            currentPdfPage = Math.max(0, Math.min(prefs.getInt("pdf_page_" + bookFile.getName(), 0), pdfRenderer.getPageCount() - 1));
            renderPdfPage();
        } catch (Exception e) {
            Toast.makeText(this, "PDF error: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void renderPdfPage() {
        if (pdfRenderer == null) return;
        if (pdfPage != null) pdfPage.close();
        pdfPage = pdfRenderer.openPage(currentPdfPage);
        int screenWidth = getResources().getDisplayMetrics().widthPixels;
        int targetWidth = Math.min(Math.max(screenWidth, 720), 1600);
        float scale = targetWidth / (float) pdfPage.getWidth();
        int targetHeight = Math.max(1, Math.round(pdfPage.getHeight() * scale));
        Bitmap bitmap = Bitmap.createBitmap(targetWidth, targetHeight, Bitmap.Config.ARGB_8888);
        bitmap.eraseColor(Color.WHITE);
        Matrix matrix = new Matrix();
        matrix.postScale(scale, scale);
        pdfPage.render(bitmap, null, matrix, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
        pdfImage.setImageBitmap(bitmap);
        resetPdfZoom();

        int percent = (int) Math.round(((currentPdfPage + 1.0) / pdfRenderer.getPageCount()) * 100.0);
        positionView.setText("Page " + (currentPdfPage + 1) + " / " + pdfRenderer.getPageCount() + "   •   " + percent + "%");
        prefs.edit()
                .putInt("pdf_page_" + bookFile.getName(), currentPdfPage)
                .putInt("percent_" + bookFile.getName(), percent)
                .apply();
        updateBookmarkIcon();
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

    private void showAppearanceDialog() {
        String[] options = new String[]{"Smaller text", "Larger text", "Light theme", "Sepia theme", "Dark theme"};
        new AlertDialog.Builder(this)
                .setTitle("Reading appearance")
                .setItems(options, (d, which) -> {
                    if (which == 0) fontPercent = Math.max(80, fontPercent - 10);
                    if (which == 1) fontPercent = Math.min(190, fontPercent + 10);
                    if (which >= 2) readerTheme = which - 2;
                    prefs.edit().putInt("epub_font", fontPercent).putInt("reader_theme", readerTheme).apply();
                    applyReaderStyle(false);
                }).show();
    }

    private void searchInBook() {
        if (isPdf || webView == null) return;
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("Word or phrase");
        int pad = dp(20);
        input.setPadding(pad, pad / 2, pad, pad / 2);
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
                }).show();
    }

    private void toggleBookmark() {
        String key = "marks_" + bookFile.getName();
        int pos = isPdf ? currentPdfPage : currentSpine;
        String token = "," + pos + ",";
        String value = prefs.getString(key, ",");
        boolean marked = value.contains(token);
        if (marked) value = value.replace(token, ",");
        else value = value + pos + ",";
        prefs.edit().putString(key, value).apply();
        updateBookmarkIcon();
        Toast.makeText(this, marked ? "Bookmark removed" : "Bookmarked", Toast.LENGTH_SHORT).show();
    }

    private void updateBookmarkIcon() {
        if (bookmarkButton == null) return;
        String key = "marks_" + bookFile.getName();
        int pos = isPdf ? currentPdfPage : currentSpine;
        String value = prefs.getString(key, ",");
        bookmarkButton.setText(value.contains("," + pos + ",") ? "★" : "☆");
    }

    private void toggleControls() {
        boolean show = topBar.getVisibility() != View.VISIBLE;
        topBar.setVisibility(show ? View.VISIBLE : View.GONE);
        bottomBar.setVisibility(show ? View.VISIBLE : View.GONE);
    }

    private void updateChromeTheme() {
        if (isPdf) return;
        int bg = readerTheme == 2 ? Color.rgb(18, 18, 18) : readerTheme == 1 ? Color.rgb(244, 236, 216) : Color.WHITE;
        int fg = readerTheme == 2 ? Color.rgb(232, 228, 235) : Color.rgb(45, 40, 52);
        topBar.setBackgroundColor(bg);
        bottomBar.setBackgroundColor(bg);
        titleView.setTextColor(fg);
        positionView.setTextColor(fg);
        getWindow().setStatusBarColor(bg);
        getWindow().setNavigationBarColor(bg);
        if (readerTheme == 2) getWindow().getDecorView().setSystemUiVisibility(0);
        else getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
    }

    private EpubInfo parseEpub(File root) throws Exception {
        File container = new File(root, "META-INF/container.xml");
        Document cdoc = parseXml(container);
        NodeList roots = cdoc.getElementsByTagNameNS("*", "rootfile");
        if (roots.getLength() == 0) roots = cdoc.getElementsByTagName("rootfile");
        if (roots.getLength() == 0) throw new Exception("container.xml has no rootfile");
        String opfPath = ((Element) roots.item(0)).getAttribute("full-path");
        File opf = new File(root, opfPath);
        Document doc = parseXml(opf);

        String title = firstText(doc, "title");
        Map<String, String> manifest = new HashMap<>();
        NodeList items = doc.getElementsByTagNameNS("*", "item");
        if (items.getLength() == 0) items = doc.getElementsByTagName("item");
        for (int i = 0; i < items.getLength(); i++) {
            Element e = (Element) items.item(i);
            manifest.put(e.getAttribute("id"), e.getAttribute("href"));
        }

        List<File> chapters = new ArrayList<>();
        NodeList refs = doc.getElementsByTagNameNS("*", "itemref");
        if (refs.getLength() == 0) refs = doc.getElementsByTagName("itemref");
        File opfDir = opf.getParentFile();
        for (int i = 0; i < refs.getLength(); i++) {
            Element e = (Element) refs.item(i);
            String href = manifest.get(e.getAttribute("idref"));
            if (href == null || href.isEmpty()) continue;
            href = href.split("#", 2)[0];
            try { href = URLDecoder.decode(href, StandardCharsets.UTF_8.name()); } catch (Exception ignored) {}
            File chapter = new File(opfDir, href);
            if (chapter.isFile()) chapters.add(chapter);
        }
        return new EpubInfo(title, chapters);
    }

    private Document parseXml(File file) throws Exception {
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setNamespaceAware(true);
        try { f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true); } catch (Exception ignored) {}
        try { f.setFeature("http://xml.org/sax/features/external-general-entities", false); } catch (Exception ignored) {}
        try { f.setFeature("http://xml.org/sax/features/external-parameter-entities", false); } catch (Exception ignored) {}
        try (InputStream in = new FileInputStream(file)) {
            return f.newDocumentBuilder().parse(in);
        }
    }

    private String firstText(Document doc, String localName) {
        NodeList list = doc.getElementsByTagNameNS("*", localName);
        if (list.getLength() == 0) list = doc.getElementsByTagName(localName);
        if (list.getLength() == 0) return null;
        return list.item(0).getTextContent();
    }

    private void unzipEpub(File epub, File dest) throws Exception {
        String destPath = dest.getCanonicalPath() + File.separator;
        try (ZipInputStream zis = new ZipInputStream(new FileInputStream(epub))) {
            ZipEntry entry;
            byte[] buffer = new byte[64 * 1024];
            while ((entry = zis.getNextEntry()) != null) {
                File out = new File(dest, entry.getName());
                String outPath = out.getCanonicalPath();
                if (!outPath.startsWith(destPath)) throw new SecurityException("Unsafe EPUB path");
                if (entry.isDirectory()) {
                    out.mkdirs();
                } else {
                    File parent = out.getParentFile();
                    if (parent != null) parent.mkdirs();
                    try (FileOutputStream fos = new FileOutputStream(out)) {
                        int n;
                        while ((n = zis.read(buffer)) > 0) fos.write(buffer, 0, n);
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
            if (children != null) for (File c : children) deleteRecursive(c);
        }
        f.delete();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (!isPdf) saveEpubState();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
        }
        if (pdfPage != null) pdfPage.close();
        if (pdfRenderer != null) pdfRenderer.close();
        if (pdfDescriptor != null) {
            try { pdfDescriptor.close(); } catch (Exception ignored) {}
        }
        super.onDestroy();
    }

    private String stripExtension(String name) {
        int dot = name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private class ReaderBridge {
        @JavascriptInterface
        public void onScroll(int permille) {
            runOnUiThread(() -> {
                updateEpubProgress(permille);
                prefs.edit()
                        .putInt("epub_chapter_" + bookFile.getName(), currentSpine)
                        .putInt("epub_scroll_" + bookFile.getName(), currentScrollPermille)
                        .apply();
            });
        }

        @JavascriptInterface
        public void prev() { runOnUiThread(BookReaderActivity.this::previous); }

        @JavascriptInterface
        public void next() { runOnUiThread(BookReaderActivity.this::next); }

        @JavascriptInterface
        public void toggle() { runOnUiThread(BookReaderActivity.this::toggleControls); }
    }

    private static class EpubInfo {
        final String title;
        final List<File> spine;
        EpubInfo(String title, List<File> spine) {
            this.title = title;
            this.spine = spine;
        }
    }
}
