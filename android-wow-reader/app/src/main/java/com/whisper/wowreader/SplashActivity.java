package com.whisper.wowreader;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

public class SplashActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable openLibrary = () -> {
        startActivity(new Intent(this, MainActivity.class));
        finish();
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().setStatusBarColor(Color.rgb(9, 60, 105));
        getWindow().setNavigationBarColor(Color.rgb(9, 60, 105));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(dp(28), dp(28), dp(28), dp(28));
        root.setBackgroundColor(Color.rgb(9, 60, 105));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.wow_logo);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        root.addView(logo, new LinearLayout.LayoutParams(dp(180), dp(180)));

        TextView title = new TextView(this);
        title.setText("WoW Reader");
        title.setTextColor(Color.WHITE);
        title.setTextSize(28);
        title.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        titleLp.topMargin = dp(18);
        root.addView(title, titleLp);

        TextView sub = new TextView(this);
        sub.setText("Whisper Of Words");
        sub.setTextColor(Color.rgb(206, 229, 244));
        sub.setTextSize(14);
        sub.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams subLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        subLp.topMargin = dp(6);
        root.addView(sub, subLp);

        setContentView(root);
        handler.postDelayed(openLibrary, 420);
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(openLibrary);
        super.onDestroy();
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
