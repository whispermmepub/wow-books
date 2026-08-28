from pathlib import Path

p = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/MainActivity.java')
s = p.read_text(encoding='utf-8')
old = 'Arrays.sort(all, Comparator.comparingLong(File::lastModified).reversed());'
new = 'Arrays.sort(all, (a, b) -> Long.compare(b.lastModified(), a.lastModified()));'
if old not in s:
    raise SystemExit('Android 23 compatibility sort anchor not found')
s = s.replace(old, new, 1)
s = s.replace('import java.util.Comparator;\n', '')
p.write_text(s, encoding='utf-8')
print('Android 23 compatibility patch applied')
