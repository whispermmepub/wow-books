from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/MainActivity.java')
s = path.read_text(encoding='utf-8')

# Google Identity / Drive account sync imports.
s = s.replace('import android.app.Activity;\n', 'import android.accounts.Account;\nimport android.app.Activity;\n', 1)
s = s.replace('import android.content.Intent;\n', 'import android.content.Intent;\nimport android.content.IntentSender;\n', 1)
anchor = 'import android.widget.Toast;\n\n'
if anchor not in s:
    raise SystemExit('v2.0 home: widget import anchor not found')
s = s.replace(anchor, anchor + '''import com.google.android.gms.auth.api.identity.AuthorizationRequest;\nimport com.google.android.gms.auth.api.identity.AuthorizationResult;\nimport com.google.android.gms.auth.api.identity.Identity;\nimport com.google.android.gms.auth.api.identity.RevokeAccessRequest;\nimport com.google.android.gms.common.api.ApiException;\nimport com.google.android.gms.common.api.Scope;\n\n''', 1)

# Fields / request code.
old = '''    private static final int REQ_RESTORE = 1003;\n'''
new = '''    private static final int REQ_RESTORE = 1003;\n    private static final int REQ_GOOGLE_AUTH = 2001;\n'''
if old not in s:
    raise SystemExit('v2.0 home: request code anchor not found')
s = s.replace(old, new, 1)

old = '''    private boolean gridMode;\n    private String searchQuery = "";\n'''
new = '''    private boolean gridMode;\n    private String searchQuery = "";\n    private TextView googleStatusView;\n    private boolean googleSyncBusy = false;\n    private boolean pendingGoogleSyncUserInitiated = false;\n    private long lastAutoSyncAttemptMs = 0L;\n'''
if old not in s:
    raise SystemExit('v2.0 home: field anchor not found')
s = s.replace(old, new, 1)

# Resume refresh + low-frequency automatic Drive refresh.
old = '''    @Override protected void onResume() { super.onResume(); if (booksContainer != null) refreshLibrary(); }\n'''
new = '''    @Override protected void onResume() {\n        super.onResume();\n        if (booksContainer != null) refreshLibrary();\n        updateGoogleStatus();\n        maybeAutoSync();\n    }\n'''
if old not in s:
    raise SystemExit('v2.0 home: onResume anchor not found')
s = s.replace(old, new, 1)

# Place Discover + Google Drive cards between search and library.
anchor = '''        LinearLayout section = new LinearLayout(this); section.setGravity(Gravity.CENTER_VERTICAL); section.setPadding(dp(20),dp(10),dp(20),dp(6));\n'''
if anchor not in s:
    raise SystemExit('v2.0 home: section anchor not found')
s = s.replace(anchor, '''        addHomeServices(root);\n\n''' + anchor, 1)

# Home cards and link launcher.
anchor = '''    private TextView iconButton(String text) { TextView v=new TextView(this); v.setText(text); v.setTextSize(22); v.setTextColor(Color.rgb(70,71,75)); v.setGravity(Gravity.CENTER); v.setBackground(roundRect(Color.TRANSPARENT,dp(24),0,0)); v.setClickable(true); return v; }\n\n'''
if anchor not in s:
    raise SystemExit('v2.0 home: iconButton anchor not found')
helpers = r'''    private void addHomeServices(LinearLayout root) {
        TextView discover = new TextView(this);
        discover.setText("Get more books");
        discover.setTextSize(15);
        discover.setTextColor(Color.rgb(60, 64, 67));
        discover.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        LinearLayout.LayoutParams hlp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(34));
        hlp.leftMargin = dp(20); hlp.rightMargin = dp(20); hlp.topMargin = dp(2);
        root.addView(discover, hlp);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(16), 0, dp(16), 0);
        LinearLayout.LayoutParams first = new LinearLayout.LayoutParams(0, dp(76), 1f);
        first.rightMargin = dp(6);
        row.addView(homeLinkCard("T", "Telegram", "@TheBookR", Color.rgb(229, 244, 253), "https://t.me/TheBookR"), first);
        LinearLayout.LayoutParams second = new LinearLayout.LayoutParams(0, dp(76), 1f);
        second.leftMargin = dp(6);
        row.addView(homeLinkCard("W", "Website", "saroatsin.com", Color.rgb(239, 246, 239), "https://saroatsin.com"), second);
        root.addView(row, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(80)));

        LinearLayout google = new LinearLayout(this);
        google.setOrientation(LinearLayout.HORIZONTAL);
        google.setGravity(Gravity.CENTER_VERTICAL);
        google.setPadding(dp(14), dp(8), dp(12), dp(8));
        google.setBackground(roundRect(Color.rgb(250, 251, 252), dp(14), dp(1), Color.rgb(225, 229, 235)));
        google.setClickable(true);
        google.setOnClickListener(v -> showCloudMenu());

        TextView icon = new TextView(this);
        icon.setText("G");
        icon.setTextSize(18);
        icon.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        icon.setTextColor(Color.rgb(66, 133, 244));
        icon.setGravity(Gravity.CENTER);
        icon.setBackground(roundRect(Color.WHITE, dp(22), dp(1), Color.rgb(220, 224, 230)));
        google.addView(icon, new LinearLayout.LayoutParams(dp(44), dp(44)));

        LinearLayout copy = new LinearLayout(this);
        copy.setOrientation(LinearLayout.VERTICAL);
        copy.setPadding(dp(12), 0, dp(8), 0);
        TextView title = new TextView(this);
        title.setText("Google Drive sync");
        title.setTextSize(15);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setTextColor(Color.rgb(32, 33, 36));
        copy.addView(title);
        googleStatusView = new TextView(this);
        googleStatusView.setTextSize(12);
        googleStatusView.setTextColor(Color.rgb(95, 99, 104));
        googleStatusView.setSingleLine(true);
        copy.addView(googleStatusView);
        google.addView(copy, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView arrow = new TextView(this);
        arrow.setText("›");
        arrow.setTextSize(28);
        arrow.setTextColor(Color.rgb(95, 99, 104));
        arrow.setGravity(Gravity.CENTER);
        google.addView(arrow, new LinearLayout.LayoutParams(dp(30), dp(44)));

        LinearLayout.LayoutParams glp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(64));
        glp.leftMargin = dp(16); glp.rightMargin = dp(16); glp.topMargin = dp(7); glp.bottomMargin = dp(5);
        root.addView(google, glp);
        updateGoogleStatus();
    }

    private View homeLinkCard(String letter, String title, String subtitle, int background, String url) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(10), dp(8), dp(8), dp(8));
        card.setBackground(roundRect(background, dp(14), 0, 0));
        card.setClickable(true);
        card.setOnClickListener(v -> openExternal(url));

        TextView badge = new TextView(this);
        badge.setText(letter);
        badge.setTextSize(16);
        badge.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        badge.setTextColor(Color.rgb(45, 55, 65));
        badge.setGravity(Gravity.CENTER);
        badge.setBackground(roundRect(Color.argb(145, 255, 255, 255), dp(20), 0, 0));
        card.addView(badge, new LinearLayout.LayoutParams(dp(40), dp(40)));

        LinearLayout copy = new LinearLayout(this);
        copy.setOrientation(LinearLayout.VERTICAL);
        copy.setPadding(dp(9), 0, dp(2), 0);
        TextView t = new TextView(this);
        t.setText(title); t.setTextSize(14); t.setTypeface(Typeface.DEFAULT, Typeface.BOLD); t.setTextColor(Color.rgb(32, 33, 36));
        TextView sub = new TextView(this);
        sub.setText(subtitle); sub.setTextSize(11); sub.setTextColor(Color.rgb(95, 99, 104)); sub.setSingleLine(true);
        copy.addView(t); copy.addView(sub);
        card.addView(copy, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return card;
    }

    private void openExternal(String url) {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            startActivity(i);
        } catch (Exception e) {
            Toast.makeText(this, "Unable to open link", Toast.LENGTH_SHORT).show();
        }
    }

    private void updateGoogleStatus() {
        if (googleStatusView == null || prefs == null) return;
        if (googleSyncBusy) {
            googleStatusView.setText("Syncing your library…");
            return;
        }
        if (prefs.getBoolean("google_drive_connected", false)) {
            String email = prefs.getString("google_drive_email", "");
            long last = prefs.getLong("last_google_sync_ms", 0L);
            if (email != null && !email.isEmpty()) googleStatusView.setText(email + (last > 0 ? " · synced" : ""));
            else googleStatusView.setText(last > 0 ? "Google Drive connected · synced" : "Google Drive connected");
        } else {
            googleStatusView.setText("Connect your Google account · books stay in your Drive");
        }
    }

'''
s = s.replace(anchor, anchor + helpers, 1)

# Importing a book should quietly schedule cloud sync when already connected.
old = '''runOnUiThread(()->{Toast.makeText(this,"Added to WoW Reader",Toast.LENGTH_SHORT).show();refreshLibrary();if(openAfter)openBook(out);});'''
new = '''runOnUiThread(()->{Toast.makeText(this,"Added to WoW Reader",Toast.LENGTH_SHORT).show();refreshLibrary();if(prefs.getBoolean("google_drive_connected",false))booksContainer.postDelayed(()->requestGoogleDriveSync(false),350);if(openAfter)openBook(out);});'''
if old not in s:
    raise SystemExit('v2.0 home: import completion anchor not found')
s = s.replace(old, new, 1)

# Replace legacy cloud picker menu / activity result with Google account sync + manual fallback.
start = s.index('    private void showCloudMenu(){')
end = s.index('\n    private void backupLibrary', start)
cloud = r'''    private void showCloudMenu() {
        boolean connected = prefs.getBoolean("google_drive_connected", false);
        String email = prefs.getString("google_drive_email", "");
        if (connected) {
            String account = (email == null || email.isEmpty()) ? "Google account connected" : email;
            new AlertDialog.Builder(this)
                    .setTitle("Google Drive")
                    .setMessage("WoW Reader keeps its EPUB/PDF library in a ‘WoW Reader’ folder in your own Google Drive.")
                    .setItems(new String[]{"Sync now", "Account · " + account, "Disconnect Google Drive", "Manual folder backup", "Manual folder restore"}, (dialog, which) -> {
                        if (which == 0) requestGoogleDriveSync(true);
                        else if (which == 2) disconnectGoogleDrive();
                        else if (which == 3) launchManualDrivePicker(true);
                        else if (which == 4) launchManualDrivePicker(false);
                    })
                    .setNegativeButton("Close", null)
                    .show();
        } else {
            new AlertDialog.Builder(this)
                    .setTitle("Google Drive")
                    .setMessage("Connect a Google account to automatically restore your books and reading state on another device. WoW Reader requests access only to Drive files it creates or you use with the app.")
                    .setItems(new String[]{"Connect Google Drive", "Manual folder backup", "Manual folder restore"}, (dialog, which) -> {
                        if (which == 0) requestGoogleDriveSync(true);
                        else if (which == 1) launchManualDrivePicker(true);
                        else if (which == 2) launchManualDrivePicker(false);
                    })
                    .setNegativeButton("Close", null)
                    .show();
        }
    }

    private void launchManualDrivePicker(boolean backup) {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(i, backup ? REQ_BACKUP : REQ_RESTORE);
    }

    private List<Scope> driveScopes() {
        return Arrays.asList(new Scope("https://www.googleapis.com/auth/drive.file"));
    }

    private void requestGoogleDriveSync(boolean userInitiated) {
        if (googleSyncBusy || prefs == null) return;
        googleSyncBusy = true;
        pendingGoogleSyncUserInitiated = userInitiated;
        updateGoogleStatus();

        AuthorizationRequest.Builder builder = AuthorizationRequest.builder().setRequestedScopes(driveScopes());
        if (userInitiated && !prefs.getBoolean("google_drive_connected", false))
            builder.setPrompt(AuthorizationRequest.Prompt.SELECT_ACCOUNT);

        Identity.getAuthorizationClient(this)
                .authorize(builder.build())
                .addOnSuccessListener(result -> {
                    if (result.hasResolution()) {
                        try {
                            startIntentSenderForResult(result.getPendingIntent().getIntentSender(), REQ_GOOGLE_AUTH,
                                    null, 0, 0, 0);
                        } catch (IntentSender.SendIntentException e) {
                            googleSyncFailed(e);
                        }
                    } else {
                        handleGoogleAuthorization(result);
                    }
                })
                .addOnFailureListener(this::googleSyncFailed);
    }

    private void handleGoogleAuthorization(AuthorizationResult result) {
        if (result == null || result.getAccessToken() == null || result.getAccessToken().isEmpty()) {
            googleSyncFailed(new Exception("Google Drive authorization did not return an access token"));
            return;
        }
        startDriveSync(result.getAccessToken());
    }

    private void startDriveSync(String token) {
        GoogleDriveSync.sync(this, libraryDir, prefs, token, new GoogleDriveSync.Callback() {
            @Override public void onStatus(String status) {
                runOnUiThread(() -> { if (googleStatusView != null) googleStatusView.setText(status); });
            }

            @Override public void onComplete(GoogleDriveSync.Profile profile, int uploaded, int downloaded) {
                runOnUiThread(() -> {
                    googleSyncBusy = false;
                    pendingGoogleSyncUserInitiated = false;
                    refreshLibrary();
                    updateGoogleStatus();
                    String detail = "Google Drive synced";
                    if (uploaded > 0 || downloaded > 0)
                        detail += " · ↑" + uploaded + " ↓" + downloaded;
                    Toast.makeText(MainActivity.this, detail, Toast.LENGTH_LONG).show();
                });
            }

            @Override public void onError(String message) {
                runOnUiThread(() -> {
                    googleSyncBusy = false;
                    pendingGoogleSyncUserInitiated = false;
                    updateGoogleStatus();
                    Toast.makeText(MainActivity.this, message, Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void googleSyncFailed(Exception e) {
        googleSyncBusy = false;
        pendingGoogleSyncUserInitiated = false;
        updateGoogleStatus();
        String message = "Google Drive connection failed";
        if (e instanceof ApiException && ((ApiException) e).getStatusCode() == 10)
            message = "Google Drive OAuth setup is required for this APK";
        else if (e != null && e.getMessage() != null && !e.getMessage().trim().isEmpty())
            message += ": " + e.getMessage();
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    private void maybeAutoSync() {
        if (prefs == null || googleSyncBusy || !prefs.getBoolean("google_drive_connected", false)) return;
        long now = System.currentTimeMillis();
        if (now - lastAutoSyncAttemptMs < 60_000L) return;
        lastAutoSyncAttemptMs = now;
        long last = prefs.getLong("last_google_sync_ms", 0L);
        if (now - last >= 15L * 60L * 1000L) requestGoogleDriveSync(false);
    }

    private void disconnectGoogleDrive() {
        new AlertDialog.Builder(this)
                .setTitle("Disconnect Google Drive?")
                .setMessage("Books already stored in your Google Drive will stay there. This device will stop automatic syncing until you connect again.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Disconnect", (d, w) -> {
                    String email = prefs.getString("google_drive_email", "");
                    if (email == null || email.isEmpty()) {
                        clearGoogleConnection();
                        return;
                    }
                    try {
                        RevokeAccessRequest request = RevokeAccessRequest.builder()
                                .setAccount(new Account(email, "com.google"))
                                .setScopes(driveScopes())
                                .build();
                        Identity.getAuthorizationClient(this).revokeAccess(request)
                                .addOnCompleteListener(task -> clearGoogleConnection());
                    } catch (Exception e) {
                        clearGoogleConnection();
                    }
                })
                .show();
    }

    private void clearGoogleConnection() {
        prefs.edit()
                .remove("google_drive_connected")
                .remove("google_drive_email")
                .remove("google_drive_name")
                .remove("last_google_sync_ms")
                .apply();
        googleSyncBusy = false;
        updateGoogleStatus();
        Toast.makeText(this, "Google Drive disconnected", Toast.LENGTH_SHORT).show();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == REQ_GOOGLE_AUTH) {
            if (resultCode != RESULT_OK || data == null) {
                googleSyncBusy = false;
                pendingGoogleSyncUserInitiated = false;
                updateGoogleStatus();
                return;
            }
            try {
                AuthorizationResult result = Identity.getAuthorizationClient(this).getAuthorizationResultFromIntent(data);
                handleGoogleAuthorization(result);
            } catch (Exception e) {
                googleSyncFailed(e);
            }
            return;
        }

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
        else if (requestCode == REQ_RESTORE) restoreLibrary(uri);
    }
'''
s = s[:start] + cloud + s[end:]

# Static contract checks.
assert 'https://t.me/TheBookR' in s
assert 'https://saroatsin.com' in s
assert 'https://www.googleapis.com/auth/drive.file' in s
assert 'AuthorizationRequest.Prompt.SELECT_ACCOUNT' in s
assert 'GoogleDriveSync.sync' in s
assert 'maybeAutoSync()' in s
assert 'Google Drive sync' in s
assert 'Manual folder backup' in s

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.0 home discovery + Google Drive sync patch applied')
