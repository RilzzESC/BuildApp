package com.example.usbmirlite;

import android.app.Activity;
import android.content.Intent;
import android.media.projection.MediaProjectionManager;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.view.View;

public class MainActivity extends Activity {
    private static final int REQ_CAPTURE = 301;
    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(32,48,32,32);
        TextView info = new TextView(this);
        info.setText("UsbMirror Helper\\n\\n1. Hubungkan HP ke PC melalui USB dan aktifkan USB debugging.\\n2. Tekan Mulai berbagi layar.\\n3. Pilih seluruh layar pada dialog Android.\\n4. Biarkan aplikasi ini berjalan selama mirroring.");
        layout.addView(info);
        Button start = new Button(this); start.setText("Mulai berbagi layar");
        start.setOnClickListener(v -> {
            MediaProjectionManager m = (MediaProjectionManager)getSystemService(MEDIA_PROJECTION_SERVICE);
            startActivityForResult(m.createScreenCaptureIntent(), REQ_CAPTURE);
        });
        layout.addView(start);
        Button stop = new Button(this); stop.setText("Hentikan layanan");
        stop.setOnClickListener(v -> stopService(new Intent(this, CaptureService.class)));
        layout.addView(stop);
        setContentView(layout);
    }
    @Override protected void onActivityResult(int req, int result, Intent data) {
        super.onActivityResult(req,result,data);
        if(req==REQ_CAPTURE && result==RESULT_OK && data!=null) {
            Intent service = new Intent(this, CaptureService.class);
            service.putExtra("resultCode", result);
            service.putExtra("resultData", data);
            startForegroundService(service);
        }
    }
}
