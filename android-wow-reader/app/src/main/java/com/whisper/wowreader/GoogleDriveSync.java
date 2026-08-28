package com.whisper.wowreader;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;

public final class GoogleDriveSync {
    private static final String API = "https://www.googleapis.com/drive/v3";
    private static final String UPLOAD = "https://www.googleapis.com/upload/drive/v3";
    private static final String FOLDER_NAME = "WoW Reader";
    private static final String STATE_NAME = ".wow-reader-state.json";

    private GoogleDriveSync() {}

    public static final class Profile {
        public String displayName = "";
        public String email = "";
    }

    public interface Callback {
        void onStatus(String status);
        void onComplete(Profile profile, int uploaded, int downloaded);
        void onError(String message);
    }

    private static final class RemoteFile {
        String id;
        String name;
        String mimeType;
        long size;
        long modifiedMs;
    }

    public static void sync(Context context, File libraryDir, SharedPreferences prefs,
                            String accessToken, Callback callback) {
        new Thread(() -> {
            int uploaded = 0;
            int downloaded = 0;
            try {
                callback.onStatus("Connecting to Google Drive…");
                Profile profile = fetchProfile(accessToken);
                String folderId = findOrCreateFolder(accessToken);

                callback.onStatus("Checking your cloud library…");
                List<RemoteFile> remoteFiles = listChildren(accessToken, folderId);
                Map<String, RemoteFile> remoteByName = newestByName(remoteFiles);

                // Restore the newest reading/settings state before reconciling files.
                RemoteFile remoteState = remoteByName.get(STATE_NAME);
                long localStateUpdated = prefs.getLong("sync_updated_ms", 0L);
                if (remoteState != null) {
                    try {
                        JSONObject state = new JSONObject(downloadText(accessToken, remoteState.id));
                        long remoteStateUpdated = state.optLong("updated_ms", 0L);
                        if (remoteStateUpdated > localStateUpdated) {
                            applyState(prefs, state);
                            localStateUpdated = remoteStateUpdated;
                        }
                    } catch (Exception ignored) {
                    }
                }

                File[] locals = libraryDir.listFiles(file -> file.isFile() && isBook(file.getName()));
                if (locals == null) locals = new File[0];
                Map<String, File> localByName = new HashMap<>();
                for (File f : locals) localByName.put(f.getName(), f);

                // Local books win only when they are newer. Otherwise the Drive copy wins.
                for (File local : locals) {
                    RemoteFile remote = remoteByName.get(local.getName());
                    if (remote == null) {
                        callback.onStatus("Uploading " + local.getName());
                        uploadNewFile(accessToken, folderId, local.getName(), mimeFor(local.getName()), local);
                        uploaded++;
                    } else if (remote.size != local.length()) {
                        if (remote.modifiedMs > local.lastModified() + 2000L) {
                            callback.onStatus("Restoring " + remote.name);
                            downloadToFile(accessToken, remote, local);
                            downloaded++;
                        } else {
                            callback.onStatus("Updating " + local.getName());
                            deleteFile(accessToken, remote.id);
                            uploadNewFile(accessToken, folderId, local.getName(), mimeFor(local.getName()), local);
                            uploaded++;
                        }
                    }
                }

                // Files that exist only in Drive are restored to this device.
                for (RemoteFile remote : remoteFiles) {
                    if (!isBook(remote.name) || localByName.containsKey(remote.name)) continue;
                    callback.onStatus("Downloading " + remote.name);
                    File out = new File(libraryDir, safeName(remote.name));
                    downloadToFile(accessToken, remote, out);
                    downloaded++;
                }

                // Push the merged reading state. The file is tiny, so replacing it is safest.
                JSONObject state = buildState(prefs);
                RemoteFile oldState = remoteByName.get(STATE_NAME);
                if (oldState != null) deleteFile(accessToken, oldState.id);
                uploadBytes(accessToken, folderId, STATE_NAME, "application/json",
                        state.toString().getBytes(StandardCharsets.UTF_8));

                prefs.edit()
                        .putBoolean("google_drive_connected", true)
                        .putString("google_drive_email", profile.email == null ? "" : profile.email)
                        .putString("google_drive_name", profile.displayName == null ? "" : profile.displayName)
                        .putLong("last_google_sync_ms", System.currentTimeMillis())
                        .apply();

                callback.onComplete(profile, uploaded, downloaded);
            } catch (Exception e) {
                callback.onError(cleanMessage(e));
            }
        }, "wow-drive-sync").start();
    }

    private static Profile fetchProfile(String token) {
        Profile p = new Profile();
        try {
            String body = getText(API + "/about?fields=user(displayName,emailAddress)", token);
            JSONObject user = new JSONObject(body).optJSONObject("user");
            if (user != null) {
                p.displayName = user.optString("displayName", "");
                p.email = user.optString("emailAddress", "");
            }
        } catch (Exception ignored) {
        }
        return p;
    }

    private static String findOrCreateFolder(String token) throws Exception {
        String q = "mimeType='application/vnd.google-apps.folder' and name='" +
                escapeDriveQuery(FOLDER_NAME) + "' and trashed=false";
        String url = API + "/files?spaces=drive&pageSize=20&fields=files(id,name,modifiedTime)&q=" + enc(q);
        JSONArray files = new JSONObject(getText(url, token)).optJSONArray("files");
        if (files != null && files.length() > 0) return files.getJSONObject(0).getString("id");

        JSONObject meta = new JSONObject();
        meta.put("name", FOLDER_NAME);
        meta.put("mimeType", "application/vnd.google-apps.folder");
        String body = sendJson(API + "/files?fields=id,name", "POST", token, meta.toString());
        return new JSONObject(body).getString("id");
    }

    private static List<RemoteFile> listChildren(String token, String folderId) throws Exception {
        String q = "'" + escapeDriveQuery(folderId) + "' in parents and trashed=false";
        String url = API + "/files?spaces=drive&pageSize=1000&fields=files(id,name,mimeType,size,modifiedTime)&q=" + enc(q);
        JSONArray arr = new JSONObject(getText(url, token)).optJSONArray("files");
        List<RemoteFile> result = new ArrayList<>();
        if (arr == null) return result;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.getJSONObject(i);
            RemoteFile f = new RemoteFile();
            f.id = o.optString("id", "");
            f.name = o.optString("name", "");
            f.mimeType = o.optString("mimeType", "");
            f.size = o.optLong("size", 0L);
            f.modifiedMs = parseDriveTime(o.optString("modifiedTime", ""));
            if (!f.id.isEmpty() && !f.name.isEmpty()) result.add(f);
        }
        return result;
    }

    private static Map<String, RemoteFile> newestByName(List<RemoteFile> files) {
        Map<String, RemoteFile> map = new HashMap<>();
        for (RemoteFile f : files) {
            RemoteFile old = map.get(f.name);
            if (old == null || f.modifiedMs >= old.modifiedMs) map.put(f.name, f);
        }
        return map;
    }

    private static JSONObject buildState(SharedPreferences prefs) throws Exception {
        JSONObject root = new JSONObject();
        long updated = Math.max(1L, prefs.getLong("sync_updated_ms", System.currentTimeMillis()));
        root.put("version", 1);
        root.put("updated_ms", updated);
        JSONObject values = new JSONObject();
        for (Map.Entry<String, ?> entry : prefs.getAll().entrySet()) {
            String key = entry.getKey();
            if (!shouldSyncPreference(key)) continue;
            Object v = entry.getValue();
            if (v instanceof String || v instanceof Boolean || v instanceof Integer || v instanceof Long || v instanceof Float)
                values.put(key, v);
        }
        root.put("values", values);
        return root;
    }

    private static void applyState(SharedPreferences prefs, JSONObject root) throws Exception {
        JSONObject values = root.optJSONObject("values");
        if (values == null) return;
        SharedPreferences.Editor editor = prefs.edit();
        Iterator<String> keys = values.keys();
        while (keys.hasNext()) {
            String key = keys.next();
            if (!shouldSyncPreference(key)) continue;
            Object v = values.opt(key);
            if (v instanceof Boolean) editor.putBoolean(key, (Boolean) v);
            else if (v instanceof Integer) editor.putInt(key, (Integer) v);
            else if (v instanceof Long) editor.putLong(key, (Long) v);
            else if (v instanceof Number) editor.putInt(key, ((Number) v).intValue());
            else if (v instanceof String) editor.putString(key, (String) v);
        }
        editor.putLong("sync_updated_ms", root.optLong("updated_ms", System.currentTimeMillis()));
        editor.apply();
    }

    private static boolean shouldSyncPreference(String key) {
        if (key == null || key.startsWith("google_") || key.equals("last_google_sync_ms")) return false;
        return key.startsWith("percent_") || key.startsWith("epub_chapter_") ||
                key.startsWith("epub_scroll_") || key.startsWith("marks_") ||
                key.startsWith("epub_") || key.startsWith("reader_") ||
                key.equals("library_grid") || key.equals("sync_updated_ms");
    }

    private static void uploadNewFile(String token, String folderId, String name,
                                      String mimeType, File source) throws Exception {
        String boundary = "wowreader_" + System.currentTimeMillis();
        HttpURLConnection c = open(UPLOAD + "/files?uploadType=multipart&fields=id,name,size,modifiedTime", "POST", token);
        c.setDoOutput(true);
        c.setChunkedStreamingMode(64 * 1024);
        c.setRequestProperty("Content-Type", "multipart/related; boundary=" + boundary);
        try (OutputStream raw = new BufferedOutputStream(c.getOutputStream());
             InputStream in = new BufferedInputStream(new FileInputStream(source))) {
            JSONObject meta = new JSONObject();
            meta.put("name", name);
            JSONArray parents = new JSONArray(); parents.put(folderId); meta.put("parents", parents);
            writeAscii(raw, "--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n");
            raw.write(meta.toString().getBytes(StandardCharsets.UTF_8));
            writeAscii(raw, "\r\n--" + boundary + "\r\nContent-Type: " + mimeType + "\r\n\r\n");
            copy(in, raw);
            writeAscii(raw, "\r\n--" + boundary + "--\r\n");
        }
        ensureSuccess(c);
        c.disconnect();
    }

    private static void uploadBytes(String token, String folderId, String name,
                                    String mimeType, byte[] bytes) throws Exception {
        String boundary = "wowreader_state_" + System.currentTimeMillis();
        HttpURLConnection c = open(UPLOAD + "/files?uploadType=multipart&fields=id,name", "POST", token);
        c.setDoOutput(true);
        c.setChunkedStreamingMode(16 * 1024);
        c.setRequestProperty("Content-Type", "multipart/related; boundary=" + boundary);
        try (OutputStream raw = new BufferedOutputStream(c.getOutputStream())) {
            JSONObject meta = new JSONObject();
            meta.put("name", name);
            JSONArray parents = new JSONArray(); parents.put(folderId); meta.put("parents", parents);
            writeAscii(raw, "--" + boundary + "\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n");
            raw.write(meta.toString().getBytes(StandardCharsets.UTF_8));
            writeAscii(raw, "\r\n--" + boundary + "\r\nContent-Type: " + mimeType + "\r\n\r\n");
            raw.write(bytes);
            writeAscii(raw, "\r\n--" + boundary + "--\r\n");
        }
        ensureSuccess(c);
        c.disconnect();
    }

    private static void downloadToFile(String token, RemoteFile remote, File target) throws Exception {
        File tmp = new File(target.getParentFile(), target.getName() + ".wowdownload");
        HttpURLConnection c = open(API + "/files/" + encPath(remote.id) + "?alt=media", "GET", token);
        int code = c.getResponseCode();
        if (code < 200 || code >= 300) throw responseError(c);
        try (InputStream in = new BufferedInputStream(c.getInputStream());
             OutputStream out = new BufferedOutputStream(new FileOutputStream(tmp))) {
            copy(in, out);
        } finally {
            c.disconnect();
        }
        if (target.exists() && !target.delete()) throw new Exception("Unable to replace " + target.getName());
        if (!tmp.renameTo(target)) {
            try (InputStream in = new FileInputStream(tmp); OutputStream out = new FileOutputStream(target)) { copy(in, out); }
            tmp.delete();
        }
        if (remote.modifiedMs > 0) target.setLastModified(remote.modifiedMs);
    }

    private static String downloadText(String token, String fileId) throws Exception {
        return getText(API + "/files/" + encPath(fileId) + "?alt=media", token);
    }

    private static void deleteFile(String token, String fileId) throws Exception {
        HttpURLConnection c = open(API + "/files/" + encPath(fileId), "DELETE", token);
        ensureSuccess(c);
        c.disconnect();
    }

    private static String getText(String url, String token) throws Exception {
        HttpURLConnection c = open(url, "GET", token);
        int code = c.getResponseCode();
        if (code < 200 || code >= 300) throw responseError(c);
        try (InputStream in = c.getInputStream()) {
            return new String(readAll(in), StandardCharsets.UTF_8);
        } finally {
            c.disconnect();
        }
    }

    private static String sendJson(String url, String method, String token, String json) throws Exception {
        HttpURLConnection c = open(url, method, token);
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
        c.setFixedLengthStreamingMode(bytes.length);
        try (OutputStream out = c.getOutputStream()) { out.write(bytes); }
        int code = c.getResponseCode();
        if (code < 200 || code >= 300) throw responseError(c);
        String result;
        try (InputStream in = c.getInputStream()) { result = new String(readAll(in), StandardCharsets.UTF_8); }
        c.disconnect();
        return result;
    }

    private static HttpURLConnection open(String url, String method, String token) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(20000);
        c.setReadTimeout(180000);
        c.setUseCaches(false);
        c.setRequestProperty("Authorization", "Bearer " + token);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("User-Agent", "WoWReader-Android");
        return c;
    }

    private static void ensureSuccess(HttpURLConnection c) throws Exception {
        int code = c.getResponseCode();
        if (code < 200 || code >= 300) throw responseError(c);
        InputStream in = c.getInputStream();
        if (in != null) try { while (in.read() != -1) {} } finally { in.close(); }
    }

    private static Exception responseError(HttpURLConnection c) {
        try {
            int code = c.getResponseCode();
            InputStream in = c.getErrorStream();
            String body = in == null ? "" : new String(readAll(in), StandardCharsets.UTF_8);
            if (code == 401) return new Exception("Google authorization expired. Please connect again.");
            if (code == 403) return new Exception("Google Drive access was denied or Drive API is not enabled.");
            String msg = body;
            try {
                JSONObject error = new JSONObject(body).optJSONObject("error");
                if (error != null) msg = error.optString("message", body);
            } catch (Exception ignored) {}
            return new Exception("Google Drive error " + code + (msg.isEmpty() ? "" : ": " + msg));
        } catch (Exception e) {
            return new Exception("Google Drive request failed");
        }
    }

    private static byte[] readAll(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        copy(in, out);
        return out.toByteArray();
    }

    private static void copy(InputStream in, OutputStream out) throws Exception {
        byte[] buf = new byte[64 * 1024];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        out.flush();
    }

    private static void writeAscii(OutputStream out, String s) throws Exception {
        out.write(s.getBytes(StandardCharsets.UTF_8));
    }

    private static String enc(String s) throws Exception {
        return URLEncoder.encode(s, "UTF-8").replace("+", "%20");
    }

    private static String encPath(String s) throws Exception {
        return URLEncoder.encode(s, "UTF-8").replace("+", "%20").replace("%2F", "/");
    }

    private static String escapeDriveQuery(String s) {
        return s.replace("\\", "\\\\").replace("'", "\\'");
    }

    private static boolean isBook(String name) {
        String n = name == null ? "" : name.toLowerCase(Locale.ROOT);
        return n.endsWith(".epub") || n.endsWith(".pdf");
    }

    private static String mimeFor(String name) {
        return name != null && name.toLowerCase(Locale.ROOT).endsWith(".pdf")
                ? "application/pdf" : "application/epub+zip";
    }

    private static String safeName(String name) {
        return name == null ? "book.epub" : name.replaceAll("[\\\\/:*?\"<>|]", "_");
    }

    private static long parseDriveTime(String value) {
        if (value == null || value.isEmpty()) return 0L;
        String s = value;
        try {
            int dot = s.indexOf('.');
            int z = s.indexOf('Z');
            if (dot > 0 && z > dot && z - dot > 4) s = s.substring(0, dot + 4) + "Z";
            SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US);
            f.setTimeZone(TimeZone.getTimeZone("UTC"));
            Date d = f.parse(s);
            return d == null ? 0L : d.getTime();
        } catch (Exception ignored) {
            try {
                SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
                f.setTimeZone(TimeZone.getTimeZone("UTC"));
                Date d = f.parse(value);
                return d == null ? 0L : d.getTime();
            } catch (Exception ignored2) { return 0L; }
        }
    }

    private static String cleanMessage(Exception e) {
        String m = e == null ? null : e.getMessage();
        if (m == null || m.trim().isEmpty()) return "Google Drive sync failed";
        if (m.length() > 220) m = m.substring(0, 220);
        return m;
    }
}
