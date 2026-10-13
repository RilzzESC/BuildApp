package com.example.usbmirlite;

import android.app.*;
import android.content.Intent;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.IBinder;
import android.os.ParcelFileDescriptor;
import android.util.DisplayMetrics;
import android.view.Surface;
import android.view.WindowManager;

import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicBoolean;

public class CaptureService extends Service {
    private MediaProjection projection;
    private VirtualDisplay virtualDisplay;
    private MediaCodec encoder;
    private Surface inputSurface;
    private ServerSocket server;
    private Thread worker;
    private final AtomicBoolean running = new AtomicBoolean(false);
    private static final int PORT = 27183;
    private static final String CHANNEL = "usbm_capture";

    @Override public void onCreate() {
        super.onCreate();
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "UsbMirror screen capture", NotificationManager.IMPORTANCE_LOW);
            ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(ch);
        }
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || !intent.hasExtra("resultData")) { stopSelf(); return START_NOT_STICKY; }
        Intent data = intent.getParcelableExtra("resultData");
        int code = intent.getIntExtra("resultCode", Activity.RESULT_CANCELED);
        Notification n = new Notification.Builder(this, CHANNEL)
            .setContentTitle("UsbMirror aktif")
            .setContentText("Berbagi layar sedang berjalan")
            .setSmallIcon(android.R.drawable.presence_video_online)
            .build();
        if (Build.VERSION.SDK_INT >= 29) startForeground(41, n, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        else startForeground(41, n);
        try {
            MediaProjectionManager mgr = (MediaProjectionManager)getSystemService(MEDIA_PROJECTION_SERVICE);
            projection = mgr.getMediaProjection(code, data);
            projection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() { stopCapture(); stopSelf(); }
            }, null);
            startCapture();
        } catch (Exception e) { stopSelf(); }
        return START_NOT_STICKY;
    }

    private void startCapture() throws Exception {
        DisplayMetrics dm = new DisplayMetrics();
        WindowManager wm = (WindowManager)getSystemService(WINDOW_SERVICE);
        if (Build.VERSION.SDK_INT >= 30) {
            android.graphics.Rect bounds = wm.getCurrentWindowMetrics().getBounds();
            dm.widthPixels = bounds.width(); dm.heightPixels = bounds.height();
            dm.densityDpi = getResources().getDisplayMetrics().densityDpi;
        } else {
            wm.getDefaultDisplay().getRealMetrics(dm);
        }
        int width = dm.widthPixels & ~1, height = dm.heightPixels & ~1;
        // 720p-ish cap reduces USB bandwidth and encoder load on midrange devices.
        float scale = Math.min(1f, 1280f / Math.max(width, height));
        width = Math.max(2, ((int)(width * scale)) & ~1);
        height = Math.max(2, ((int)(height * scale)) & ~1);
        MediaFormat format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height);
        format.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);
        format.setInteger(MediaFormat.KEY_BIT_RATE, 8_000_000);
        format.setInteger(MediaFormat.KEY_FRAME_RATE, 60);
        format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1);
        if (Build.VERSION.SDK_INT >= 29) format.setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_VBR);
        encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC);
        encoder.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
        inputSurface = encoder.createInputSurface();
        encoder.start();
        virtualDisplay = projection.createVirtualDisplay("UsbMirrorCapture", width, height, dm.densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, inputSurface, null, null);
        running.set(true);
        worker = new Thread(() -> streamLoop(), "UsbMirror-H264");
        worker.start();
    }

    private void streamLoop() {
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        while (running.get()) {
            Socket client = null;
            try {
                if (server == null || server.isClosed()) server = new ServerSocket(PORT);
                server.setSoTimeout(1000);
                try { client = server.accept(); } catch (java.net.SocketTimeoutException ex) { continue; }
                client.setTcpNoDelay(true);
                OutputStream out = client.getOutputStream();
                // Send codec config and subsequent H.264 access units directly to FFmpeg.
                while (running.get() && !client.isClosed()) {
                    int index = encoder.dequeueOutputBuffer(info, 10000);
                    if (index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                        MediaFormat f = encoder.getOutputFormat();
                        ByteBuffer csd0 = f.getByteBuffer("csd-0");
                        ByteBuffer csd1 = f.getByteBuffer("csd-1");
                        if (csd0 != null) { byte[] b = new byte[csd0.remaining()]; csd0.get(b); out.write(b); }
                        if (csd1 != null) { byte[] b = new byte[csd1.remaining()]; csd1.get(b); out.write(b); }
                        out.flush();
                    } else if (index >= 0) {
                        ByteBuffer buffer = encoder.getOutputBuffer(index);
                        if (buffer != null && info.size > 0) {
                            buffer.position(info.offset); buffer.limit(info.offset + info.size);
                            byte[] bytes = new byte[info.size]; buffer.get(bytes); out.write(bytes);
                        }
                        encoder.releaseOutputBuffer(index, false);
                    }
                }
            } catch (Exception e) {
                // Wait for the desktop client to reconnect; keep the projection alive.
            } finally {
                if (client != null) try { client.close(); } catch (Exception ignored) {}
            }
        }
    }

    private void stopCapture() {
        running.set(false);
        try { if (server != null) server.close(); } catch (Exception ignored) {}
        try { if (virtualDisplay != null) virtualDisplay.release(); } catch (Exception ignored) {}
        try { if (inputSurface != null) inputSurface.release(); } catch (Exception ignored) {}
        try { if (encoder != null) { encoder.stop(); encoder.release(); } } catch (Exception ignored) {}
        try { if (projection != null) projection.stop(); } catch (Exception ignored) {}
    }
    @Override public void onDestroy() { stopCapture(); super.onDestroy(); }
    @Override public IBinder onBind(Intent intent) { return null; }
}
