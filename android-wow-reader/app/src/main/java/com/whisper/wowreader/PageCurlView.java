package com.whisper.wowreader;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Shader;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;

final class PageCurlView extends View {
    private static final int MESH_W = 28;
    private static final int MESH_H = 8;

    private final Paint meshPaint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final Paint shadowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint edgePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float[] verts = new float[(MESH_W + 1) * (MESH_H + 1) * 2];

    private Bitmap fromBitmap;
    private Bitmap toBitmap;
    private ValueAnimator animator;
    private float progress;
    private int direction = 1;
    private Runnable completion;

    PageCurlView(Context context) {
        super(context);
        setVisibility(GONE);
        setClickable(false);
        setLayerType(View.LAYER_TYPE_HARDWARE, null);
        edgePaint.setStrokeWidth(Math.max(1f, getResources().getDisplayMetrics().density));
    }

    boolean isBusy() {
        return getVisibility() == VISIBLE || (animator != null && animator.isRunning());
    }

    void hold(Bitmap current) {
        cancelAnimator(false);
        recycleBitmaps();
        fromBitmap = current;
        toBitmap = null;
        progress = 0f;
        direction = 1;
        setAlpha(1f);
        setVisibility(VISIBLE);
        bringToFront();
        invalidate();
    }

    void startCurl(Bitmap target, int direction, Runnable completion) {
        if (fromBitmap == null || target == null) {
            if (target != null && !target.isRecycled()) target.recycle();
            finishImmediately(completion);
            return;
        }
        this.toBitmap = target;
        this.direction = direction < 0 ? -1 : 1;
        this.completion = completion;
        this.progress = 0f;

        cancelAnimator(false);
        animator = ValueAnimator.ofFloat(0f, 1f);
        animator.setDuration(430L);
        animator.setInterpolator(new AccelerateDecelerateInterpolator());
        animator.addUpdateListener(a -> {
            progress = (float) a.getAnimatedValue();
            invalidate();
        });
        animator.addListener(new AnimatorListenerAdapter() {
            private boolean cancelled;

            @Override public void onAnimationCancel(Animator animation) {
                cancelled = true;
            }

            @Override public void onAnimationEnd(Animator animation) {
                Runnable done = PageCurlView.this.completion;
                PageCurlView.this.completion = null;
                PageCurlView.this.animator = null;
                setVisibility(GONE);
                recycleBitmaps();
                if (!cancelled && done != null) done.run();
            }
        });
        animator.start();
    }

    void release() {
        cancelAnimator(false);
        completion = null;
        setVisibility(GONE);
        recycleBitmaps();
    }

    private void finishImmediately(Runnable done) {
        setVisibility(GONE);
        recycleBitmaps();
        if (done != null) done.run();
    }

    private void cancelAnimator(boolean notify) {
        if (animator == null) return;
        Runnable old = completion;
        completion = null;
        ValueAnimator a = animator;
        animator = null;
        a.cancel();
        if (notify && old != null) old.run();
    }

    private void recycleBitmaps() {
        if (fromBitmap != null && !fromBitmap.isRecycled()) fromBitmap.recycle();
        if (toBitmap != null && toBitmap != fromBitmap && !toBitmap.isRecycled()) toBitmap.recycle();
        fromBitmap = null;
        toBitmap = null;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (fromBitmap == null || fromBitmap.isRecycled()) return;

        if (toBitmap == null || toBitmap.isRecycled()) {
            canvas.drawBitmap(fromBitmap, 0f, 0f, meshPaint);
            return;
        }

        if (direction > 0) {
            canvas.drawBitmap(toBitmap, 0f, 0f, meshPaint);
            drawCurledBitmap(canvas, fromBitmap, progress);
        } else {
            canvas.drawBitmap(fromBitmap, 0f, 0f, meshPaint);
            drawCurledBitmap(canvas, toBitmap, 1f - progress);
        }
    }

    private void drawCurledBitmap(Canvas canvas, Bitmap bitmap, float amount) {
        float q = Math.max(0f, Math.min(1f, amount));
        int width = getWidth();
        int height = getHeight();
        if (width <= 0 || height <= 0) return;

        if (q <= 0.001f) {
            canvas.drawBitmap(bitmap, 0f, 0f, meshPaint);
            return;
        }

        float foldX = width * (1f - q);
        float foldedWidth = Math.max(1f, width - foldX);
        float wave = (float) Math.sin(Math.PI * q);
        int p = 0;

        for (int row = 0; row <= MESH_H; row++) {
            float v = row / (float) MESH_H;
            float y = height * v;
            for (int col = 0; col <= MESH_W; col++) {
                float u = col / (float) MESH_W;
                float x = width * u;
                float nx = x;
                float ny = y;

                if (x > foldX) {
                    float t = Math.max(0f, Math.min(1f, (x - foldX) / foldedWidth));
                    float foldBack = foldedWidth * (0.20f + 0.80f * q);
                    float curve = (float) Math.sin(Math.PI * t);
                    nx = foldX - t * foldBack + curve * foldedWidth * 0.075f * wave;
                    float bow = curve * wave * height * 0.018f;
                    ny = y + bow * ((v - 0.5f) * 2f);
                }

                verts[p++] = nx;
                verts[p++] = ny;
            }
        }

        canvas.drawBitmapMesh(bitmap, MESH_W, MESH_H, verts, 0, null, 0, meshPaint);

        if (q > 0.015f && q < 0.985f) {
            float shadowWidth = Math.max(18f, Math.min(width * 0.12f, foldedWidth * 0.34f + 18f));
            int dark = Color.argb((int) (105f * wave), 0, 0, 0);
            int soft = Color.argb((int) (38f * wave), 0, 0, 0);
            shadowPaint.setShader(new LinearGradient(
                    foldX - shadowWidth, 0f, foldX + shadowWidth * 0.28f, 0f,
                    new int[]{Color.TRANSPARENT, soft, dark, Color.TRANSPARENT},
                    new float[]{0f, 0.42f, 0.72f, 1f}, Shader.TileMode.CLAMP));
            canvas.drawRect(foldX - shadowWidth, 0f, foldX + shadowWidth * 0.28f, height, shadowPaint);
            shadowPaint.setShader(null);

            edgePaint.setColor(Color.argb((int) (145f * wave), 255, 255, 255));
            canvas.drawLine(foldX, 0f, foldX, height, edgePaint);
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        release();
        super.onDetachedFromWindow();
    }
}
