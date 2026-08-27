package com.whisper.wowreader;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.pdf.PdfRenderer;
import android.net.Uri;
import android.os.Bundle;
import android.os.ParcelFileDescriptor;
import android.provider.DocumentsContract;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.ImageView;
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
    private File coverCacheDir;
    private LinearLayout booksContainer;
    private TextView countView;
    private TextView viewModeButton;
    private SharedPreferences prefs;
    private boolean gridMode;
    private String searchQuery = "";

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.WHITE);
        getWindow().setNavigationBarColor(Color.WHITE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        libraryDir = new File(getFilesDir(), "library");
        coverCacheDir = new File(getFilesDir(), "cover_cache");
        if (!libraryDir.exists()) libraryDir.mkdirs();
        if (!coverCacheDir.exists()) coverCacheDir.mkdirs();
        prefs = getSharedPreferences("wow_reader", MODE_PRIVATE);
        gridMode = prefs.getBoolean("library_grid", true);
        buildUi();
        handleIncomingIntent(getIntent());
    }

    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent); setIntent(intent); handleIncomingIntent(intent); }
    @Override protected void onResume() { super.onResume(); if (booksContainer != null) refreshLibrary(); }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(Color.WHITE);
        LinearLayout top = new LinearLayout(this); top.setOrientation(LinearLayout.HORIZONTAL); top.setGravity(Gravity.CENTER_VERTICAL); top.setPadding(dp(20), dp(10), dp(10), dp(6));
        TextView brand = new TextView(this); brand.setText("Library"); brand.setTextSize(28); brand.setTextColor(Color.rgb(32,33,36)); brand.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        top.addView(brand, new LinearLayout.LayoutParams(0, dp(54), 1));
        TextView cloud = iconButton("☁"); cloud.setContentDescription("Cloud backup"); cloud.setOnClickListener(v -> showCloudMenu()); top.addView(cloud, new LinearLayout.LayoutParams(dp(48), dp(48)));
        viewModeButton = iconButton(gridMode ? "☷" : "▦"); viewModeButton.setContentDescription("Change library view");
        viewModeButton.setOnClickListener(v -> { gridMode = !gridMode; prefs.edit().putBoolean("library_grid", gridMode).apply(); viewModeButton.setText(gridMode ? "☷" : "▦"); refreshLibrary(); });
        top.addView(viewModeButton, new LinearLayout.LayoutParams(dp(48), dp(48)));
        TextView add = iconButton("＋"); add.setTextSize(28); add.setContentDescription("Add book"); add.setOnClickListener(v -> chooseBook()); top.addView(add, new LinearLayout.LayoutParams(dp(48), dp(48)));
        root.addView(top);

        EditText search = new EditText(this); search.setSingleLine(true); search.setHint("Search your library"); search.setTextSize(16); search.setTextColor(Color.rgb(32,33,36)); search.setHintTextColor(Color.rgb(112,117,122)); search.setPadding(dp(18),0,dp(18),0); search.setBackground(roundRect(Color.rgb(245,247,250), dp(24),0,0));
        LinearLayout.LayoutParams searchLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(48)); searchLp.leftMargin=dp(16); searchLp.rightMargin=dp(16); searchLp.topMargin=dp(4); searchLp.bottomMargin=dp(8); root.addView(search, searchLp);
        search.addTextChangedListener(new TextWatcher() { @Override public void beforeTextChanged(CharSequence s,int start,int count,int after){} @Override public void onTextChanged(CharSequence s,int start,int before,int count){ searchQuery=s.toString().trim().toLowerCase(Locale.ROOT); refreshLibrary(); } @Override public void afterTextChanged(Editable s){} });

        LinearLayout section = new LinearLayout(this); section.setGravity(Gravity.CENTER_VERTICAL); section.setPadding(dp(20),dp(10),dp(20),dp(6));
        TextView label = new TextView(this); label.setText("Your books"); label.setTextSize(18); label.setTextColor(Color.rgb(32,33,36)); label.setTypeface(Typeface.DEFAULT, Typeface.BOLD); section.addView(label,new LinearLayout.LayoutParams(0,dp(40),1));
        countView = new TextView(this); countView.setTextSize(13); countView.setTextColor(Color.rgb(95,99,104)); countView.setGravity(Gravity.CENTER_VERTICAL|Gravity.END); section.addView(countView,new LinearLayout.LayoutParams(dp(100),dp(40))); root.addView(section);

        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true); booksContainer = new LinearLayout(this); booksContainer.setOrientation(LinearLayout.VERTICAL); booksContainer.setPadding(dp(14),dp(2),dp(14),dp(32)); scroll.addView(booksContainer,new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT)); root.addView(scroll,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,1));
        setContentView(root); refreshLibrary();
    }

    private TextView iconButton(String text) { TextView v=new TextView(this); v.setText(text); v.setTextSize(22); v.setTextColor(Color.rgb(70,71,75)); v.setGravity(Gravity.CENTER); v.setBackground(roundRect(Color.TRANSPARENT,dp(24),0,0)); v.setClickable(true); return v; }

    private void refreshLibrary() {
        booksContainer.removeAllViews();
        File[] all=libraryDir.listFiles(file -> file.isFile() && isBook(file.getName())); if(all==null) all=new File[0]; Arrays.sort(all, Comparator.comparingLong(File::lastModified).reversed());
        List<File> files=new ArrayList<>(); for(File f:all) if(searchQuery.isEmpty()||stripExtension(f.getName()).toLowerCase(Locale.ROOT).contains(searchQuery)) files.add(f);
        countView.setText(files.size()+(files.size()==1?" book":" books"));
        if(files.isEmpty()){ TextView empty=new TextView(this); empty.setText(searchQuery.isEmpty()?"Your library is empty\n\nTap ＋ to add an EPUB or PDF.":"No books found"); empty.setTextSize(17); empty.setTextColor(Color.rgb(95,99,104)); empty.setGravity(Gravity.CENTER); empty.setPadding(dp(20),dp(100),dp(20),dp(60)); booksContainer.addView(empty,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT)); return; }
        if(gridMode) addGrid(files); else for(File f:files) booksContainer.addView(createListCard(f));
    }

    private void addGrid(List<File> files) {
        int screen=getResources().getDisplayMetrics().widthPixels, gap=dp(10), padding=dp(28), cellWidth=Math.max(dp(100),(screen-padding-gap*2)/3);
        for(int i=0;i<files.size();i+=3){ LinearLayout row=new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL); row.setGravity(Gravity.TOP);
            for(int j=0;j<3;j++){ int idx=i+j; LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(cellWidth,ViewGroup.LayoutParams.WRAP_CONTENT); if(j>0) lp.leftMargin=gap; if(idx<files.size()) row.addView(createGridCard(files.get(idx),cellWidth),lp); else row.addView(new View(this),lp); }
            LinearLayout.LayoutParams rlp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT); rlp.bottomMargin=dp(18); booksContainer.addView(row,rlp); }
    }

    private View createGridCard(File file,int cellWidth){
        LinearLayout cell=new LinearLayout(this); cell.setOrientation(LinearLayout.VERTICAL); cell.setClickable(true); cell.setOnClickListener(v->openBook(file)); cell.setOnLongClickListener(v->{confirmDelete(file);return true;});
        int coverHeight=Math.round(cellWidth*1.46f); ImageView cover=new ImageView(this); cover.setScaleType(ImageView.ScaleType.CENTER_CROP); String initial=stripExtension(file.getName()); cover.setImageBitmap(placeholderBitmap(initial,Math.max(180,cellWidth),Math.max(260,coverHeight))); cover.setBackground(roundRect(Color.rgb(232,234,237),dp(8),0,0)); cover.setClipToOutline(true); cover.setElevation(dp(2)); cell.addView(cover,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,coverHeight));
        TextView title=new TextView(this); title.setText(initial); title.setTextSize(14); title.setTextColor(Color.rgb(32,33,36)); title.setTypeface(Typeface.DEFAULT,Typeface.BOLD); title.setMaxLines(2); title.setPadding(dp(2),dp(8),dp(2),0); cell.addView(title);
        TextView author=new TextView(this); int progress=prefs.getInt("percent_"+file.getName(),0); author.setText((file.getName().toLowerCase(Locale.ROOT).endsWith(".pdf")?"PDF":"EPUB")+" · "+progress+"%"); author.setTextSize(12); author.setTextColor(Color.rgb(95,99,104)); author.setSingleLine(true); author.setPadding(dp(2),dp(3),dp(2),0); cell.addView(author); loadBookVisual(file,cover,title,author); return cell;
    }

    private View createListCard(File file){
        LinearLayout card=new LinearLayout(this); card.setOrientation(LinearLayout.HORIZONTAL); card.setGravity(Gravity.CENTER_VERTICAL); card.setPadding(dp(4),dp(8),dp(4),dp(8)); card.setOnClickListener(v->openBook(file)); card.setOnLongClickListener(v->{confirmDelete(file);return true;});
        ImageView cover=new ImageView(this); cover.setScaleType(ImageView.ScaleType.CENTER_CROP); String initial=stripExtension(file.getName()); cover.setImageBitmap(placeholderBitmap(initial,180,260)); cover.setBackground(roundRect(Color.rgb(232,234,237),dp(7),0,0)); cover.setClipToOutline(true); cover.setElevation(dp(1)); card.addView(cover,new LinearLayout.LayoutParams(dp(72),dp(104)));
        LinearLayout text=new LinearLayout(this); text.setOrientation(LinearLayout.VERTICAL); text.setPadding(dp(16),dp(5),dp(8),dp(5)); TextView title=new TextView(this); title.setText(initial); title.setTextSize(17); title.setTextColor(Color.rgb(32,33,36)); title.setTypeface(Typeface.DEFAULT,Typeface.BOLD); title.setMaxLines(2); text.addView(title);
        TextView author=new TextView(this); int progress=prefs.getInt("percent_"+file.getName(),0); author.setText((file.getName().toLowerCase(Locale.ROOT).endsWith(".pdf")?"PDF":"EPUB")+" · "+progress+"% read"); author.setTextSize(13); author.setTextColor(Color.rgb(95,99,104)); author.setPadding(0,dp(7),0,0); text.addView(author);
        TextView cont=new TextView(this); cont.setText(progress>0?"Continue reading":"Start reading"); cont.setTextSize(13); cont.setTextColor(Color.rgb(26,115,232)); cont.setPadding(0,dp(9),0,0); text.addView(cont); card.addView(text,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1)); loadBookVisual(file,cover,title,author);
        LinearLayout wrap=new LinearLayout(this); wrap.setOrientation(LinearLayout.VERTICAL); wrap.addView(card,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT)); View divider=new View(this); divider.setBackgroundColor(Color.rgb(238,238,238)); LinearLayout.LayoutParams dlp=new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(1)); dlp.leftMargin=dp(92); wrap.addView(divider,dlp); return wrap;
    }

    private void loadBookVisual(File file,ImageView cover,TextView titleView,TextView metaView){
        new Thread(()->{ String title=stripExtension(file.getName()),author=""; Bitmap bitmap=null; try{ if(file.getName().toLowerCase(Locale.ROOT).endsWith(".epub")){ EpubUtil.Summary s=EpubUtil.extractSummary(file,coverCacheDir); if(s.title!=null&&!s.title.isEmpty()) title=s.title; if(s.author!=null) author=s.author; if(s.cover!=null&&s.cover.isFile()) bitmap=BitmapFactory.decodeFile(s.cover.getAbsolutePath()); } else bitmap=renderPdfCover(file); }catch(Exception ignored){}
            String ft=title,fa=author; Bitmap fb=bitmap; int progress=prefs.getInt("percent_"+file.getName(),0); runOnUiThread(()->{ if(fb!=null) cover.setImageBitmap(fb); titleView.setText(ft); String type=file.getName().toLowerCase(Locale.ROOT).endsWith(".pdf")?"PDF":"EPUB"; metaView.setText(fa.isEmpty()?type+" · "+progress+"%":fa+" · "+progress+"%"); }); }).start();
    }

    private Bitmap renderPdfCover(File file){ ParcelFileDescriptor pfd=null; PdfRenderer renderer=null; PdfRenderer.Page page=null; try{ pfd=ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY); renderer=new PdfRenderer(pfd); if(renderer.getPageCount()==0)return null; page=renderer.openPage(0); int width=360,height=Math.max(1,Math.round(width*(page.getHeight()/(float)page.getWidth()))); Bitmap b=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888); b.eraseColor(Color.WHITE); page.render(b,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY); return b; }catch(Exception e){return null;} finally{try{if(page!=null)page.close();}catch(Exception ignored){} try{if(renderer!=null)renderer.close();}catch(Exception ignored){} try{if(pfd!=null)pfd.close();}catch(Exception ignored){}} }

    private Bitmap placeholderBitmap(String title,int width,int height){ Bitmap b=Bitmap.createBitmap(Math.max(1,width),Math.max(1,height),Bitmap.Config.ARGB_8888); Canvas c=new Canvas(b); Paint p=new Paint(Paint.ANTI_ALIAS_FLAG); p.setColor(colorForName(title)); c.drawRect(0,0,b.getWidth(),b.getHeight(),p); p.setColor(Color.WHITE); p.setTypeface(Typeface.create(Typeface.DEFAULT,Typeface.BOLD)); p.setTextSize(Math.min(width,height)*.25f); p.setTextAlign(Paint.Align.CENTER); String letter=title==null||title.trim().isEmpty()?"W":title.trim().substring(0,1).toUpperCase(Locale.ROOT); Paint.FontMetrics fm=p.getFontMetrics(); float y=height/2f-(fm.ascent+fm.descent)/2f; c.drawText(letter,width/2f,y,p); return b; }

    private void chooseBook(){ Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT); i.addCategory(Intent.CATEGORY_OPENABLE); i.setType("*/*"); i.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/epub+zip","application/pdf"}); startActivityForResult(i,REQ_IMPORT); }
    private void handleIncomingIntent(Intent intent){ if(intent==null||!Intent.ACTION_VIEW.equals(intent.getAction()))return; Uri data=intent.getData(); if(data!=null) importBook(data,true); }

    private void importBook(Uri uri,boolean openAfter){ new Thread(()->{ try{ String name=queryDisplayName(uri); if(name==null||name.trim().isEmpty())name="book_"+System.currentTimeMillis(); String lower=name.toLowerCase(Locale.ROOT),mime=getContentResolver().getType(uri); if(!lower.endsWith(".epub")&&!lower.endsWith(".pdf")){ if("application/pdf".equals(mime))name+=".pdf"; else if("application/epub+zip".equals(mime))name+=".epub"; else throw new Exception("Only EPUB and PDF files are supported"); } File out=uniqueFile(name); try(InputStream in=getContentResolver().openInputStream(uri);OutputStream os=new FileOutputStream(out)){if(in==null)throw new Exception("Unable to open file");copy(in,os);} runOnUiThread(()->{Toast.makeText(this,"Added to WoW Reader",Toast.LENGTH_SHORT).show();refreshLibrary();if(openAfter)openBook(out);}); }catch(Exception e){runOnUiThread(()->Toast.makeText(this,e.getMessage(),Toast.LENGTH_LONG).show());} }).start(); }

    private String queryDisplayName(Uri uri){ if("file".equalsIgnoreCase(uri.getScheme()))return new File(uri.getPath()).getName(); Cursor c=null; try{c=getContentResolver().query(uri,new String[]{android.provider.OpenableColumns.DISPLAY_NAME},null,null,null);if(c!=null&&c.moveToFirst())return c.getString(0);}catch(Exception ignored){}finally{if(c!=null)c.close();}return null; }
    private File uniqueFile(String originalName){ String safe=originalName.replaceAll("[\\\\/:*?\"<>|]","_"); File f=new File(libraryDir,safe);if(!f.exists())return f;int dot=safe.lastIndexOf('.');String base=dot>0?safe.substring(0,dot):safe,ext=dot>0?safe.substring(dot):"";return new File(libraryDir,base+"_"+System.currentTimeMillis()+ext); }
    private void openBook(File file){Intent i=new Intent(this,BookReaderActivity.class);i.putExtra("path",file.getAbsolutePath());startActivity(i);}
    private void confirmDelete(File file){new AlertDialog.Builder(this).setTitle("Remove from library?").setMessage(stripExtension(file.getName())).setNegativeButton("Cancel",null).setPositiveButton("Remove",(d,w)->{if(file.delete()){prefs.edit().remove("percent_"+file.getName()).apply();refreshLibrary();}}).show();}

    private void showCloudMenu(){new AlertDialog.Builder(this).setTitle("Cloud / Google Drive").setItems(new String[]{"Backup library","Restore books"},(dialog,which)->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);startActivityForResult(i,which==0?REQ_BACKUP:REQ_RESTORE);}).show();}
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){super.onActivityResult(requestCode,resultCode,data);if(resultCode!=RESULT_OK||data==null||data.getData()==null)return;Uri uri=data.getData();if(requestCode==REQ_IMPORT){importBook(uri,false);return;}try{getContentResolver().takePersistableUriPermission(uri,data.getFlags()&(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION));}catch(Exception ignored){}if(requestCode==REQ_BACKUP)backupLibrary(uri);else if(requestCode==REQ_RESTORE)restoreLibrary(uri);}

    private void backupLibrary(Uri treeUri){new Thread(()->{int count=0;try{File[] files=libraryDir.listFiles();if(files!=null)for(File file:files){if(!isBook(file.getName()))continue;Uri target=findChild(treeUri,file.getName());if(target==null){String mime=file.getName().toLowerCase(Locale.ROOT).endsWith(".pdf")?"application/pdf":"application/epub+zip";target=DocumentsContract.createDocument(getContentResolver(),treeDocumentUri(treeUri),mime,file.getName());}if(target!=null)try(InputStream in=new FileInputStream(file);OutputStream out=getContentResolver().openOutputStream(target,"wt")){if(out!=null){copy(in,out);count++;}}}int n=count;runOnUiThread(()->Toast.makeText(this,"Backup complete: "+n+" books",Toast.LENGTH_LONG).show());}catch(Exception e){runOnUiThread(()->Toast.makeText(this,"Backup failed: "+e.getMessage(),Toast.LENGTH_LONG).show());}}).start();}
    private void restoreLibrary(Uri treeUri){new Thread(()->{int count=0;Cursor c=null;try{Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(treeUri,DocumentsContract.getTreeDocumentId(treeUri));c=getContentResolver().query(children,new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null);if(c!=null)while(c.moveToNext()){String id=c.getString(0),name=c.getString(1);if(!isBook(name))continue;Uri doc=DocumentsContract.buildDocumentUriUsingTree(treeUri,id);File out=new File(libraryDir,name.replaceAll("[\\\\/:*?\"<>|]","_"));try(InputStream in=getContentResolver().openInputStream(doc);OutputStream os=new FileOutputStream(out)){if(in!=null){copy(in,os);count++;}}}int n=count;runOnUiThread(()->{refreshLibrary();Toast.makeText(this,"Restored: "+n+" books",Toast.LENGTH_LONG).show();});}catch(Exception e){runOnUiThread(()->Toast.makeText(this,"Restore failed: "+e.getMessage(),Toast.LENGTH_LONG).show());}finally{if(c!=null)c.close();}}).start();}
    private Uri findChild(Uri treeUri,String name){Cursor c=null;try{Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(treeUri,DocumentsContract.getTreeDocumentId(treeUri));c=getContentResolver().query(children,new String[]{DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME},null,null,null);if(c!=null)while(c.moveToNext())if(name.equals(c.getString(1)))return DocumentsContract.buildDocumentUriUsingTree(treeUri,c.getString(0));}catch(Exception ignored){}finally{if(c!=null)c.close();}return null;}
    private Uri treeDocumentUri(Uri treeUri){return DocumentsContract.buildDocumentUriUsingTree(treeUri,DocumentsContract.getTreeDocumentId(treeUri));}
    private boolean isBook(String n){String s=n==null?"":n.toLowerCase(Locale.ROOT);return s.endsWith(".epub")||s.endsWith(".pdf");}
    private static void copy(InputStream in,OutputStream out)throws Exception{byte[] b=new byte[64*1024];int n;while((n=in.read(b))>0)out.write(b,0,n);}
    private String stripExtension(String name){int dot=name.lastIndexOf('.');return dot>0?name.substring(0,dot):name;}
    private int colorForName(String name){int[] colors={Color.rgb(96,74,139),Color.rgb(55,102,136),Color.rgb(151,78,74),Color.rgb(76,111,82),Color.rgb(130,89,55)};return colors[Math.abs(name==null?0:name.hashCode())%colors.length];}
    private GradientDrawable roundRect(int color,float radius,int strokeWidth,int strokeColor){GradientDrawable g=new GradientDrawable();g.setColor(color);g.setCornerRadius(radius);if(strokeWidth>0)g.setStroke(strokeWidth,strokeColor);return g;}
    private int dp(int v){return Math.round(v*getResources().getDisplayMetrics().density);}
}
