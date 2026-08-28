from pathlib import Path

path = Path('android-wow-reader/app/src/main/java/com/whisper/wowreader/MainActivity.java')
s = path.read_text(encoding='utf-8')

# Insert a clean 2x2 discovery section above the user's local library.
anchor = '''        LinearLayout section = new LinearLayout(this); section.setGravity(Gravity.CENTER_VERTICAL); section.setPadding(dp(20),dp(10),dp(20),dp(6));\n'''
if anchor not in s:
    raise SystemExit('v2.3 home: library section anchor not found')
s = s.replace(anchor, '''        addDiscoverySection(root);\n\n''' + anchor, 1)

anchor = '''    private TextView iconButton(String text) { TextView v=new TextView(this); v.setText(text); v.setTextSize(22); v.setTextColor(Color.rgb(70,71,75)); v.setGravity(Gravity.CENTER); v.setBackground(roundRect(Color.TRANSPARENT,dp(24),0,0)); v.setClickable(true); return v; }\n\n'''
if anchor not in s:
    raise SystemExit('v2.3 home: iconButton anchor not found')

helpers = r'''    private void addDiscoverySection(LinearLayout root) {
        TextView heading = new TextView(this);
        heading.setText("Discover & community");
        heading.setTextSize(15);
        heading.setTextColor(Color.rgb(60, 64, 67));
        heading.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        LinearLayout.LayoutParams hlp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(34));
        hlp.leftMargin = dp(20); hlp.rightMargin = dp(20); hlp.topMargin = dp(2);
        root.addView(heading, hlp);

        LinearLayout row1 = new LinearLayout(this);
        row1.setOrientation(LinearLayout.HORIZONTAL);
        row1.setPadding(dp(16), 0, dp(16), 0);
        LinearLayout.LayoutParams left = new LinearLayout.LayoutParams(0, dp(72), 1f);
        left.rightMargin = dp(6);
        row1.addView(discoveryCard("T", "Telegram Channel", "New books", Color.rgb(229, 244, 253), "https://t.me/TheBookR"), left);
        LinearLayout.LayoutParams right = new LinearLayout.LayoutParams(0, dp(72), 1f);
        right.leftMargin = dp(6);
        row1.addView(discoveryCard("D", "Discussion", "Reader community", Color.rgb(238, 240, 255), "https://t.me/+rUiqzi2mdhNiNGZl"), right);
        root.addView(row1, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(76)));

        LinearLayout row2 = new LinearLayout(this);
        row2.setOrientation(LinearLayout.HORIZONTAL);
        row2.setPadding(dp(16), 0, dp(16), 0);
        LinearLayout.LayoutParams left2 = new LinearLayout.LayoutParams(0, dp(72), 1f);
        left2.rightMargin = dp(6);
        row2.addView(discoveryCard("W", "Book Website", "saroatsin.com", Color.rgb(239, 247, 240), "https://saroatsin.com"), left2);
        LinearLayout.LayoutParams right2 = new LinearLayout.LayoutParams(0, dp(72), 1f);
        right2.leftMargin = dp(6);
        row2.addView(discoveryCard("R", "Book Reviews", "အညွှန်း & review", Color.rgb(253, 242, 232), "https://whispermmepub.github.io/Review/"), right2);
        LinearLayout.LayoutParams row2lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(78));
        row2lp.bottomMargin = dp(3);
        root.addView(row2, row2lp);
    }

    private View discoveryCard(String letter, String title, String subtitle, int background, String url) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(10), dp(8), dp(8), dp(8));
        card.setBackground(roundRect(background, dp(14), 0, 0));
        card.setClickable(true);
        card.setElevation(dp(1));
        card.setOnClickListener(v -> openExternal(url));

        TextView badge = new TextView(this);
        badge.setText(letter);
        badge.setTextSize(16);
        badge.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        badge.setTextColor(Color.rgb(45, 55, 65));
        badge.setGravity(Gravity.CENTER);
        badge.setBackground(roundRect(Color.argb(155, 255, 255, 255), dp(20), 0, 0));
        card.addView(badge, new LinearLayout.LayoutParams(dp(40), dp(40)));

        LinearLayout copy = new LinearLayout(this);
        copy.setOrientation(LinearLayout.VERTICAL);
        copy.setPadding(dp(9), 0, dp(1), 0);
        TextView t = new TextView(this);
        t.setText(title);
        t.setTextSize(13);
        t.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        t.setTextColor(Color.rgb(32, 33, 36));
        t.setMaxLines(1);
        TextView sub = new TextView(this);
        sub.setText(subtitle);
        sub.setTextSize(10);
        sub.setTextColor(Color.rgb(95, 99, 104));
        sub.setMaxLines(1);
        copy.addView(t);
        copy.addView(sub);
        card.addView(copy, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return card;
    }

    private void openExternal(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            Toast.makeText(this, "Unable to open link", Toast.LENGTH_SHORT).show();
        }
    }

'''
s = s.replace(anchor, anchor + helpers, 1)

# Google-account sync is intentionally not surfaced in v2.3. Keep the existing
# manual Storage Access Framework backup/restore as the only cloud-style menu.
s = s.replace('setTitle("Cloud / Google Drive")', 'setTitle("Backup & restore")', 1)

path.write_text(s, encoding='utf-8')
print('WoW Reader v2.3 home discovery links patch applied')
