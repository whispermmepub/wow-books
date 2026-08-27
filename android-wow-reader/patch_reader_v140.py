from pathlib import Path
import re

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/BookReaderActivity.java')
s = path.read_text(encoding='utf-8')

# Android 13+ predictive/system back must be captured explicitly. This prevents an
# edge-back gesture from finishing the reader activity while the user is reading.
if 'import android.os.Build;\n' not in s:
    s = s.replace('import android.os.Bundle;\n', 'import android.os.Bundle;\nimport android.os.Build;\n')
if 'import android.window.OnBackInvokedDispatcher;\n' not in s:
    s = s.replace('import android.view.ViewGroup;\n', 'import android.view.ViewGroup;\nimport android.window.OnBackInvokedDispatcher;\n')

# Register the Android 13+ back callback after the UI exists.
old = '        buildReaderUi();\n        if (isPdf) openPdf(); else openEpub();\n'
new = '        buildReaderUi();\n        registerSystemBackGuard();\n        if (isPdf) openPdf(); else openEpub();\n'
if old not in s:
    raise SystemExit('Could not find onCreate reader startup')
s = s.replace(old, new, 1)

# In page mode, disable horizontal swipe page turning. Edge swipes belong to the
# Android navigation system and were the main source of accidental reader exits.
# Page mode still supports left/right screen taps and the optional bottom arrows.
s, n_touch = re.subn(
    r'\n\s*"document\.addEventListener\(\'touchend\'.*?\);" \+\n',
    '\n',
    s,
    count=1
)
if n_touch != 1:
    raise SystemExit('Could not remove page swipe touchend handler')

# Side-tap behaviour:
#   Page mode   -> left/right = previous/next page, center = controls
#   Scroll mode -> left/right = previous/next chapter, center = controls
# Keep real EPUB links clickable and do not navigate while text is selected.
new_click = '''                "document.addEventListener('click',function(e){if(Date.now()<suppress)return;if(window.getSelection&&String(window.getSelection()).length>0)return;var node=e.target;while(node&&node!==document){if(node.tagName&&node.tagName.toLowerCase()==='a')return;node=node.parentNode;}var x=e.clientX/window.innerWidth;if(window.__wowMode==='page'){if(x<0.30)window.__wowTurn(-1);else if(x>0.70)window.__wowTurn(1);else WoW.toggle();}else{if(x<0.24)WoW.prevChapter();else if(x>0.76)WoW.nextChapter();else WoW.toggle();}});" +\n'''
s, n_click = re.subn(
    r'\s*"document\.addEventListener\(\'click\'.*?\);" \+\n',
    new_click,
    s,
    count=1
)
if n_click != 1:
    raise SystemExit('Could not replace reader click handler')

# Add one shared back handler and register it with OnBackInvokedDispatcher on API 33+.
# Legacy Android versions continue to use onBackPressed(). Only the visible top-left
# back button intentionally calls finish().
marker = '    @Override public void onWindowFocusChanged(boolean hasFocus){\n'
if marker not in s:
    raise SystemExit('Could not find window-focus method for back guard insertion')
back_guard = '''    private void registerSystemBackGuard(){
        if(Build.VERSION.SDK_INT >= 33){
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT,
                    this::handleSystemBack);
        }
    }

    private void handleSystemBack(){
        enterImmersive();
        showControlsTemporarily();
        long now = System.currentTimeMillis();
        if(now > backArmedUntil){
            backArmedUntil = now + 1600L;
            Toast.makeText(this,"Use ‹ to return to Library",Toast.LENGTH_SHORT).show();
        }
    }

'''
s = s.replace(marker, back_guard + marker, 1)

s, n_back = re.subn(
    r'    @Override public void onBackPressed\(\)\{.*?\n    \}\n',
    '''    @Override public void onBackPressed(){
        handleSystemBack();
    }
''',
    s,
    count=1,
    flags=re.S
)
if n_back != 1:
    raise SystemExit('Could not replace legacy onBackPressed')

path.write_text(s, encoding='utf-8')
print('WoW Reader v1.4.0 reader patch applied')
