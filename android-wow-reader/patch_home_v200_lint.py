from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/MainActivity.java')
s = path.read_text(encoding='utf-8')

old = '''    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {\n'''
new = '''    @SuppressLint("WrongConstant")\n    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {\n'''
if old not in s:
    raise SystemExit('v2.0 lint: onActivityResult anchor not found')
s = s.replace(old, new, 1)

assert '@SuppressLint("WrongConstant")' in s
path.write_text(s, encoding='utf-8')
print('WoW Reader v2.0 SAF lint annotation restored')
