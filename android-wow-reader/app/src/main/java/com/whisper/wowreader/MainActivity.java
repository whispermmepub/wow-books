package com.whisper.wowreader;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int REQ_IMPORT = 1001;
    private static final int REQ_BACKUP = 1002;
    private static final int REQ_RESTORE = 1003;

    private File libraryDir;
    private LinearLayout booksContainer;
    private TextView emptyView;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.WHITE);
        getWindow().setNavigationBarColor(Color.WHITE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);

        libraryDir = new File(getFilesDir(), "library");
        if (!libraryDir.exists()) libraryDir.mkdirs();
        prefs = getSharedPreferences("wow_reader", MODE_PRIVATE);

        buildUi();
        handleIncomingIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIncomingIntent(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (booksContainer != null) refreshLibrary();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(250, 249, 252));

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setOrientation(LinearLayout.HORIZONTAL);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(18), dp(12), dp(12), dp(10));
        toolbar.setBackgroundColor(Color.WHITE);

        TextView brand = new TextView(this);
        brand.setText("WoW Reader");
        brand.setTextSize(24);
        brand.setTextColor(Color.rgb(50, 43, 63));
        brand.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        toolbar.addView(brand, new LinearLayout.LayoutParams(0, dp(52), 1));

        Button cloud = smallButton("Cloud");
        cloud.setOnClickListener(v -> showCloudMenu());
        toolbar.addView(cloud, new LinearLayout.LayoutParams(dp(82), dp(42)));

        Button add = smallButton("+ Add");
        LinearLayout.LayoutParams addLp = new LinearLayout.LayoutParams(dp(82), dp(42));
        addLp.leftMargin = dp(8);
        toolbar.addView(add, addLp);
        add.setOnClickListener(v -> chooseBook());

        root.addView(toolbar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView subtitle = new TextView(this);
        subtitle.setText("Your offline library");
        subtitle.setTextSize(14);
        subtitle.setTextColor(Color.rgb(110, 104, 120));
        subtitle.setPadding(dp(20), dp(18), dp(20), dp(8));
        root.addView(subtitle);

        ScrollView scroll = new ScrollView(this);
        booksContainer = new LinearLayout(this);
        booksContainer.setOrientation(LinearLayout.VERTICAL);
        booksContainer.setPadding(dp(16), dp(4), dp(16), dp(30));
        scroll.addView(booksContainer, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        setContentView(root);
        refreshLibrary();
    }

    private Button smallButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(13);
        b.setTextColor(Color.WHITE);
        b.setAllCaps(false);
        GradientDrawable gd = new GradientDrawable();
        gd.setColor(Color.rgb(95, 75, 139));
        gd.setCornerRadius(dp(18));
        b.setBackground(gd);
        b.setPadding(dp(6), 0, dp(6), 0);
        return b;
    }

    private void chooseBook() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        i.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/epub+zip", "application/pdf"});
        startActivityForResult(i, REQ_IMPORT);
    }

    private void handleIncomingIntent(Intent intent) {
        if (intent == null || !Intent.ACTION_VIEW.equals(intent.getAction())) return;
        Uri data = intent.getData();
        if (data != null) importBook(data, true);
    }

    private void importBook(Uri uri, boolean openAfter) {
        new Thread(() -> {
            try {
                String name = queryDisplayName(uri);
                if (name == null || name.trim().isEmpty()) name = "book_" + System.currentTimeMillis();
                String lower = name.toLowerCase(Locale.ROOT);
                String mime = getContentResolver().getType(uri);
                if (!lower.endsWith(".epub") && !lower.endsWith(".pdf")) {
                    if ("application/pdf".equals(mime)) name += ".pdf";
                    else if ("application/epub+zip".equals(mime)) name += ".epub";
                    else throw new Exception("Only EPUB and PDF files are supported");
                }

                File out = uniqueFile(name);
                try (InputStream in = getContentResolver().openInputStream(uri);
                     OutputStream os = new FileOutputStream(out)) {
                    if (in == null) throw new Exception("Unable to open file");
                    copy(in, os);
                }
                File result = out;
                runOnUiThread(() -> {
                    Toast.makeText(this, "Added to WoW Reader", Toast.LENGTH_SHORT).show();
                    refreshLibrary();
                    if (openAfter) openBook(result);
                });
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(this, e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }).start();
    }

    private File uniqueFile(String originalName) {
        String safe = originalName.replaceAll("[\\\\/:*?\"<>|]", "_");
        File f = new File(libraryDir, safe);
        if (!f.exists()) return f;
        int dot = safe.lastIndexOf('.');
        String base = dot > 0 ? safe.substring(0, dot) : safe;
        String ext = dot > 0 ? safe.substring(dot) : "";
        return new File(libraryDir, base + "_" + System.currentTimeMillis() + ext);
    }

    private String queryDisplayName(Uri uri) {
        if ("file".equalsIgnoreCase(uri.getScheme())) return new File(uri.getPath()).getName();
        Cursor c = null;
        try {
            c = getContentResolver().query(uri, new String[]{android.provider.OpenableColumns.DISPLAY_NAME}, null, null, null);
            if (c != null && c.moveToFirst()) return c.getString(0);
        } catch (Exception ignored) {
        } finally {
            if (c != null) c.close();
        }
        return null;
    }

    private void refreshLibrary() {
        booksContainer.removeAllViews();
        File[] files = libraryDir.listFiles(file -> {
            String n = file.getName().toLowerCase(Locale.ROOT);
            return file.isFile() && (n.endsWith(".epub") || n.endsWith(".pdf"));
        });
        if (files == null) files = new File[0];
        Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());

        if (files.length == 0) {
            emptyView = new TextView(this);
            emptyView.setText("No books yet\n\nTap + Add to import EPUB or PDF files.");
            emptyView.setGravity(Gravity.CENTER);
            emptyView.setTextSize(17);
            emptyView.setTextColor(Color.rgb(118, 111, 126));
            emptyView.setPadding(dp(20), dp(90), dp(20), dp(40));
            booksContainer.addView(emptyView, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            return;
        }

        for (File file : files) addBookCard(file);
    }

    private void addBookCard(File file) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(12), dp(12), dp(12), dp(12));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.WHITE);
        bg.setCornerRadius(dp(18));
        bg.setStroke(dp(1), Color.rgb(236, 232, 241));
        card.setBackground(bg);
        card.setElevation(dp(1));

        TextView cover = new TextView(this);
        String title = stripExtension(file.getName());
        cover.setText(title.isEmpty() ? "W" : title.substring(0, 1).toUpperCase(Locale.ROOT));
        cover.setTextColor(Color.WHITE);
        cover.setTextSize(30);
        cover.setGravity(Gravity.CENTER);
        cover.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        GradientDrawable coverBg = new GradientDrawable();
        coverBg.setColor(colorForName(title));
        coverBg.setCornerRadius(dp(8));
        cover.setBackground(coverBg);
        card.addView(cover, new LinearLayout.LayoutParams(dp(72), dp(102)));

        LinearLayout textBox = new LinearLayout(this);
        textBox.setOrientation(LinearLayout.VERTICAL);
        textBox.setPadding(dp(14), dp(6), dp(4), dp(4));
        TextView titleView = new TextView(this);
        titleView.setText(title);
        titleView.setTextSize(17);
        titleView.setTextColor(Color.rgb(45, 40, 53));
        titleView.setMaxLines(2);
        titleView.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);
        textBox.addView(titleView);

        TextView meta = new TextView(this);
        String type = file.getName().toLowerCase(Locale.ROOT).endsWith(".pdf") ? "PDF" : "EPUB";
        int progress = prefs.getInt("percent_" + file.getName(), 0);
        meta.setText(type + "   •   " + progress + "% read");
        meta.setTextSize(13);
        meta.setTextColor(Color.rgb(112, 106, 119));
        meta.setPadding(0, dp(8), 0, 0);
        textBox.addView(meta);

        TextView hint = new TextView(this);
        hint.setText(progress > 0 ? "Continue reading" : "Start reading");
        hint.setTextSize(13);
        hint.setTextColor(Color.rgb(95, 75, 139));
        hint.setPadding(0, dp(10), 0, 0);
        textBox.addView(hint);

        card.addView(textBox, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        card.setOnClickListener(v -> openBook(file));
        card.setOnLongClickListener(v -> {
            confirmDelete(file);
            return true;
        });

        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.bottomMargin = dp(12);
        booksContainer.addView(card, lp);
    }

    private void openBook(File file) {
        Intent i = new Intent(this, BookReaderActivity.class);
        i.putExtra("path", file.getAbsolutePath());
        startActivity(i);
    }

    private void confirmDelete(File file) {
        new AlertDialog.Builder(this)
                .setTitle("Remove book?")
                .setMessage(stripExtension(file.getName()))
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Remove", (d, w) -> {
                    if (file.delete()) {
                        prefs.edit().remove("percent_" + file.getName()).apply();
                        refreshLibrary();
                    }
                }).show();
    }

    private void showCloudMenu() {
        new AlertDialog.Builder(this)
                .setTitle("Cloud / Google Drive")
                .setItems(new String[]{"Backup library", "Restore books"}, (dialog, which) -> {
                    Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                    startActivityForResult(i, which == 0 ? REQ_BACKUP : REQ_RESTORE);
                }).show();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        if (requestCode == REQ_IMPORT) {
            importBook(uri, false);
            return;
        }
        try {
            getContentResolver().takePersistableUriPermission(uri,
                    data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION));
        } catch (Exception ignored) {}
        if (requestCode == REQ_BACKUP) backupLibrary(uri);
        if (requestCode == REQ_RESTORE) restoreLibrary(uri);
    }

    private void backupLibrary(Uri treeUri) {
        new Thread(() -> {
            int count = 0;
            try {
                File[] files = libraryDir.listFiles();
                if (files != null) {
                    for (File file : files) {
                        if (!isBook(file.getName())) continue;
                        Uri target = findChild(treeUri, file.getName());
                        if (target == null) {
                            String mime = file.getName().toLowerCase(Locale.ROOT).endsWith(".pdf") ? "application/pdf" : "application/epub+zip";
                            target = DocumentsContract.createDocument(getContentResolver(), treeDocumentUri(treeUri), mime, file.getName());
                        }
                        if (target != null) {
                            try (InputStream in = new FileInputStream(file);
                                 OutputStream out = getContentResolver().openOutputStream(target, "wt")) {
                                if (out != null) {
                                    copy(in, out);
                                    count++;
                                }
                            }
                        }
                    }
                }
                int finalCount = count;
                runOnUiThread(() -> Toast.makeText(this, "Backup complete: " + finalCount + " books", Toast.LENGTH_LONG).show());
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(this, "Backup failed: " + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }).start();
    }

    private void restoreLibrary(Uri treeUri) {
        new Thread(() -> {
            int count = 0;
            Cursor c = null;
            try {
                Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri));
                c = getContentResolver().query(children,
                        new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME},
                        null, null, null);
                if (c != null) {
                    while (c.moveToNext()) {
                        String id = c.getString(0);
                        String name = c.getString(1);
                        if (!isBook(name)) continue;
                        Uri doc = DocumentsContract.buildDocumentUriUsingTree(treeUri, id);
                        File out = new File(libraryDir, name.replaceAll("[\\\\/:*?\"<>|]", "_"));
                        try (InputStream in = getContentResolver().openInputStream(doc);
                             OutputStream os = new FileOutputStream(out)) {
                            if (in != null) {
                                copy(in, os);
                                count++;
                            }
                        }
                    }
                }
                int finalCount = count;
                runOnUiThread(() -> {
                    refreshLibrary();
                    Toast.makeText(this, "Restored: " + finalCount + " books", Toast.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(this, "Restore failed: " + e.getMessage(), Toast.LENGTH_LONG).show());
            } finally {
                if (c != null) c.close();
            }
        }).start();
    }

    private Uri findChild(Uri treeUri, String displayName) {
        Cursor c = null;
        try {
            Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri));
            c = getContentResolver().query(children,
                    new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME},
                    null, null, null);
            if (c != null) {
                while (c.moveToNext()) {
                    if (displayName.equals(c.getString(1))) {
                        return DocumentsContract.buildDocumentUriUsingTree(treeUri, c.getString(0));
                    }
                }
            }
        } catch (Exception ignored) {
        } finally {
            if (c != null) c.close();
        }
        return null;
    }

    private Uri treeDocumentUri(Uri treeUri) {
        return DocumentsContract.buildDocumentUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri));
    }

    private boolean isBook(String name) {
        if (name == null) return false;
        String n = name.toLowerCase(Locale.ROOT);
        return n.endsWith(".epub") || n.endsWith(".pdf");
    }

    private static void copy(InputStream in, OutputStream out) throws Exception {
        byte[] buf = new byte[64 * 1024];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        out.flush();
    }

    private String stripExtension(String name) {
        int dot = name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private int colorForName(String value) {
        int[] colors = new int[]{
                Color.rgb(95, 75, 139), Color.rgb(63, 101, 134), Color.rgb(139, 83, 83),
                Color.rgb(70, 115, 92), Color.rgb(142, 105, 55), Color.rgb(92, 80, 118)
        };
        return colors[Math.abs(value.hashCode()) % colors.length];
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
