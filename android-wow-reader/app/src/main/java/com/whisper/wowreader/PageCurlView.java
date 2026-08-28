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
import android.view.animation.PathInterpolator;

final class PageCurlView extends View {
    private static final int MESH_W = 34;
    private static final int MESH_H = 10;

    private final Paint meshPaint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final Paint shadowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint sheenPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
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
        float d = getResources().getDisplayMetrics().density;
        edgePaint.setStrokeWidth(Math.max(1f, d * 0.8f));
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
        animator.setDuration(360L);
        animator.setInterpolator(new PathInterpolator(0.20f, 0.00f, 0.18f, 1.00f));
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

        // The next page always stays underneath. The current page itself curls
        // away from the touched edge. This keeps forward and backward turns
        // visually consistent and avoids the old "target page curling in" look.
        canvas.drawBitmap(toBitmap, 0f, 0f, meshPaint);
        drawCurledBitmap(canvas, fromBitmap, progress, direction);
    }

    private void drawCurledBitmap(Canvas canvas, Bitmap bitmap, float amount, int turnDirection) {
        float q = Math.max(0f, Math.min(1f, amount));
        int width = getWidth();
        int height = getHeight();
        if (width <= 0 || height <= 0) return;

        if (q <= 0.001f) {
            canvas.drawBitmap(bitmap, 0f, 0f, meshPaint);
            return;
        }

        float foldXLogical = width * (1f - q);
        float foldedWidth = Math.max(1f, width - foldXLogical);
        float wave = (float) Math.sin(Math.PI * q);
        int p = 0;

        for (int row = 0; row <= MESH_H; row++) {
            float v = row / (float) MESH_H;
            float y = height * v;

            for (int col = 0; col <= MESH_W; col++) {
                float u = col / (float) MESH_W;
                float sourceX = width * u;
                float logicalX = turnDirection > 0 ? sourceX : width - sourceX;
                float nxLogical = logicalX;
                float ny = y;

                if (logicalX > foldXLogical) {
                    float t = Math.max(0f, Math.min(1f,
                            (logicalX - foldXLogical) / foldedWidth));
                    float curve = (float) Math.sin(Math.PI * t);
                    float outer = (float) Math.sin(Math.PI * 0.5f * t);

                    // Travel gradually grows through the turn, while a small
                    // cylindrical bulge keeps the fold from looking like a flat slide.
                    float foldBack = foldedWidth * (0.18f + 0.82f * q);
                    nxLogical = foldXLogical - t * foldBack
                            + curve * foldedWidth * (0.055f + 0.040f * wave)
                            + outer * width * 0.006f * wave;

                    float verticalBow = curve * wave * height * 0.024f;
                    ny = y + verticalBow * ((v - 0.5f) * 2f);
                }

                float nx = turnDirection > 0 ? nxLogical : width - nxLogical;
                verts[p++] = nx;
                verts[p++] = ny;
            }
        }

        canvas.drawBitmapMesh(bitmap, MESH_W, MESH_H, verts, 0, null, 0, meshPaint);

        if (q > 0.012f && q < 0.992f) {
            float foldX = turnDirection > 0 ? foldXLogical : width - foldXLogical;
            float shadowWidth = Math.max(20f,
                    Math.min(width * 0.14f, foldedWidth * 0.30f + 22f));

            float sx0 = turnDirection > 0 ? foldX - shadowWidth : foldX + shadowWidth;
            float sx1 = turnDirection > 0 ? foldX + shadowWidth * 0.24f : foldX - shadowWidth * 0.24f;
            int dark = Color.argb((int) (118f * wave), 0, 0, 0);
            int soft = Color.argb((int) (44f * wave), 0, 0, 0);
            shadowPaint.setShader(new LinearGradient(
                    sx0, 0f, sx1, 0f,
                    new int[]{Color.TRANSPARENT, soft, dark, Color.TRANSPARENT},
                    new float[]{0f, 0.42f, 0.76f, 1f}, Shader.TileMode.CLAMP));
            float left = Math.min(sx0, sx1);
            float right = Math.max(sx0, sx1);
            canvas.drawRect(left, 0f, right, height, shadowPaint);
            shadowPaint.setShader(null);

            // Soft paper sheen on the folding side.
            float sheenOuter = turnDirection > 0 ? foldX + shadowWidth * 0.52f : foldX - shadowWidth * 0.52f;
            sheenPaint.setShader(new LinearGradient(
                    foldX, 0f, sheenOuter, 0f,
                    new int[]{Color.argb((int) (72f * wave), 255, 255, 255), Color.TRANSPARENT},
                    null, Shader.TileMode.CLAMP));
            canvas.drawRect(Math.min(foldX, sheenOuter), 0f,
                    Math.max(foldX, sheenOuter), height, sheenPaint);
            sheenPaint.setShader(null);

            edgePaint.setColor(Color.argb((int) (165f * wave), 255, 255, 255));
            canvas.drawLine(foldX, 0f, foldX, height, edgePaint);
        }

        // The final few percent are gently faded so the curled bitmap does not
        // leave a one-pixel seam when it disappears off-screen.
        if (q > 0.94f) {
            float fade = Math.max(0f, 1f - (q - 0.94f) / 0.06f);
            meshPaint.setAlpha((int) (255f * fade));
            meshPaint.setAlpha(255);
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        release();
        super.onDetachedFromWindow();
    }
}
