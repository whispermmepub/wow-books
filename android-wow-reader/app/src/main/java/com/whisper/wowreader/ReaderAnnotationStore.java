package com.whisper.wowreader;

import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public final class ReaderAnnotationStore {
    private ReaderAnnotationStore() {}

    public static final class Annotation {
        public String id = "";
        public int chapter = 0;
        public int start = 0;
        public int end = 0;
        public String quote = "";
        public String color = "rgba(255,235,59,.48)";
        public String note = "";
        public long createdMs = 0L;

        JSONObject toJson() throws Exception {
            JSONObject o = new JSONObject();
            o.put("id", id);
            o.put("chapter", chapter);
            o.put("start", start);
            o.put("end", end);
            o.put("quote", quote);
            o.put("color", color);
            o.put("note", note);
            o.put("created_ms", createdMs);
            return o;
        }

        static Annotation fromJson(JSONObject o) {
            Annotation a = new Annotation();
            a.id = o.optString("id", "");
            a.chapter = Math.max(0, o.optInt("chapter", 0));
            a.start = Math.max(0, o.optInt("start", 0));
            a.end = Math.max(a.start, o.optInt("end", a.start));
            a.quote = o.optString("quote", "");
            a.color = o.optString("color", "rgba(255,235,59,.48)");
            a.note = o.optString("note", "");
            a.createdMs = o.optLong("created_ms", 0L);
            return a;
        }
    }

    private static String key(String bookName) {
        String value = bookName == null ? "book" : bookName;
        return "annotations_" + Integer.toHexString(value.hashCode());
    }

    public static List<Annotation> load(SharedPreferences prefs, String bookName) {
        List<Annotation> result = new ArrayList<>();
        if (prefs == null) return result;
        try {
            JSONArray arr = new JSONArray(prefs.getString(key(bookName), "[]"));
            for (int i = 0; i < arr.length(); i++) {
                Annotation a = Annotation.fromJson(arr.optJSONObject(i));
                if (a.id != null && !a.id.isEmpty() && a.end > a.start) result.add(a);
            }
        } catch (Exception ignored) {
        }
        return result;
    }

    public static List<Annotation> forChapter(SharedPreferences prefs, String bookName, int chapter) {
        List<Annotation> result = new ArrayList<>();
        for (Annotation a : load(prefs, bookName)) if (a.chapter == chapter) result.add(a);
        return result;
    }

    public static Annotation add(SharedPreferences prefs, String bookName, int chapter,
                                 int start, int end, String quote, String color, String note) {
        Annotation a = new Annotation();
        a.chapter = Math.max(0, chapter);
        a.start = Math.max(0, start);
        a.end = Math.max(a.start, end);
        a.quote = quote == null ? "" : quote.trim();
        a.color = color == null || color.isEmpty() ? "rgba(255,235,59,.48)" : color;
        a.note = note == null ? "" : note.trim();
        a.createdMs = System.currentTimeMillis();
        a.id = Long.toHexString(a.createdMs) + "_" + Integer.toHexString((a.quote + ":" + a.start + ":" + chapter).hashCode());

        List<Annotation> items = load(prefs, bookName);
        items.add(a);
        save(prefs, bookName, items);
        return a;
    }

    public static void remove(SharedPreferences prefs, String bookName, String id) {
        List<Annotation> items = load(prefs, bookName);
        for (int i = items.size() - 1; i >= 0; i--) {
            if (items.get(i).id.equals(id)) items.remove(i);
        }
        save(prefs, bookName, items);
    }

    public static Annotation find(SharedPreferences prefs, String bookName, String id) {
        for (Annotation a : load(prefs, bookName)) if (a.id.equals(id)) return a;
        return null;
    }

    public static int count(SharedPreferences prefs, String bookName) {
        return load(prefs, bookName).size();
    }

    public static String chapterJson(SharedPreferences prefs, String bookName, int chapter) {
        JSONArray arr = new JSONArray();
        for (Annotation a : forChapter(prefs, bookName, chapter)) {
            try { arr.put(a.toJson()); } catch (Exception ignored) {}
        }
        return arr.toString();
    }

    private static void save(SharedPreferences prefs, String bookName, List<Annotation> items) {
        if (prefs == null) return;
        JSONArray arr = new JSONArray();
        for (Annotation a : items) {
            try { arr.put(a.toJson()); } catch (Exception ignored) {}
        }
        prefs.edit()
                .putString(key(bookName), arr.toString())
                .putLong("sync_updated_ms", System.currentTimeMillis())
                .apply();
    }
}
