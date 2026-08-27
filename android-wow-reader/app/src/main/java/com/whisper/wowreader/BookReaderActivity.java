package com.whisper.wowreader;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.drawable.GradientDrawable;
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

    private LinearLayout topBar;
    private LinearLayout bottomBar;
    private TextView titleView;
    private TextView positionView;
    private TextView bookmarkButton;
    private TextView contentsButton;

    private WebView webView;
    private final List<File> spine = new ArrayList<>();
    private final List<String> chapterTitles = new ArrayList<>();
    private int currentSpine = 0;
    private int currentScrollPermille = 0;
    private int readerTheme = 0;
    private int fontPercent = 115;
    private String fontChoice = "publisher";
    private String readingMode = "scroll";
    private int currentPageInChapter = 1;
    private int pageCountInChapter = 1;
    private long backArmedUntil = 0L;

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

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String path = getIntent().getStringExtra("path");
        if (path == null) { finish(); return; }
        bookFile = new File(path);
        prefs = getSharedPreferences("wow_reader", MODE_PRIVATE);
        isPdf = bookFile.getName().toLowerCase(Locale.ROOT).endsWith(".pdf");
        readerTheme = prefs.getInt("reader_theme", 0);
        fontPercent = prefs.getInt("epub_font", 115);
        fontChoice = prefs.getString("epub_font_choice", "publisher");
        readingMode = prefs.getString("epub_reading_mode", "scroll");
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
        topBar.setPadding(dp(4), dp(5), dp(4), dp(5));

        TextView back = iconButton("‹", 30);
        back.setOnClickListener(v -> finish());
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
        contentsButton.setOnClickListener(v -> showContents());
        topBar.addView(contentsButton, new LinearLayout.LayoutParams(dp(46), dp(50)));

        TextView search = iconButton("⌕", 22);
        search.setContentDescription("Search chapter");
        search.setOnClickListener(v -> searchInBook());
        topBar.addView(search, new LinearLayout.LayoutParams(dp(46), dp(50)));

        bookmarkButton = iconButton("☆", 23);
        bookmarkButton.setContentDescription("Bookmark");
        bookmarkButton.setOnClickListener(v -> toggleBookmark());
        topBar.addView(bookmarkButton, new LinearLayout.LayoutParams(dp(46), dp(50)));

        TextView appearance = iconButton("Aa", 15);
        appearance.setContentDescription("Reading appearance");
        appearance.setOnClickListener(v -> showAppearanceDialog());
        topBar.addView(appearance, new LinearLayout.LayoutParams(dp(48), dp(50)));

        root.addView(topBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(60)));

        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        bottomBar = new LinearLayout(this);
        bottomBar.setOrientation(LinearLayout.HORIZONTAL);
        bottomBar.setGravity(Gravity.CENTER_VERTICAL);
        bottomBar.setPadding(dp(8), dp(4), dp(8), dp(4));

        TextView prev = textButton("‹");
        prev.setTextSize(28);
        prev.setOnClickListener(v -> previous());
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
        next.setOnClickListener(v -> next());
        bottomBar.addView(next, new LinearLayout.LayoutParams(dp(56), dp(50)));
        root.addView(bottomBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(58)));

        setContentView(root);
        if (isPdf) {
            contentsButton.setVisibility(View.GONE);
            search.setVisibility(View.GONE);
            appearance.setVisibility(View.GONE);
            setupPdfView(content);
        } else setupWebView(content);
        updateChromeTheme();
    }

    private TextView iconButton(String text, int size) {
        TextView v = new TextView(this);
        v.setText(text); v.setTextSize(size); v.setTextColor(Color.rgb(60,64,67)); v.setGravity(Gravity.CENTER); v.setClickable(true); v.setBackgroundColor(Color.TRANSPARENT); return v;
    }

    private TextView textButton(String text) { return iconButton(text, 18); }

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
        webView.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view, String url) { super.onPageFinished(view, url); applyReaderStyle(true); }
        });
        content.addView(webView, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private void setupPdfView(FrameLayout content) {
        pdfImage = new ImageView(this);
        pdfImage.setScaleType(ImageView.ScaleType.FIT_CENTER);
        pdfImage.setBackgroundColor(Color.rgb(48,49,52));
        content.addView(pdfImage, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        scaleDetector = new ScaleGestureDetector(this, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector detector) {
                pdfScale *= detector.getScaleFactor(); pdfScale = Math.max(1f, Math.min(pdfScale, 4f)); pdfImage.setScaleX(pdfScale); pdfImage.setScaleY(pdfScale); return true;
            }
        });
        gestureDetector = new GestureDetector(this, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDoubleTap(MotionEvent e) {
                if (pdfScale > 1.05f) resetPdfZoom(); else { pdfScale=2f; pdfImage.setPivotX(e.getX()); pdfImage.setPivotY(e.getY()); pdfImage.setScaleX(pdfScale); pdfImage.setScaleY(pdfScale); } return true;
            }
            @Override public boolean onSingleTapConfirmed(MotionEvent e) { toggleControls(); return true; }
        });
        pdfImage.setOnTouchListener((v,event)->{
            scaleDetector.onTouchEvent(event); gestureDetector.onTouchEvent(event);
            if(event.getActionMasked()==MotionEvent.ACTION_DOWN){lastTouchX=event.getX();lastTouchY=event.getY();}
            else if(event.getActionMasked()==MotionEvent.ACTION_MOVE&&pdfScale>1.01f&&!scaleDetector.isInProgress()){float dx=event.getX()-lastTouchX,dy=event.getY()-lastTouchY;pdfImage.setTranslationX(pdfImage.getTranslationX()+dx);pdfImage.setTranslationY(pdfImage.getTranslationY()+dy);lastTouchX=event.getX();lastTouchY=event.getY();}
            return true;
        });
    }

    private void openEpub() {
        new Thread(() -> {
            try {
                String id = Integer.toHexString((bookFile.getAbsolutePath()+":"+bookFile.lastModified()+":"+bookFile.length()).hashCode());
                File extractDir = new File(getFilesDir(), "epub_cache/"+id);
                if (!new File(extractDir,".ready").exists()) {
                    deleteRecursive(extractDir);
                    if (!extractDir.mkdirs() && !extractDir.exists()) throw new Exception("Cannot prepare EPUB folder");
                    unzipEpub(bookFile,extractDir);
                    new File(extractDir,".ready").createNewFile();
                }
                EpubUtil.BookInfo info = EpubUtil.parseExtracted(extractDir);
                runOnUiThread(() -> {
                    spine.clear(); spine.addAll(info.spine);
                    chapterTitles.clear(); chapterTitles.addAll(info.chapterTitles);
                    if(info.title!=null&&!info.title.isEmpty()) titleView.setText(info.title);
                    if(spine.isEmpty()){Toast.makeText(this,"This EPUB has no readable chapters",Toast.LENGTH_LONG).show();return;}
                    currentSpine=Math.max(0,Math.min(prefs.getInt("epub_chapter_"+bookFile.getName(),0),spine.size()-1));
                    currentScrollPermille=prefs.getInt("epub_scroll_"+bookFile.getName(),0);
                    loadCurrentEpubChapter();
                });
            } catch(Exception e) {
                runOnUiThread(() -> {Toast.makeText(this,"EPUB error: "+e.getMessage(),Toast.LENGTH_LONG).show();positionView.setText("Unable to open EPUB");});
            }
        }).start();
    }

    private void loadCurrentEpubChapter(){if(spine.isEmpty())return;webView.loadUrl(Uri.fromFile(spine.get(currentSpine)).toString());updateEpubProgress(currentScrollPermille);updateBookmarkIcon();}

    private void showContents(){if(isPdf||spine.isEmpty())return;String[] items=new String[spine.size()];for(int i=0;i<items.length;i++){String name=i<chapterTitles.size()?chapterTitles.get(i):"Chapter "+(i+1);items[i]=(i==currentSpine?"●  ":"     ")+name;}new AlertDialog.Builder(this).setTitle("Table of contents").setSingleChoiceItems(items,currentSpine,(dialog,which)->{currentSpine=which;currentScrollPermille=0;currentPageInChapter=1;pageCountInChapter=1;saveEpubState();loadCurrentEpubChapter();dialog.dismiss();}).setNegativeButton("Close",null).show();}

    private void applyReaderStyle(boolean restoreScroll) {
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
            modeCss =
                    "html{height:100% !important;width:100% !important;margin:0 !important;padding:0 !important;overflow:hidden !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:1.72 !important;height:100vh !important;width:auto !important;max-width:none !important;" +
                    "margin:0 !important;padding:4vh 7vw 6vh 7vw !important;box-sizing:border-box !important;overflow:visible !important;" +
                    "column-width:86vw !important;column-gap:14vw !important;column-fill:auto !important;}" +
                    "img,svg{max-height:78vh !important;}";
        } else {
            modeCss =
                    "html{overflow-x:hidden !important;}" +
                    "body{font-size:" + fontPercent + "% !important;line-height:1.72 !important;padding:3.5vh 7vw 12vh 7vw !important;" +
                    "max-width:900px !important;margin:auto !important;box-sizing:border-box !important;}";
        }
        String css = baseCss + modeCss;
        String mode = paged ? "page" : "scroll";

        String js = "(function(){" +
                "window.__wowMode='" + mode + "';" +
                "var s=document.getElementById('wow-reader-style');if(!s){s=document.createElement('style');s.id='wow-reader-style';document.head.appendChild(s);}s.innerHTML=" + jsQuote(css) + ";" +
                "window.__wowMetrics=function(report){var w=Math.max(1,window.innerWidth);var sw=Math.max(document.documentElement.scrollWidth,document.body?document.body.scrollWidth:0);var count=Math.max(1,Math.round(Math.max(0,sw-w)/w)+1);var page=Math.max(0,Math.min(count-1,Math.round(window.scrollX/w)));var perm=count<=1?0:Math.round((page/(count-1))*1000);if(report&&window.__wowMode==='page')WoW.onPage(page+1,count,perm);return {w:w,count:count,page:page,perm:perm};};" +
                "window.__wowTurn=function(delta){if(window.__wowMode!=='page')return;var m=window.__wowMetrics(false);if(delta<0&&m.page<=0){WoW.prevChapter();return;}if(delta>0&&m.page>=m.count-1){WoW.nextChapter();return;}var target=Math.max(0,Math.min(m.count-1,m.page+delta));window.scrollTo({left:target*m.w,top:0,behavior:'smooth'});setTimeout(function(){window.__wowMetrics(true);},260);};" +
                "if(!window.__wowBound){window.__wowBound=true;var t=0;var sx=0,sy=0,st=0,suppress=0;" +
                "window.addEventListener('scroll',function(){clearTimeout(t);t=setTimeout(function(){if(window.__wowMode==='scroll'){var h=Math.max(1,document.documentElement.scrollHeight-window.innerHeight);WoW.onScroll(Math.round((window.scrollY/h)*1000));}},100);},{passive:true});" +
                "document.addEventListener('touchstart',function(e){if(e.touches&&e.touches.length===1){sx=e.touches[0].clientX;sy=e.touches[0].clientY;st=Date.now();}},{passive:true});" +
                "document.addEventListener('touchend',function(e){if(window.__wowMode!=='page'||!e.changedTouches||!e.changedTouches.length)return;var dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;if(Math.abs(dx)>48&&Math.abs(dx)>Math.abs(dy)*1.2&&Date.now()-st<900){suppress=Date.now()+350;window.__wowTurn(dx>0?-1:1);}},{passive:true});" +
                "document.addEventListener('click',function(e){if(Date.now()<suppress)return;var node=e.target;while(node&&node!==document){if(node.tagName&&node.tagName.toLowerCase()==='a')return;node=node.parentNode;}if(window.__wowMode==='page'){var x=e.clientX/window.innerWidth;if(x<0.32)window.__wowTurn(-1);else if(x>0.68)window.__wowTurn(1);else WoW.toggle();}else{WoW.toggle();}});" +
                "}" +
                "setTimeout(function(){if(window.__wowMode==='page'){var m=window.__wowMetrics(false);var p=" + (restore >= 0 ? (restore / 1000.0) : 0.0) + ";var target=Math.max(0,Math.min(m.count-1,Math.round((m.count-1)*p)));window.scrollTo(target*m.w,0);setTimeout(function(){window.__wowMetrics(true);},80);}else{" +
                (restore >= 0 ? "var h=Math.max(0,document.documentElement.scrollHeight-window.innerHeight);window.scrollTo(0,h*" + (restore / 1000.0) + ");" : "") +
                "}},120);" +
                "})();";
        webView.evaluateJavascript(js, null);
        updateChromeTheme();
    }

    private String jsQuote(String s) { return "'"+s.replace("\\","\\\\").replace("'","\\'").replace("\n"," ")+"'"; }

    private void showAppearanceDialog() {
        String[] options = new String[]{
                "Reading mode · " + readingModeDisplayName(),
                "Text smaller",
                "Text larger",
                "Font · " + fontDisplayName(),
                "Light theme",
                "Sepia theme",
                "Dark theme",
                "Reset reading style"
        };
        new AlertDialog.Builder(this).setTitle("Reading appearance").setItems(options,(d,which)->{
            if (which == 0) { showReadingModeDialog(); return; }
            if (which == 1) fontPercent = Math.max(80, fontPercent - 10);
            else if (which == 2) fontPercent = Math.min(200, fontPercent + 10);
            else if (which == 3) { showFontDialog(); return; }
            else if (which >= 4 && which <= 6) readerTheme = which - 4;
            else if (which == 7) { fontPercent = 115; readerTheme = 0; fontChoice = "publisher"; readingMode = "scroll"; }
            saveAppearance();
            applyReaderStyle(false);
        }).show();
    }

    private void showReadingModeDialog() {
        String[] labels = new String[]{"Page by page", "Vertical scroll"};
        int selected = "page".equals(readingMode) ? 0 : 1;
        new AlertDialog.Builder(this)
                .setTitle("Reading mode")
                .setSingleChoiceItems(labels, selected, (dialog, which) -> {
                    readingMode = which == 0 ? "page" : "scroll";
                    currentPageInChapter = 1;
                    pageCountInChapter = 1;
                    saveAppearance();
                    applyReaderStyle(true);
                    dialog.dismiss();
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void showFontDialog() {
        String[] fonts = new String[]{"Publisher font (EPUB original)", "Pyidaungsu", "A10 YoeShin", "Burma2"};
        String[] ids = new String[]{"publisher","pyidaungsu","yoeshin","burma2"};
        int selected=0; for(int i=0;i<ids.length;i++) if(ids[i].equals(fontChoice)) selected=i;
        new AlertDialog.Builder(this).setTitle("Font").setSingleChoiceItems(fonts,selected,(dialog,which)->{fontChoice=ids[which];saveAppearance();applyReaderStyle(false);dialog.dismiss();}).setNegativeButton("Cancel",null).show();
    }

    private void saveAppearance(){prefs.edit().putInt("epub_font",fontPercent).putInt("reader_theme",readerTheme).putString("epub_font_choice",fontChoice).putString("epub_reading_mode",readingMode).apply();}
    private String fontDisplayName(){if("pyidaungsu".equals(fontChoice))return "Pyidaungsu";if("yoeshin".equals(fontChoice))return "A10 YoeShin";if("burma2".equals(fontChoice))return "Burma2";return "Publisher";}
    private String readingModeDisplayName(){return "page".equals(readingMode)?"Pages":"Scroll";}

    private void previous(){
        if(isPdf){if(currentPdfPage>0){currentPdfPage--;renderPdfPage();}return;}
        if("page".equals(readingMode)){if(webView!=null)webView.evaluateJavascript("window.__wowTurn&&window.__wowTurn(-1);",null);return;}
        previousChapter(false);
    }

    private void next(){
        if(isPdf){if(pdfRenderer!=null&&currentPdfPage<pdfRenderer.getPageCount()-1){currentPdfPage++;renderPdfPage();}return;}
        if("page".equals(readingMode)){if(webView!=null)webView.evaluateJavascript("window.__wowTurn&&window.__wowTurn(1);",null);return;}
        nextChapter();
    }

    private void previousChapter(boolean restoreEnd){
        if(currentSpine<=0)return;
        currentSpine--;
        currentScrollPermille=restoreEnd?1000:0;
        currentPageInChapter=1;pageCountInChapter=1;
        saveEpubState();
        loadCurrentEpubChapter();
    }

    private void nextChapter(){
        if(currentSpine>=spine.size()-1)return;
        currentSpine++;
        currentScrollPermille=0;
        currentPageInChapter=1;pageCountInChapter=1;
        saveEpubState();
        loadCurrentEpubChapter();
    }

    private void updateEpubProgress(int scrollPermille){
        currentScrollPermille=Math.max(0,Math.min(1000,scrollPermille));
        if(spine.isEmpty())return;
        double overall=(currentSpine+currentScrollPermille/1000.0)/spine.size();
        int percent=(int)Math.round(overall*100.0);
        if("page".equals(readingMode)&&pageCountInChapter>0) positionView.setText("Page "+currentPageInChapter+" / "+pageCountInChapter+" · "+percent+"%");
        else {String chapter=currentSpine<chapterTitles.size()?chapterTitles.get(currentSpine):"Chapter "+(currentSpine+1);positionView.setText(chapter+" · "+percent+"%");}
        prefs.edit().putInt("percent_"+bookFile.getName(),percent).apply();
    }

    private void updateEpubPageProgress(int page,int count,int permille){
        currentPageInChapter=Math.max(1,page);
        pageCountInChapter=Math.max(1,count);
        updateEpubProgress(permille);
        prefs.edit().putInt("epub_scroll_"+bookFile.getName(),currentScrollPermille).putInt("epub_chapter_"+bookFile.getName(),currentSpine).apply();
    }

    private void saveEpubState(){prefs.edit().putInt("epub_chapter_"+bookFile.getName(),currentSpine).putInt("epub_scroll_"+bookFile.getName(),currentScrollPermille).apply();updateEpubProgress(currentScrollPermille);}

    private void searchInBook(){if(isPdf||webView==null)return;EditText input=new EditText(this);input.setSingleLine(true);input.setHint("Word or phrase");input.setPadding(dp(20),dp(8),dp(20),dp(8));new AlertDialog.Builder(this).setTitle("Find in chapter").setView(input).setNegativeButton("Cancel",null).setPositiveButton("Find",(d,w)->{String q=input.getText().toString().trim();if(!q.isEmpty()){webView.findAllAsync(q);webView.showFindDialog(q,false);}}).show();}

    private void toggleBookmark(){String key="marks_"+bookFile.getName();int pos=isPdf?currentPdfPage:currentSpine;String token=","+pos+",";String value=prefs.getString(key,",");boolean marked=value.contains(token);value=marked?value.replace(token,","):value+pos+",";prefs.edit().putString(key,value).apply();updateBookmarkIcon();Toast.makeText(this,marked?"Bookmark removed":"Bookmarked",Toast.LENGTH_SHORT).show();}
    private void updateBookmarkIcon(){if(bookmarkButton==null)return;String value=prefs.getString("marks_"+bookFile.getName(),",");int pos=isPdf?currentPdfPage:currentSpine;bookmarkButton.setText(value.contains(","+pos+",")?"★":"☆");}
    private void toggleControls(){boolean show=topBar.getVisibility()!=View.VISIBLE;topBar.setVisibility(show?View.VISIBLE:View.INVISIBLE);bottomBar.setVisibility(show?View.VISIBLE:View.INVISIBLE);}

    private void updateChromeTheme(){if(isPdf){topBar.setBackgroundColor(Color.WHITE);bottomBar.setBackgroundColor(Color.WHITE);getWindow().setStatusBarColor(Color.WHITE);return;}int bg=readerTheme==2?Color.rgb(18,18,18):readerTheme==1?Color.rgb(244,236,216):Color.WHITE;int fg=readerTheme==2?Color.rgb(232,234,237):Color.rgb(32,33,36);topBar.setBackgroundColor(bg);bottomBar.setBackgroundColor(bg);titleView.setTextColor(fg);positionView.setTextColor(fg);getWindow().setStatusBarColor(bg);getWindow().setNavigationBarColor(bg);if(readerTheme==2)getWindow().getDecorView().setSystemUiVisibility(0);else getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);}

    private void openPdf(){try{pdfDescriptor=ParcelFileDescriptor.open(bookFile,ParcelFileDescriptor.MODE_READ_ONLY);pdfRenderer=new PdfRenderer(pdfDescriptor);if(pdfRenderer.getPageCount()==0)throw new Exception("PDF has no pages");currentPdfPage=Math.max(0,Math.min(prefs.getInt("pdf_page_"+bookFile.getName(),0),pdfRenderer.getPageCount()-1));renderPdfPage();}catch(Exception e){Toast.makeText(this,"PDF error: "+e.getMessage(),Toast.LENGTH_LONG).show();}}
    private void renderPdfPage(){if(pdfRenderer==null)return;if(pdfPage!=null)pdfPage.close();pdfPage=pdfRenderer.openPage(currentPdfPage);int screenWidth=getResources().getDisplayMetrics().widthPixels,targetWidth=Math.min(Math.max(screenWidth,720),1600);float scale=targetWidth/(float)pdfPage.getWidth();int targetHeight=Math.max(1,Math.round(pdfPage.getHeight()*scale));Bitmap bitmap=Bitmap.createBitmap(targetWidth,targetHeight,Bitmap.Config.ARGB_8888);bitmap.eraseColor(Color.WHITE);Matrix matrix=new Matrix();matrix.postScale(scale,scale);pdfPage.render(bitmap,null,matrix,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);pdfImage.setImageBitmap(bitmap);resetPdfZoom();int percent=(int)Math.round(((currentPdfPage+1.0)/pdfRenderer.getPageCount())*100.0);positionView.setText("Page "+(currentPdfPage+1)+" / "+pdfRenderer.getPageCount()+" · "+percent+"%");prefs.edit().putInt("pdf_page_"+bookFile.getName(),currentPdfPage).putInt("percent_"+bookFile.getName(),percent).apply();updateBookmarkIcon();}
    private void resetPdfZoom(){pdfScale=1f;if(pdfImage!=null){pdfImage.setScaleX(1f);pdfImage.setScaleY(1f);pdfImage.setTranslationX(0f);pdfImage.setTranslationY(0f);pdfImage.setPivotX(pdfImage.getWidth()/2f);pdfImage.setPivotY(pdfImage.getHeight()/2f);}}

    private void unzipEpub(File epub,File dest)throws Exception{String destPath=dest.getCanonicalPath()+File.separator;try(ZipInputStream zis=new ZipInputStream(new FileInputStream(epub))){ZipEntry entry;byte[] buffer=new byte[64*1024];while((entry=zis.getNextEntry())!=null){File out=new File(dest,entry.getName());String outPath=out.getCanonicalPath();if(!outPath.startsWith(destPath))throw new SecurityException("Unsafe EPUB path");if(entry.isDirectory())out.mkdirs();else{File parent=out.getParentFile();if(parent!=null)parent.mkdirs();try(FileOutputStream fos=new FileOutputStream(out)){int n;while((n=zis.read(buffer))>0)fos.write(buffer,0,n);}}zis.closeEntry();}}}
    private void deleteRecursive(File f){if(f==null||!f.exists())return;if(f.isDirectory()){File[] children=f.listFiles();if(children!=null)for(File c:children)deleteRecursive(c);}f.delete();}

    private class ReaderBridge {
        @JavascriptInterface public void onScroll(int p){runOnUiThread(()->{updateEpubProgress(p);prefs.edit().putInt("epub_scroll_"+bookFile.getName(),currentScrollPermille).putInt("epub_chapter_"+bookFile.getName(),currentSpine).apply();});}
        @JavascriptInterface public void onPage(int page,int count,int p){runOnUiThread(()->updateEpubPageProgress(page,count,p));}
        @JavascriptInterface public void prevChapter(){runOnUiThread(()->previousChapter(true));}
        @JavascriptInterface public void nextChapter(){runOnUiThread(()->nextChapter());}
        @JavascriptInterface public void toggle(){runOnUiThread(()->toggleControls());}
    }

    @Override public void onBackPressed(){
        long now=System.currentTimeMillis();
        if(topBar!=null&&topBar.getVisibility()!=View.VISIBLE){toggleControls();return;}
        if(now<backArmedUntil){super.onBackPressed();return;}
        backArmedUntil=now+1800L;
        Toast.makeText(this,"Press Back again to return to Library",Toast.LENGTH_SHORT).show();
    }

    @Override protected void onPause(){super.onPause();if(!isPdf)saveEpubState();}
    @Override protected void onDestroy(){super.onDestroy();if(webView!=null){webView.removeJavascriptInterface("WoW");webView.destroy();}try{if(pdfPage!=null)pdfPage.close();}catch(Exception ignored){}try{if(pdfRenderer!=null)pdfRenderer.close();}catch(Exception ignored){}try{if(pdfDescriptor!=null)pdfDescriptor.close();}catch(Exception ignored){}}
    private String stripExtension(String name){int dot=name.lastIndexOf('.');return dot>0?name.substring(0,dot):name;}
    private int dp(int v){return Math.round(v*getResources().getDisplayMetrics().density);}
}
