from pathlib import Path

# MainActivity: keep sorting compatible with API 23 and document the valid dynamic
# read/write persistable-permission bitmask for Android Lint.
p = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/MainActivity.java')
s = p.read_text(encoding='utf-8')
old = 'Arrays.sort(all, Comparator.comparingLong(File::lastModified).reversed());'
new = 'Arrays.sort(all, (a, b) -> Long.compare(b.lastModified(), a.lastModified()));'
if old not in s:
    raise SystemExit('Android 23 compatibility sort anchor not found')
s = s.replace(old, new, 1)
s = s.replace('import java.util.Comparator;\n', '')
if 'import android.annotation.SuppressLint;\n' not in s:
    s = s.replace('import android.app.Activity;\n', 'import android.annotation.SuppressLint;\nimport android.app.Activity;\n', 1)
old_activity_result = '    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data)'
if old_activity_result not in s:
    raise SystemExit('onActivityResult anchor not found')
s = s.replace(old_activity_result, '    @SuppressLint("WrongConstant")\n' + old_activity_result, 1)
p.write_text(s, encoding='utf-8')

# This is a file MIME-type VIEW filter, not a web/app-link filter. BROWSABLE is not
# needed for Android's document "Open with" flow. Android Lint's AppLink checker
# nevertheless treats ACTION_VIEW as a web link, so explicitly suppress only that
# irrelevant check on this MIME filter.
manifest = Path('android-wow-reader/app/src/main/AndroidManifest.xml')
m = manifest.read_text(encoding='utf-8')
if 'xmlns:tools=' not in m:
    m = m.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
                  '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n    xmlns:tools="http://schemas.android.com/tools">', 1)
browsable = '                <category android:name="android.intent.category.BROWSABLE" />\n'
if browsable in m:
    m = m.replace(browsable, '', 1)
view_filter = '''            <intent-filter>\n                <action android:name="android.intent.action.VIEW" />'''
view_filter_ignored = '''            <intent-filter tools:ignore="AppLinkUrlError">\n                <action android:name="android.intent.action.VIEW" />'''
if view_filter not in m:
    if view_filter_ignored not in m:
        raise SystemExit('VIEW MIME intent-filter anchor not found')
else:
    m = m.replace(view_filter, view_filter_ignored, 1)
manifest.write_text(m, encoding='utf-8')

print('Android 23 and lint compatibility patch applied')
