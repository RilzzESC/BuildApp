# UsbMirror v2 — Android 16-compatible architecture (no scrcpy)

This revision replaces the unsupported `screenrecord --output-format=h264` path with an Android companion APK using the official MediaProjection + MediaCodec APIs. The Windows app uses ADB port forwarding over USB and FFmpeg for H.264 decoding. It does not use scrcpy or scrcpy-derived code.

## Project layout
- `desktop/`: Windows UI, FFmpeg pipeline, ADB input control, PyInstaller build script.
- `android/`: Android Studio project for the screen-capture helper APK.

## Build Android helper APK
Requirements: Android Studio (recent version), Android SDK Platform 35, JDK 17.
1. Open the `android` folder in Android Studio.
2. Let Gradle sync.
3. Build > Build Bundle(s) / APK(s) > Build APK(s).
4. Install `android/app/build/outputs/apk/debug/app-debug.apk` on the TECNO phone.
5. Open **UsbMirror Helper**, tap **Mulai berbagi layar**, and approve Android's system screen-capture prompt. Keep the service active during mirroring.

Or, with Gradle installed:
```powershell
cd android
gradle assembleDebug
```
The project does not include a Gradle wrapper. Android Studio is the recommended build path.

## Build Windows app
1. Put the official Android Platform-Tools files `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll` in `desktop/tools/`.
2. Put `ffmpeg.exe` in `desktop/tools/`.
3. Install Python 3.10+.
4. Run `desktop/build.bat`.
5. Output: `desktop/dist/UsbMirror/UsbMirror.exe`. The `tools` folder is copied alongside the executable.

## Use
1. Enable USB debugging and connect phone with a data cable.
2. Install/open the helper APK and grant screen capture permission.
3. Start `UsbMirror.exe`, select the device, click Start.
4. Click on preview to tap, drag to swipe, focus preview and type to send text. Android may handle keyboard/IME text differently depending on app.

## Notes and limitations
- Android requires user approval for every MediaProjection session on Android 14+.
- This is a source project; it has not been built/tested against the user's specific phone in this environment.
- Vendor Android builds may restrict background services or capture. If video does not start, keep helper app foregrounded and check notification.
- Input is sent using `adb shell input`; text/IME support is basic. Secure/DRM content can be black.
- This starter sends AVC/H.264 over a local TCP socket forwarded through ADB. It prioritizes simple implementation and low buffering, but actual latency/FPS depend on device encoder, USB, and PC decoder.
- If FFmpeg reports corrupt H.264 on a device, the next fix is to normalize MediaCodec codec-specific data and reconnect/keyframe handling for that device.
- FFmpeg and Android Platform-Tools are external tools with separate license/terms. Obtain them from official sources.

## Build APK online without Android Studio (GitHub Actions)

The repository includes `.github/workflows/build-android-apk.yml` so GitHub can build the Android helper APK for you.

1. Sign in to GitHub and create a **new repository** (a public repository is simplest for this workflow). Do not add a README or license during creation.
2. Open the new repository and choose **Add file → Upload files**.
3. Extract this ZIP on Windows. Upload the *contents* of the `UsbMirror_v2` folder, including the hidden `.github` folder, `android` folder, and `desktop` folder. If `.github` is hidden by Windows, enable **View → Show → Hidden items** in File Explorer.
4. Commit the uploaded files to the repository's `main` branch.
5. Open the repository's **Actions** tab. Select **Build Android APK** on the left, then click **Run workflow → Run workflow** if it has not started automatically.
6. Wait for the workflow run to finish with a green check. Open that run, scroll to **Artifacts**, and download **UsbMirror-Helper-APK**.
7. Extract the downloaded artifact ZIP. It contains `app-debug.apk`. Transfer that APK to your phone and install it. If Android asks, allow installing apps from that file manager/browser.
8. Open **UsbMirror Helper** on the phone, tap **Mulai berbagi layar**, and approve Android's screen-capture prompt.

The GitHub Actions workflow uses the Gradle/Android build process documented by Gradle and uploads the APK as a workflow artifact. See [Gradle's GitHub Actions guide](https://docs.gradle.org/current/userguide/github-actions.html).

**Important:** This workflow automates building only the Android helper APK. The Windows desktop app still needs ADB Platform-Tools and `ffmpeg.exe` in `desktop/tools/`. This source project has not yet been verified by a successful GitHub build or on your specific phone; if the Actions run fails, open it and share the error log so it can be fixed.
